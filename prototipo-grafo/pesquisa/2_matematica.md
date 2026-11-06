# Relatório: thiagopatzdorf/Matematica (agente 2)

Clone: `git clone --depth 50` numa pasta temporária isolada (HEAD `080a818`, v0.10.0, 103 MB). Nada do repo foi executado; os scripts de análise ficaram fora do clone e rodaram com `python3 -I`.

## 1. O que é (verificado)

É um **ledger de cotas de códigos de cobertura `K_q(n,R)`**, verificado por máquina. `K_q(n,R)` é o menor conjunto de palavras de comprimento n sobre q símbolos tal que toda palavra do espaço fica a distância de Hamming ≤ R de alguma delas (`README.md` §I, `CoveringLean/Regras.lean:41`, onde `K q n R := sInf {M | UB q n R M}`). O ponto de partida são as tabelas de Kéri: 1145 células, q de 2 a 21.

- Estado declarado (`README.md`, gerado de `ledger/cells.json`): 524 células exatas e 621 abertas. 700 cotas superiores são teoremas do kernel do Lean. Nas cotas inferiores, 1138 são CLAIMED (herdadas da literatura), 5 CERTIFICATE_VERIFIED e 2 FORMALIZED. São 45 códigos explícitos em `data/codes/`.
- Resultados próprios (`paper/main.tex`, resumo):
  - Cotas superiores melhores que as publicadas, por exemplo `K_7(9,4) ≤ 1134` (antes 1475), `K_7(10,4) ≤ 5607` e `K_5(11,4) ≤ 2875`. O método é uma união de cosets de um código linear mais um "remendo".
  - Valores exatos: `K_7(4,2)=19`, com os dois lados no kernel; o lado inferior usa 70 refutações LRAT reexecutadas por um verificador LRAT verificado dentro do Lean. `K_2(6,1)=12`.
  - Exatos "potencialmente novos", com cota inferior fora do Lean: `K_3(6,2)=17`, `K_7(6,4)=14` e `K_7(5,3)=17`. Os certificados são Farkas inteiros, LRAT e VeriPB.
  - `K_4(7,4)=10`, ainda sem red team.
- Tamanho: 1122 arquivos `.lean` (51.948 linhas, cerca de 9.400 `theorem`/`lemma`, a maioria gerada), 237 `.py` (33.855 linhas), 25 `.c`, 1 `.rs` e uma nota LaTeX.
- **Conferência independente feita por mim** (verificador próprio em força bruta): `q4_n7_R4_M10`, `q7_n6_R4_M14` e `q7_n5_R3_M17` cobrem o espaço inteiro, com 0 pontos descobertos e M correto. As cotas superiores dessas três células se confirmam. Não conferi as cotas inferiores.
- Há um segundo domínio, só começando: fatoração de inteiros (`docs/fatoracao/`). Hoje existem registro dos números RSA, um verificador `N % d == 0` e uma linha de base do CADO-NFS. Ainda não há resultado.

## 2. Filosofia / tese central

`docs/PHILOSOPHY.md` organiza o texto pela ordem aristotélica: definições, princípios, proposições, método e as quatro causas.

- **"Achar é caro, verificar é barato."** Busca, SAT, ILP e LLMs apenas *propõem*. Quem decide é um avaliador exato (`tools/verify/verify.c`) e o kernel do Lean.
- **"Só conta o que a máquina confere."** A confiança sobe por uma escada de estados: CLAIMED, WITNESS_CHECKED, CERTIFICATE_VERIFIED, FORMALIZED e INDEPENDENTLY_REPRODUCED. O estado é calculado por script (`ledger/build.py`).
- Outros princípios: "todo erro vira regra" (um teste que falha), "tudo é reversível" e "nunca afirmar mais do que foi provado".
- O vocabulário é metafórico: "entropia local" é a distância entre as cotas, e "colapso de estado" é o intervalo virando ponto. **Não há** tese sobre colapsar estruturas não polinomiais em polinomiais nem sobre espaços vetoriais nesse sentido.
- **P vs NP aparece apenas como inspiração.** O texto diz explicitamente que é uma "bússola de engenharia, não um teorema" e que "não atacamos nenhum" dos Problemas do Milênio (`PHILOSOPHY.md` §II.1 e §VII). Em `campanha-compressao.md` uma regra proíbe tirar de benchmark qualquer alegação sobre P=NP ou sobre quebra de RSA.
- O repo se liga ao `james-theorems`, que traz teoremas Lean sobre *modelos* de amortização (custo = D·busca + N·verificação), de gate de segurança e de replay de log.

