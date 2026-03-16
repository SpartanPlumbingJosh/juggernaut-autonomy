import { query } from "@/lib/supabase";
import Link from "next/link";

export const dynamic = "force-dynamic";

interface Params { params: Promise<{ id: string }> }

export default async function PlaybookPage({ params }: Params) {
  const { id } = await params;

  let playbook: { id: string; name: string; library_name: string; board_name: string; board_id: string } | null = null;
  let cards: Array<{ id: string; title: string; content_length: number; sort_order: number }> = [];

  try {
    const pRows = await query(`
      SELECT p.id, p.name, l.name as library_name, b.name as board_name, b.id as board_id
      FROM knowledge_lake.sop_playbooks p
      JOIN knowledge_lake.sop_libraries l ON l.id = p.library_id
      JOIN knowledge_lake.sop_boards b ON b.id = l.board_id
      WHERE p.id = '${id}'
    `);
    playbook = pRows?.[0] || null;

    const cRows = await query(`
      SELECT c.id, c.title, c.content_length, c.sort_order
      FROM knowledge_lake.sop_cards c
      WHERE c.playbook_id = '${id}'
      ORDER BY c.sort_order
    `);
    cards = cRows || [];
  } catch (e) {
    console.error("Failed to load playbook:", e);
  }

  if (!playbook) {
    return <div style={{ padding: 40, textAlign: "center", color: "var(--text3)" }}>Playbook not found</div>;
  }

  return (
    <div>
      <div style={{ marginBottom: 8, display: "flex", gap: 8, fontSize: 13, color: "var(--text3)" }}>
        <Link href="/">All Boards</Link>
        <span>→</span>
        <Link href={`/board/${playbook.board_id}`}>{playbook.board_name}</Link>
        <span>→</span>
        <span style={{ color: "var(--text2)" }}>{playbook.library_name}</span>
      </div>

      <h1 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: 4 }}>{playbook.name}</h1>
      <p style={{ color: "var(--text3)", fontSize: 13, marginBottom: 24 }}>
        {cards.length} SOPs in this playbook
      </p>

      <div style={{ display: "grid", gap: 6 }}>
        {cards.map((card, i) => (
          <Link key={card.id} href={`/playbook/${id}/card/${card.id}`} style={{ textDecoration: "none" }}>
            <div className="card" style={{
              padding: "14px 20px",
              display: "flex", alignItems: "center", gap: 14,
            }}>
              <div style={{
                width: 28, height: 28, borderRadius: 8,
                background: "var(--bg3)", display: "flex",
                alignItems: "center", justifyContent: "center",
                fontSize: 12, fontWeight: 600, color: "var(--text3)", flexShrink: 0,
              }}>
                {i + 1}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 500, color: "var(--text)", fontSize: 14 }}>
                  {card.title}
                </div>
                <div style={{ fontSize: 12, color: "var(--text3)", marginTop: 2 }}>
                  ~{Math.ceil((card.content_length || 0) / 200)} min read
                </div>
              </div>
              <div className="check-pending" />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
