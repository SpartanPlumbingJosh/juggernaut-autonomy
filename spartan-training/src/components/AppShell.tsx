"use client";

import { useState, useEffect, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";

interface User { id: string; email: string; name: string; role: string }

const NAV: { href: string; label: string; icon: string; adminOnly?: boolean }[] = [
  { href: "/", label: "Training Library", icon: "📚" },
  { href: "/onboard", label: "My Onboarding", icon: "🎯" },
  { href: "/admin", label: "Command Center", icon: "🔒", adminOnly: true },
  { href: "/admin/content", label: "SOP Content", icon: "📝", adminOnly: true },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const pathname = usePathname();
  const router = useRouter();

  const seedSessionStorage = useCallback((email: string) => {
    if (typeof window === "undefined") return;
    // Pre-seed sessionStorage keys that AdminApp and OnboardingApp check
    // so they skip their internal login gates
    if (!sessionStorage.getItem("sa_admin")) sessionStorage.setItem("sa_admin", email);
    if (!sessionStorage.getItem("sa_email")) sessionStorage.setItem("sa_email", email);
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

  // Don't render shell on login/setup pages
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
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  const visibleNav = NAV.filter(n => !n.adminOnly || user?.role === "admin");

  return (
    <div style={{ minHeight: "100vh", background: "#0a0a0a" }}>
      {/* ─── TOP BAR ─── */}
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
        {/* Logo */}
        <a href="/" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="https://spartan-plumbing.com/wp-content/uploads/spartan-logo-nav.svg"
            alt="Spartan Plumbing"
            style={{ height: 32, width: "auto" }}
          />
          <span style={{
            fontFamily: "'Archivo Black', sans-serif",
            fontSize: 14,
            color: "#c8a84e",
            letterSpacing: 2,
            textTransform: "uppercase" as const,
          }}>
            Academy
          </span>
        </a>

        {/* Nav Links */}
        <nav style={{ display: "flex", alignItems: "center", gap: 4, height: "100%" }}>
          {visibleNav.map(n => {
            const active = isActive(n.href);
            return (
              <a
                key={n.href}
                href={n.href}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "6px 14px",
                  borderRadius: 6,
                  fontSize: 13,
                  fontFamily: "'Barlow Condensed', sans-serif",
                  fontWeight: 600,
                  letterSpacing: 0.5,
                  textDecoration: "none",
                  color: active ? "#c8a84e" : "#666",
                  background: active ? "rgba(200,168,78,0.08)" : "transparent",
                  transition: "all 0.15s",
                }}
              >
                <span style={{ fontSize: 15 }}>{n.icon}</span>
                {n.label}
              </a>
            );
          })}
        </nav>

        {/* User */}
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
              <button
                onClick={handleLogout}
                style={{
                  background: "transparent", border: "1px solid #222",
                  color: "#555", padding: "5px 12px", borderRadius: 6,
                  fontSize: 11, cursor: "pointer",
                  fontFamily: "'Barlow Condensed', sans-serif",
                  fontWeight: 600, letterSpacing: 0.5, transition: "all 0.15s",
                }}
              >
                Sign Out
              </button>
            </>
          )}
        </div>
      </header>

      {/* ─── CONTENT ─── */}
      <main style={{ maxWidth: 960, margin: "0 auto", padding: "24px 16px" }}>
        {children}
      </main>
    </div>
  );
}
