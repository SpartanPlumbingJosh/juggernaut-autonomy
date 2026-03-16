"use client";
import { useState, useEffect, useRef, useCallback } from "react";

const LEVELS = [
  { min: 0, name: "Recruit", icon: "🔰", color: "#64748b" },
  { min: 100, name: "Trainee", icon: "📘", color: "#3b82f6" },
  { min: 250, name: "Apprentice", icon: "🔧", color: "#8b5cf6" },
  { min: 450, name: "Journeyman", icon: "⚡", color: "#f59e0b" },
  { min: 700, name: "Spartan", icon: "🏆", color: "#c8a84e" },
];
const CAT_META: Record<string, { icon: string; color: string; bg: string }> = {
  "Pre-employment": { icon: "📋", color: "#60a5fa", bg: "rgba(96,165,250,0.08)" },
  Documents: { icon: "📄", color: "#a78bfa", bg: "rgba(167,139,250,0.08)" },
  Accounts: { icon: "🔑", color: "#22d3ee", bg: "rgba(34,211,238,0.08)" },
  Profile: { icon: "👤", color: "#fbbf24", bg: "rgba(251,191,36,0.08)" },
  Equipment: { icon: "🖥️", color: "#818cf8", bg: "rgba(129,140,248,0.08)" },
  Training: { icon: "📚", color: "#34d399", bg: "rgba(52,211,153,0.08)" },
  "Field setup": { icon: "🛠️", color: "#f87171", bg: "rgba(248,113,113,0.08)" },
  Uniforms: { icon: "👕", color: "#f472b6", bg: "rgba(244,114,182,0.08)" },
  Vehicle: { icon: "🚐", color: "#fb923c", bg: "rgba(251,146,60,0.08)" },
  Shadowing: { icon: "👥", color: "#2dd4bf", bg: "rgba(45,212,191,0.08)" },
  "Final checks": { icon: "✅", color: "#4ade80", bg: "rgba(74,222,128,0.08)" },
};
interface Item { id: string; title: string; description: string; xp_value: number; category: string; requires_value: boolean; value_label: string; progress_status: string; progress_value: string; completed_at: string }
interface Category { items: Item[]; done: number; total: number }
interface Stats { totalXp: number; earnedXp: number; level: number; levelName: string; totalItems: number; completedItems: number }
interface Achievement { badge_code: string; badge_name: string; badge_description: string; earned_at: string }
interface Employee { id: string; name: string; role: string; position: string; email: string }
interface ChatMsg { role: string; content: string }