## 3. MCP definido (exato)

Há **um** servidor: **"Infinito"**, em `infinito/infinito_mcp/server.py`. Usa FastMCP do pacote `mcp>=1.30,<2`, HTTP sem estado e roda no Cloud Run. A autenticação é por URL com token por pessoa ou por Cloudflare Access. Cada pessoa tem um teto de crédito em US$, guardado num ledger no GCS. Os módulos são plugáveis por `INF_MODULOS`.

- **Núcleo:** `meus_creditos` (saldo e teto), `admin_usuarios`, `admin_creditos`, `admin_convidar` (gera a URL com token), `admin_revogar` e `admin_acessos`.
- **matematica:**
  - `celula(id)`: cotas e estado de uma célula `K_q(n,R)`.
  - `alvos(...)`: ranking de onde há chance de melhorar.
  - `nossos_resultados`.
  - `codigos`: lista o que há em `data/codes/`.
  - `verificar_codigo(arquivo)`: roda o verificador C oficial e devolve o sha256 canônico.
  - `documento(nome)`: lê documentos do repo.
- **papers:** `papers_buscar` (arXiv, OpenAlex, Semantic Scholar, Zenodo), `paper_guardar` (baixa o PDF para um bucket) e `biblioteca_buscar`.
- **pesado** (cobra): `pesado_tipos`, `pesado(tipo, horas, paralelo, ...)` e `pesado_status`. Os tipos são `lake_build`, `verificar_grande` e `script`, este de uma allowlist em `pesado/jobs/`. Os jobs rodam em VMs spot efêmeras, com reserva de custo antes da execução.
- **gemini** (cobra): `gemini(prompt, ...)`.

Publicar e fazer merge ficam fora do MCP de propósito. Tudo que custa dinheiro é "seco" por padrão e só roda com `confirmar=true`.

## 4. Grafo AST (Python)

Análise com o módulo `ast`, numa passada estática.

- Números: 237 módulos, 0 falhas de parse, 2070 funções, 62 classes.
- Importações internas: 268 arestas.
- Chamadas: 19.133 pontos de chamada. Resolvi 1621 arestas distintas de chamada entre funções; contei só chamadas por nome, para descartar falsos positivos como `.items`.
- Distribuição: `tools` 120, `tests` 58, `scripts` 22, `infinito` 16, `verification` 7, `evaluators` 6, `ledger` 3.
- **Módulos centrais** (mais importados):
  - `tools.exatos.gaps2.fatia` (19)
  - `tests.conftest` (17)
  - `tools.exatos.fibras.fib_encode` (14), o codificador SAT do lema das fibras
  - `tools.exatos.k362.hard6.solvers` (11)
  - `tools.exatos.k742.encode` (9)
  - `evaluators.base`, `infinito_mcp.armazem` e `infinito_mcp.creditos` (6 cada)
- **Funções mais chamadas:** `infinito_mcp.server:quem` (identidade), `creditos:saldo`, `tools.literatura.varredura:log/dados` e `tools.problems.lifecycle:transicionar`.
- **Orquestradores** (maior grau de saída): `scripts.loop.record_loop:main`, `tools.certificar.gerar:gerar`, `ledger.build:construir` e `modulos.pesado:registrar`.
- Dependências externas: principalmente a stdlib, além de numpy (36), scipy (20) e pytest (44).
- Partes que não são Python:
  - Lean: Mathlib v4.34.1. Os alvos são `CoveringLean`, `CoveringHeavy` e `CoveringSyn`, com centenas de `SynLeaf_*` e `G610_Chunk_*` gerados.
  - C: verificador, busca SA/tabu e BFS.
  - Rust: um verificador BFS independente.
  - CI: `ci.yml`, `verify-codes.yml` e `lean-syn.yml`.
