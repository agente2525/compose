# Painel Financeiro MOR&CO

Painel de entradas e custos. Página estática servida por nginx (EasyPanel),
com os dados em Postgres no Supabase.

- **App:** https://finances-morco-painel.nxcafx.easypanel.host/
- **Supabase:** projeto `Finances` (`mxkewplpvtiqkmulhkfs`)

## Arquitetura

```
browser ──POST──▶ Edge Function `painel-api` ──service_role──▶ Postgres
        (senha,                (Deno)                   (entradas, custos)
     token HMAC)
```

O browser **não** tem chave do Supabase. Ele faz login contra a Edge Function,
recebe um token de sessão assinado (HMAC-SHA256, validade 12h) e manda esse
token em `x-painel-token` a cada chamada. As tabelas estão fechadas para `anon`
— o único caminho até os dados é a função, que roda com `service_role`.

### Ações da API

Tudo é `POST` no mesmo endpoint, com `{"acao": "..."}` no corpo.

| ação        | corpo                          | token? |
|-------------|--------------------------------|--------|
| `login`     | `{senha}`                      | não    |
| `listar`    | —                              | sim    |
| `inserir`   | `{tabela, linha}`              | sim    |
| `atualizar` | `{tabela, id, linha}`          | sim    |
| `excluir`   | `{tabela, id}`                 | sim    |

`tabela` é só `entradas` ou `custos`, e cada uma tem allowlist de colunas na
constante `SCHEMA` — campo que não está lá não chega no banco.

## Estrutura

```
web/index.html                              o painel (página única)
Dockerfile, nginx.conf                      build servido pelo EasyPanel
supabase/functions/painel-api/index.ts      backend
supabase/migrations/0001_fecha_rls_painel.sql
```

## Deploy

**Front (EasyPanel):** aponte o serviço para este repo, pasta `painel-financeiro/`,
build por Dockerfile. Push na branch → rebuild.

**Backend:**

```bash
supabase functions deploy painel-api --project-ref mxkewplpvtiqkmulhkfs --no-verify-jwt
```

`--no-verify-jwt` é obrigatório: o painel não tem anon key para mandar no
`Authorization`, e a função faz a própria autenticação.

**Secrets:** ver `.env.example`. Sem `PANEL_PASSWORD` e `PANEL_SESSION_SECRET`
a função responde 500 em tudo (falha fechada, de propósito).

## Histórico

O painel nasceu no Claude Cowork como um HTML só, com a anon key e a senha
(`adm` / `Mor@2026`) em texto puro no fonte, e as tabelas com policy
`ALL USING (true)` para `public` — ou seja, qualquer um com a URL tinha leitura
e escrita completas via PostgREST, sem passar pela tela de login. A migration
`0001` fecha isso e a Edge Function passa a ser o único caminho.

Aquela senha está queimada: ela ficou pública num HTML estático. A nova
`PANEL_PASSWORD` tem que ser diferente.

## Pontas soltas conhecidas

- O fallback offline (`carregar()`) ainda guarda lançamentos em `localStorage`.
  Some se o browser for compartilhado — vale trocar por um estado em memória.
- O throttle de login é por instância da função, não global.
- As tabelas `mp_*` e `vendas_hubla` no mesmo projeto seguem com as policies
  originais; não foram tocadas aqui.
