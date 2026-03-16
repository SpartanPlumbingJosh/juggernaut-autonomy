import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Spartan Academy",
  description: "Spartan Plumbing — Training, SOPs & Onboarding",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header style={{
          background: "var(--bg2)",
          borderBottom: "1px solid var(--border)",
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
            <a href="/" style={{ fontSize: 14, color: "var(--text2)" }}>SOPs</a>
            <a href="/onboard" style={{ fontSize: 14, color: "var(--gold)", fontWeight: 600 }}>Onboarding</a>
          </nav>
        </header>
        <main style={{ maxWidth: 960, margin: "0 auto", padding: "24px 16px" }}>
          {children}
        </main>
      </body>
    </html>
  );
}
