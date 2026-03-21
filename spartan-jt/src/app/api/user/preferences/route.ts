import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/supabase';

export async function GET(request: NextRequest) {
  const userName = request.nextUrl.searchParams.get('user');
  if (!userName) return NextResponse.json({ error: 'Missing user param' }, { status: 400 });

  try {
    const rows = await query(`
      SELECT user_name, theme FROM spartan_ops.user_preferences
      WHERE user_name = '${userName.replace(/'/g, "''")}'
      LIMIT 1
    `);
    if (rows.length > 0) return NextResponse.json(rows[0]);
    return NextResponse.json({ user_name: userName, theme: 'dark' });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { user_name, theme } = body;
    if (!user_name || !['dark', 'light'].includes(theme)) {
      return NextResponse.json({ error: 'Invalid params' }, { status: 400 });
    }
    const safeName = user_name.replace(/'/g, "''");
    await query(`
      INSERT INTO spartan_ops.user_preferences (user_name, theme, updated_at)
      VALUES ('${safeName}', '${theme}', now())
      ON CONFLICT (user_name) DO UPDATE SET theme = '${theme}', updated_at = now()
    `);
    return NextResponse.json({ user_name, theme });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
