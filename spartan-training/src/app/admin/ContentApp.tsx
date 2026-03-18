"use client";
import { useState, useEffect, useCallback } from "react";

interface Board { id: string; name: string; slug: string; sort_order: number; description: string; icon: string; color: string; card_count: number; library_count: number; }
interface Library { id: string; board_id: string; name: string; slug: string; sort_order: number; description: string; card_count: number; playbook_count: number; }
interface Playbook { id: string; library_id: string; name: string; slug: string; sort_order: number; description: string; card_count: number; }
interface Card { id: string; playbook_id: string; title: string; content: string; sort_order: number; xp_value: number; tags: string; }
type View = "boards" | "libraries" | "playbooks" | "cards";
type AnyItem = Board | Library | Playbook | Card;

const CSS = `
.cnt-field{width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:7px;background:#0a0a0a;color:var(--text);font-size:14px;font-family:inherit;outline:none;box-sizing:border-box;transition:border-color .2s}
.cnt-field:focus{border-color:var(--gold)}
.cnt-field::placeholder{color:var(--text3)}
.cnt-ta{width:100%;padding:12px 14px;border:1px solid var(--border);border-radius:7px;background:#0a0a0a;color:var(--text);font-size:13px;font-family:'JetBrains Mono',monospace;outline:none;box-sizing:border-box;resize:vertical;min-height:340px;line-height:1.65;transition:border-color .2s}
.cnt-ta:focus{border-color:var(--gold)}
.cnt-label{font-size:11px;color:var(--text3);font-weight:500;margin-bottom:4px;display:block}
.cnt-toast{position:fixed;top:70px;left:50%;transform:translateX(-50%);background:var(--gold);color:#0a0a0a;padding:10px 28px;border-radius:20px;font-weight:600;font-size:14px;z-index:500;box-shadow:0 4px 20px rgba(200,168,78,0.4)}
.cnt-overlay{position:fixed;inset:0;background:rgba(0,0,0,0.75);z-index:300;display:flex;align-items:flex-start;justify-content:center;padding:32px 16px;overflow-y:auto}
.cnt-modal{width:100%;max-width:800px;background:#111;border:1px solid var(--border);border-radius:12px;overflow:hidden}
.cnt-preview h1{font-size:1.3rem;font-weight:700;margin:16px 0 8px}
.cnt-preview h2{font-size:1.1rem;font-weight:600;margin:14px 0 6px;color:var(--gold)}
.cnt-preview h3{font-size:1rem;font-weight:600;margin:12px 0 4px}
.cnt-preview ul{margin:8px 0;padding-left:20px}
.cnt-preview li{margin:4px 0;line-height:1.6}
.cnt-preview strong{color:var(--text);font-weight:600}
.cnt-preview blockquote{border-left:3px solid var(--gold);padding-left:14px;margin:12px 0;color:var(--text2)}
.cnt-preview code{background:#1a1a1a;padding:2px 6px;border-radius:4px;font-family:monospace;font-size:13px}
.cnt-preview hr{border:none;border-top:1px solid var(--border);margin:16px 0}
`;

