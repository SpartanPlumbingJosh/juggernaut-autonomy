"use client";

import { useState } from "react";

export function MarkCompleteButton({ cardId, playbookId }: { cardId: string; playbookId: string }) {
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState("");
  const [showForm, setShowForm] = useState(false);

  async function handleComplete() {
    if (!email) {
      setShowForm(true);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/completions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          employee_email: email,
          employee_name: email.split("@")[0],
          card_id: cardId,
          playbook_id: playbookId,
          time_spent_seconds: 0,
        }),
      });
      if (res.ok) setDone(true);
    } catch {
      alert("Failed to record completion");
    }
    setLoading(false);
  }

  if (done) {
    return (
      <div style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "10px 20px", borderRadius: 8,
        background: "rgba(62,207,142,0.1)",
        color: "var(--green)", fontWeight: 600,
      }}>
        ✓ Marked complete
      </div>
    );
  }

  if (showForm && !email) {
    return (
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <input
          type="email"
          placeholder="your@spartan-plumbing.com"
          onChange={(e) => setEmail(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleComplete(); }}
          style={{
            padding: "8px 14px", borderRadius: 8,
            border: "1px solid var(--border)", background: "var(--bg3)",
            color: "var(--text)", fontSize: 14, width: 260,
          }}
        />
        <button
          className="btn btn-gold"
          onClick={handleComplete}
          disabled={loading}
        >
          {loading ? "Saving..." : "Confirm ✓"}
        </button>
      </div>
    );
  }

  return (
    <button
      className="btn btn-gold"
      onClick={handleComplete}
      disabled={loading}
    >
      {loading ? "Saving..." : email ? "Mark Complete ✓" : "I've Read This — Mark Complete"}
    </button>
  );
}
