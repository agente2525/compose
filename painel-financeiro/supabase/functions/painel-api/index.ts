// Painel Financeiro MOR&CO — backend único do painel.
//
// O front não fala mais direto com o PostgREST: toda leitura e escrita passa
// por aqui. Isso permite que a service_role key e a senha do painel fiquem
// apenas no servidor, e que as tabelas fiquem 100% fechadas para `anon`.

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const PANEL_PASSWORD = Deno.env.get("PANEL_PASSWORD") ?? "";
const SESSION_SECRET = Deno.env.get("PANEL_SESSION_SECRET") ?? "";
const ALLOWED_ORIGINS = (Deno.env.get("PANEL_ALLOWED_ORIGINS") ?? "")
  .split(",").map((s) => s.trim()).filter(Boolean);

const SESSION_TTL_MS = 12 * 60 * 60 * 1000; // 12h
const MAX_LOGIN_ATTEMPTS = 8;
const LOGIN_WINDOW_MS = 10 * 60 * 1000;

// Só estas tabelas, e só estas colunas. Nada que chegue no body além disto
// alcança o banco.
const SCHEMA: Record<string, Record<string, "text" | "number">> = {
  entradas: {
    mes: "text", data: "text", descricao: "text",
    proj: "text", val: "number", status: "text", obs: "text",
  },
  custos: {
    mes: "text", data: "text", descricao: "text",
    cat: "text", val: "number", status: "text", obs: "text",
  },
};

// ─── sessão ──────────────────────────────────────────────────────────────────

const enc = new TextEncoder();

async function hmacKey(): Promise<CryptoKey> {
  return await crypto.subtle.importKey(
    "raw", enc.encode(SESSION_SECRET),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"],
  );
}

function b64url(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function issueToken(): Promise<{ token: string; expiraEm: number }> {
  const exp = Date.now() + SESSION_TTL_MS;
  const payload = String(exp);
  const sig = await crypto.subtle.sign("HMAC", await hmacKey(), enc.encode(payload));
  return { token: `${payload}.${b64url(new Uint8Array(sig))}`, expiraEm: exp };
}

async function tokenValido(token: string | null): Promise<boolean> {
  if (!token) return false;
  const dot = token.indexOf(".");
  if (dot < 1) return false;
  const payload = token.slice(0, dot);
  const exp = Number(payload);
  if (!Number.isFinite(exp) || Date.now() > exp) return false;
  const sig = await crypto.subtle.sign("HMAC", await hmacKey(), enc.encode(payload));
  return timingSafeEqual(b64url(new Uint8Array(sig)), token.slice(dot + 1));
}

// Comparação de tempo constante — não vaza o prefixo correto pelo tempo de resposta.
function timingSafeEqual(a: string, b: string): boolean {
  const ab = enc.encode(a), bb = enc.encode(b);
  let diff = ab.length ^ bb.length;
  for (let i = 0; i < Math.max(ab.length, bb.length); i++) {
    diff |= (ab[i] ?? 0) ^ (bb[i] ?? 0);
  }
  return diff === 0;
}

// Throttle de login por IP. É por instância (não é um lock global), mas já
// derruba força bruta ingênua.
const tentativas = new Map<string, { n: number; ate: number }>();

function excedeuTentativas(ip: string): boolean {
  const agora = Date.now();
  const reg = tentativas.get(ip);
  if (!reg || agora > reg.ate) {
    tentativas.set(ip, { n: 1, ate: agora + LOGIN_WINDOW_MS });
    return false;
  }
  reg.n++;
  return reg.n > MAX_LOGIN_ATTEMPTS;
}

// ─── PostgREST com service_role ──────────────────────────────────────────────

async function pg(path: string, init: RequestInit = {}): Promise<unknown> {
  const res = await fetch(`${SUPABASE_URL}/rest/v1${path}`, {
    ...init,
    headers: {
      apikey: SERVICE_ROLE,
      Authorization: `Bearer ${SERVICE_ROLE}`,
      "Content-Type": "application/json",
      Prefer: "return=representation",
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) throw new Error(`postgrest ${res.status}: ${await res.text()}`);
  return res.status === 204 ? null : await res.json();
}

function limpaLinha(tabela: string, entrada: unknown): Record<string, unknown> {
  const cols = SCHEMA[tabela];
  if (!cols) throw new HttpError(400, "tabela desconhecida");
  if (typeof entrada !== "object" || entrada === null) {
    throw new HttpError(400, "corpo inválido");
  }
  const saida: Record<string, unknown> = {};
  for (const [col, tipo] of Object.entries(cols)) {
    if (!(col in entrada)) continue;
    const v = (entrada as Record<string, unknown>)[col];
    if (v === null || v === "") { saida[col] = tipo === "number" ? 0 : null; continue; }
    if (tipo === "number") {
      const n = Number(v);
      if (!Number.isFinite(n)) throw new HttpError(400, `campo ${col} não é numérico`);
      saida[col] = n;
    } else {
      saida[col] = String(v).slice(0, 500);
    }
  }
  if (Object.keys(saida).length === 0) throw new HttpError(400, "nenhum campo válido");
  return saida;
}

function idValido(id: unknown): number {
  const n = Number(id);
  if (!Number.isInteger(n) || n <= 0) throw new HttpError(400, "id inválido");
  return n;
}

// ─── HTTP ────────────────────────────────────────────────────────────────────

class HttpError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

function corsHeaders(origin: string | null): Record<string, string> {
  const permitido = origin && ALLOWED_ORIGINS.includes(origin);
  return {
    "Access-Control-Allow-Origin": permitido ? origin : (ALLOWED_ORIGINS[0] ?? ""),
    "Access-Control-Allow-Headers": "content-type, x-painel-token",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Vary": "Origin",
  };
}

function json(body: unknown, status: number, origin: string | null): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders(origin) },
  });
}

