"use client";

import { useState, useEffect } from "react";
import { AdminApp } from "./AdminApp";

// Renders AdminApp immediately (so its useEffect starts loading data)
// but covers it with a full-screen overlay until the API pre-warm completes.
// By the time the overlay fades, AdminApp has received its data and set authed=true.
export default function AdminPage() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    async function init() {
      try {
        const res = await fetch("/api/auth/me");
        if (res.ok) {
          const me = await res.json();
          const email = me.user?.email;
          if (email) {
            sessionStorage.setItem("sa_admin", email);
            // Pre-warm ALL admin APIs in parallel
            await Promise.all([
              fetch(`/api/admin?admin_email=${encodeURIComponent(email)}`),
              fetch(`/api/admin/templates?admin_email=${encodeURIComponent(email)}`),
              fetch("/api/admin/users"),
            ]);
          }
        }
      } catch { /* proceed */ }
      // Give AdminApp's useEffect time to process the (now-cached) responses
      await new Promise(r => setTimeout(r, 300));
      setReady(true);
    }
    init();
  }, []);

  return (
    <div style={{ position: "relative", minHeight: "60vh" }}>
      {!ready && (
        <div style={{
          position: "fixed", inset: 0, background: "#0a0a0a", zIndex: 150,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <div style={{ color: "#555", fontSize: 14, fontFamily: "'Barlow Condensed', sans-serif" }}>
            Loading Command Center...
          </div>
        </div>
      )}
      <AdminApp />
    </div>
  );
}
