import { NextResponse } from "next/server";
import { query } from "@/lib/supabase";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { employee_email, employee_name, card_id, playbook_id, time_spent_seconds } = body;
    if (!employee_email || !card_id) {
      return NextResponse.json({ error: "employee_email and card_id required" }, { status: 400 });
    }
    const name = (employee_name || "").replace(/'/g, "''");
    const email = employee_email.replace(/'/g, "''");
    await query(`
      INSERT INTO knowledge_lake.training_completions 
        (employee_email, employee_name, card_id, playbook_id, time_spent_seconds)
      VALUES ('${email}', '${name}', '${card_id}', ${playbook_id ? `'${playbook_id}'` : "NULL"}, ${time_spent_seconds || 0})
      ON CONFLICT (employee_email, card_id) DO UPDATE SET 
        completed_at = now(), 
        time_spent_seconds = EXCLUDED.time_spent_seconds
    `);
    return NextResponse.json({ ok: true });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const email = searchParams.get("email");
  if (!email) return NextResponse.json({ error: "email required" }, { status: 400 });
  try {
    const rows = await query(`
      SELECT tc.card_id, tc.completed_at, tc.time_spent_seconds,
        c.title as card_title, p.name as playbook_name
      FROM knowledge_lake.training_completions tc
      JOIN knowledge_lake.sop_cards c ON c.id = tc.card_id
      JOIN knowledge_lake.sop_playbooks p ON p.id = c.playbook_id
      WHERE tc.employee_email = '${email.replace(/'/g, "''")}'
      ORDER BY tc.completed_at DESC
    `);
    return NextResponse.json(rows);
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
