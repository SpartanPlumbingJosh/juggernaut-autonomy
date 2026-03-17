import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { query } from "@/lib/supabase";

function esc(s: string) { return String(s || "").replace(/'/g, "''"); }

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session || session.role !== "admin") {
    return NextResponse.json({ error: "Admin only" }, { status: 403 });
  }

  const { searchParams } = new URL(req.url);
  const type = searchParams.get("type");

  if (type === "boards") {
    const rows = await query(`
      SELECT b.id, b.name, b.slug, b.sort_order, b.description, b.icon, b.color,
        (SELECT count(*) FROM knowledge_lake.sop_cards c
         JOIN knowledge_lake.sop_playbooks p ON p.id = c.playbook_id
         JOIN knowledge_lake.sop_libraries l ON l.id = p.library_id
         WHERE l.board_id = b.id) as card_count,
        (SELECT count(*) FROM knowledge_lake.sop_libraries WHERE board_id = b.id) as library_count
      FROM knowledge_lake.sop_boards b
      ORDER BY b.sort_order, b.name
    `);
    return NextResponse.json({ boards: rows || [] });
  }

  if (type === "libraries") {
    const boardId = searchParams.get("board_id");
    if (!boardId) return NextResponse.json({ error: "board_id required" }, { status: 400 });
    const rows = await query(`
      SELECT l.id, l.board_id, l.name, l.slug, l.sort_order, l.description,
        (SELECT count(*) FROM knowledge_lake.sop_cards c
         JOIN knowledge_lake.sop_playbooks p ON p.id = c.playbook_id
         WHERE p.library_id = l.id) as card_count,
        (SELECT count(*) FROM knowledge_lake.sop_playbooks WHERE library_id = l.id) as playbook_count
      FROM knowledge_lake.sop_libraries l
      WHERE l.board_id = '${esc(boardId)}'
      ORDER BY l.sort_order, l.name
    `);
    return NextResponse.json({ libraries: rows || [] });
  }

  if (type === "playbooks") {
    const libraryId = searchParams.get("library_id");
    if (!libraryId) return NextResponse.json({ error: "library_id required" }, { status: 400 });
    const rows = await query(`
      SELECT p.id, p.library_id, p.name, p.slug, p.sort_order, p.description,
        count(c.id) as card_count
      FROM knowledge_lake.sop_playbooks p
      LEFT JOIN knowledge_lake.sop_cards c ON c.playbook_id = p.id
      WHERE p.library_id = '${esc(libraryId)}'
      GROUP BY p.id ORDER BY p.sort_order, p.name
    `);
    return NextResponse.json({ playbooks: rows || [] });
  }

  if (type === "cards") {
    const playbookId = searchParams.get("playbook_id");
    if (!playbookId) return NextResponse.json({ error: "playbook_id required" }, { status: 400 });
    const rows = await query(`
      SELECT id, playbook_id, title, content, sort_order, xp_value, tags
      FROM knowledge_lake.sop_cards
      WHERE playbook_id = '${esc(playbookId)}'
      ORDER BY sort_order, title
    `);
    return NextResponse.json({ cards: rows || [] });
  }

  return NextResponse.json({ error: "Unknown type" }, { status: 400 });
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session || session.role !== "admin") {
    return NextResponse.json({ error: "Admin only" }, { status: 403 });
  }

  const body = await req.json();
  const { type } = body;

  if (type === "board") {
    const { name, description, icon, color } = body;
    if (!name) return NextResponse.json({ error: "Name required" }, { status: 400 });
    const maxRes = await query(`SELECT coalesce(max(sort_order), 0) as m FROM knowledge_lake.sop_boards`);
    const nextOrder = Number(maxRes?.[0]?.m || 0) + 1;
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    await query(`
      INSERT INTO knowledge_lake.sop_boards (name, slug, sort_order, description, icon, color)
      VALUES ('${esc(name)}', '${esc(slug)}', ${nextOrder}, '${esc(description || "")}', '${esc(icon || "📋")}', '${esc(color || "#c9a84c")}')
    `);
    return NextResponse.json({ ok: true });
  }

  if (type === "library") {
    const { board_id, name, description } = body;
    if (!name || !board_id) return NextResponse.json({ error: "Name and board_id required" }, { status: 400 });
    const maxRes = await query(`SELECT coalesce(max(sort_order), 0) as m FROM knowledge_lake.sop_libraries WHERE board_id = '${esc(board_id)}'`);
    const nextOrder = Number(maxRes?.[0]?.m || 0) + 1;
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    await query(`
      INSERT INTO knowledge_lake.sop_libraries (board_id, name, slug, sort_order, description)
      VALUES ('${esc(board_id)}', '${esc(name)}', '${esc(slug)}', ${nextOrder}, '${esc(description || "")}')
    `);
    return NextResponse.json({ ok: true });
  }

  if (type === "playbook") {
    const { library_id, name, description } = body;
    if (!name || !library_id) return NextResponse.json({ error: "Name and library_id required" }, { status: 400 });
    const maxRes = await query(`SELECT coalesce(max(sort_order), 0) as m FROM knowledge_lake.sop_playbooks WHERE library_id = '${esc(library_id)}'`);
    const nextOrder = Number(maxRes?.[0]?.m || 0) + 1;
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    await query(`
      INSERT INTO knowledge_lake.sop_playbooks (library_id, name, slug, sort_order, description)
      VALUES ('${esc(library_id)}', '${esc(name)}', '${esc(slug)}', ${nextOrder}, '${esc(description || "")}')
    `);
    return NextResponse.json({ ok: true });
  }

  if (type === "card") {
    const { playbook_id, title, content, xp_value, tags } = body;
    if (!title || !playbook_id) return NextResponse.json({ error: "Title and playbook_id required" }, { status: 400 });
    const maxRes = await query(`SELECT coalesce(max(sort_order), 0) as m FROM knowledge_lake.sop_cards WHERE playbook_id = '${esc(playbook_id)}'`);
    const nextOrder = Number(maxRes?.[0]?.m || 0) + 1;
    await query(`
      INSERT INTO knowledge_lake.sop_cards (playbook_id, title, content, sort_order, xp_value, tags)
      VALUES ('${esc(playbook_id)}', '${esc(title)}', '${esc(content || "")}', ${nextOrder}, ${Number(xp_value) || 10}, '${esc(tags || "")}')
    `);
    return NextResponse.json({ ok: true });
  }

  return NextResponse.json({ error: "Unknown type" }, { status: 400 });
}

