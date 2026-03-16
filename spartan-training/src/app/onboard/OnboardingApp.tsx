"use client";
import { useState, useEffect, useRef } from "react";

const LEVELS = [
  { min: 0, name: "Recruit", icon: "🔰" },
  { min: 100, name: "Trainee", icon: "📘" },
  { min: 250, name: "Apprentice", icon: "🔧" },
  { min: 450, name: "Journeyman", icon: "⚡" },
  { min: 700, name: "Spartan", icon: "🏆" },
];

const CAT_ICONS: Record<string, string> = {
  "Pre-employment": "📋", Documents: "📄", Accounts: "🔑", Profile: "👤",
  Equipment: "🖥️", Training: "📚", "Field setup": "🛠️", Uniforms: "👕",
  Vehicle: "🚐", Shadowing: "👥", "Final checks": "✅",
};

const CAT_COLORS: Record<string, string> = {
  "Pre-employment": "#3b82f6", Documents: "#8b5cf6", Accounts: "#06b6d4",
  Profile: "#f59e0b", Equipment: "#6366f1", Training: "#22c55e",
  "Field setup": "#ef4444", Uniforms: "#ec4899", Vehicle: "#f97316",
  Shadowing: "#14b8a6", "Final checks": "#10b981",
};

interface Item {
  id: string; title: string; description: string; xp_value: number;
  category: string; requires_value: boolean; value_label: string;
  progress_status: string; progress_value: string; completed_at: string;
}
interface Category { items: Item[]; done: number; total: number }
interface Stats { totalXp: number; earnedXp: number; level: number; levelName: string; totalItems: number; completedItems: number }
interface Achievement { badge_code: string; badge_name: string; badge_description: string; earned_at: string }
interface Employee { id: string; name: string; role: string; position: string; email: string }
interface ChatMsg { role: string; content: string }

