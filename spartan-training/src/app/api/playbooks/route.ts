import { NextResponse } from "next/server";
import { query } from "@/lib/supabase";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const boardId = searchParams.get("boardId");
  const libraryId = searchParams.get("libraryId");

  try {
    let sql = "";
    if (libraryId) {
      sql = `
        SELECT p.id, p.name, p.library_id, l.name as library_name,
          (SELECT count(*) FROM knowledge_lake.sop_cards c WHERE c.playbook_id = p.id) as card_count
        FROM knowledge_lake.sop_playbooks p
        JOIN knowledge_lake.sop_libraries l ON l.id = p.library_id
        WHERE p.library_id = '${libraryId}'
        ORDER BY p.sort_order, p.name
      `;
    } else if (boardId) {
      sql = `
        SELECT p.id, p.name, p.library_id, l.name as library_name,
          (SELECT count(*) FROM knowledge_lake.sop_cards c WHERE c.playbook_id = p.id) as card_count
        FROM knowledge_lake.sop_playbooks p
        JOIN knowledge_lake.sop_libraries l ON l.id = p.library_id
        WHERE l.board_id = '${boardId}'
        ORDER BY l.sort_order, p.sort_order, p.name
      `;
    } else {
      return NextResponse.json({ error: "boardId or libraryId required" }, { status: 400 });
    }
    const rows = await query(sql);
    return NextResponse.json(rows);
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
