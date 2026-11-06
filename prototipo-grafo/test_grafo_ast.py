import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from grafo_ast import analisar  # noqa: E402

CODIGO = textwrap.dedent('''
    import os

    def soma_lista(xs):
        total = 0
        for x in xs:
            if x > 0:
                total = total + x * 2
        return total

    def conta_pares(ys):
        acc = 0
        for y in ys:
            if y > 1:
                acc = acc + y * 3
        return acc

    class Caixa:
        def usa(self):
            return soma_lista([1, 2]) + conta_pares([3])
''')


class TesteGrafo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        (Path(self.tmp.name) / "exemplo.py").write_text(CODIGO)
        self.r = analisar(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_nos_e_arestas(self):
        tipos = self.r["grafo"]["nos_por_tipo"]
        self.assertEqual(tipos["funcao"], 3)
        self.assertEqual(tipos["classe"], 1)
        arestas = self.r["_grafo"].arestas
        self.assertIn(("exemplo.Caixa.usa", "exemplo.soma_lista", "chama"), arestas)
        self.assertIn(("exemplo", "os", "importa"), arestas)

    def test_funcoes_com_mesma_forma_sao_detectadas(self):
        pares = self.r["funcoes_parecidas"]
        self.assertTrue(pares)
        self.assertTrue(pares[0]["estrutura_identica"])
        self.assertAlmostEqual(pares[0]["cosseno"], 1.0)

    def test_dag_comprime(self):
        c = self.r["compressao"]
        self.assertGreater(c["razao_dag"], 1.0)
        self.assertLess(c["subarvores_unicas"], c["nos_ast"])
        self.assertTrue(c["maiores_repeticoes"])

    def test_pagerank_soma_um(self):
        rank = self.r["_grafo"].pagerank()
        self.assertAlmostEqual(sum(rank.values()), 1.0, places=6)

    def test_servidor_mcp(self):
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "nos_centrais", "arguments": {"caminho": self.tmp.name, "top": 3}}},
        ]
        entrada = "\n".join(json.dumps(m) for m in msgs) + "\n"
        saida = subprocess.run([sys.executable, str(AQUI / "servidor_mcp.py")],
                               input=entrada, capture_output=True, text=True, timeout=30).stdout
        resp = [json.loads(l) for l in saida.splitlines()]
        self.assertEqual([r["id"] for r in resp], [1, 2, 3])
        self.assertEqual(len(resp[1]["result"]["tools"]), 4)
        centrais = json.loads(resp[2]["result"]["content"][0]["text"])
        self.assertEqual(len(centrais), 3)


if __name__ == "__main__":
    unittest.main()