export function ContentApp() {
  const [view, setView] = useState<View>("boards");
  const [selBoard, setSelBoard] = useState<Board | null>(null);
  const [selLibrary, setSelLibrary] = useState<Library | null>(null);
  const [selPlaybook, setSelPlaybook] = useState<Playbook | null>(null);
  const [items, setItems] = useState<AnyItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editData, setEditData] = useState<Record<string, string | number>>({});
  const [adding, setAdding] = useState(false);
  const [addData, setAddData] = useState<Record<string, string | number>>({});
  const [cardDraft, setCardDraft] = useState<Partial<Card> | null>(null);
  const [mdPreview, setMdPreview] = useState(false);

  const notify = (msg: string) => { setToast(msg); setTimeout(() => setToast(""), 3200); };

  const load = useCallback(async (v: View, b?: Board | null, l?: Library | null, p?: Playbook | null) => {
    setLoading(true);
    try {
      let qs = `type=${v === "boards" ? "boards" : v === "libraries" ? "libraries" : v === "playbooks" ? "playbooks" : "cards"}`;
      if (v === "libraries" && b) qs += `&board_id=${b.id}`;
      if (v === "playbooks" && l) qs += `&library_id=${l.id}`;
      if (v === "cards" && p) qs += `&playbook_id=${p.id}`;
      const res = await fetch(`/api/admin/content?${qs}`);
      if (res.ok) {
        const d = await res.json();
        setItems(d.boards || d.libraries || d.playbooks || d.cards || []);
      }
    } catch { notify("Load failed"); }
    setLoading(false);
  }, []);

  useEffect(() => { load(view, selBoard, selLibrary, selPlaybook); }, [view, selBoard, selLibrary, selPlaybook, load]);

  const refresh = () => load(view, selBoard, selLibrary, selPlaybook);

  async function apiCall(method: "POST" | "PUT" | "DELETE", body?: Record<string, unknown>, deleteParams?: string) {
    try {
      const res = method === "DELETE"
        ? await fetch(`/api/admin/content?${deleteParams}`, { method: "DELETE" })
        : await fetch("/api/admin/content", { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const d = await res.json();
      if (d.ok) { notify("Saved ✓"); refresh(); return true; }
      notify(d.error || "Failed"); return false;
    } catch { notify("Connection error"); return false; }
  }

  function navTo(v: View, b?: Board | null, l?: Library | null, p?: Playbook | null) {
    setView(v);
    setSelBoard(b !== undefined ? b : selBoard);
    setSelLibrary(l !== undefined ? l : v === "libraries" ? null : selLibrary);
    setSelPlaybook(p !== undefined ? p : v === "boards" || v === "libraries" ? null : selPlaybook);
    setEditingId(null); setAdding(false); setAddData({});
  }

  function startEdit(item: AnyItem) {
    const it = item as unknown as Record<string, unknown>;
    setEditingId(it.id as string);
    setEditData({
      name: (it.name || it.title || "") as string,
      description: (it.description || "") as string,
      icon: (it.icon || "") as string,
      sort_order: (it.sort_order || 0) as number,
    });
  }

  const typeKey: Record<View, string> = { boards: "board", libraries: "library", playbooks: "playbook", cards: "card" };

  async function submitEdit() {
    if (!editingId) return;
    const ok = await apiCall("PUT", { type: typeKey[view], id: editingId, ...editData });
    if (ok) setEditingId(null);
  }

  async function submitAdd() {
    const extra: Record<string, string> = {};
    if (view === "libraries" && selBoard) extra.board_id = selBoard.id;
    if (view === "playbooks" && selLibrary) extra.library_id = selLibrary.id;
    if (view === "cards" && selPlaybook) extra.playbook_id = selPlaybook.id;
    const ok = await apiCall("POST", { type: typeKey[view], ...addData, ...extra });
    if (ok) { setAdding(false); setAddData({}); }
  }

  async function deleteItem(id: string) {
    if (!confirm("Delete this permanently?")) return;
    await apiCall("DELETE", undefined, `type=${typeKey[view]}&id=${id}`);
  }

  async function saveCard() {
    if (!cardDraft?.title) { notify("Title required"); return; }
    const isNew = !cardDraft.id;
    const ok = await apiCall(isNew ? "POST" : "PUT", {
      type: "card",
      ...(isNew ? { playbook_id: selPlaybook?.id } : { id: cardDraft.id }),
      title: cardDraft.title,
      content: cardDraft.content || "",
      xp_value: cardDraft.xp_value || 10,
      tags: cardDraft.tags || "",
      sort_order: cardDraft.sort_order || 0,
    });
    if (ok) setCardDraft(null);
  }

  function renderMd(md: string) {
    return (md || "")
      .replace(/^---$/gm, '<hr>')
      .replace(/^### (.+)$/gm, '<h3>$1</h3>')
      .replace(/^## (.+)$/gm, '<h2>$1</h2>')
      .replace(/^# (.+)$/gm, '<h1>$1</h1>')
      .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/`(.+?)`/g, '<code>$1</code>')
      .replace(/^- (.+)$/gm, '<li>$1</li>')
      .replace(/(<li>.*<\/li>\n?)+/g, m => `<ul>${m}</ul>`)
      .replace(/\n\n/g, '<br><br>')
      .replace(/\n/g, '<br>');
  }

  return (
    <div>
      <style>{CSS}</style>
      {toast && <div className="cnt-toast">{toast}</div>}

      {/* Card editor modal */}
      {cardDraft !== null && (
        <div className="cnt-overlay" onClick={() => setCardDraft(null)}>
          <div className="cnt-modal" onClick={e => e.stopPropagation()}>
            {/* Header */}
            <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--border)", display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
              <div style={{ flex: 3, minWidth: 200 }}>
                <label className="cnt-label">Card Title *</label>
                <input className="cnt-field" value={cardDraft.title || ""} onChange={e => setCardDraft({ ...cardDraft, title: e.target.value })} placeholder="e.g. How to Handle a Service Call" autoFocus />
              </div>
              <div style={{ width: 80 }}>
                <label className="cnt-label">XP Value</label>
                <input className="cnt-field" type="number" min={1} value={cardDraft.xp_value || 10} onChange={e => setCardDraft({ ...cardDraft, xp_value: Number(e.target.value) })} />
              </div>
              <div style={{ width: 160 }}>
                <label className="cnt-label">Tags (comma-separated)</label>
                <input className="cnt-field" value={cardDraft.tags || ""} onChange={e => setCardDraft({ ...cardDraft, tags: e.target.value })} placeholder="safety, tools" />
              </div>
            </div>
            {/* Edit / Preview toggle */}
            <div style={{ padding: "12px 24px", borderBottom: "1px solid var(--border)", display: "flex", gap: 8 }}>
              <button className={`badge ${!mdPreview ? "badge-gold" : ""}`} style={{ cursor: "pointer", border: mdPreview ? "1px solid var(--border)" : undefined, background: mdPreview ? "transparent" : undefined, color: mdPreview ? "var(--text3)" : undefined }} onClick={() => setMdPreview(false)}>✏️ Markdown</button>
              <button className={`badge ${mdPreview ? "badge-gold" : ""}`} style={{ cursor: "pointer", border: !mdPreview ? "1px solid var(--border)" : undefined, background: !mdPreview ? "transparent" : undefined, color: !mdPreview ? "var(--text3)" : undefined }} onClick={() => setMdPreview(true)}>👁 Preview</button>
              <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--text3)", alignSelf: "center" }}>Markdown supported — ## headings, **bold**, - lists, &gt; quotes, `code`</span>
            </div>
            {/* Editor / Preview */}
            <div style={{ padding: "16px 24px", borderBottom: "1px solid var(--border)" }}>
              {!mdPreview
                ? <textarea className="cnt-ta" value={cardDraft.content || ""} onChange={e => setCardDraft({ ...cardDraft, content: e.target.value })} placeholder={"## Overview\n\nDescribe what this SOP covers.\n\n## Steps\n\n- Step 1\n- Step 2\n- Step 3\n\n## Notes\n\n**Important:** Any key callouts here."} />
                : <div className="cnt-preview" style={{ fontSize: 14, lineHeight: 1.7, minHeight: 340 }} dangerouslySetInnerHTML={{ __html: renderMd(cardDraft.content || "") }} />
              }
            </div>
            {/* Footer */}
            <div style={{ padding: "16px 24px", display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button className="btn btn-outline" onClick={() => setCardDraft(null)}>Cancel</button>
              <button className="btn btn-gold" onClick={saveCard} disabled={!cardDraft.title}>
                {cardDraft.id ? "Save Changes" : "Create Card"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Breadcrumb nav */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 20, flexWrap: "wrap" }}>
        <button className={`badge ${view === "boards" ? "badge-gold" : ""}`}
          style={{ cursor: "pointer", border: view !== "boards" ? "1px solid var(--border)" : undefined, background: view !== "boards" ? "transparent" : undefined, color: view !== "boards" ? "var(--text3)" : undefined }}
          onClick={() => navTo("boards", null, null, null)}>
          📋 All Boards
        </button>
        {selBoard && <>
          <span style={{ color: "var(--text3)", fontSize: 13 }}>›</span>
          <button className={`badge ${view === "libraries" ? "badge-gold" : ""}`}
            style={{ cursor: "pointer", border: view !== "libraries" ? "1px solid var(--border)" : undefined, background: view !== "libraries" ? "transparent" : undefined, color: view !== "libraries" ? "var(--text3)" : undefined }}
            onClick={() => navTo("libraries", selBoard, null, null)}>
            {selBoard.icon || "📂"} {selBoard.name}
          </button>
        </>}
        {selLibrary && <>
          <span style={{ color: "var(--text3)", fontSize: 13 }}>›</span>
          <button className={`badge ${view === "playbooks" ? "badge-gold" : ""}`}
            style={{ cursor: "pointer", border: view !== "playbooks" ? "1px solid var(--border)" : undefined, background: view !== "playbooks" ? "transparent" : undefined, color: view !== "playbooks" ? "var(--text3)" : undefined }}
            onClick={() => navTo("playbooks", selBoard, selLibrary, null)}>
            📚 {selLibrary.name}
          </button>
        </>}
        {selPlaybook && <>
          <span style={{ color: "var(--text3)", fontSize: 13 }}>›</span>
          <span className="badge badge-gold">📄 {selPlaybook.name}</span>
        </>}
      </div>

      {/* Main content card */}
      <div className="card" style={{ padding: 0 }}>
        {/* Card header */}
        <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ flex: 1 }}>
            <h2 style={{ fontSize: "1.05rem", fontWeight: 600, margin: 0 }}>
              {view === "boards" ? "Boards"
                : view === "libraries" ? `Libraries — ${selBoard?.name}`
                : view === "playbooks" ? `Playbooks — ${selLibrary?.name}`
                : `Cards — ${selPlaybook?.name}`}
            </h2>
            <p style={{ fontSize: 12, color: "var(--text3)", margin: "2px 0 0" }}>
              {items.length} item{items.length !== 1 ? "s" : ""}
              {view === "boards" && ` · ${(items as Board[]).reduce((s, b) => s + Number(b.card_count || 0), 0)} total cards`}
            </p>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            {view === "cards" && (
              <button className="btn btn-gold" style={{ fontSize: 12, padding: "6px 14px" }}
                onClick={() => { setMdPreview(false); setCardDraft({ title: "", content: "", xp_value: 10, tags: "", sort_order: items.length + 1 }); }}>
                + New Card
              </button>
            )}
            {view !== "cards" && (
              <button className="btn btn-gold" style={{ fontSize: 12, padding: "6px 14px" }}
                onClick={() => { setAdding(!adding); setAddData({}); setEditingId(null); }}>
                {adding ? "Cancel" : `+ New ${typeKey[view].charAt(0).toUpperCase() + typeKey[view].slice(1)}`}
              </button>
            )}
          </div>
        </div>

        {/* Add form */}
        {adding && (
          <div style={{ padding: "16px 20px", background: "rgba(200,168,78,0.04)", borderBottom: "1px solid var(--border)" }}>
            <div style={{ display: "grid", gridTemplateColumns: view === "boards" ? "1fr 1fr 80px 80px" : "1fr 1fr", gap: 10, marginBottom: 10 }}>
              <div>
                <label className="cnt-label">Name *</label>
                <input className="cnt-field" value={String(addData.name || "")} onChange={e => setAddData({ ...addData, name: e.target.value })} placeholder="Name..." autoFocus onKeyDown={e => e.key === "Enter" && submitAdd()} />
              </div>
              <div>
                <label className="cnt-label">Description</label>
                <input className="cnt-field" value={String(addData.description || "")} onChange={e => setAddData({ ...addData, description: e.target.value })} placeholder="Optional description..." />
              </div>
              {view === "boards" && <>
                <div>
                  <label className="cnt-label">Icon</label>
                  <input className="cnt-field" value={String(addData.icon || "")} onChange={e => setAddData({ ...addData, icon: e.target.value })} placeholder="📋" />
                </div>
                <div>
                  <label className="cnt-label">Color</label>
                  <input className="cnt-field" value={String(addData.color || "")} onChange={e => setAddData({ ...addData, color: e.target.value })} placeholder="#c9a84c" />
                </div>
              </>}
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-gold" style={{ fontSize: 12, padding: "7px 16px" }} onClick={submitAdd} disabled={!addData.name}>
                Create {typeKey[view]}
              </button>
              <button className="btn btn-outline" style={{ fontSize: 12, padding: "7px 14px" }} onClick={() => { setAdding(false); setAddData({}); }}>Cancel</button>
            </div>
          </div>
        )}

        {/* Loading */}
        {loading && <p style={{ textAlign: "center", padding: 40, color: "var(--text3)", fontSize: 13, margin: 0 }}>Loading...</p>}

        {/* Item rows */}
        {!loading && items.map((item) => {
          const it = item as unknown as Record<string, unknown>;
          const isEditing = editingId === it.id;
          const displayName = (it.title || it.name || "") as string;
          const cardCount = it.card_count as number | undefined;
          const playbookCount = it.playbook_count as number | undefined;

          return (
            <div key={it.id as string} style={{ borderBottom: "1px solid var(--border)" }}>
              {isEditing ? (
                <div style={{ padding: "14px 20px", background: "rgba(200,168,78,0.04)" }}>
                  <div style={{ display: "grid", gridTemplateColumns: view === "boards" ? "1fr 1fr 80px 80px 60px" : "1fr 1fr 60px", gap: 8, marginBottom: 10 }}>
                    <div>
                      <label className="cnt-label">Name</label>
                      <input className="cnt-field" value={String(editData.name || "")} onChange={e => setEditData({ ...editData, name: e.target.value })} />
                    </div>
                    <div>
                      <label className="cnt-label">Description</label>
                      <input className="cnt-field" value={String(editData.description || "")} onChange={e => setEditData({ ...editData, description: e.target.value })} />
                    </div>
                    {view === "boards" && <>
                      <div>
                        <label className="cnt-label">Icon</label>
                        <input className="cnt-field" value={String(editData.icon || "")} onChange={e => setEditData({ ...editData, icon: e.target.value })} />
                      </div>
                      <div>
                        <label className="cnt-label">Color</label>
                        <input className="cnt-field" value={String(editData.color || editData.icon || "")} onChange={e => setEditData({ ...editData, color: e.target.value })} placeholder="#c9a84c" />
                      </div>
                    </>}
                    <div>
                      <label className="cnt-label">Order</label>
                      <input className="cnt-field" type="number" value={Number(editData.sort_order)} onChange={e => setEditData({ ...editData, sort_order: Number(e.target.value) })} />
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button className="btn btn-gold" style={{ fontSize: 12, padding: "6px 14px" }} onClick={submitEdit}>Save</button>
                    <button className="btn btn-outline" style={{ fontSize: 12, padding: "6px 14px" }} onClick={() => setEditingId(null)}>Cancel</button>
                  </div>
                </div>
              ) : (
                <div style={{ padding: "13px 20px", display: "flex", alignItems: "center", gap: 12 }}>
                  {/* Icon or order indicator */}
                  <div style={{ width: 36, height: 36, borderRadius: 8, background: "rgba(200,168,78,0.08)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, flexShrink: 0 }}>
                    {view === "boards" ? (it.icon as string || "📋") : view === "cards" ? "📄" : view === "libraries" ? "📚" : "📁"}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: "0.92rem", display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 360 }}>{displayName}</span>
                      {cardCount !== undefined && cardCount > 0 && (
                        <span className="badge" style={{ fontSize: 10, background: "transparent", border: "1px solid var(--border)", color: "var(--text3)", padding: "1px 7px" }}>{cardCount} cards</span>
                      )}
                      {playbookCount !== undefined && playbookCount > 0 && (
                        <span className="badge" style={{ fontSize: 10, background: "transparent", border: "1px solid var(--border)", color: "var(--text3)", padding: "1px 7px" }}>{playbookCount} playbooks</span>
                      )}
                      {it.xp_value !== undefined && (
                        <span className="badge badge-gold" style={{ fontSize: 10, padding: "1px 7px" }}>{it.xp_value as number} XP</span>
                      )}
                    </div>
                    {(it.description as string) && (
                      <div style={{ fontSize: 12, color: "var(--text3)", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 500 }}>
                        {it.description as string}
                      </div>
                    )}
                    {view === "cards" && (it.content as string) && (
                      <div style={{ fontSize: 11, color: "var(--text3)", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 500, fontFamily: "monospace" }}>
                        {((it.content as string) || "").substring(0, 120)}{(it.content as string).length > 120 ? "…" : ""}
                      </div>
                    )}
                    {view === "cards" && (it.tags as string) && (
                      <div style={{ fontSize: 11, color: "var(--text3)", marginTop: 2 }}>🏷 {it.tags as string}</div>
                    )}
                  </div>
                  {/* Actions */}
                  <div style={{ display: "flex", gap: 6, flexShrink: 0, flexWrap: "wrap", justifyContent: "flex-end" }}>
                    {view !== "cards" && (
                      <button className="btn btn-gold" style={{ fontSize: 11, padding: "4px 11px" }} onClick={() => {
                        if (view === "boards") navTo("libraries", item as Board, null, null);
                        else if (view === "libraries") navTo("playbooks", selBoard, item as Library, null);
                        else navTo("cards", selBoard, selLibrary, item as Playbook);
                      }}>Open →</button>
                    )}
                    {view === "cards" && (
                      <button className="btn btn-outline" style={{ fontSize: 11, padding: "4px 11px" }} onClick={() => { setMdPreview(false); setCardDraft({ ...(item as Card) }); }}>Edit</button>
                    )}
                    {view !== "cards" && (
                      <button className="btn btn-outline" style={{ fontSize: 11, padding: "4px 11px" }} onClick={() => startEdit(item)}>Edit</button>
                    )}
                    <button className="btn" style={{ fontSize: 11, padding: "4px 11px", background: "rgba(239,68,68,.08)", color: "#ef4444", border: "1px solid rgba(239,68,68,.2)" }} onClick={() => deleteItem(it.id as string)}>
                      Delete
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {!loading && items.length === 0 && !adding && (
          <div style={{ textAlign: "center", padding: "48px 20px" }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>📭</div>
            <p style={{ color: "var(--text3)", fontSize: 13, margin: 0 }}>
              No {view} yet.{" "}
              {view !== "boards" ? `Click "+ New ${typeKey[view]}" to create one.` : "Boards are the top-level sections of Spartan Academy."}
            </p>
          </div>
        )}
      </div>

      {/* Help hint */}
      <div style={{ marginTop: 16, padding: "12px 16px", background: "rgba(200,168,78,0.04)", borderRadius: 8, border: "1px solid rgba(200,168,78,0.15)", fontSize: 12, color: "var(--text3)", lineHeight: 1.6 }}>
        <strong style={{ color: "var(--text2)" }}>Structure:</strong> Boards → Libraries → Playbooks → Cards (SOPs).{" "}
        Click <strong style={{ color: "var(--text2)" }}>Open →</strong> to drill into the next level.{" "}
        Cards support full Markdown with the built-in editor. Changes are live immediately for all users.
      </div>
    </div>
  );
}