export function OnboardingApp() {
  const [email, setEmail] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);
  const [employee, setEmployee] = useState<Employee | null>(null);
  const [categories, setCategories] = useState<Record<string, Category>>({});
  const [stats, setStats] = useState<Stats | null>(null);
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [expandedCat, setExpandedCat] = useState<string | null>(null);
  const [showChat, setShowChat] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [xpAnim, setXpAnim] = useState(0);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const saved = typeof window !== "undefined" ? localStorage.getItem("spartan_email") : null;
    if (saved) { setEmail(saved); loadEmployee(saved); }
  }, []);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [chatMessages]);

  useEffect(() => {
    if (stats && xpAnim < stats.earnedXp) {
      const timer = setTimeout(() => setXpAnim(prev => Math.min(prev + 5, stats.earnedXp)), 16);
      return () => clearTimeout(timer);
    }
  }, [xpAnim, stats]);

  async function loadEmployee(em: string) {
    const res = await fetch(`/api/onboard?email=${encodeURIComponent(em)}`);
    const data = await res.json();
    if (data && data.employee) {
      setEmployee(data.employee);
      setCategories(data.categories);
      setStats(data.stats);
      setAchievements(data.achievements || []);
      setLoggedIn(true);
      setXpAnim(0);
      if (typeof window !== "undefined") localStorage.setItem("spartan_email", em);
    } else {
      setLoggedIn(false);
      setEmployee(null);
    }
  }

  async function handleComplete(item: Item) {
    if (!employee) return;
    const newStatus = item.progress_status === "done" ? "pending" : "done";
    const res = await fetch("/api/onboard/progress", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ employee_id: employee.id, template_id: item.id, status: newStatus }),
    });
    const data = await res.json();
    if (data.ok) {
      if (data.newBadges?.length > 0) {
        for (const b of data.newBadges) {
          showToast(`🏅 Achievement unlocked: ${b.name}!`);
        }
      }
      if (newStatus === "done") showToast(`+${item.xp_value} XP`);
      await loadEmployee(email);
    }
  }

  async function sendChat() {
    if (!chatInput.trim() || !employee || chatLoading) return;
    const msg = chatInput.trim();
    setChatInput("");
    setChatMessages(prev => [...prev, { role: "user", content: msg }]);
    setChatLoading(true);
    try {
      const res = await fetch("/api/onboard/coach", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ employee_id: employee.id, message: msg }),
      });
      const data = await res.json();
      setChatMessages(prev => [...prev, { role: "assistant", content: data.reply || "Hmm, try that again." }]);
    } catch {
      setChatMessages(prev => [...prev, { role: "assistant", content: "Connection issue — try again in a sec." }]);
    }
    setChatLoading(false);
  }

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  }

  function getLevel(xp: number) {
    for (let i = LEVELS.length - 1; i >= 0; i--) {
      if (xp >= LEVELS[i].min) return { ...LEVELS[i], index: i };
    }
    return { ...LEVELS[0], index: 0 };
  }

  function getNextLevel(xp: number) {
    const cur = getLevel(xp);
    return cur.index < LEVELS.length - 1 ? LEVELS[cur.index + 1] : null;
  }

  if (!loggedIn) {
    return (
      <div style={S.loginWrap}>
        <div style={S.loginCard}>
          <div style={S.loginLogo}>⚔️</div>
          <h1 style={S.loginTitle}>Spartan Academy</h1>
          <p style={S.loginSub}>Your onboarding journey starts here</p>
          <input
            type="email" placeholder="Enter your @spartan-plumbing.com email"
            value={email} onChange={e => setEmail(e.target.value)}
            onKeyDown={e => e.key === "Enter" && loadEmployee(email)}
            style={S.loginInput}
          />
          <button onClick={() => loadEmployee(email)} style={S.loginBtn}>
            Start Your Journey
          </button>
          <p style={S.loginHint}>New hire? Ask your manager to set you up first.</p>
        </div>
      </div>
    );
  }

  if (!employee || !stats) return <div style={{ padding: 40, textAlign: "center", color: "#9ca3b8" }}>Loading...</div>;

  const curLevel = getLevel(stats.earnedXp);
  const nextLevel = getNextLevel(stats.earnedXp);
  const pct = stats.totalItems > 0 ? Math.round(100 * stats.completedItems / stats.totalItems) : 0;
  const levelPct = nextLevel ? Math.round(100 * (stats.earnedXp - curLevel.min) / (nextLevel.min - curLevel.min)) : 100;

  return (
    <div style={S.wrap}>
      {toast && <div style={S.toast}>{toast}</div>}

      <div style={S.hero}>
        <div style={S.heroLeft}>
          <div style={S.greeting}>Welcome back, {employee.name.split(" ")[0]}</div>
          <div style={S.roleTag}>{employee.role === "tech" ? "Service Technician" : employee.role === "office" ? "Office Staff" : "Apprentice"} Track</div>
        </div>
        <div style={S.heroRight}>
          <div style={S.xpBox}>
            <div style={S.xpNumber}>{xpAnim}</div>
            <div style={S.xpLabel}>XP earned</div>
          </div>
          <div style={S.levelBox}>
            <span style={{ fontSize: 28 }}>{curLevel.icon}</span>
            <div style={S.levelName}>{curLevel.name}</div>
            <div style={S.levelBar}>
              <div style={{ ...S.levelFill, width: `${levelPct}%` }} />
            </div>
            {nextLevel && <div style={S.levelNext}>{nextLevel.min - stats.earnedXp} XP to {nextLevel.name}</div>}
          </div>
        </div>
      </div>

      <div style={S.progressCard}>
        <div style={S.progressRing}>
          <svg width="80" height="80" viewBox="0 0 80 80">
            <circle cx="40" cy="40" r="34" fill="none" stroke="#2a3348" strokeWidth="6" />
            <circle cx="40" cy="40" r="34" fill="none" stroke="#d4a843" strokeWidth="6"
              strokeDasharray={`${2 * Math.PI * 34}`}
              strokeDashoffset={`${2 * Math.PI * 34 * (1 - pct / 100)}`}
              strokeLinecap="round" transform="rotate(-90 40 40)"
              style={{ transition: "stroke-dashoffset 1s ease" }} />
          </svg>
          <div style={S.progressPct}>{pct}%</div>
        </div>
        <div style={S.progressInfo}>
          <div style={S.progressTitle}>{stats.completedItems} of {stats.totalItems} tasks complete</div>
          <div style={S.progressSub}>{stats.totalXp - stats.earnedXp} XP remaining to collect</div>
        </div>
        {achievements.length > 0 && (
          <div style={S.badgeRow}>
            {achievements.map(a => (
              <div key={a.badge_code} style={S.badge} title={a.badge_description}>🏅</div>
            ))}
          </div>
        )}
      </div>

      <div style={S.catGrid}>
        {Object.entries(categories).map(([catName, cat]) => {
          const isOpen = expandedCat === catName;
          const catPct = cat.total > 0 ? Math.round(100 * cat.done / cat.total) : 0;
          const color = CAT_COLORS[catName] || "#d4a843";
          return (
            <div key={catName} style={{ ...S.catCard, borderColor: isOpen ? color : "#2a3348" }}>
              <div style={S.catHeader} onClick={() => setExpandedCat(isOpen ? null : catName)}>
                <div style={S.catIconWrap}>
                  <span style={{ fontSize: 20 }}>{CAT_ICONS[catName] || "📦"}</span>
                </div>
                <div style={{ flex: 1 }}>
                  <div style={S.catName}>{catName}</div>
                  <div style={S.catCount}>{cat.done}/{cat.total} complete</div>
                </div>
                <div style={S.catPctWrap}>
                  <div style={{ ...S.miniBar }}>
                    <div style={{ ...S.miniFill, width: `${catPct}%`, background: color }} />
                  </div>
                  <span style={{ ...S.catPct, color }}>{catPct}%</span>
                </div>
                <span style={{ ...S.chevron, transform: isOpen ? "rotate(180deg)" : "rotate(0)" }}>▾</span>
              </div>

              {isOpen && (
                <div style={S.catBody}>
                  {cat.items.map(item => (
                    <div key={item.id} style={{ ...S.item, opacity: item.progress_status === "done" ? 0.7 : 1 }}
                      onClick={() => handleComplete(item)}>
                      <div style={{
                        ...S.checkbox,
                        background: item.progress_status === "done" ? color : "transparent",
                        borderColor: item.progress_status === "done" ? color : "#4a5568",
                      }}>
                        {item.progress_status === "done" && <span style={{ color: "#fff", fontSize: 12, fontWeight: 700 }}>✓</span>}
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{
                          ...S.itemTitle,
                          textDecoration: item.progress_status === "done" ? "line-through" : "none",
                        }}>{item.title}</div>
                        <div style={S.itemDesc}>{item.description}</div>
                      </div>
                      <div style={{ ...S.xpBadge, background: item.progress_status === "done" ? "rgba(62,207,142,0.15)" : "rgba(212,168,67,0.15)", color: item.progress_status === "done" ? "#3ecf8e" : "#d4a843" }}>
                        {item.progress_status === "done" ? "✓" : `+${item.xp_value}`} XP
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <button style={S.chatToggle} onClick={() => { setShowChat(!showChat); if (!showChat && chatMessages.length === 0) {
        setChatMessages([{ role: "assistant", content: `Hey ${employee.name.split(" ")[0]}! I'm your Spartan Academy coach. Ask me anything about your onboarding — what to do next, how something works, or if you're stuck on anything. I'm here to help!` }]);
      }}}>
        {showChat ? "✕" : "💬"}
      </button>

      {showChat && (
        <div style={S.chatPanel}>
          <div style={S.chatHead}>
            <span style={{ fontSize: 18 }}>⚔️</span>
            <div>
              <div style={{ fontWeight: 600, fontSize: 14 }}>Spartan Coach</div>
              <div style={{ fontSize: 11, color: "#9ca3b8" }}>AI onboarding assistant</div>
            </div>
          </div>
          <div style={S.chatMessages}>
            {chatMessages.map((m, i) => (
              <div key={i} style={{ ...S.chatBubble, ...(m.role === "user" ? S.chatUser : S.chatBot) }}>
                {m.content}
              </div>
            ))}
            {chatLoading && <div style={{ ...S.chatBubble, ...S.chatBot, opacity: 0.6 }}>Thinking...</div>}
            <div ref={chatEndRef} />
          </div>
          <div style={S.chatInputWrap}>
            <input
              value={chatInput} onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && sendChat()}
              placeholder="Ask your coach anything..."
              style={S.chatInputField}
            />
            <button onClick={sendChat} style={S.chatSendBtn} disabled={chatLoading}>→</button>
          </div>
        </div>
      )}
    </div>
  );
}

const S: Record<string, React.CSSProperties> = {
  wrap: { position: "relative", paddingBottom: 80 },
  loginWrap: { minHeight: "70vh", display: "flex", alignItems: "center", justifyContent: "center" },
  loginCard: { background: "#141820", border: "1px solid #2a3348", borderRadius: 16, padding: "48px 40px", textAlign: "center", maxWidth: 420, width: "100%" },
  loginLogo: { fontSize: 48, marginBottom: 12 },
  loginTitle: { fontSize: "1.75rem", fontWeight: 700, color: "#d4a843", marginBottom: 4 },
  loginSub: { color: "#9ca3b8", fontSize: 14, marginBottom: 32 },
  loginInput: { width: "100%", padding: "12px 16px", borderRadius: 10, border: "1px solid #2a3348", background: "#1a2030", color: "#e8eaf0", fontSize: 15, marginBottom: 16, outline: "none" },
  loginBtn: { width: "100%", padding: "12px 24px", borderRadius: 10, background: "#d4a843", color: "#0c0f13", fontWeight: 700, fontSize: 15, border: "none", cursor: "pointer" },
  loginHint: { fontSize: 12, color: "#636d83", marginTop: 16 },
  hero: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24, flexWrap: "wrap" as const, gap: 16 },
  heroLeft: {},
  heroRight: { display: "flex", gap: 24, alignItems: "center" },
  greeting: { fontSize: "1.5rem", fontWeight: 700, color: "#e8eaf0" },
  roleTag: { display: "inline-block", padding: "3px 12px", borderRadius: 20, background: "rgba(212,168,67,0.15)", color: "#d4a843", fontSize: 13, fontWeight: 500, marginTop: 4 },
  xpBox: { textAlign: "center" as const },
  xpNumber: { fontSize: "2rem", fontWeight: 700, color: "#d4a843", fontFamily: "'JetBrains Mono', monospace", lineHeight: 1 },
  xpLabel: { fontSize: 11, color: "#636d83", marginTop: 2 },
  levelBox: { textAlign: "center" as const, minWidth: 100 },
  levelName: { fontSize: 13, fontWeight: 600, color: "#e8eaf0", marginTop: 2 },
  levelBar: { width: 100, height: 6, borderRadius: 3, background: "#2a3348", marginTop: 4, overflow: "hidden" as const },
  levelFill: { height: "100%", borderRadius: 3, background: "#d4a843", transition: "width 1s ease" },
  levelNext: { fontSize: 10, color: "#636d83", marginTop: 2 },
  progressCard: { background: "#141820", border: "1px solid #2a3348", borderRadius: 14, padding: "20px 24px", display: "flex", alignItems: "center", gap: 20, marginBottom: 24, flexWrap: "wrap" as const },
  progressRing: { position: "relative" as const, width: 80, height: 80, flexShrink: 0 },
  progressPct: { position: "absolute" as const, inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 18, color: "#d4a843" },
  progressInfo: { flex: 1 },
  progressTitle: { fontSize: 16, fontWeight: 600, color: "#e8eaf0" },
  progressSub: { fontSize: 13, color: "#636d83", marginTop: 2 },
  badgeRow: { display: "flex", gap: 6 },
  badge: { width: 32, height: 32, borderRadius: 8, background: "rgba(212,168,67,0.1)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, cursor: "pointer" },
  catGrid: { display: "grid", gap: 10 },
  catCard: { background: "#141820", border: "1px solid #2a3348", borderRadius: 12, overflow: "hidden" as const, transition: "border-color 0.2s" },
  catHeader: { display: "flex", alignItems: "center", gap: 14, padding: "16px 20px", cursor: "pointer" },
  catIconWrap: { width: 40, height: 40, borderRadius: 10, background: "rgba(255,255,255,0.05)", display: "flex", alignItems: "center", justifyContent: "center" },
  catName: { fontWeight: 600, fontSize: 15, color: "#e8eaf0" },
  catCount: { fontSize: 12, color: "#636d83" },
  catPctWrap: { display: "flex", alignItems: "center", gap: 8 },
  miniBar: { width: 60, height: 4, borderRadius: 2, background: "#2a3348", overflow: "hidden" as const },
  miniFill: { height: "100%", borderRadius: 2, transition: "width 0.5s ease" },
  catPct: { fontSize: 13, fontWeight: 600, minWidth: 36, textAlign: "right" as const },
  chevron: { fontSize: 16, color: "#636d83", transition: "transform 0.2s" },
  catBody: { borderTop: "1px solid #1e2738", padding: "8px 12px" },
  item: { display: "flex", alignItems: "center", gap: 12, padding: "10px 8px", borderRadius: 8, cursor: "pointer", transition: "background 0.15s" },
  checkbox: { width: 22, height: 22, borderRadius: 6, border: "2px solid #4a5568", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "all 0.2s" },
  itemTitle: { fontSize: 14, fontWeight: 500, color: "#e8eaf0" },
  itemDesc: { fontSize: 12, color: "#636d83", marginTop: 1 },
  xpBadge: { padding: "2px 8px", borderRadius: 12, fontSize: 11, fontWeight: 600, whiteSpace: "nowrap" as const },
  chatToggle: { position: "fixed" as const, bottom: 24, right: 24, width: 56, height: 56, borderRadius: 28, background: "#d4a843", color: "#0c0f13", fontSize: 24, border: "none", cursor: "pointer", boxShadow: "0 4px 20px rgba(0,0,0,0.4)", zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700 },
  chatPanel: { position: "fixed" as const, bottom: 92, right: 24, width: 360, height: 480, background: "#141820", border: "1px solid #2a3348", borderRadius: 16, display: "flex", flexDirection: "column" as const, zIndex: 200, boxShadow: "0 8px 40px rgba(0,0,0,0.5)", overflow: "hidden" as const },
  chatHead: { display: "flex", alignItems: "center", gap: 10, padding: "14px 16px", borderBottom: "1px solid #2a3348", background: "#1a2030" },
  chatMessages: { flex: 1, overflowY: "auto" as const, padding: "12px 14px", display: "flex", flexDirection: "column" as const, gap: 8 },
  chatBubble: { padding: "10px 14px", borderRadius: 14, fontSize: 13, lineHeight: 1.5, maxWidth: "85%" },
  chatUser: { background: "#d4a843", color: "#0c0f13", alignSelf: "flex-end" as const, borderBottomRightRadius: 4 },
  chatBot: { background: "#1e2738", color: "#e8eaf0", alignSelf: "flex-start" as const, borderBottomLeftRadius: 4 },
  chatInputWrap: { display: "flex", gap: 8, padding: "12px 14px", borderTop: "1px solid #2a3348" },
  chatInputField: { flex: 1, padding: "10px 14px", borderRadius: 10, border: "1px solid #2a3348", background: "#1a2030", color: "#e8eaf0", fontSize: 13, outline: "none" },
  chatSendBtn: { width: 40, height: 40, borderRadius: 10, background: "#d4a843", color: "#0c0f13", border: "none", cursor: "pointer", fontSize: 18, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center" },
  toast: { position: "fixed" as const, top: 80, left: "50%", transform: "translateX(-50%)", background: "#d4a843", color: "#0c0f13", padding: "10px 24px", borderRadius: 12, fontWeight: 700, fontSize: 15, zIndex: 300, boxShadow: "0 4px 20px rgba(212,168,67,0.4)", animation: "fadeIn 0.3s ease" },
};
