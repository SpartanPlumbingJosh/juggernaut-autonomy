import type { Metadata } from "next";
import "./globals.css";
import { UserNav } from "@/components/UserNav";

export const metadata: Metadata = {
  title: "Spartan Academy",
  description: "Spartan Plumbing — Training, SOPs & Onboarding",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header style={{
          background: "#111",
          borderBottom: "1px solid #222",
          padding: "10px 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          position: "sticky",
          top: 0,
          zIndex: 100,
        }}>
          <a href="/" style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="https://spartan-plumbing.com/wp-content/uploads/spartan-logo-nav.svg"
              alt="Spartan Plumbing"
              style={{ height: 36, width: "auto" }}
            />
          </a>
          <nav style={{ display: "flex", gap: 20, alignItems: "center" }}>
            <a href="/" style={{ fontSize: 14, color: "#999", fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600, letterSpacing: 1, textTransform: "uppercase" as const }}>SOPs</a>
            <a href="/onboard" style={{ fontSize: 14, color: "#c8a84e", fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700, letterSpacing: 1, textTransform: "uppercase" as const }}>Onboarding</a>
            <a href="/admin" style={{ fontSize: 14, color: "#b91c1c", fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700, letterSpacing: 1, textTransform: "uppercase" as const }}>Admin</a>
            <div style={{ width: 1, height: 20, background: "#333" }} />
            <UserNav />
          </nav>
        </header>
        <main style={{ maxWidth: 960, margin: "0 auto", padding: "24px 16px" }}>
          {children}
        </main>
      </body>
    </html>
  );
}
