"use client";

import { useState, useEffect } from "react";
import { AdminApp } from "./AdminApp";

// This wrapper ensures sessionStorage is seeded AND the admin API is
// pre-warmed before AdminApp mounts, preventing the login flash.
export default function AdminPage() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    async function init() {
      try {
        // Get JWT user email
        const meRes = await fetch("/api/auth/me");
        if (!meRes.ok) { setReady(true); return; }
        const me = await meRes.json();
        const email = me.user?.email;
        if (!email) { setReady(true); return; }

        // Seed sessionStorage BEFORE AdminApp mounts
        sessionStorage.setItem("sa_admin", email);

        // Pre-warm the admin API so AdminApp's loadData succeeds immediately
        await fetch(`/api/admin?admin_email=${encodeURIComponent(email)}`);
      } catch { /* proceed anyway */ }
      setReady(true);
    }
    init();
  }, []);

  if (!ready) {
    return (
      <div style={{ padding: 60, textAlign: "center", color: "#555", fontSize: 14 }}>
        Loading Command Center...
      </div>
    );
  }

  return <AdminApp />;
}
