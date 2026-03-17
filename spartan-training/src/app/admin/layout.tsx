export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <div style={{
        display: "flex", gap: 10, marginBottom: 24, flexWrap: "wrap",
        borderBottom: "1px solid #222", paddingBottom: 14,
      }}>
        <a href="/admin" style={{
          fontSize: 13, color: "#b91c1c", fontFamily: "'Barlow Condensed', sans-serif",
          fontWeight: 600, letterSpacing: 1, padding: "6px 14px", borderRadius: 6,
          background: "rgba(185,28,28,0.08)", textDecoration: "none",
        }}>
          👥 Team &amp; Onboarding
        </a>
        <a href="/admin/content" style={{
          fontSize: 13, color: "#c8a84e", fontFamily: "'Barlow Condensed', sans-serif",
          fontWeight: 600, letterSpacing: 1, padding: "6px 14px", borderRadius: 6,
          background: "rgba(200,168,78,0.08)", textDecoration: "none",
        }}>
          📝 SOP Content
        </a>
      </div>
      {children}
    </div>
  );
}
