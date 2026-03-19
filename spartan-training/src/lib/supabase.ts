const SB_URL = process.env.SUPABASE_URL || "https://kong.thejuggernaut.org";
const SB_KEY = process.env.SUPABASE_KEY || "";
const CF_ID = process.env.CF_ACCESS_CLIENT_ID || "";
const CF_SECRET = process.env.CF_ACCESS_CLIENT_SECRET || "";

async function supabaseFetch(sql: string, schema: string): Promise<unknown[]> {
  const url = `${SB_URL}/rest/v1/rpc/exec_sql`;
  const headers: Record<string, string> = {
    apikey: SB_KEY,
    Authorization: `Bearer ${SB_KEY}`,
    "Content-Profile": schema,
    "Content-Type": "application/json",
    "CF-Access-Client-Id": CF_ID,
    "CF-Access-Client-Secret": CF_SECRET,
  };
  const body = JSON.stringify({ query: sql });

  // Retry once on failure (Cloudflare Access can be intermittent)
  for (let attempt = 0; attempt < 2; attempt++) {
    let res: Response;
    try {
      res = await fetch(url, { method: "POST", headers, body, cache: "no-store" });
    } catch (fetchErr) {
      if (attempt === 0) { await new Promise(r => setTimeout(r, 500)); continue; }
      throw new Error(`Supabase fetch failed (network): ${fetchErr}`);
    }
    if (!res.ok) {
      if (attempt === 0 && (res.status === 403 || res.status >= 500)) {
        await new Promise(r => setTimeout(r, 500));
        continue;
      }
      let errBody = "";
      try { errBody = await res.text(); } catch { /* ignore */ }
      throw new Error(`Supabase error ${res.status}: ${errBody.slice(0, 500)}`);
    }
    return res.json();
  }
  throw new Error("Supabase: exhausted retries");
}

export async function query(sql: string) {
  return supabaseFetch(sql, "knowledge_lake");
}

export async function querySpartanOps(sql: string) {
  return supabaseFetch(sql, "spartan_ops");
}
