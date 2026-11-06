# Fichário (https://fichario.app/): relatório

Coleta feita em 06/11/2026 com WebFetch, curl direto (llms.txt, llms-full.txt, robots.txt, sitemap.xml, /mcp, /openapi.json, /api/v1/*), uma chamada JSON-RPC `tools/list` ao MCP e WebSearch.
Legenda: **[V]** = verificado em fonte primária. **[I]** = inferência minha.

## 1. O que é

- **[V]** É um site brasileiro de consulta de CNPJ grátis. Monta fichas de empresas a partir dos **dados abertos do CNPJ da Receita Federal** (base 2026-10, 28.380.653 estabelecimentos ATIVOS). Fontes: homepage, https://fichario.app/llms.txt e https://fichario.app/mcp.
- **[V]** Lema da homepage: "Tudo sobre qualquer empresa, a partir do CNPJ." Também diz "Grátis e sem cadastro".
- **[V]** Funcionalidades:
  - ficha da empresa em /cnpj/{14 dígitos}
  - busca por nome, CNPJ, e-mail, domínio de e-mail ou CEP
  - busca avançada por CNAE, UF, cidade, porte, capital social, data de abertura, regime tributário (Simples/MEI), situação, e-commerce e plataforma de loja (VTEX, Shopify...), com export CSV/XLSX
  - consulta em massa de até 1.000 CNPJs por chamada
  - "Enriquecer base"
  - concorrentes (mesmo CNAE na cidade ou UF)
  - licitações (ComprasGov)
  - CVM/B3 ("Genesis Bolsa")
  - publicações judiciais (DJEN/CNJ)
  - CNDT do TST em PDF
  - sanções/PEP (CEIS, CNEP, CEPIM, PGFN)
  - rankings ("Maiores"), "Abertas recentemente" (RSS e JSON), Mapa 3D por cidade, "Ao vivo"
  - "Mural" de avaliações, onde agentes de IA também postam
- **[V]** Enriquecimento próprio: site e Instagram "achados automáticos e podem conter erros". Também há estimativas heurísticas de faturamento e funcionários, rotuladas como "ESTIMATIVA" e baseadas no porte legal (LC 123/2006), no capital social e em RAIS/CAGED. O campo de verificação ao vivo usa a BrasilAPI.
- **[V]** Quem faz: "Fichário é um produto da Genesis Innovation". O domínio espelho é cnpj.genesisinnovation.io. O repositório de docs é https://github.com/james-patzdorf/fichario (só documentação: "O código-fonte do site não fica aqui", 1 commit). O rodapé tem LinkedIn de Thiago Patzdorf e um contato de suporte por WhatsApp.
- **[V]** Preços (/precos):
  - Grátis: 60 req/min e 3.000/dia por IP.
  - Pro: R$ 100/mês, 10x os limites, chave Bearer `fch_live_…`, cobrança via Stripe.
  - Estouro avulso: x402, cerca de 0,01 USDC por requisição na rede Base (eip155:8453).
- **[V]** Infra citada na página de preços: "Coleções salvas (D1; R2 em breve)" e "conta Cloudflare". **[I]** Isso sugere Cloudflare Workers + D1.
- **[V]** A busca web pública não acha nada sobre "fichario.app", Genesis Innovation ou Patzdorf. O produto é novo e pouco indexado.

## 2. Filosofia / tese central

**[V]** Trechos literais:
- "Grátis, sem login. API REST, OpenAPI e servidor MCP." (llms.txt)
- "Agentes que usam navegador ou tela (computer-use) podem usar o Fichário como uma pessoa usaria, sem instalar MCP nem chave de API." (/agentes)
- "Resultados vêm prontos no HTML (funciona sem JavaScript)", "ids estáveis" (llms.txt)
- "Não faça loop de milhares de CNPJs." (llms.txt)
- "Receita não publica faturamento: faixa_receita_estimada pelo porte"
- "Para fins legais, vale o comprovante oficial da Receita Federal."

**[I]** A tese é "agent-first". O mesmo dado é servido em quatro superfícies equivalentes: HTML semântico com ids estáveis, REST/OpenAPI, MCP e llms.txt. Cada resposta traz proveniência explícita (`fonte.base`, header `X-Fichario-Base`, `verificacao.consultado_em`) e separa dado oficial de estimativa. A monetização é pensada para máquinas: x402, HTTP 402 e mural com selo "Agente". Há preocupação com LGPD: CPF de MEI/EI mascarado e remoção via /remover.

## 3. MCP / ferramentas / API expostas

**[V]** O servidor é "Fichário MCP", com transporte streamable-http (JSON-RPC 2.0) em `POST https://fichario.app/mcp`. Um GET devolve um manifesto. Rodei `tools/list` e voltaram **14 ferramentas** (o llms-full.txt está desatualizado e lista só 2):

| Ferramenta | Argumentos |
|---|---|
| `buscar_empresa` | consulta, uf, cidade |
| `consultar_cnpj` | cnpj, verificar |
| `consultar_lote` | cnpjs (até 1.000) |
| `busca_avancada` | cnae, uf, cidade, situacao, porte, capital_min/max, abertura_de/ate, regime, tem_telefone, tem_site, e_commerce, plataforma, ordem, por_pagina, pagina, listada, cvm |
| `exportar_lista` | mesmos filtros; devolve csv_url |
| `listar_concorrentes` | cnpj, limite |
| `licitacoes_empresa` | cnpj |
| `sancoes_pep` | cnpj |
| `dados_cvm` | cnpj |
| `dados_bolsa` | cnpj |
| `publicacoes_judiciais` | cnpj |
| `deixar_avaliacao` | handle, token, nota, mensagem, agente |
| `checar_handle` | handle |
| `criar_handle` | handle, avatar, dono_handle, dono_token |

**[V]** Caminhos REST no OpenAPI 3.1 (/openapi.json):
- `/api/v1/cnpj/{cnpj}`
- `/api/v1/cnpj/{cnpj}/concorrentes`
- `/api/v1/cnpj/{cnpj}/licitacoes`
- `/api/v1/cnpj/{cnpj}/bolsa`
- `/api/v1/cnpj/{cnpj}/publicacoes`
- `/api/v1/cnpj/{cnpj}/certidao-trabalhista` (GET/POST)
- `/api/v1/busca`
- `/api/v1/consulta-lote` (POST)
- `/api/v1/mural` (GET/POST)
- `/api/v1/mural/handle`
- `/api/v1/mural/handle/{handle}`

Fora do OpenAPI, mas documentados no llms.txt ou funcionando: `/api/v1/busca-avancada` e `/api/v1/abertas` (testado, 200).

**[V]** Não existe /docs (404). O robots.txt bloqueia /busca e /api/v1/ para crawlers, mas libera /openapi.json e /llms.txt. O sitemap é dividido por UF (sitemap-catalogo-{uf}.xml).

## 4. Modelo de dados implícito (grafo)

Campos verificados no JSON real de /api/v1/cnpj/{cnpj}. A forma de grafo é inferência minha **[I]**.

**Nós:**
- **Empresa/Estabelecimento**: cnpj, razão social, fantasia, situação, abertura, natureza jurídica, porte, capital, telefone, e-mail, site, instagram, e_commerce, plataforma
- **CNAE/Atividade**: código de 7 dígitos, descrição
- **Município**
- **UF**
- **Endereço/CEP**
- **Sócio**: PF/PJ, documento mascarado, qualificação
- **RegimeTributário**: Simples/MEI
- **Estimativa**: faturamento e funcionários, com metodologia e confiança
- **EstatísticaSetorial**: RAIS/CAGED
- **Licitação**
- **Ticker/CompanhiaAberta**: CVM/B3
- **PublicaçãoJudicial**
- **Sanção/PEP**
- **CNDT**
- **Fonte/Base**: versão mensal
- **Agente/Handle**
- **Avaliação**

**Arestas:**
- Empresa –exerce→ CNAE
- Empresa –localiza_em→ Endereço –em→ Município –em→ UF
- Sócio –participa_de {qualificação, desde}→ Empresa
- Sócio –outras_empresas→ Empresa (link /socios?nome=&doc=). Isso forma um grafo bipartido de sócios e empresas.
- Empresa –concorre_com→ Empresa (mesmo CNAE e município, derivada)
- Empresa –optante→ Regime
- Empresa –estimada_por→ Estimativa ←calibra– EstatísticaSetorial(CNAE, município)
- Empresa –participou→ Licitação
- Empresa –listada_como→ Ticker
- Empresa –parte_em→ Publicação. O casamento é por nome exato, então pode haver homônimos.
- Empresa –sancionada→ Sanção
- Sócio –é→ PEP (casamento por nome + 6 dígitos)
- todo dado –proveniente_de→ Fonte(base 2026-10, consultado_em)
- Agente –possui→ Handle –publica→ Avaliação

## 5. Pontes possíveis (todas [I])

- **Matemática (espaço vetorial / redução NP → P):**
  - Cada empresa vira um vetor esparso: one-hot de CNAE, UF e município; porte; log(capital); idade; flags. "Concorrentes" vira vizinhança k-NN nesse espaço.
  - O grafo sócio–empresa permite problemas difíceis em geral, como clique máximo, cobertura e detecção de grupos econômicos ocultos. A estrutura real, porém, é bipartida e esparsa. Restringir a componentes conexos, aos filtros hierárquicos UF→município→CNAE (que já são obrigatórios na API) ou a grafos bipartidos (emparelhamento e fluxo em tempo polinomial) é um exemplo concreto de reduzir o espaço de busca até virar polinomial.
- **Parsing / AST:**
  - O OpenAPI 3.1 e os `inputSchema` do MCP são árvores JSON-Schema. Dá para parsear e gerar clientes, validadores e testes.
  - Uma query de busca avançada pode ser modelada como AST (AND de predicados) e compilada em URL, REST ou chamada MCP.
  - O HTML com ids estáveis (#ba-resultados tr[data-cnpj]) permite extração determinística via DOM.
- **Compressão:**
  - Os dados são muito redundantes (os 8 primeiros dígitos do CNPJ formam a raiz compartilhada por matriz e filiais; CNAE e município têm baixa cardinalidade; há snapshots mensais).
  - Dá para usar codificação de dicionário ou colunar e deltas entre bases mensais (`fonte.base`). O feed /abertas já é um delta diário natural.
- **Deep learning:**
  - Embeddings de razão social, CNAE e endereço servem para busca semântica, deduplicação e resolução de entidades. Isso resolveria os homônimos que o próprio site admite em DJEN/PEP.
  - Uma GNN sobre o grafo sócio–empresa poderia prever risco, sanção ou grupo econômico.
  - Um regressor treinado com RAIS/CAGED poderia substituir a heurística "capital × 1" das estimativas de faturamento e funcionários.
  - O MCP pode servir de ferramenta de recuperação (RAG) para agentes.
