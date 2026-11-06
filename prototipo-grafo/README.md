# Grafo AST

Protótipo que lê código Python e transforma em **árvore**, **grafo**, **vetores** e **medida de compressão**. Também expõe tudo isso como um **servidor MCP**, para um assistente de IA usar como ferramenta.

Usa só a biblioteca padrão do Python 3.10+.

```bash
python3 grafo_ast.py caminho/do/projeto          # relatório legível
python3 grafo_ast.py caminho/do/projeto --json   # para outras ferramentas
python3 -m unittest -v test_grafo_ast            # testes
```

Para registrar como ferramenta MCP no Claude Code:

```bash
claude mcp add grafo-ast -- python3 /caminho/absoluto/prototipo-grafo/servidor_mcp.py
```

Ferramentas expostas: `analisar_codigo`, `nos_centrais`, `redundancia`, `funcoes_parecidas`.

## O que ele faz

| Etapa | Técnica | O que sai |
|---|---|---|
| 1. Parse | `ast.parse` (AST = árvore sintática abstrata) | árvore de cada arquivo |
| 2. Grafo | nós = módulo/classe/função; arestas = `contem`, `importa`, `chama` | grafo do projeto |
| 3. Centralidade | PageRank (autovetor dominante, calculado por iteração de potência) | quem é o "coração" do código |
| 4. Compressão | hash-consing: subárvores iguais, ignorando nomes, ficam guardadas uma vez só | razão árvore/DAG e trechos repetidos |
| 5. Espaço vetorial | cada função vira um vetor de contagens de tipos de nó; similaridade de cosseno | pares de funções quase iguais |

Exemplo real, rodando no pacote `json` da biblioteca padrão:

```
Grafo: 45 nós, 83 arestas
Mais central: encoder._make_iterencode._iterencode
zlib no texto:   3.72x
árvore -> DAG:   9.11x  (5076 nós -> 557 únicos)
dump ~ dumps:    cosseno 0.9936
```

A compressão estrutural (9x) é bem maior que a textual (3,7x). Isso quer dizer que boa parte do código é feita das mesmas formas, só com nomes diferentes.

## Explicado em quatro níveis

**5 anos.** Imagina uma caixa de LEGO montada. O programa desmonta a caixa e vê quais peças se ligam com quais (isso é o grafo). Depois percebe que várias partes foram montadas do mesmo jeito, e guarda o "jeito de montar" uma vez só (isso é compressão). No fim descobre qual peça segura todas as outras.

**10 anos.** Código é como uma receita com passos dentro de passos, e isso forma uma árvore. Se várias receitas pedem "bata os ovos e misture a farinha", não precisa escrever isso toda vez: dá para escrever uma vez e apontar para lá. O programa encontra essas repetições e também mostra quais receitas são usadas por todas as outras.

**15 anos.** A AST é a árvore que o interpretador monta antes de rodar o código. A gente transforma as chamadas entre funções num grafo dirigido e aplica PageRank, que é o mesmo algoritmo que o Google usava para ranquear páginas. Para comprimir, cada subárvore ganha um hash calculado a partir dos hashes dos filhos. Subárvores com o mesmo hash são a mesma forma, e a árvore vira um DAG (grafo acíclico dirigido). Por fim, cada função vira um vetor (quantos `if`, `for`, chamadas…), e o cosseno entre dois vetores mede o quanto elas se parecem.

**Especialista.** A centralidade é o autovetor estacionário da cadeia de Markov com teleporte (α = 0,85), resolvida por iteração de potência. A compressão é hash-consing de Merkle sobre a AST com rótulos apagados; a razão |árvore|/|DAG| é um limite inferior simples de compressão estrutural, parente de gramáticas de árvore (TreeRePair) e de MDL. O vetor é um *bag-of-node-types*, uma imersão de baixa resolução. Os próximos passos naturais são caminhos AST (code2vec), *graph neural networks* sobre o *code property graph*, ou embeddings de um modelo de código. Limites conhecidos: a resolução de chamadas é por nome, sem inferência de tipos, então chamadas dinâmicas e homônimos se perdem. A comparação de pares é O(n²) e está limitada a 600 funções.

## Ligação com "colapsar o não polinomial no polinomial"

O protótipo usa, em escala pequena, a ideia legítima por trás dessa frase. Uma estrutura difícil de comparar diretamente (duas árvores; comparar árvores em geral é caro) é **levantada para um espaço vetorial**, onde comparar custa um produto interno. É o mesmo princípio do *kernel trick* e das relaxações convexas.

O preço é perder informação: dois códigos diferentes podem cair no mesmo vetor. Isso **não** resolve problemas NP-difíceis em tempo polinomial. É uma aproximação útil, com garantias limitadas, e é exatamente assim que ela deve ser vendida.

## Próximos passos

- Suportar outras linguagens via tree-sitter (JS/TS, que é o que existe neste repositório).
- Trocar o vetor de contagens por embeddings aprendidos e guardar em pgvector (o Supabase já está no repositório).
- Exportar o grafo para um formato de fichas/notas: cada função vira uma ficha e cada aresta vira um link.