export async function PUT(req: NextRequest) {
  const session = await getSession();
  if (!session || session.role !== "admin") {
    return NextResponse.json({ error: "Admin only" }, { status: 403 });
  }

  const body = await req.json();
  const { type, id } = body;
  if (!id) return NextResponse.json({ error: "id required" }, { status: 400 });

  if (type === "board") {
    const { name, description, icon, color, sort_order } = body;
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    await query(`
      UPDATE knowledge_lake.sop_boards
      SET name='${esc(name)}', slug='${esc(slug)}', description='${esc(description || "")}',
          icon='${esc(icon || "📋")}', color='${esc(color || "#c9a84c")}', sort_order=${Number(sort_order) || 0}
      WHERE id='${esc(id)}'
    `);
    return NextResponse.json({ ok: true });
  }

  if (type === "library") {
    const { name, description, sort_order } = body;
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    await query(`
      UPDATE knowledge_lake.sop_libraries
      SET name='${esc(name)}', slug='${esc(slug)}', description='${esc(description || "")}', sort_order=${Number(sort_order) || 0}
      WHERE id='${esc(id)}'
    `);
    return NextResponse.json({ ok: true });
  }

  if (type === "playbook") {
    const { name, description, sort_order } = body;
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    await query(`
      UPDATE knowledge_lake.sop_playbooks
      SET name='${esc(name)}', slug='${esc(slug)}', description='${esc(description || "")}', sort_order=${Number(sort_order) || 0}
      WHERE id='${esc(id)}'
    `);
    return NextResponse.json({ ok: true });
  }

  if (type === "card") {
    const { title, content, xp_value, tags, sort_order } = body;
    await query(`
      UPDATE knowledge_lake.sop_cards
      SET title='${esc(title)}', content='${esc(content || "")}',
          xp_value=${Number(xp_value) || 10}, tags='${esc(tags || "")}', sort_order=${Number(sort_order) || 0}
      WHERE id='${esc(id)}'
    `);
    return NextResponse.json({ ok: true });
  }

  return NextResponse.json({ error: "Unknown type" }, { status: 400 });
}

export async function DELETE(req: NextRequest) {
  const session = await getSession();
  if (!session || session.role !== "admin") {
    return NextResponse.json({ error: "Admin only" }, { status: 403 });
  }

  const { searchParams } = new URL(req.url);
  const type = searchParams.get("type");
  const id = searchParams.get("id");
  if (!id) return NextResponse.json({ error: "id required" }, { status: 400 });

  if (type === "board") {
    const check = await query(`SELECT count(*) as c FROM knowledge_lake.sop_libraries WHERE board_id='${esc(id)}'`);
    if (Number(check?.[0]?.c || 0) > 0) return NextResponse.json({ error: "Board has libraries — remove them first" }, { status: 400 });
    await query(`DELETE FROM knowledge_lake.sop_boards WHERE id='${esc(id)}'`);
    return NextResponse.json({ ok: true });
  }

  if (type === "library") {
    const check = await query(`SELECT count(*) as c FROM knowledge_lake.sop_playbooks WHERE library_id='${esc(id)}'`);
    if (Number(check?.[0]?.c || 0) > 0) return NextResponse.json({ error: "Library has playbooks — remove them first" }, { status: 400 });
    await query(`DELETE FROM knowledge_lake.sop_libraries WHERE id='${esc(id)}'`);
    return NextResponse.json({ ok: true });
  }

  if (type === "playbook") {
    const check = await query(`SELECT count(*) as c FROM knowledge_lake.sop_cards WHERE playbook_id='${esc(id)}'`);
    if (Number(check?.[0]?.c || 0) > 0) return NextResponse.json({ error: "Playbook has cards — remove them first" }, { status: 400 });
    await query(`DELETE FROM knowledge_lake.sop_playbooks WHERE id='${esc(id)}'`);
    return NextResponse.json({ ok: true });
  }

  if (type === "card") {
    // Also remove completions for this card
    await query(`DELETE FROM knowledge_lake.training_completions WHERE card_id='${esc(id)}'`);
    await query(`DELETE FROM knowledge_lake.sop_cards WHERE id='${esc(id)}'`);
    return NextResponse.json({ ok: true });
  }

  return NextResponse.json({ error: "Unknown type" }, { status: 400 });
}