const CSS = `@import url('https://fonts.googleapis.com/css2?family=Archivo+Black&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
.sa{font-family:'Plus Jakarta Sans',sans-serif;position:relative;padding-bottom:100px}
.sa h2,.sa h3{font-family:'Archivo Black',sans-serif;letter-spacing:.5px}
.sa-toast{position:fixed;top:76px;left:50%;transform:translateX(-50%);background:linear-gradient(135deg,#c8a84e,#a08530);color:#0a0e17;padding:10px 28px;border-radius:40px;font-weight:700;font-size:14px;z-index:400;box-shadow:0 4px 20px rgba(200,168,78,0.4);animation:sa-pop .3s ease}
@keyframes sa-pop{from{opacity:0;transform:translateX(-50%) translateY(-10px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}
.sa-login{min-height:80vh;display:flex;align-items:center;justify-content:center;font-family:'Plus Jakarta Sans',sans-serif}
.sa-login-card{width:100%;max-width:400px;text-align:center}
.sa-shield{width:80px;height:92px;margin:0 auto 20px;background:linear-gradient(135deg,#c8a84e 0%,#8b6914 100%);clip-path:polygon(50% 0%,100% 25%,100% 75%,50% 100%,0% 75%,0% 25%);display:flex;align-items:center;justify-content:center}
.sa-shield-inner{width:68px;height:78px;background:#0a0e17;clip-path:polygon(50% 0%,100% 25%,100% 75%,50% 100%,0% 75%,0% 25%);display:flex;align-items:center;justify-content:center;font-size:28px}
.sa-login h1{font-family:'Archivo Black',sans-serif;font-size:2rem;color:#c8a84e;letter-spacing:1px;margin:0 0 6px}
.sa-login p.sub{color:#7a8599;font-size:14px;margin:0 0 32px}
.sa-field{width:100%;padding:14px 16px;border:1px solid #1e2a3a;border-radius:10px;background:#0d1320;color:#e2e8f0;font-size:15px;font-family:inherit;outline:none;margin-bottom:12px;transition:border-color .2s}
.sa-field:focus{border-color:#c8a84e}
.sa-field::placeholder{color:#4a5568}
.sa-btn{width:100%;padding:14px;border:none;border-radius:10px;background:linear-gradient(135deg,#c8a84e,#a08530);color:#0a0e17;font-weight:700;font-size:15px;font-family:inherit;cursor:pointer;letter-spacing:.5px;transition:transform .15s,box-shadow .15s}
.sa-btn:hover{transform:translateY(-2px);box-shadow:0 6px 24px rgba(200,168,78,0.3)}
.sa-btn:disabled{opacity:.6;cursor:not-allowed;transform:none}
.sa-error{color:#f87171;font-size:13px;margin:8px 0 0;min-height:20px}
.sa-hint{color:#4a5568;font-size:12px;margin-top:24px}
.sa-hero{display:flex;align-items:center;justify-content:space-between;padding:24px 28px;background:linear-gradient(135deg,#0d1320 0%,#131b2e 100%);border:1px solid #1a2540;border-radius:16px;margin-bottom:20px;flex-wrap:wrap;gap:20px}
.sa-hero h2{font-size:1.4rem;color:#e2e8f0;margin:0 0 2px}
.sa-role{display:inline-block;padding:3px 14px;border-radius:20px;background:rgba(200,168,78,0.12);color:#c8a84e;font-size:12px;font-weight:600;letter-spacing:.5px;text-transform:uppercase}
.sa-hero-right{display:flex;align-items:center;gap:24px}
.sa-lvl{width:72px;height:72px;border-radius:50%;display:flex;align-items:center;justify-content:center;position:relative}
.sa-lvl-inner{width:60px;height:60px;border-radius:50%;background:#0d1320;display:flex;flex-direction:column;align-items:center;justify-content:center}
.sa-lvl-inner span{font-size:24px;line-height:1}
.sa-lvl-inner small{font-size:9px;font-weight:700;color:#c8a84e;letter-spacing:.5px;margin-top:2px}
.sa-xp{text-align:right}
.sa-xp-num{font-family:'Archivo Black',sans-serif;font-size:1.8rem;color:#c8a84e;line-height:1}
.sa-xp-label{font-size:11px;color:#4a5568;margin-top:1px}
.sa-xp-bar{width:140px;height:6px;border-radius:3px;background:#1a2540;overflow:hidden;margin-top:6px}
.sa-xp-fill{height:100%;border-radius:3px;background:linear-gradient(90deg,#c8a84e,#e8d48a);transition:width .8s ease}
.sa-xp-next{font-size:10px;color:#4a5568;margin-top:2px;text-align:right}
.sa-overall{display:flex;align-items:center;gap:16px;background:#0d1320;border:1px solid #1a2540;border-radius:14px;padding:16px 20px;margin-bottom:20px}
.sa-ring{position:relative;flex-shrink:0}.sa-ring svg{display:block}
.sa-ring-pct{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-family:'Archivo Black',sans-serif;font-size:14px;color:#c8a84e}
.sa-overall-title{font-size:14px;font-weight:600;color:#e2e8f0}
.sa-overall-sub{font-size:12px;color:#4a5568;margin-top:1px}
.sa-badges{display:flex;gap:8px;flex-wrap:wrap}
.sa-badge{width:40px;height:40px;border-radius:10px;background:rgba(200,168,78,0.08);border:1px solid #1a2540;display:flex;align-items:center;justify-content:center;font-size:18px}
.sa-label{font-family:'Archivo Black',sans-serif;font-size:11px;color:#4a5568;letter-spacing:2px;text-transform:uppercase;margin:28px 0 12px;padding-left:4px}
.sa-missions{background:#0d1320;border:1px solid #1a2540;border-radius:14px;padding:16px 20px;margin-bottom:20px}
.sa-missions h3{font-size:13px;color:#c8a84e;margin:0 0 12px;letter-spacing:1px}
.sa-mi{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #111827;cursor:pointer}
.sa-mi:last-child{border:none}
.sa-mi-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.sa-mi-text{flex:1;font-size:13px;color:#cbd5e1}
.sa-mi-cat{font-size:11px;color:#4a5568}
.sa-mi-xp{font-size:12px;font-weight:700;color:#c8a84e}
.sa-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:640px){.sa-grid{grid-template-columns:1fr}}
.sa-cat{background:#0d1320;border:1px solid #1a2540;border-radius:12px;overflow:hidden;transition:border-color .2s;cursor:pointer}
.sa-cat:hover{border-color:#2a3a54}
.sa-cat.open{grid-column:1/-1}
.sa-ch{display:flex;align-items:center;gap:12px;padding:14px 16px}
.sa-ci{width:36px;height:36px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0}
.sa-cn{font-size:14px;font-weight:600;color:#e2e8f0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sa-cc{font-size:11px;color:#4a5568}
.sa-cr{width:36px;height:36px;position:relative;flex-shrink:0}
.sa-cr svg{width:36px;height:36px;display:block}
.sa-cr-p{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700}
.sa-cb{border-top:1px solid #111827;padding:6px 10px 10px}
.sa-t{display:flex;align-items:center;gap:10px;padding:8px 6px;border-radius:8px;cursor:pointer;transition:background .1s}
.sa-t:hover{background:rgba(255,255,255,0.02)}
.sa-ck{width:20px;height:20px;border-radius:5px;border:2px solid #2a3a54;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:all .15s;font-size:11px;color:#fff;font-weight:700}
.sa-ck.done{border-color:var(--c);background:var(--c)}
.sa-tt{font-size:13px;color:#cbd5e1;flex:1}.sa-tt.done{text-decoration:line-through;opacity:.5}
.sa-txp{font-size:10px;font-weight:700;padding:2px 8px;border-radius:10px;white-space:nowrap}
.sa-fab{position:fixed;bottom:24px;right:24px;width:56px;height:56px;border-radius:16px;background:linear-gradient(135deg,#c8a84e,#a08530);color:#0a0e17;font-size:22px;border:none;cursor:pointer;box-shadow:0 4px 24px rgba(200,168,78,0.35);z-index:300;display:flex;align-items:center;justify-content:center;font-weight:700;transition:transform .15s}
.sa-fab:hover{transform:scale(1.08)}
.sa-chat{position:fixed;bottom:92px;right:24px;width:370px;max-height:500px;background:#0d1320;border:1px solid #1a2540;border-radius:16px;z-index:300;display:flex;flex-direction:column;box-shadow:0 12px 48px rgba(0,0,0,0.6);overflow:hidden}
@media(max-width:480px){.sa-chat{right:8px;left:8px;width:auto;bottom:88px}}
.sa-chat-h{padding:14px 16px;border-bottom:1px solid #1a2540;display:flex;align-items:center;gap:10px;background:#0a0e17}
.sa-chat-h b{font-size:14px;color:#e2e8f0}
.sa-chat-h small{font-size:11px;color:#4a5568;display:block}
.sa-chat-b{flex:1;overflow-y:auto;padding:12px 14px;display:flex;flex-direction:column;gap:8px;min-height:200px;max-height:320px}
.sa-m{padding:10px 14px;border-radius:14px;font-size:13px;line-height:1.55;max-width:88%;word-wrap:break-word}
.sa-m.u{background:linear-gradient(135deg,#c8a84e,#a08530);color:#0a0e17;align-self:flex-end;border-bottom-right-radius:4px}
.sa-m.b{background:#131b2e;color:#cbd5e1;align-self:flex-start;border-bottom-left-radius:4px}
.sa-chat-f{display:flex;gap:8px;padding:12px 14px;border-top:1px solid #1a2540}
.sa-chat-i{flex:1;padding:10px 14px;border-radius:10px;border:1px solid #1a2540;background:#0a0e17;color:#e2e8f0;font-size:13px;font-family:inherit;outline:none}
.sa-chat-i:focus{border-color:#c8a84e}
.sa-chat-s{width:40px;height:40px;border-radius:10px;background:linear-gradient(135deg,#c8a84e,#a08530);color:#0a0e17;border:none;cursor:pointer;font-size:16px;font-weight:700;display:flex;align-items:center;justify-content:center}
.sa-chat-s:disabled{opacity:.5}
.sa-out{font-size:12px;color:#4a5568;background:none;border:1px solid #1a2540;border-radius:8px;padding:4px 12px;cursor:pointer;font-family:inherit;transition:all .15s}
.sa-out:hover{border-color:#f87171;color:#f87171}`;

