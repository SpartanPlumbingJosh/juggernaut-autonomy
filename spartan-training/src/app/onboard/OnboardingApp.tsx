"use client";
import { useState, useEffect, useRef, useCallback } from "react";

const MASCOT = "https://spartan-plumbing.com/wp-content/uploads/spartan-mascot-shield.svg";
const LOGO_NAV = "https://spartan-plumbing.com/wp-content/uploads/spartan-logo-nav.svg";
const MASCOT_R = "https://spartan-plumbing.com/wp-content/uploads/spartan-mascot-right.svg";
const MASCOT_L = "https://spartan-plumbing.com/wp-content/uploads/spartan-mascot-left.svg";

const LEVELS = [
  { min: 0, name: "Recruit", rank: "I", color: "#888" },
  { min: 100, name: "Trainee", rank: "II", color: "#c8a84e" },
  { min: 250, name: "Apprentice", rank: "III", color: "#c8a84e" },
  { min: 450, name: "Journeyman", rank: "IV", color: "#c8a84e" },
  { min: 700, name: "Spartan", rank: "V", color: "#c8a84e" },
];

const CAT_COLORS: Record<string,string> = {
  "Pre-employment":"#c8a84e",Documents:"#c8a84e",Accounts:"#c8a84e",Profile:"#c8a84e",
  Equipment:"#b91c1c",Training:"#b91c1c","Field setup":"#b91c1c",Uniforms:"#b91c1c",
  Vehicle:"#b91c1c",Shadowing:"#c8a84e","Final checks":"#c8a84e",
};

interface Item { id: string; title: string; description: string; xp_value: number; category: string; requires_value: boolean; value_label: string; progress_status: string; progress_value: string; completed_at: string }
interface Category { items: Item[]; done: number; total: number }
interface Stats { totalXp: number; earnedXp: number; level: number; levelName: string; totalItems: number; completedItems: number }
interface Achievement { badge_code: string; badge_name: string; badge_description: string; earned_at: string }
interface Employee { id: string; name: string; role: string; position: string; email: string }
interface ChatMsg { role: string; content: string }

