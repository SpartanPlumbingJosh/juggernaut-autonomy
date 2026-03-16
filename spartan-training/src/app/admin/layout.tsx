export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <div style={{
        display: "flex", gap: 12, marginBottom: 24,
        borderBottom: "1px solid #222", paddingBottom: 12,
      }}>
        <a href="/admin" style={{
          fontSize: 14, color: "#b91c1c", fontFamily: "'Barlow Condensed', sans-serif",
          fontWeight: 600, letterSpacing: 1, padding: "6px 14px", borderRadius: 6,
          background: "rgba(185,28,28,0.08)",
        }}>
          Team & Onboarding
        </a>
        <a href="/admin/users" style={{
          fontSize: 14, color: "#c8a84e", fontFamily: "'Barlow Condensed', sans-serif",
          fontWeight: 600, letterSpacing: 1, padding: "6px 14px", borderRadius: 6,
          background: "rgba(200,168,78,0.08)",
        }}>
          🔒 User Access
        </a>
      </div>
      {children}
    </div>
  );
}
