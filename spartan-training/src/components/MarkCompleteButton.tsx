"use client";

import { useState, useEffect } from "react";

export function MarkCompleteButton({ cardId, playbookId }: { cardId: string; playbookId: string }) {
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);
  const [user, setUser] = useState<{ email: string; name: string } | null>(null);

  useEffect(() => {
    fetch("/api/auth/me")
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (d?.user) setUser(d.user); })
      .catch(() => {});
  }, []);

  async function handleComplete() {
    if (!user) return;
    setLoading(true);
    try {
      const res = await fetch("/api/completions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          employee_email: user.email,
          employee_name: user.name,
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

  return (
    <button
      className="btn btn-gold"
      onClick={handleComplete}
      disabled={loading || !user}
    >
      {loading ? "Saving..." : "I've Read This — Mark Complete ✓"}
    </button>
  );
}
