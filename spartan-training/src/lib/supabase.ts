const SB_URL = process.env.SUPABASE_URL || "https://kong.thejuggernaut.org";
const SB_KEY = process.env.SUPABASE_KEY || "";
const CF_ID = process.env.CF_ACCESS_CLIENT_ID || "";
const CF_SECRET = process.env.CF_ACCESS_CLIENT_SECRET || "";

export async function query(sql: string) {
  const res = await fetch(`${SB_URL}/rest/v1/rpc/exec_sql`, {
    method: "POST",
    headers: {
      apikey: SB_KEY,
      Authorization: `Bearer ${SB_KEY}`,
      "Content-Profile": "knowledge_lake",
      "Content-Type": "application/json",
      "CF-Access-Client-Id": CF_ID,
      "CF-Access-Client-Secret": CF_SECRET,
    },
    body: JSON.stringify({ query: sql }),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Supabase error: ${res.status}`);
  return res.json();
}

export async function querySpartanOps(sql: string) {
  const res = await fetch(`${SB_URL}/rest/v1/rpc/exec_sql`, {
    method: "POST",
    headers: {
      apikey: SB_KEY,
      Authorization: `Bearer ${SB_KEY}`,
      "Content-Profile": "spartan_ops",
      "Content-Type": "application/json",
      "CF-Access-Client-Id": CF_ID,
      "CF-Access-Client-Secret": CF_SECRET,
    },
    body: JSON.stringify({ query: sql }),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Supabase error: ${res.status}`);
  return res.json();
}
