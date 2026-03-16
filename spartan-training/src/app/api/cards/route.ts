import { NextResponse } from "next/server";
import { query } from "@/lib/supabase";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const playbookId = searchParams.get("playbookId");
  const cardId = searchParams.get("cardId");

  try {
    if (cardId) {
      const rows = await query(`
        SELECT c.id, c.title, c.content, c.content_length, c.sort_order, c.status,
          p.name as playbook_name, l.name as library_name, b.name as board_name
        FROM knowledge_lake.sop_cards c
        JOIN knowledge_lake.sop_playbooks p ON p.id = c.playbook_id
        JOIN knowledge_lake.sop_libraries l ON l.id = p.library_id
        JOIN knowledge_lake.sop_boards b ON b.id = l.board_id
        WHERE c.id = '${cardId}'
      `);
      return NextResponse.json(rows[0] || null);
    }
    if (!playbookId) {
      return NextResponse.json({ error: "playbookId or cardId required" }, { status: 400 });
    }
    const rows = await query(`
      SELECT c.id, c.title, c.content_length, c.sort_order, c.status
      FROM knowledge_lake.sop_cards c
      WHERE c.playbook_id = '${playbookId}'
      ORDER BY c.sort_order
    `);
    return NextResponse.json(rows);
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
