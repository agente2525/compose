-- Fecha o acesso direto de `anon` às tabelas do painel.
--
-- Antes: as políticas `public_all_*` eram ALL / USING (true) / WITH CHECK (true)
-- para o role `public`, o que dava leitura e escrita completas a qualquer um
-- com a URL do painel (a anon key fica sempre visível no HTML).
--
-- Agora: RLS continua ligada e sem nenhuma política — ou seja, `anon` e
-- `authenticated` não enxergam nada. O único caminho é a Edge Function
-- `painel-api`, que usa a service_role e ignora RLS.

drop policy if exists "public_all_entradas" on public.entradas;
drop policy if exists "public_all_custos"   on public.custos;

alter table public.entradas enable row level security;
alter table public.custos   enable row level security;

revoke all on public.entradas from anon, authenticated;
revoke all on public.custos   from anon, authenticated;

revoke all on sequence public.entradas_id_seq from anon, authenticated;
revoke all on sequence public.custos_id_seq   from anon, authenticated;
