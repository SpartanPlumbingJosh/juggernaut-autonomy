import { query } from "@/lib/supabase";
import Link from "next/link";
import { MarkCompleteButton } from "@/components/MarkCompleteButton";

export const dynamic = "force-dynamic";

interface Params { params: Promise<{ id: string; cardId: string }> }

export default async function CardPage({ params }: Params) {
  const { id: playbookId, cardId } = await params;

  let card: {
    id: string; title: string; content: string; content_length: number;
    sort_order: number; playbook_name: string; library_name: string;
    board_name: string; board_id: string; playbook_id: string;
  } | null = null;
  let nextCard: { id: string; title: string } | null = null;
  let prevCard: { id: string; title: string } | null = null;

  try {
    const cRows = await query(`
      SELECT c.id, c.title, c.content, c.content_length, c.sort_order, c.playbook_id,
        p.name as playbook_name, l.name as library_name, b.name as board_name, b.id as board_id
      FROM knowledge_lake.sop_cards c
      JOIN knowledge_lake.sop_playbooks p ON p.id = c.playbook_id
      JOIN knowledge_lake.sop_libraries l ON l.id = p.library_id
      JOIN knowledge_lake.sop_boards b ON b.id = l.board_id
      WHERE c.id = '${cardId}'
    `);
    card = cRows?.[0] || null;

    if (card) {
      const nextRows = await query(`
        SELECT id, title FROM knowledge_lake.sop_cards
        WHERE playbook_id = '${playbookId}' AND sort_order > ${card.sort_order}
        ORDER BY sort_order LIMIT 1
      `);
      nextCard = nextRows?.[0] || null;

      const prevRows = await query(`
        SELECT id, title FROM knowledge_lake.sop_cards
        WHERE playbook_id = '${playbookId}' AND sort_order < ${card.sort_order}
        ORDER BY sort_order DESC LIMIT 1
      `);
      prevCard = prevRows?.[0] || null;
    }
  } catch (e) {
    console.error("Failed to load card:", e);
  }

  if (!card) {
    return <div style={{ padding: 40, textAlign: "center", color: "var(--text3)" }}>SOP not found</div>;
  }

  const readMinutes = Math.ceil((card.content_length || 0) / 200);

  return (
    <div>
      <div style={{ marginBottom: 8, display: "flex", gap: 8, fontSize: 13, color: "var(--text3)", flexWrap: "wrap" }}>
        <Link href="/">All Boards</Link>
        <span>→</span>
        <Link href={`/board/${card.board_id}`}>{card.board_name}</Link>
        <span>→</span>
        <Link href={`/playbook/${playbookId}`}>{card.playbook_name}</Link>
      </div>

      <div className="card" style={{ padding: "32px 28px", marginTop: 12 }}>
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
            <span className="badge badge-gold">{card.library_name}</span>
            <span className="badge badge-blue">~{readMinutes} min</span>
          </div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 700 }}>{card.title}</h1>
        </div>

        <div
          className="markdown-content"
          style={{ borderTop: "1px solid var(--border)", paddingTop: 24 }}
          dangerouslySetInnerHTML={{
            __html: renderMarkdown(card.content || "No content available."),
          }}
        />

        <div style={{
          marginTop: 32, paddingTop: 24,
          borderTop: "1px solid var(--border)",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          flexWrap: "wrap", gap: 12,
        }}>
          <MarkCompleteButton cardId={card.id} playbookId={playbookId} />
        </div>
      </div>

      <div style={{
        display: "flex", justifyContent: "space-between",
        marginTop: 16, gap: 12,
      }}>
        {prevCard ? (
          <Link href={`/playbook/${playbookId}/card/${prevCard.id}`}
            className="btn btn-outline" style={{ fontSize: 13 }}>
            ← {prevCard.title.substring(0, 30)}{prevCard.title.length > 30 ? "..." : ""}
          </Link>
        ) : <div />}
        {nextCard ? (
          <Link href={`/playbook/${playbookId}/card/${nextCard.id}`}
            className="btn btn-gold" style={{ fontSize: 13 }}>
            {nextCard.title.substring(0, 30)}{nextCard.title.length > 30 ? "..." : ""} →
          </Link>
        ) : (
          <Link href={`/playbook/${playbookId}`}
            className="btn btn-gold" style={{ fontSize: 13 }}>
            Back to Playbook ✓
          </Link>
        )}
      </div>
    </div>
  );
}

function renderMarkdown(md: string): string {
  return md
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`(.+?)`/g, "<code>$1</code>")
    .replace(/^> (.+)$/gm, "<blockquote>$1</blockquote>")
    .replace(/^- (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>\n?)+/g, (match) => `<ul>${match}</ul>`)
    .replace(/^\d+\. (.+)$/gm, "<li>$1</li>")
    .replace(/\n\n/g, "</p><p>")
    .replace(/^(?!<[hublop])(.+)$/gm, "<p>$1</p>")
    .replace(/<p><\/p>/g, "");
}
