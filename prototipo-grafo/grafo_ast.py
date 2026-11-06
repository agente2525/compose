"""Grafo AST: transforma código Python em grafo, vetores e medidas de compressão.

Só usa a biblioteca padrão. Rodar:
    python3 grafo_ast.py <pasta_ou_arquivo> [--json]

Quatro ideias num lugar só:
  1. AST      -> o código vira árvore (ast.parse).
  2. Grafo    -> módulos/classes/funções são nós; contém/importa/chama são arestas.
                 PageRank diz quem é central.
  3. Compressão -> subárvores iguais (ignorando nomes) são guardadas uma vez só
                 (hash-consing: árvore vira DAG). A razão nós/únicos mede redundância.
  4. Espaço vetorial -> cada função vira um vetor de contagens de tipos de nó;
                 cosseno entre vetores encontra funções parecidas.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import sys
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

IGNORAR_PASTAS = {".git", "node_modules", "__pycache__", ".venv", "venv", "build", "dist"}


# ---------------------------------------------------------------- grafo


@dataclass
class Grafo:
    nos: dict[str, dict] = field(default_factory=dict)  # id -> atributos
    arestas: set[tuple[str, str, str]] = field(default_factory=set)  # (origem, destino, tipo)

    def no(self, ident: str, **attrs) -> None:
        self.nos.setdefault(ident, {}).update(attrs)

    def aresta(self, a: str, b: str, tipo: str) -> None:
        if a != b:
            self.arestas.add((a, b, tipo))

    def pagerank(self, amortecimento: float = 0.85, iteracoes: int = 100) -> dict[str, float]:
        """PageRank por iteração de potência: o autovetor dominante da matriz de transição."""
        ids = list(self.nos)
        n = len(ids)
        if n == 0:
            return {}
        saida: dict[str, list[str]] = defaultdict(list)
        for a, b, _ in self.arestas:
            if b in self.nos:
                saida[a].append(b)
        rank = {i: 1.0 / n for i in ids}
        for _ in range(iteracoes):
            sem_saida = sum(rank[i] for i in ids if not saida[i])
            novo = {i: (1 - amortecimento) / n + amortecimento * sem_saida / n for i in ids}
            for a in ids:
                for b in saida[a]:
                    novo[b] += amortecimento * rank[a] / len(saida[a])
            delta = sum(abs(novo[i] - rank[i]) for i in ids)
            rank = novo
            if delta < 1e-10:
                break
        return rank


# ---------------------------------------------------------------- vetores


def vetor_estrutura(no: ast.AST) -> Counter:
    """Saco de tipos de nó: a 'impressão digital' estrutural de um trecho de código."""
    return Counter(type(n).__name__ for n in ast.walk(no))


def cosseno(a: Counter, b: Counter) -> float:
    comum = set(a) & set(b)
    num = sum(a[k] * b[k] for k in comum)
    den = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return num / den if den else 0.0


# ---------------------------------------------------------------- compressão


class HashConsing:
    """Guarda cada subárvore distinta uma vez. Nomes e constantes são ignorados,
    então `soma(a, b)` e `total(x, y)` com o mesmo formato contam como iguais."""

    def __init__(self) -> None:
        self.tabela: dict[str, int] = {}  # hash -> quantas vezes apareceu
        self.tamanho: dict[str, int] = {}  # hash -> nós na subárvore
        self.total_nos = 0

    def visitar(self, no: ast.AST) -> tuple[str, int]:
        filhos = [self.visitar(f) for f in ast.iter_child_nodes(no)]
        assinatura = type(no).__name__ + "(" + ",".join(h for h, _ in filhos) + ")"
        h = hashlib.blake2b(assinatura.encode(), digest_size=8).hexdigest()
        tam = 1 + sum(t for _, t in filhos)
        self.tabela[h] = self.tabela.get(h, 0) + 1
        self.tamanho[h] = tam
        self.total_nos += 1
        return h, tam

    def razao(self) -> float:
        """Nós da árvore / nós do DAG. 1.0 = nada se repete; maior = mais redundância."""
        return self.total_nos / len(self.tabela) if self.tabela else 1.0

    def duplicatas(self, tamanho_minimo: int = 12) -> list[tuple[str, int, int]]:
        """Subárvores grandes que se repetem: candidatas a virar uma função só."""
        achados = [
            (h, vezes, self.tamanho[h])
            for h, vezes in self.tabela.items()
            if vezes > 1 and self.tamanho[h] >= tamanho_minimo
        ]
        return sorted(achados, key=lambda x: x[1] * x[2], reverse=True)


# ---------------------------------------------------------------- análise


@dataclass
class Funcao:
    ident: str
    arquivo: str
    linha: int
    vetor: Counter
    hash_estrutura: str


class Analisador(ast.NodeVisitor):
    def __init__(self, grafo: Grafo, modulo: str, arquivo: str, hc: HashConsing, funcoes: list):
        self.g, self.modulo, self.arquivo, self.hc, self.funcoes = grafo, modulo, arquivo, hc, funcoes
        self.pilha = [modulo]

    def _definicao(self, no, tipo: str) -> None:
        ident = f"{self.pilha[-1]}.{no.name}"
        self.g.no(ident, tipo=tipo, arquivo=self.arquivo, linha=no.lineno)
        self.g.aresta(self.pilha[-1], ident, "contem")
        if tipo == "funcao":
            h, _ = HashConsing().visitar(no)  # hash isolado, só desta função
            self.funcoes.append(Funcao(ident, self.arquivo, no.lineno, vetor_estrutura(no), h))
        self.pilha.append(ident)
        self.generic_visit(no)
        self.pilha.pop()

    def visit_ClassDef(self, no):
        self._definicao(no, "classe")

    def visit_FunctionDef(self, no):
        self._definicao(no, "funcao")

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Import(self, no):
        for a in no.names:
            self.g.no(a.name, tipo=self.g.nos.get(a.name, {}).get("tipo", "externo"))
            self.g.aresta(self.modulo, a.name, "importa")

    def visit_ImportFrom(self, no):
        if no.module:
            self.g.no(no.module, tipo=self.g.nos.get(no.module, {}).get("tipo", "externo"))
            self.g.aresta(self.modulo, no.module, "importa")

    def visit_Call(self, no):
        alvo = no.func
        nome = alvo.id if isinstance(alvo, ast.Name) else alvo.attr if isinstance(alvo, ast.Attribute) else None
        if nome:
            # resolvido depois, quando todas as definições forem conhecidas
            self.g.aresta(self.pilha[-1], "?" + nome, "chama")
        self.generic_visit(no)


def arquivos_python(raiz: Path) -> list[Path]:
    if raiz.is_file():
        return [raiz]
    return sorted(
        p for p in raiz.rglob("*.py") if not any(parte in IGNORAR_PASTAS for parte in p.parts)
    )


def analisar(raiz: Path, top: int = 10) -> dict:
    raiz = raiz.resolve()
    g, hc, funcoes = Grafo(), HashConsing(), []
    bytes_fonte = bytes_zip = 0
    erros = []
    base = raiz if raiz.is_dir() else raiz.parent

    for caminho in arquivos_python(raiz):
        rel = str(caminho.relative_to(base))
        modulo = rel[:-3].replace("/", ".").removesuffix(".__init__")
        try:
            fonte = caminho.read_text(encoding="utf-8", errors="replace")
            arvore = ast.parse(fonte, filename=rel)
        except SyntaxError as e:
            erros.append(f"{rel}: {e.msg} (linha {e.lineno})")
            continue
        bytes_fonte += len(fonte.encode())
        bytes_zip += len(zlib.compress(fonte.encode(), 9))
        g.no(modulo, tipo="modulo", arquivo=rel, linha=1)
        hc.visitar(arvore)
        Analisador(g, modulo, rel, hc, funcoes).visit(arvore)

    # resolve "?nome" para a definição com esse nome (se for única); senão descarta
    por_nome = defaultdict(list)
    for ident, at in g.nos.items():
        if at.get("tipo") in ("funcao", "classe"):
            por_nome[ident.rsplit(".", 1)[-1]].append(ident)
    resolvidas = set()
    for a, b, t in g.arestas:
        if b.startswith("?"):
            candidatos = por_nome.get(b[1:], [])
            if len(candidatos) == 1:
                resolvidas.add((a, candidatos[0], t))
        else:
            resolvidas.add((a, b, t))
    g.arestas = resolvidas

    rank = g.pagerank()
    tipos_aresta = Counter(t for _, _, t in g.arestas)
    tipos_no = Counter(at.get("tipo", "?") for at in g.nos.values())

    # pares de funções estruturalmente parecidas (O(n^2), limitado)
    amostra = funcoes[:600]
    pares = []
    for i in range(len(amostra)):
        for j in range(i + 1, len(amostra)):
            a, b = amostra[i], amostra[j]
            if sum(a.vetor.values()) < 15 or sum(b.vetor.values()) < 15:
                continue
            s = cosseno(a.vetor, b.vetor)
            if s >= 0.97:
                pares.append((s, a, b, a.hash_estrutura == b.hash_estrutura))
    pares.sort(key=lambda x: x[0], reverse=True)

    return {
        "raiz": str(raiz),
        "arquivos": len(arquivos_python(raiz)),
        "erros_de_parse": erros,
        "grafo": {
            "nos": len(g.nos),
            "arestas": len(g.arestas),
            "nos_por_tipo": dict(tipos_no),
            "arestas_por_tipo": dict(tipos_aresta),
        },
        "centrais": [
            {"no": i, "tipo": g.nos[i].get("tipo"), "pagerank": round(r, 5)}
            for i, r in sorted(rank.items(), key=lambda x: x[1], reverse=True)[:top]
        ],
        "compressao": {
            "bytes_fonte": bytes_fonte,
            "bytes_zlib": bytes_zip,
            "razao_zlib": round(bytes_fonte / bytes_zip, 2) if bytes_zip else None,
            "nos_ast": hc.total_nos,
            "subarvores_unicas": len(hc.tabela),
            "razao_dag": round(hc.razao(), 2),
            "maiores_repeticoes": [
                {"hash": h, "vezes": v, "tamanho": t} for h, v, t in hc.duplicatas()[:top]
            ],
        },
        "funcoes_parecidas": [
            {
                "a": f"{a.ident} ({a.arquivo}:{a.linha})",
                "b": f"{b.ident} ({b.arquivo}:{b.linha})",
                "cosseno": round(s, 4),
                "estrutura_identica": igual,
            }
            for s, a, b, igual in pares[:top]
        ],
        "_grafo": g,  # removido na saída JSON
    }


def para_json(resultado: dict) -> dict:
    return {k: v for k, v in resultado.items() if not k.startswith("_")}


def imprimir(r: dict) -> None:
    gr, c = r["grafo"], r["compressao"]
    print(f"Raiz: {r['raiz']}  ({r['arquivos']} arquivos .py)")
    print(f"\nGrafo: {gr['nos']} nós, {gr['arestas']} arestas")
    print(f"  nós:     {gr['nos_por_tipo']}")
    print(f"  arestas: {gr['arestas_por_tipo']}")
    print("\nMais centrais (PageRank):")
    for x in r["centrais"]:
        print(f"  {x['pagerank']:.5f}  [{x['tipo']}] {x['no']}")
    print("\nCompressão:")
    print(f"  zlib no texto:         {c['razao_zlib']}x  ({c['bytes_fonte']} -> {c['bytes_zlib']} bytes)")
    print(f"  árvore -> DAG:         {c['razao_dag']}x  ({c['nos_ast']} nós -> {c['subarvores_unicas']} únicos)")
    if c["maiores_repeticoes"]:
        print("  subárvores grandes repetidas (vezes x tamanho):")
        for d in c["maiores_repeticoes"][:5]:
            print(f"    {d['vezes']}x {d['tamanho']} nós  ({d['hash']})")
    if r["funcoes_parecidas"]:
        print("\nFunções parecidas (cosseno dos vetores de estrutura):")
        for p in r["funcoes_parecidas"]:
            marca = "  [mesma estrutura]" if p["estrutura_identica"] else ""
            print(f"  {p['cosseno']}  {p['a']}  ~  {p['b']}{marca}")
    if r["erros_de_parse"]:
        print(f"\nArquivos que não parsearam: {len(r['erros_de_parse'])}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("caminho", nargs="?", default=".")
    ap.add_argument("--json", action="store_true", help="saída em JSON")
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args(argv)
    r = analisar(Path(args.caminho), top=args.top)
    if args.json:
        json.dump(para_json(r), sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        imprimir(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
