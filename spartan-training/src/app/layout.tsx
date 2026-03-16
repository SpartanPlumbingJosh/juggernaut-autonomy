import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Spartan Training",
  description: "Spartan Plumbing — Training & SOPs",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header style={{
          background: "var(--bg2)",
          borderBottom: "1px solid var(--border)",
          padding: "12px 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          position: "sticky",
          top: 0,
          zIndex: 100,
        }}>
          <a href="/" style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontWeight: 700, fontSize: "1.1rem", color: "var(--gold)", letterSpacing: 0.5 }}>
              SPARTAN TRAINING
            </span>
          </a>
          <nav style={{ display: "flex", gap: 16, alignItems: "center" }}>
            <a href="/" style={{ fontSize: 14, color: "var(--text2)" }}>Home</a>
          </nav>
        </header>
        <main style={{ maxWidth: 960, margin: "0 auto", padding: "24px 16px" }}>
          {children}
        </main>
      </body>
    </html>
  );
}
