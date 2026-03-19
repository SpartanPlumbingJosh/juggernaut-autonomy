"use client";

import { useState, useEffect, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";

interface User { id: string; email: string; name: string; role: string }

const NAV: { href: string; label: string; adminOnly?: boolean }[] = [
  { href: "/", label: "SOPs" },
  { href: "/onboard", label: "Onboarding" },
  { href: "/admin", label: "Command Center", adminOnly: true },
  { href: "/admin/content", label: "SOP Content", adminOnly: true },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const pathname = usePathname();
  const router = useRouter();

  const seedSessionStorage = useCallback((email: string) => {
    if (typeof window === "undefined") return;
    sessionStorage.setItem("sa_admin", email);
    sessionStorage.setItem("sa_email", email);
  }, []);

  useEffect(() => {
    fetch("/api/auth/me")
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d?.user) {
          setUser(d.user);
          seedSessionStorage(d.user.email);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [seedSessionStorage]);

  async function handleLogout() {
    sessionStorage.removeItem("sa_admin");
    sessionStorage.removeItem("sa_email");
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  if (pathname === "/login" || pathname === "/setup-password") {
    return <>{children}</>;
  }

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", background: "#0a0a0a", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ color: "#555", fontSize: 14 }}>Loading...</div>
      </div>
    );
  }

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/" || pathname.startsWith("/board") || pathname.startsWith("/playbook");
    if (href === "/admin") return pathname === "/admin";
    return pathname.startsWith(href);
  };

  const visibleNav = NAV.filter(n => !n.adminOnly || user?.role === "admin");

  return (
    <div style={{ minHeight: "100vh", background: "#0a0a0a" }}>
      <header style={{
        background: "#111",
        borderBottom: "1px solid #1a1a1a",
        padding: "0 24px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        position: "sticky",
        top: 0,
        zIndex: 200,
        height: 56,
      }}>
        <a href="/" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="https://spartan-plumbing.com/wp-content/uploads/spartan-logo-nav.svg"
            alt="Spartan Plumbing"
            style={{ height: 32, width: "auto" }}
          />
          <span style={{
            fontFamily: "'Archivo Black', sans-serif",
            fontSize: 14, color: "#c8a84e", letterSpacing: 2,
            textTransform: "uppercase" as const,
          }}>
            Academy
          </span>
        </a>

        <nav style={{ display: "flex", alignItems: "center", gap: 2, height: "100%" }}>
          {visibleNav.map(n => {
            const active = isActive(n.href);
            return (
              <a key={n.href} href={n.href} style={{
                padding: "8px 16px",
                borderRadius: 6,
                fontSize: 13,
                fontFamily: "'Barlow Condensed', sans-serif",
                fontWeight: active ? 700 : 600,
                letterSpacing: 1,
                textTransform: "uppercase" as const,
                textDecoration: "none",
                color: active ? "#c8a84e" : "#555",
                background: active ? "rgba(200,168,78,0.08)" : "transparent",
                borderBottom: active ? "2px solid #c8a84e" : "2px solid transparent",
                transition: "all 0.15s",
              }}>
                {n.label}
              </a>
            );
          })}
        </nav>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {user && (
            <>
              <span style={{ fontSize: 13, color: "#666", fontFamily: "'Barlow Condensed', sans-serif" }}>
                {user.name}
                {user.role === "admin" && (
                  <span style={{
                    marginLeft: 6, fontSize: 10,
                    background: "rgba(200,168,78,0.15)", color: "#c8a84e",
                    padding: "2px 6px", borderRadius: 4, fontWeight: 700,
                    letterSpacing: 1,
                  }}>ADMIN</span>
                )}
              </span>
              <button onClick={handleLogout} style={{
                background: "transparent", border: "1px solid #222",
                color: "#555", padding: "5px 12px", borderRadius: 6,
                fontSize: 11, cursor: "pointer",
                fontFamily: "'Barlow Condensed', sans-serif",
                fontWeight: 600, letterSpacing: 0.5, transition: "all 0.15s",
              }}>
                Sign Out
              </button>
            </>
          )}
        </div>
      </header>

      <main style={{ maxWidth: 960, margin: "0 auto", padding: "24px 16px" }}>
        {children}
      </main>
    </div>
  );
}
