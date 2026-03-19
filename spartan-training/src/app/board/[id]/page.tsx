import { query } from "@/lib/supabase";
import Link from "next/link";

export const dynamic = "force-dynamic";

interface Params { params: Promise<{ id: string }> }

/* eslint-disable @typescript-eslint/no-explicit-any */
export default async function BoardPage({ params }: Params) {
  const { id } = await params;
  
  let board: { id: string; name: string } | null = null;
  let libraries: Array<{
    id: string; name: string; sort_order: number;
    playbooks: Array<{ id: string; name: string; card_count: number }>;
  }> = [];

  try {
    const bRows = await query(`SELECT id, name FROM knowledge_lake.sop_boards WHERE id = '${id}'`);
    board = bRows?.[0] || null;

    const lRows = await query(`
      SELECT l.id, l.name, l.sort_order
      FROM knowledge_lake.sop_libraries l
      WHERE l.board_id = '${id}'
      ORDER BY l.sort_order
    `);
    libraries = (lRows || []).map((l: any) => ({ ...l, playbooks: [] }));

    for (const lib of libraries) {
      const pRows = await query(`
        SELECT p.id, p.name,
          (SELECT count(*) FROM knowledge_lake.sop_cards c WHERE c.playbook_id = p.id) as card_count
        FROM knowledge_lake.sop_playbooks p
        WHERE p.library_id = '${lib.id}'
        ORDER BY p.sort_order, p.name
      `);
      lib.playbooks = (pRows || []).map((p: any) => ({
        ...p,
        card_count: Number(p.card_count),
      }));
    }
  } catch (e) {
    console.error("Failed to load board:", e);
  }

  if (!board) {
    return <div style={{ padding: 40, textAlign: "center", color: "var(--text3)" }}>Board not found</div>;
  }

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Link href="/" style={{ fontSize: 13, color: "var(--text3)" }}>← All Boards</Link>
      </div>
      <h1 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: 24 }}>{board.name}</h1>

      {libraries.map((lib) => (
        <div key={lib.id} style={{ marginBottom: 32 }}>
          <h2 style={{
            fontSize: "0.85rem", fontWeight: 600, textTransform: "uppercase",
            letterSpacing: 1, color: "var(--gold)", marginBottom: 12,
          }}>
            {lib.name}
          </h2>
          <div style={{ display: "grid", gap: 8 }}>
            {lib.playbooks.map((pb) => (
              <Link key={pb.id} href={`/playbook/${pb.id}`} style={{ textDecoration: "none" }}>
                <div className="card" style={{
                  padding: "16px 20px",
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                }}>
                  <span style={{ fontWeight: 500, color: "var(--text)" }}>{pb.name}</span>
                  <span className="badge badge-blue">{pb.card_count} cards</span>
                </div>
              </Link>
            ))}
            {lib.playbooks.length === 0 && (
              <div style={{ padding: 16, color: "var(--text3)", fontSize: 13 }}>
                No playbooks in this library yet.
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