Deno.serve(async (req) => {
  const origin = req.headers.get("origin");

  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders(origin) });
  }
  if (req.method !== "POST") {
    return json({ erro: "método não suportado" }, 405, origin);
  }
  if (!PANEL_PASSWORD || !SESSION_SECRET) {
    console.error("PANEL_PASSWORD ou PANEL_SESSION_SECRET não configurados");
    return json({ erro: "função mal configurada" }, 500, origin);
  }

  try {
    const body = await req.json().catch(() => ({}));
    const acao = (body as { acao?: string }).acao;

    // login é a única ação que dispensa token
    if (acao === "login") {
      const ip = req.headers.get("x-forwarded-for")?.split(",")[0].trim() ?? "desconhecido";
      if (excedeuTentativas(ip)) {
        return json({ erro: "muitas tentativas, tente de novo em alguns minutos" }, 429, origin);
      }
      const senha = String((body as { senha?: unknown }).senha ?? "");
      if (!timingSafeEqual(senha, PANEL_PASSWORD)) {
        return json({ erro: "senha incorreta" }, 401, origin);
      }
      tentativas.delete(ip);
      return json(await issueToken(), 200, origin);
    }

    if (!(await tokenValido(req.headers.get("x-painel-token")))) {
      return json({ erro: "sessão expirada" }, 401, origin);
    }

    switch (acao) {
      case "listar": {
        const [entradas, custos] = await Promise.all([
          pg("/entradas?select=*&order=id.asc&limit=5000"),
          pg("/custos?select=*&order=id.asc&limit=5000"),
        ]);
        return json({ entradas, custos }, 200, origin);
      }
      case "inserir": {
        const tabela = String((body as { tabela?: unknown }).tabela ?? "");
        const linha = limpaLinha(tabela, (body as { linha?: unknown }).linha);
        const res = await pg(`/${tabela}`, { method: "POST", body: JSON.stringify(linha) });
        return json({ linha: (res as unknown[])[0] }, 200, origin);
      }
      case "atualizar": {
        const tabela = String((body as { tabela?: unknown }).tabela ?? "");
        const id = idValido((body as { id?: unknown }).id);
        const linha = limpaLinha(tabela, (body as { linha?: unknown }).linha);
        const res = await pg(`/${tabela}?id=eq.${id}`, { method: "PATCH", body: JSON.stringify(linha) });
        return json({ linha: (res as unknown[])[0] }, 200, origin);
      }
      case "excluir": {
        const tabela = String((body as { tabela?: unknown }).tabela ?? "");
        if (!SCHEMA[tabela]) throw new HttpError(400, "tabela desconhecida");
        const id = idValido((body as { id?: unknown }).id);
        await pg(`/${tabela}?id=eq.${id}`, { method: "DELETE" });
        return json({ ok: true }, 200, origin);
      }
      default:
        return json({ erro: "ação desconhecida" }, 400, origin);
    }
  } catch (e) {
    if (e instanceof HttpError) return json({ erro: e.message }, e.status, origin);
    console.error(e);
    return json({ erro: "erro interno" }, 500, origin);
  }
});
