const SUPABASE_URL = process.env.SUPABASE_URL || 'https://kong.thejuggernaut.org/rest/v1/rpc/run_sql';
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY || '';
const CF_CLIENT_ID = process.env.CF_ACCESS_CLIENT_ID || '';
const CF_CLIENT_SECRET = process.env.CF_ACCESS_CLIENT_SECRET || '';

export async function query<T = Record<string, unknown>>(sql: string, schema = 'spartan_ops'): Promise<T[]> {
  const res = await fetch(SUPABASE_URL, {
    method: 'POST',
    headers: {
      'apikey': SUPABASE_KEY,
      'Authorization': `Bearer ${SUPABASE_KEY}`,
      'CF-Access-Client-Id': CF_CLIENT_ID,
      'CF-Access-Client-Secret': CF_CLIENT_SECRET,
      'Content-Profile': schema,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query: sql }),
    next: { revalidate: 30 },
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Supabase query failed (${res.status}): ${text}`);
  }

  const data = await res.json();
  return Array.isArray(data) ? data : [];
}