- Fluxo de dados: fontes → `ledger/` → `targets` → geradores → avaliador → `data/codes` → gerador Lean → kernel → paper, Zenodo e site.

## 5. Avaliação rigorosa

**Matemática padrão e sólida:**
- A definição de covering codes e a cota de cobertura por esferas.
- Construções por cosets e síndromes de códigos lineares, que são clássicas (Cohen, Honkala, Litsyn, Lobstein).
- A redução de inexistência a SAT, com certificados LRAT e VeriPB.
- Inviabilidade de relaxação LP certificada por multiplicadores de Farkas inteiros, que é dualidade LP padrão.
- Quebra de simetria por forma canônica.

Uma cota superior é objetiva: basta um código explícito, e eu confirmei três. A formalização em Lean sem `sorry`/`native_decide` é uma escolha forte: grep confirma que não há `axiom` novo, e as menções a `native_decide` estão em comentários.

**Pontos que exigem cautela** (o próprio repo os declara):
1. As cotas inferiores novas de `K_3(6,2)`, `K_7(6,4)`, `K_7(5,3)` e `K_4(7,4)` dependem de uma redução *provada em papel* (normalização por fibra mínima e o lema das fibras para `K_q(n,n-2)`) e de certificados verificados fora do Lean. A solidez depende dessa redução e da completude da enumeração canônica. Ali está o elo mais fraco, mesmo com red team.
2. "Potencialmente novo" não é novidade estabelecida: textos fechados de 2004 a 2009 não foram lidos.
3. `K_4(7,4)` e `K_4(6,3)` ainda não passaram pela revisão adversarial.
4. Grande parte das "700 no kernel" reproduz valores já publicados. Isso é valioso como auditoria, mas não é descoberta.

**Especulativo ou inexistente:** não há alegação de P vs NP nem de colapso polinomial. A analogia "verificar é barato" corresponde à definição de NP, mas o repo **não** a usa como prova, e diz isso. O programa "bater o GNFS" é declarado como pergunta aberta, com critério de parada pré-registrado.

**Veredito:** trabalho sério de matemática computacional certificada, bem acima da média em honestidade epistêmica. As alegações centrais são verificáveis e, onde conferi, corretas.

## 6. Conexões com fichario.app, compressão e deep learning

- **Escada de estados como metadado de ficha.** Cada ficha pode carregar um nível de evidência (CLAIMED → VERIFICADO → FORMALIZADO) calculado por regra, não editado à mão. É o mesmo padrão do livro PROVADO/VERIFICADO/EVIDÊNCIA/HIPÓTESE em `tools/fatoracao/baseline/claims.jsonl`.
- **Contrato de avaliador** (`evaluators/base.py`): um JSON com `ok`, `veredito`, `evidencia`, `sha256_arquivo` e `sha256_canonico`. O sha256 canônico é útil para deduplicar fichas por conteúdo.
- **Amortização busca/verificação**, ou "o ledger é memória": a ficha guarda o *certificado* e a próxima pessoa confere em vez de pesquisar de novo. É exatamente o valor de um fichário.
- **Compressão.** Um código de cobertura é literalmente um quantizador vetorial ou codebook de raio R; `K_q(n,R)` mede o menor codebook com distorção de Hamming máxima R, a compressão com perdas na pior distorção. Daí saem ligações com a quantização de embeddings para busca (PQ/VQ, LSH Hamming) e com a quantização de pesos em deep learning, onde o codebook mínimo é a pergunta direta. A "razão de compressão ρ" de `campanha-compressao.md` é outra coisa: razão de custo computacional.
- **Deep learning.** O padrão "LLM ou heurística propõe, avaliador exato decide" é o mesmo do FunSearch e do AlphaEvolve; o paper relata programas evoluídos por LLM sem ganho. No fichario dá para replicar com geração por LLM mais um verificador determinístico antes de gravar.
- **MCP Infinito como molde.** Mostra um MCP modular com orçamento por pessoa, ações caras secas por padrão e auditoria por chamada, reaproveitável para um MCP do fichario.
