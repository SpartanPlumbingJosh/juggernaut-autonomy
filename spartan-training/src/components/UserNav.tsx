"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
}

export function UserNav() {
  const [user, setUser] = useState<User | null>(null);
  const router = useRouter();

  useEffect(() => {
    fetch("/api/auth/me")
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (d?.user) setUser(d.user); })
      .catch(() => {});
  }, []);

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  if (!user) return null;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <span style={{
        fontSize: 13,
        color: "#999",
        fontFamily: "'Barlow Condensed', sans-serif",
      }}>
        {user.name}
        {user.role === "admin" && (
          <span style={{
            marginLeft: 6,
            fontSize: 10,
            background: "rgba(185,28,28,0.2)",
            color: "#ef4444",
            padding: "2px 6px",
            borderRadius: 4,
            fontWeight: 600,
          }}>
            ADMIN
          </span>
        )}
      </span>
      <button
        onClick={handleLogout}
        style={{
          background: "transparent",
          border: "1px solid #333",
          color: "#666",
          padding: "4px 12px",
          borderRadius: 6,
          fontSize: 12,
          cursor: "pointer",
          fontFamily: "'Barlow Condensed', sans-serif",
          fontWeight: 600,
          letterSpacing: 0.5,
          transition: "all 0.2s",
        }}
        onMouseOver={(e) => {
          e.currentTarget.style.borderColor = "#b91c1c";
          e.currentTarget.style.color = "#ef4444";
        }}
        onMouseOut={(e) => {
          e.currentTarget.style.borderColor = "#333";
          e.currentTarget.style.color = "#666";
        }}
      >
        Sign Out
      </button>
    </div>
  );
}
