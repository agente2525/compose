"""Servidor MCP mínimo (stdio, JSON-RPC 2.0) que expõe o grafo_ast como ferramentas.

Sem dependências. Para usar no Claude Code:
    claude mcp add grafo-ast -- python3 /caminho/para/prototipo-grafo/servidor_mcp.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grafo_ast import analisar, para_json  # noqa: E402

VERSAO_PROTOCOLO = "2025-06-18"

_CAMINHO = {
    "type": "object",
    "properties": {
        "caminho": {"type": "string", "description": "Pasta ou arquivo .py a analisar"},
        "top": {"type": "integer", "description": "Quantos itens listar", "default": 10},
    },
    "required": ["caminho"],
}

FERRAMENTAS = {
    "analisar_codigo": (
        "Parseia o código Python em AST e devolve o grafo (nós, arestas, PageRank), "
        "as medidas de compressão e as funções parecidas.",
        lambda r: para_json(r),
    ),
    "nos_centrais": (
        "Lista os módulos, classes e funções mais centrais pelo PageRank do grafo de chamadas.",
        lambda r: r["centrais"],
    ),
    "redundancia": (
        "Mede quanto da estrutura do código se repete (árvore vira DAG) e lista as "
        "subárvores grandes repetidas, que são candidatas a virar uma função só.",
        lambda r: r["compressao"],
    ),
    "funcoes_parecidas": (
        "Encontra pares de funções com estrutura quase igual (cosseno >= 0.97 entre os "
        "vetores de tipos de nó da AST).",
        lambda r: r["funcoes_parecidas"],
    ),
}


def responder(ident, resultado=None, erro=None) -> None:
    msg = {"jsonrpc": "2.0", "id": ident}
    if erro:
        msg["error"] = erro
    else:
        msg["result"] = resultado
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def tratar(msg: dict) -> None:
    metodo, ident = msg.get("method"), msg.get("id")
    if ident is None:  # notificação (ex.: notifications/initialized)
        return
    if metodo == "initialize":
        responder(ident, {
            "protocolVersion": msg.get("params", {}).get("protocolVersion", VERSAO_PROTOCOLO),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "grafo-ast", "version": "0.1.0"},
        })
    elif metodo == "ping":
        responder(ident, {})
    elif metodo == "tools/list":
        responder(ident, {"tools": [
            {"name": nome, "description": desc, "inputSchema": _CAMINHO}
            for nome, (desc, _) in FERRAMENTAS.items()
        ]})
    elif metodo == "tools/call":
        params = msg.get("params", {})
        nome, args = params.get("name"), params.get("arguments", {}) or {}
        if nome not in FERRAMENTAS:
            responder(ident, erro={"code": -32602, "message": f"Ferramenta desconhecida: {nome}"})
            return
        caminho = Path(args.get("caminho", "."))
        if not caminho.exists():
            responder(ident, {"isError": True,
                              "content": [{"type": "text", "text": f"Caminho não existe: {caminho}"}]})
            return
        r = analisar(caminho, top=int(args.get("top", 10)))
        saida = FERRAMENTAS[nome][1](r)
        responder(ident, {"content": [{"type": "text",
                                       "text": json.dumps(saida, ensure_ascii=False, indent=2)}]})
    else:
        responder(ident, erro={"code": -32601, "message": f"Método não suportado: {metodo}"})


def main() -> None:
    for linha in sys.stdin:
        linha = linha.strip()
        if not linha:
            continue
        try:
            tratar(json.loads(linha))
        except json.JSONDecodeError:
            responder(None, erro={"code": -32700, "message": "JSON inválido"})
        except Exception as e:  # nunca derrubar o servidor por causa de uma chamada
            responder(None, erro={"code": -32603, "message": str(e)})


if __name__ == "__main__":
    main()
