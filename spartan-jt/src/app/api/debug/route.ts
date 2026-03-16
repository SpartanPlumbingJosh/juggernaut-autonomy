import { NextResponse } from 'next/server';

export async function GET() {
  const hasUrl = !!process.env.SUPABASE_URL;
  const hasKey = !!process.env.SUPABASE_SERVICE_KEY;
  const hasCfId = !!process.env.CF_ACCESS_CLIENT_ID;
  const hasCfSecret = !!process.env.CF_ACCESS_CLIENT_SECRET;
  
  // Try a simple query
  let queryResult = 'not attempted';
  if (hasUrl && hasKey) {
    try {
      const res = await fetch(process.env.SUPABASE_URL!, {
        method: 'POST',
        headers: {
          'apikey': process.env.SUPABASE_SERVICE_KEY!,
          'Authorization': `Bearer ${process.env.SUPABASE_SERVICE_KEY!}`,
          'CF-Access-Client-Id': process.env.CF_ACCESS_CLIENT_ID || '',
          'CF-Access-Client-Secret': process.env.CF_ACCESS_CLIENT_SECRET || '',
          'Content-Profile': 'spartan_ops',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: "SELECT count(*) as cnt FROM spartan_ops.jobs" }),
      });
      const text = await res.text();
      queryResult = `status=${res.status} body=${text.substring(0, 200)}`;
    } catch (e) {
      queryResult = `error: ${String(e)}`;
    }
  }

  return NextResponse.json({
    env: { hasUrl, hasKey, hasCfId, hasCfSecret },
    urlPrefix: process.env.SUPABASE_URL?.substring(0, 30) || 'NOT SET',
    queryResult,
  });
}