const CSS = `@import url('https://fonts.googleapis.com/css2?family=Archivo+Black&family=Barlow+Condensed:wght@400;500;600;700&family=Barlow:wght@400;500;600&display=swap');
:root{--black:#0a0a0a;--card:#111;--border:#222;--border2:#333;--gold:#c8a84e;--red:#b91c1c;--red2:#8b1a1a;--text:#e8e8e8;--text2:#888;--text3:#555}
.sa{font-family:'Barlow',sans-serif;color:var(--text);position:relative;padding-bottom:100px}
.sa h2,.sa h3,.sa-rank-text{font-family:'Archivo Black',sans-serif}

/* ANIMATIONS */
@keyframes sa-in{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
@keyframes sa-toast-in{from{opacity:0;transform:translateX(-50%) translateY(-12px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}
@keyframes sa-pulse{0%,100%{box-shadow:0 0 0 0 rgba(200,168,78,0.4)}50%{box-shadow:0 0 0 8px rgba(200,168,78,0)}}
.sa-anim{animation:sa-in .5s ease both}
.sa-anim-1{animation-delay:.05s}.sa-anim-2{animation-delay:.1s}.sa-anim-3{animation-delay:.15s}.sa-anim-4{animation-delay:.2s}

/* TOAST */
.sa-toast{position:fixed;top:76px;left:50%;transform:translateX(-50%);background:var(--gold);color:var(--black);padding:10px 28px;border-radius:40px;font-weight:700;font-size:14px;z-index:400;box-shadow:0 4px 24px rgba(200,168,78,0.5);animation:sa-toast-in .3s ease;font-family:'Archivo Black',sans-serif;letter-spacing:.5px}

/* LOGIN */
.sa-login{min-height:80vh;display:flex;align-items:center;justify-content:center}
.sa-login-card{width:100%;max-width:420px;text-align:center;background:var(--card);border:1px solid var(--border);border-radius:20px;padding:48px 40px;position:relative;overflow:hidden}
.sa-login-card::before{content:'';position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,var(--red),var(--gold),var(--red))}
.sa-login-mascot{width:100px;height:100px;margin:0 auto 20px;object-fit:contain;filter:drop-shadow(0 4px 12px rgba(200,168,78,0.3))}
.sa-login h1{font-family:'Archivo Black',sans-serif;font-size:1.8rem;color:var(--gold);letter-spacing:2px;margin:0 0 4px}
.sa-login .sub{color:var(--text2);font-size:14px;margin:0 0 28px}
.sa-field{width:100%;padding:14px 16px;border:1px solid var(--border2);border-radius:8px;background:var(--black);color:var(--text);font-size:15px;font-family:inherit;outline:none;margin-bottom:12px;transition:border-color .2s;box-sizing:border-box}
.sa-field:focus{border-color:var(--gold)}
.sa-field::placeholder{color:var(--text3)}
.sa-btn{width:100%;padding:14px;border:none;border-radius:8px;background:var(--red);color:#fff;font-weight:700;font-size:15px;font-family:'Barlow Condensed',sans-serif;cursor:pointer;letter-spacing:1px;text-transform:uppercase;transition:all .15s}
.sa-btn:hover{background:#d32f2f;transform:translateY(-1px);box-shadow:0 4px 16px rgba(185,28,28,0.4)}
.sa-btn:disabled{opacity:.6;cursor:not-allowed;transform:none}
.sa-error{color:#f87171;font-size:13px;margin:8px 0 0;min-height:20px}
.sa-hint{color:var(--text3);font-size:12px;margin-top:20px}

/* HERO */
.sa-hero{position:relative;display:flex;align-items:center;justify-content:space-between;padding:28px 32px;background:var(--card);border:1px solid var(--border);border-radius:16px;margin-bottom:16px;overflow:hidden;flex-wrap:wrap;gap:16px;animation:sa-in .5s ease both}
.sa-hero::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--red),var(--gold))}
.sa-hero-mascot{position:absolute;right:-10px;top:50%;transform:translateY(-50%);width:140px;height:140px;opacity:.08;pointer-events:none}
.sa-hero h2{font-size:1.6rem;color:var(--text);margin:0 0 6px;letter-spacing:.5px}
.sa-role{display:inline-block;padding:4px 16px;border-radius:4px;background:var(--red);color:#fff;font-size:11px;font-weight:700;font-family:'Barlow Condensed',sans-serif;letter-spacing:1.5px;text-transform:uppercase}
.sa-hero-stats{display:flex;align-items:center;gap:20px;position:relative;z-index:1}
.sa-rank{text-align:center;min-width:64px}
.sa-rank-text{font-size:2.2rem;color:var(--gold);line-height:1}
.sa-rank-name{font-size:10px;color:var(--text2);text-transform:uppercase;letter-spacing:1px;margin-top:2px;font-weight:600}
.sa-xp-block{text-align:right}
.sa-xp-num{font-family:'Archivo Black',sans-serif;font-size:2rem;color:var(--gold);line-height:1}
.sa-xp-lbl{font-size:11px;color:var(--text3);margin-top:1px}
.sa-xp-bar{width:120px;height:4px;border-radius:2px;background:var(--border2);overflow:hidden;margin-top:6px}
.sa-xp-fill{height:100%;border-radius:2px;background:var(--gold);transition:width .8s ease}
.sa-xp-nxt{font-size:10px;color:var(--text3);margin-top:3px;text-align:right}
.sa-out{font-size:11px;color:var(--text3);background:none;border:1px solid var(--border2);border-radius:6px;padding:5px 14px;cursor:pointer;font-family:inherit;transition:all .15s;font-weight:500}
.sa-out:hover{border-color:var(--red);color:var(--red)}

/* PROGRESS BAR */
.sa-progress{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px 24px;margin-bottom:16px;animation:sa-in .5s ease both;animation-delay:.05s}
.sa-progress-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.sa-progress-title{font-family:'Barlow Condensed',sans-serif;font-size:15px;font-weight:600;color:var(--text);text-transform:uppercase;letter-spacing:1px}
.sa-progress-pct{font-family:'Archivo Black',sans-serif;font-size:18px;color:var(--gold)}
.sa-progress-bar{width:100%;height:8px;border-radius:4px;background:var(--border2);overflow:hidden}
.sa-progress-fill{height:100%;border-radius:4px;background:linear-gradient(90deg,var(--red),var(--gold));transition:width 1s ease}
.sa-progress-sub{font-size:12px;color:var(--text3);margin-top:6px}

/* NEXT UP */
.sa-next{background:var(--card);border:1px solid var(--border);border-left:4px solid var(--red);border-radius:12px;padding:16px 20px;margin-bottom:16px;animation:sa-in .5s ease both;animation-delay:.1s}
.sa-next h3{font-size:14px;color:var(--red);margin:0 0 10px;letter-spacing:1px;text-transform:uppercase}
.sa-ni{display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--border);cursor:pointer;transition:padding-left .15s}
.sa-ni:hover{padding-left:4px}
.sa-ni:last-child{border:none}
.sa-ni-bar{width:3px;height:24px;border-radius:2px;flex-shrink:0}
.sa-ni-text{flex:1;font-size:14px;color:var(--text);font-weight:500}
.sa-ni-cat{font-size:11px;color:var(--text3);font-weight:500}
.sa-ni-xp{font-family:'Barlow Condensed',sans-serif;font-size:14px;font-weight:700;color:var(--gold)}

/* SECTION LABEL */
.sa-section{font-family:'Archivo Black',sans-serif;font-size:12px;color:var(--text3);letter-spacing:3px;text-transform:uppercase;margin:28px 0 14px;padding-left:2px}

/* CATEGORY GRID */
.sa-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:640px){.sa-grid{grid-template-columns:1fr}}
.sa-cat{background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden;transition:all .2s;cursor:pointer;animation:sa-in .4s ease both}
.sa-cat:nth-child(1){animation-delay:.15s}.sa-cat:nth-child(2){animation-delay:.18s}.sa-cat:nth-child(3){animation-delay:.21s}.sa-cat:nth-child(4){animation-delay:.24s}.sa-cat:nth-child(5){animation-delay:.27s}.sa-cat:nth-child(6){animation-delay:.3s}
.sa-cat:hover{border-color:var(--border2)}
.sa-cat.open{grid-column:1/-1}
.sa-ch{display:flex;align-items:center;gap:14px;padding:16px 18px}
.sa-ch-bar{width:4px;align-self:stretch;border-radius:2px;flex-shrink:0}
.sa-ch-info{flex:1;min-width:0}
.sa-ch-name{font-family:'Barlow Condensed',sans-serif;font-size:16px;font-weight:600;color:var(--text);text-transform:uppercase;letter-spacing:.5px}
.sa-ch-count{font-size:12px;color:var(--text3);margin-top:1px}
.sa-ch-pct{font-family:'Archivo Black',sans-serif;font-size:14px;min-width:40px;text-align:right}

/* TASK LIST */
.sa-tasks{border-top:1px solid var(--border);padding:8px 14px 14px}
.sa-task{display:flex;align-items:center;gap:10px;padding:9px 4px;border-radius:6px;cursor:pointer;transition:background .1s}
.sa-task:hover{background:rgba(255,255,255,0.03)}
.sa-ck{width:18px;height:18px;border-radius:4px;border:2px solid var(--border2);display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:all .15s;font-size:10px;color:#fff;font-weight:700}
.sa-ck.done{border-color:var(--c);background:var(--c)}
.sa-task-name{font-size:13px;color:var(--text);flex:1;font-weight:500}.sa-task-name.done{text-decoration:line-through;color:var(--text3)}
.sa-task-xp{font-family:'Barlow Condensed',sans-serif;font-size:12px;font-weight:700;color:var(--gold)}
.sa-task-xp.done{color:var(--text3)}

/* BADGES */
.sa-badges{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
.sa-badge{width:36px;height:36px;border-radius:6px;background:rgba(200,168,78,0.1);border:1px solid rgba(200,168,78,0.2);display:flex;align-items:center;justify-content:center}
.sa-badge img{width:22px;height:22px}

/* FAB */
.sa-fab{position:fixed;bottom:24px;right:24px;width:60px;height:60px;border-radius:50%;background:var(--red);border:3px solid var(--gold);cursor:pointer;box-shadow:0 4px 24px rgba(185,28,28,0.4);z-index:300;display:flex;align-items:center;justify-content:center;transition:transform .15s;overflow:hidden;animation:sa-pulse 2s infinite}
.sa-fab:hover{transform:scale(1.1)}
.sa-fab img{width:36px;height:36px;object-fit:contain}
.sa-fab-x{font-family:'Archivo Black',sans-serif;font-size:20px;color:#fff}

/* CHAT */
.sa-chat{position:fixed;bottom:96px;right:24px;width:380px;max-height:500px;background:var(--card);border:1px solid var(--border);border-radius:16px;z-index:300;display:flex;flex-direction:column;box-shadow:0 16px 48px rgba(0,0,0,0.7);overflow:hidden}
@media(max-width:480px){.sa-chat{right:8px;left:8px;width:auto;bottom:92px}}
.sa-chat-hd{padding:14px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px;background:var(--black)}
.sa-chat-hd img{width:28px;height:28px}
.sa-chat-hd b{font-size:14px;color:var(--text)}
.sa-chat-hd small{font-size:11px;color:var(--text3);display:block}
.sa-chat-body{flex:1;overflow-y:auto;padding:12px 14px;display:flex;flex-direction:column;gap:8px;min-height:200px;max-height:320px}
.sa-msg{padding:10px 14px;border-radius:12px;font-size:13px;line-height:1.55;max-width:88%;word-wrap:break-word}
.sa-msg.u{background:var(--gold);color:var(--black);align-self:flex-end;border-bottom-right-radius:4px;font-weight:500}
.sa-msg.a{background:#1a1a1a;color:var(--text);align-self:flex-start;border-bottom-left-radius:4px;border:1px solid var(--border)}
.sa-chat-ft{display:flex;gap:8px;padding:12px 14px;border-top:1px solid var(--border)}
.sa-chat-in{flex:1;padding:10px 14px;border-radius:8px;border:1px solid var(--border);background:var(--black);color:var(--text);font-size:13px;font-family:inherit;outline:none;box-sizing:border-box}
.sa-chat-in:focus{border-color:var(--gold)}
.sa-chat-btn{width:40px;height:40px;border-radius:8px;background:var(--red);color:#fff;border:none;cursor:pointer;font-size:16px;font-weight:700;display:flex;align-items:center;justify-content:center}
.sa-chat-btn:disabled{opacity:.5}`;

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
    if (data.ok) { if (ns === "done") notify(`+${item.xp_value} XP`); if (data.newBadges?.length) data.newBadges.forEach((b:{name:string}) => notify(`${b.name} unlocked`)); await loadData(email); }
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

  if (!loggedIn) return (<><style>{CSS}</style>
    <div className="sa-login"><div className="sa-login-card">
      <img src={MASCOT} alt="" className="sa-login-mascot"/>
      <h1>SPARTAN ACADEMY</h1>
      <p className="sub">Enter your credentials to begin</p>
      <input className="sa-field" type="email" placeholder="work email" value={email} onChange={e=>setEmail(e.target.value)} onKeyDown={e=>e.key==="Enter"&&document.getElementById("pin-input")?.focus()}/>
      <input className="sa-field" id="pin-input" type="password" placeholder="6-digit PIN" maxLength={6} value={pin} onChange={e=>setPin(e.target.value.replace(/\D/g,""))} onKeyDown={e=>e.key==="Enter"&&handleLogin()}/>
      <button className="sa-btn" onClick={handleLogin} disabled={loginLoading}>{loginLoading?"Verifying...":"Enter the Academy"}</button>
      <div className="sa-error">{loginError}</div>
      <p className="sa-hint">PIN provided by your manager on day one</p>
    </div></div></>);

  if (!employee || !stats) return <div style={{padding:60,textAlign:"center",color:"#555"}}>Loading...</div>;

  const cur = getLevel(stats.earnedXp);
  const next = cur.idx < LEVELS.length - 1 ? LEVELS[cur.idx + 1] : null;
  const pct = stats.totalItems > 0 ? Math.round(100 * stats.completedItems / stats.totalItems) : 0;
  const xpPct = next ? Math.min(100, Math.round(100 * (stats.earnedXp - cur.min) / (next.min - cur.min))) : 100;
  const pending = Object.values(categories).flatMap(c => c.items).filter(i => i.progress_status !== "done");
  const nextMissions = pending.slice(0, 3);
  const roleName = employee.role === "tech" ? "Service Technician" : employee.role === "office" ? "Office Staff" : "Apprentice";

  return (<><style>{CSS}</style><div className="sa">
    {toast && <div className="sa-toast">{toast}</div>}

    {/* HERO */}
    <div className="sa-hero">
      <img src={MASCOT_L} alt="" className="sa-hero-mascot"/>
      <div>
        <h2>Welcome, {employee.name.split(" ")[0]}</h2>
        <span className="sa-role">{roleName} Track</span>
      </div>
      <div className="sa-hero-stats">
        <div className="sa-rank">
          <div className="sa-rank-text">{cur.rank}</div>
          <div className="sa-rank-name">{cur.name}</div>
        </div>
        <div style={{width:1,height:40,background:"var(--border2)"}}/>
        <div className="sa-xp-block">
          <div className="sa-xp-num">{stats.earnedXp}</div>
          <div className="sa-xp-lbl">XP earned</div>
          <div className="sa-xp-bar"><div className="sa-xp-fill" style={{width:`${xpPct}%`}}/></div>
          {next&&<div className="sa-xp-nxt">{next.min-stats.earnedXp} to {next.name}</div>}
        </div>
        <button className="sa-out" onClick={()=>{sessionStorage.removeItem("sa_email");setLoggedIn(false);setEmployee(null);}}>Sign out</button>
      </div>
    </div>

    {/* PROGRESS */}
    <div className="sa-progress sa-anim sa-anim-1">
      <div className="sa-progress-top">
        <div className="sa-progress-title">Battle Readiness</div>
        <div className="sa-progress-pct">{pct}%</div>
      </div>
      <div className="sa-progress-bar"><div className="sa-progress-fill" style={{width:`${pct}%`}}/></div>
      <div className="sa-progress-sub">{stats.completedItems} of {stats.totalItems} objectives complete  /  {stats.totalXp-stats.earnedXp} XP remaining</div>
      {achievements.length>0&&<div className="sa-badges">{achievements.map(a=><div key={a.badge_code} className="sa-badge" title={a.badge_description}><img src={MASCOT} alt=""/></div>)}</div>}
    </div>

    {/* NEXT UP */}
    {nextMissions.length>0&&<div className="sa-next sa-anim sa-anim-2">
      <h3>Next Objectives</h3>
      {nextMissions.map(m=>{const c=CAT_COLORS[m.category]||"#c8a84e";return(
        <div key={m.id} className="sa-ni" onClick={()=>setExpandedCat(m.category)}>
          <div className="sa-ni-bar" style={{background:c}}/>
          <div className="sa-ni-text">{m.title}</div>
          <div className="sa-ni-cat">{m.category}</div>
          <div className="sa-ni-xp">+{m.xp_value} XP</div>
        </div>
      );})}
    </div>}

    {/* CATEGORIES */}
    <div className="sa-section">Missions</div>
    <div className="sa-grid">
      {Object.entries(categories).map(([cn,cat])=>{
        const o=expandedCat===cn;
        const c=CAT_COLORS[cn]||"#c8a84e";
        const cp=cat.total>0?Math.round(100*cat.done/cat.total):0;
        return(
          <div key={cn} className={`sa-cat${o?" open":""}`} style={{borderColor:o?c:undefined}}>
            <div className="sa-ch" onClick={()=>setExpandedCat(o?null:cn)}>
              <div className="sa-ch-bar" style={{background:c}}/>
              <div className="sa-ch-info">
                <div className="sa-ch-name">{cn}</div>
                <div className="sa-ch-count">{cat.done} of {cat.total} complete</div>
              </div>
              <div className="sa-ch-pct" style={{color:cp>0?c:"var(--text3)"}}>{cp}%</div>
            </div>
            {o&&<div className="sa-tasks">{cat.items.map(it=>(
              <div key={it.id} className="sa-task" onClick={()=>handleComplete(it)} style={{opacity:it.progress_status==="done"?.6:1}}>
                <div className={`sa-ck${it.progress_status==="done"?" done":""}`} style={{"--c":c} as React.CSSProperties}>{it.progress_status==="done"?"\u2713":""}</div>
                <div className={`sa-task-name${it.progress_status==="done"?" done":""}`}>{it.title}</div>
                <div className={`sa-task-xp${it.progress_status==="done"?" done":""}`}>{it.progress_status==="done"?"Done":`+${it.xp_value} XP`}</div>
              </div>
            ))}</div>}
          </div>
        );
      })}
    </div>

    {/* CHAT FAB */}
    <button className="sa-fab" onClick={()=>{setShowChat(!showChat);if(!showChat&&!chatMessages.length)setChatMessages([{role:"assistant",content:`Hey ${employee.name.split(" ")[0]}! I'm your Spartan coach. What do you need help with?`}]);}}>
      {showChat?<span className="sa-fab-x">{"\u2715"}</span>:<img src={MASCOT_R} alt="Coach"/>}
    </button>

    {/* CHAT */}
    {showChat&&<div className="sa-chat">
      <div className="sa-chat-hd"><img src={LOGO_NAV} alt=""/><div><b>Spartan Coach</b><small>AI assistant</small></div></div>
      <div className="sa-chat-body">{chatMessages.map((m,i)=><div key={i} className={`sa-msg ${m.role==="user"?"u":"a"}`}>{m.content}</div>)}{chatLoading&&<div className="sa-msg a" style={{opacity:.6}}>Thinking...</div>}<div ref={chatEndRef}/></div>
      <div className="sa-chat-ft"><input className="sa-chat-in" value={chatInput} onChange={e=>setChatInput(e.target.value)} onKeyDown={e=>e.key==="Enter"&&sendChat()} placeholder="Ask anything..."/><button className="sa-chat-btn" onClick={sendChat} disabled={chatLoading}>{"\u2192"}</button></div>
    </div>}
  </div></>);
}
