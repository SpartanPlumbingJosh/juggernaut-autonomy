import { NextResponse } from "next/server";
import { query } from "@/lib/supabase";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const role = searchParams.get("role") || "all";

  try {
    const boards = await query(`
      SELECT b.id, b.name,
        (SELECT count(*) FROM knowledge_lake.sop_libraries l WHERE l.board_id = b.id) as library_count,
        (SELECT count(*) FROM knowledge_lake.sop_cards c 
         JOIN knowledge_lake.sop_playbooks p ON p.id = c.playbook_id
         JOIN knowledge_lake.sop_libraries l ON l.id = p.library_id
         WHERE l.board_id = b.id) as card_count
      FROM knowledge_lake.sop_boards b
      ORDER BY b.name
    `);
    return NextResponse.json(boards);
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
