import { NextResponse } from 'next/server';
import { query } from '@/lib/supabase';

export async function GET() {
  try {
    const users = await query(`
      SELECT name, role, slack_member_id
      FROM spartan_ops.system_users
      WHERE is_active = true
      ORDER BY name
    `);
    return NextResponse.json(users);
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
