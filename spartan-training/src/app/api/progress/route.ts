import { NextResponse } from "next/server";
import { query } from "@/lib/supabase";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const email = searchParams.get("email");
  if (!email) return NextResponse.json({ error: "email required" }, { status: 400 });
  try {
    const rows = await query(`
      SELECT b.id as board_id, b.name as board_name,
        count(DISTINCT c.id) as total_cards,
        count(DISTINCT tc.card_id) as completed_cards,
        CASE WHEN count(DISTINCT c.id) > 0 
          THEN round(100.0 * count(DISTINCT tc.card_id) / count(DISTINCT c.id), 1)
          ELSE 0 END as pct_complete
      FROM knowledge_lake.sop_boards b
      JOIN knowledge_lake.sop_libraries l ON l.board_id = b.id
      JOIN knowledge_lake.sop_playbooks p ON p.library_id = l.id
      JOIN knowledge_lake.sop_cards c ON c.playbook_id = p.id
      LEFT JOIN knowledge_lake.training_completions tc 
        ON tc.card_id = c.id AND tc.employee_email = '${email.replace(/'/g, "''")}'
      GROUP BY b.id, b.name
      ORDER BY b.name
    `);
    return NextResponse.json(rows);
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
