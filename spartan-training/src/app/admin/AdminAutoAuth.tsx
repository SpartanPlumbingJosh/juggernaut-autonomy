"use client";
import { useEffect, useState } from "react";
import { AdminApp } from "./AdminApp";

export function AdminAutoAuth() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    async function init() {
      try {
        const res = await fetch("/api/auth/me");
        if (res.ok) {
          const data = await res.json();
          const email = data.user?.email || data.email;
          if (email) {
            sessionStorage.setItem("sa_admin", email);
          }
        }
      } catch { /* proceed anyway */ }
      setReady(true);
    }
    init();
  }, []);

  if (!ready) {
    return (
      <div style={{ padding: 60, textAlign: "center", color: "var(--text3)" }}>
        Loading Command Center...
      </div>
    );
  }

  return <AdminApp />;
}
