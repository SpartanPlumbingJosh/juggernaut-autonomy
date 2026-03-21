import { NextResponse } from 'next/server';
import { query } from '@/lib/supabase';

export async function GET() {
  try {
    // Pull from team_roster (27 people, better data) + system_users for anyone not in roster
    const users = await query(`
      SELECT name, position as role, slack_user_id as slack_member_id, employee_type
      FROM spartan_ops.team_roster
      WHERE status = 'active'
      UNION
      SELECT su.name, su.role as role, su.slack_member_id, null as employee_type
      FROM spartan_ops.system_users su
      WHERE su.is_active = true
      AND su.name NOT IN (SELECT name FROM spartan_ops.team_roster WHERE status = 'active')
      ORDER BY name
    `);
    return NextResponse.json(users);
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