export function OnboardingApp() {
  const [email, setEmail] = useState("");
  const [pin, setPin] = useState("");
  const [loginError, setLoginError] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
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
  const chatEndRef = useRef<HTMLDivElement>(null);

  const loadData = useCallback(async (em: string) => {
    const res = await fetch(`/api/onboard?email=${encodeURIComponent(em)}`);
    const data = await res.json();
    if (data?.employee) { setEmployee(data.employee); setCategories(data.categories); setStats(data.stats); setAchievements(data.achievements || []); setLoggedIn(true); }
  }, []);

  useEffect(() => { const s = typeof window !== "undefined" ? sessionStorage.getItem("sa_email") : null; if (s) { setEmail(s); loadData(s); } }, [loadData]);
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [chatMessages]);

  async function handleLogin() {
    if (!email || !pin) { setLoginError("Enter both email and PIN"); return; }
    setLoginLoading(true); setLoginError("");
    try {
      const res = await fetch("/api/onboard/auth", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, pin }) });
      if (res.ok) { sessionStorage.setItem("sa_email", email); await loadData(email); } else { const d = await res.json(); setLoginError(d.error || "Login failed"); }
    } catch { setLoginError("Connection error"); }
    setLoginLoading(false);
  }

  async function handleComplete(item: Item) {
    if (!employee) return;
    const ns = item.progress_status === "done" ? "pending" : "done";
    const res = await fetch("/api/onboard/progress", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ employee_id: employee.id, template_id: item.id, status: ns }) });
    const data = await res.json();
    if (data.ok) { if (ns === "done") notify(`+${item.xp_value} XP earned`); if (data.newBadges?.length) data.newBadges.forEach((b:{name:string}) => notify(`🏅 ${b.name} unlocked!`)); await loadData(email); }
  }

  async function sendChat() {
    if (!chatInput.trim() || !employee || chatLoading) return;
    const msg = chatInput.trim(); setChatInput("");
    setChatMessages(p => [...p, { role: "user", content: msg }]); setChatLoading(true);
    try { const res = await fetch("/api/onboard/coach", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ employee_id: employee.id, message: msg }) }); const data = await res.json(); setChatMessages(p => [...p, { role: "assistant", content: data.reply || "Try again." }]); } catch { setChatMessages(p => [...p, { role: "assistant", content: "Connection issue." }]); }
    setChatLoading(false);
  }

  function notify(msg: string) { setToast(msg); setTimeout(() => setToast(null), 2500); }
  function getLevel(xp: number) { for (let i = LEVELS.length - 1; i >= 0; i--) { if (xp >= LEVELS[i].min) return { ...LEVELS[i], idx: i }; } return { ...LEVELS[0], idx: 0 }; }

  if (!loggedIn) return (<><style>{CSS}</style><div className="sa-login"><div className="sa-login-card"><div className="sa-shield"><div className="sa-shield-inner">⚔️</div></div><h1>SPARTAN ACADEMY</h1><p className="sub">Enter your credentials to begin</p><input className="sa-field" type="email" placeholder="work email" value={email} onChange={e=>setEmail(e.target.value)} onKeyDown={e=>e.key==="Enter"&&document.getElementById("pin-input")?.focus()}/><input className="sa-field" id="pin-input" type="password" placeholder="6-digit PIN" maxLength={6} value={pin} onChange={e=>setPin(e.target.value.replace(/\D/g,""))} onKeyDown={e=>e.key==="Enter"&&handleLogin()}/><button className="sa-btn" onClick={handleLogin} disabled={loginLoading}>{loginLoading?"Verifying...":"Enter the Academy"}</button><div className="sa-error">{loginError}</div><p className="sa-hint">PIN provided by your manager on day one</p></div></div></>);

  if (!employee || !stats) return <div style={{padding:60,textAlign:"center",color:"#4a5568"}}>Loading your mission data...</div>;

  const cur = getLevel(stats.earnedXp);
  const next = cur.idx < LEVELS.length - 1 ? LEVELS[cur.idx + 1] : null;
  const pct = stats.totalItems > 0 ? Math.round(100 * stats.completedItems / stats.totalItems) : 0;
  const xpPct = next ? Math.min(100, Math.round(100 * (stats.earnedXp - cur.min) / (next.min - cur.min))) : 100;
  const pending = Object.values(categories).flatMap(c => c.items).filter(i => i.progress_status !== "done");
  const nextMissions = pending.slice(0, 3);
  const roleName = employee.role === "tech" ? "Service Technician" : employee.role === "office" ? "Office Staff" : "Apprentice";

  return (<><style>{CSS}</style><div className="sa">
    {toast && <div className="sa-toast">{toast}</div>}

    <div className="sa-hero">
      <div><h2>Welcome, {employee.name.split(" ")[0]}</h2><span className="sa-role">{roleName} Track</span></div>
      <div className="sa-hero-right">
        <div className="sa-lvl" style={{background:`conic-gradient(${cur.color} ${xpPct*3.6}deg,#1a2540 0)`}}><div className="sa-lvl-inner"><span>{cur.icon}</span><small>{cur.name.toUpperCase()}</small></div></div>
        <div className="sa-xp"><div className="sa-xp-num">{stats.earnedXp}</div><div className="sa-xp-label">XP earned</div><div className="sa-xp-bar"><div className="sa-xp-fill" style={{width:`${xpPct}%`}}/></div>{next&&<div className="sa-xp-next">{next.min-stats.earnedXp} to {next.name}</div>}</div>
        <button className="sa-out" onClick={()=>{sessionStorage.removeItem("sa_email");setLoggedIn(false);setEmployee(null);}}>Sign out</button>
      </div>
    </div>

    <div className="sa-overall">
      <div className="sa-ring" style={{width:56,height:56}}><svg viewBox="0 0 56 56" width="56" height="56"><circle cx="28" cy="28" r="22" fill="none" stroke="#1a2540" strokeWidth="5"/><circle cx="28" cy="28" r="22" fill="none" stroke="#c8a84e" strokeWidth="5" strokeDasharray={`${2*Math.PI*22}`} strokeDashoffset={`${2*Math.PI*22*(1-pct/100)}`} strokeLinecap="round" transform="rotate(-90 28 28)" style={{transition:"stroke-dashoffset 1s ease"}}/></svg><div className="sa-ring-pct">{pct}%</div></div>
      <div style={{flex:1}}><div className="sa-overall-title">{stats.completedItems} of {stats.totalItems} tasks complete</div><div className="sa-overall-sub">{stats.totalXp-stats.earnedXp} XP left to collect</div></div>
      {achievements.length>0&&<div className="sa-badges">{achievements.map(a=><div key={a.badge_code} className="sa-badge" title={a.badge_description}>🏅</div>)}</div>}
    </div>

    {nextMissions.length>0&&<div className="sa-missions"><h3>NEXT UP</h3>{nextMissions.map(m=>{const mt=CAT_META[m.category]||{icon:"📦",color:"#c8a84e"};return(<div key={m.id} className="sa-mi" onClick={()=>setExpandedCat(m.category)}><div className="sa-mi-dot" style={{background:mt.color}}/><div className="sa-mi-text">{m.title}</div><div className="sa-mi-cat">{m.category}</div><div className="sa-mi-xp">+{m.xp_value}</div></div>);})}</div>}

    <div className="sa-label">YOUR MISSIONS</div>
    <div className="sa-grid">
      {Object.entries(categories).map(([cn,cat])=>{const o=expandedCat===cn;const mt=CAT_META[cn]||{icon:"📦",color:"#c8a84e",bg:"rgba(200,168,78,0.08)"};const cp=cat.total>0?Math.round(100*cat.done/cat.total):0;const r=14;const ci=2*Math.PI*r;return(
        <div key={cn} className={`sa-cat${o?" open":""}`} style={{borderColor:o?mt.color:undefined}}>
          <div className="sa-ch" onClick={()=>setExpandedCat(o?null:cn)}>
            <div className="sa-ci" style={{background:mt.bg}}>{mt.icon}</div>
            <div style={{flex:1,minWidth:0}}><div className="sa-cn">{cn}</div><div className="sa-cc">{cat.done}/{cat.total}</div></div>
            <div className="sa-cr"><svg viewBox="0 0 36 36"><circle cx="18" cy="18" r={r} fill="none" stroke="#1a2540" strokeWidth="3"/><circle cx="18" cy="18" r={r} fill="none" stroke={mt.color} strokeWidth="3" strokeDasharray={`${ci}`} strokeDashoffset={`${ci*(1-cp/100)}`} strokeLinecap="round" transform="rotate(-90 18 18)" style={{transition:"stroke-dashoffset .5s ease"}}/></svg><div className="sa-cr-p" style={{color:mt.color}}>{cp}%</div></div>
          </div>
          {o&&<div className="sa-cb">{cat.items.map(it=>(
            <div key={it.id} className="sa-t" onClick={()=>handleComplete(it)} style={{opacity:it.progress_status==="done"?.65:1}}>
              <div className={`sa-ck${it.progress_status==="done"?" done":""}`} style={{"--c":mt.color} as React.CSSProperties}>{it.progress_status==="done"?"✓":""}</div>
              <div className={`sa-tt${it.progress_status==="done"?" done":""}`}>{it.title}</div>
              <div className="sa-txp" style={{background:it.progress_status==="done"?"rgba(74,222,128,0.1)":mt.bg,color:it.progress_status==="done"?"#4ade80":mt.color}}>{it.progress_status==="done"?"✓":`+${it.xp_value}`} XP</div>
            </div>
          ))}</div>}
        </div>
      );})}
    </div>

    <button className="sa-fab" onClick={()=>{setShowChat(!showChat);if(!showChat&&!chatMessages.length)setChatMessages([{role:"assistant",content:`Hey ${employee.name.split(" ")[0]}! I'm your Spartan coach. What do you need help with?`}]);}}>{showChat?"✕":"💬"}</button>

    {showChat&&<div className="sa-chat">
      <div className="sa-chat-h"><span style={{fontSize:18}}>⚔️</span><div><b>Spartan Coach</b><small>AI assistant</small></div></div>
      <div className="sa-chat-b">{chatMessages.map((m,i)=><div key={i} className={`sa-m ${m.role==="user"?"u":"b"}`}>{m.content}</div>)}{chatLoading&&<div className="sa-m b" style={{opacity:.6}}>Thinking...</div>}<div ref={chatEndRef}/></div>
      <div className="sa-chat-f"><input className="sa-chat-i" value={chatInput} onChange={e=>setChatInput(e.target.value)} onKeyDown={e=>e.key==="Enter"&&sendChat()} placeholder="Ask anything..."/><button className="sa-chat-s" onClick={sendChat} disabled={chatLoading}>→</button></div>
    </div>}
  </div></>);
}
