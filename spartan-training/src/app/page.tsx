import { query } from "@/lib/supabase";
import Link from "next/link";

const BOARD_ICONS: Record<string, string> = {
  "Everyone @ Spartan": "🏠",
  "Install Technicians": "🔧",
  "Service Technicians": "🛠",
  "Sales": "💰",
  "Office & Admin": "🖥",
  "Leadership": "⭐",
  "Safety & Compliance": "🦺",
};

export const dynamic = "force-dynamic";

/* eslint-disable @typescript-eslint/no-explicit-any */
export default async function HomePage() {
  let boards: Array<{
    id: string; name: string;
    library_count: number; card_count: number;
    libraries: Array<{ id: string; name: string; playbook_count: number }>;
  }> = [];

  try {
    const raw = await query(`
      SELECT b.id, b.name,
        (SELECT count(*) FROM knowledge_lake.sop_libraries l WHERE l.board_id = b.id) as library_count,
        (SELECT count(*) FROM knowledge_lake.sop_cards c 
         JOIN knowledge_lake.sop_playbooks p ON p.id = c.playbook_id
         JOIN knowledge_lake.sop_libraries l ON l.id = p.library_id
         WHERE l.board_id = b.id) as card_count
      FROM knowledge_lake.sop_boards b
      ORDER BY b.name
    `);
    boards = (raw || []).map((b: any) => ({
      ...b,
      library_count: Number(b.library_count),
      card_count: Number(b.card_count),
      libraries: [],
    }));

    for (const board of boards) {
      const libs = await query(`
        SELECT l.id, l.name,
          (SELECT count(*) FROM knowledge_lake.sop_playbooks p WHERE p.library_id = l.id) as playbook_count
        FROM knowledge_lake.sop_libraries l
        WHERE l.board_id = '${board.id}'
        ORDER BY l.sort_order
      `);
      board.libraries = (libs || []).map((l: any) => ({
        ...l,
        playbook_count: Number(l.playbook_count),
      }));
    }
  } catch (e) {
    console.error("Failed to load boards:", e);
  }

  return (
    <div>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: "1.75rem", fontWeight: 700, marginBottom: 4 }}>
          Training Library
        </h1>
        <p style={{ color: "var(--text2)", fontSize: 14 }}>
          282 SOPs across 7 departments. Read, learn, track your progress.
        </p>
      </div>

      <div style={{ display: "grid", gap: 16 }}>
        {boards.map((board) => (
          <div key={board.id} className="card" style={{ padding: 0 }}>
            <div style={{
              padding: "20px 24px",
              display: "flex",
              alignItems: "flex-start",
              gap: 16,
            }}>
              <div style={{
                width: 48, height: 48, borderRadius: 12,
                background: "rgba(212,168,67,0.1)",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 24, flexShrink: 0,
              }}>
                {BOARD_ICONS[board.name] || "📋"}
              </div>
              <div style={{ flex: 1 }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: 4 }}>
                  {board.name}
                </h2>
                <div style={{ display: "flex", gap: 12, fontSize: 13, color: "var(--text3)" }}>
                  <span>{board.library_count} libraries</span>
                  <span>·</span>
                  <span>{board.card_count} SOPs</span>
                </div>
              </div>
            </div>

            <div style={{
              borderTop: "1px solid var(--border)",
              padding: "12px 24px",
              display: "flex",
              flexWrap: "wrap",
              gap: 8,
            }}>
              {board.libraries.map((lib) => (
                <Link
                  key={lib.id}
                  href={`/board/${board.id}?library=${lib.id}`}
                  className="badge badge-gold"
                  style={{ cursor: "pointer" }}
                >
                  {lib.name} ({lib.playbook_count})
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
