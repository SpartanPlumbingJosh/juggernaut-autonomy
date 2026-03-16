"use client";
import { useState, useEffect, useCallback } from "react";

const MASCOT = "https://spartan-plumbing.com/wp-content/uploads/spartan-mascot-shield.svg";
const MASCOT_L = "https://spartan-plumbing.com/wp-content/uploads/spartan-mascot-left.svg";

const ROLES = [
  { value: "tech", label: "Service Technician" },
  { value: "install_tech", label: "Install Technician" },
  { value: "apprentice", label: "Apprentice" },
  { value: "office", label: "Office Staff" },
  { value: "sales", label: "Sales" },
  { value: "leadership", label: "Leadership" },
];

interface Employee {
  id: string; name: string; email: string; personal_email: string; phone: string;
  role: string; position: string; hire_date: string; status: string; total_xp: number;
  level: number; is_admin: boolean; pin_code: string; manager_id: string;
  manager_name: string; due_30_date: string; due_60_date: string; due_90_date: string;
  created_at: string; last_activity_at: string;
}
interface Progress { total: number; done: number; totalXp: number; earnedXp: number }
interface Template {
  id: string; role: string; category: string; title: string; description: string;
  xp_value: number; sort_order: number; requires_value: boolean; value_label: string;
  requires_manager_approval: boolean;
}

/* ── REUSE the exact onboarding CSS + admin-specific additions ── */
const CSS = `@import url('https://fonts.googleapis.com/css2?family=Archivo+Black&family=Barlow+Condensed:wght@400;500;600;700&family=Barlow:wght@400;500;600&display=swap');
:root{--black:#0a0a0a;--card:#111;--border:#222;--border2:#333;--gold:#c8a84e;--red:#b91c1c;--red2:#8b1a1a;--text:#e8e8e8;--text2:#888;--text3:#555;--green:#22c55e}
.sa{font-family:'Barlow',sans-serif;color:var(--text);position:relative;padding-bottom:100px}
.sa h2,.sa h3{font-family:'Archivo Black',sans-serif}
@keyframes sa-in{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
@keyframes sa-toast-in{from{opacity:0;transform:translateX(-50%) translateY(-12px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}
.sa-anim{animation:sa-in .5s ease both}
.sa-anim-1{animation-delay:.05s}.sa-anim-2{animation-delay:.1s}.sa-anim-3{animation-delay:.15s}.sa-anim-4{animation-delay:.2s}.sa-anim-5{animation-delay:.25s}.sa-anim-6{animation-delay:.3s}
.sa-toast{position:fixed;top:76px;left:50%;transform:translateX(-50%);background:var(--gold);color:var(--black);padding:10px 28px;border-radius:40px;font-weight:700;font-size:14px;z-index:400;box-shadow:0 4px 24px rgba(200,168,78,0.5);animation:sa-toast-in .3s ease;font-family:'Archivo Black',sans-serif;letter-spacing:.5px}
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
.sa-hero{position:relative;display:flex;align-items:center;justify-content:space-between;padding:28px 32px;background:var(--card);border:1px solid var(--border);border-radius:16px;margin-bottom:16px;overflow:hidden;flex-wrap:wrap;gap:16px;animation:sa-in .5s ease both}
.sa-hero::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--red),var(--gold))}
.sa-hero-mascot{position:absolute;right:-10px;top:50%;transform:translateY(-50%);width:140px;height:140px;opacity:.08;pointer-events:none}
.sa-hero h2{font-size:1.6rem;color:var(--text);margin:0 0 6px;letter-spacing:.5px}
.sa-role{display:inline-block;padding:4px 16px;border-radius:4px;background:var(--red);color:#fff;font-size:11px;font-weight:700;font-family:'Barlow Condensed',sans-serif;letter-spacing:1.5px;text-transform:uppercase}
.sa-hero-stats{display:flex;align-items:center;gap:20px;position:relative;z-index:1}
.sa-out{font-size:11px;color:var(--text3);background:none;border:1px solid var(--border2);border-radius:6px;padding:5px 14px;cursor:pointer;font-family:inherit;transition:all .15s;font-weight:500}
.sa-out:hover{border-color:var(--red);color:var(--red)}
.sa-progress{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px 24px;margin-bottom:16px}
.sa-progress-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.sa-progress-title{font-family:'Barlow Condensed',sans-serif;font-size:15px;font-weight:600;color:var(--text);text-transform:uppercase;letter-spacing:1px}
.sa-progress-pct{font-family:'Archivo Black',sans-serif;font-size:18px;color:var(--gold)}
.sa-progress-bar{width:100%;height:8px;border-radius:4px;background:var(--border2);overflow:hidden}
.sa-progress-fill{height:100%;border-radius:4px;background:linear-gradient(90deg,var(--red),var(--gold));transition:width 1s ease}
.sa-progress-sub{font-size:12px;color:var(--text3);margin-top:6px}
.sa-next{background:var(--card);border:1px solid var(--border);border-left:4px solid var(--red);border-radius:12px;padding:16px 20px;margin-bottom:16px}
.sa-next h3{font-size:14px;color:var(--red);margin:0 0 10px;letter-spacing:1px;text-transform:uppercase}
.sa-ni{display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--border);transition:padding-left .15s}
.sa-ni:hover{padding-left:4px}
.sa-ni:last-child{border:none}
.sa-ni-bar{width:3px;height:24px;border-radius:2px;flex-shrink:0}
.sa-ni-text{flex:1;font-size:14px;color:var(--text);font-weight:500}
.sa-ni-cat{font-size:11px;color:var(--text3);font-weight:500}
.sa-ni-xp{font-family:'Barlow Condensed',sans-serif;font-size:14px;font-weight:700;color:var(--gold)}
.sa-section{font-family:'Archivo Black',sans-serif;font-size:12px;color:var(--text3);letter-spacing:3px;text-transform:uppercase;margin:28px 0 14px;padding-left:2px}
.sa-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:640px){.sa-grid{grid-template-columns:1fr}}
.sa-cat{background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden;transition:all .2s;cursor:pointer;animation:sa-in .4s ease both}
.sa-cat:nth-child(1){animation-delay:.15s}.sa-cat:nth-child(2){animation-delay:.18s}.sa-cat:nth-child(3){animation-delay:.21s}.sa-cat:nth-child(4){animation-delay:.24s}
.sa-cat:hover{border-color:var(--border2)}
.sa-cat.open{grid-column:1/-1}
.sa-ch{display:flex;align-items:center;gap:14px;padding:16px 18px}
.sa-ch-bar{width:4px;align-self:stretch;border-radius:2px;flex-shrink:0}
.sa-ch-info{flex:1;min-width:0}
.sa-ch-name{font-family:'Barlow Condensed',sans-serif;font-size:16px;font-weight:600;color:var(--text);text-transform:uppercase;letter-spacing:.5px}
.sa-ch-count{font-size:12px;color:var(--text3);margin-top:1px}
.sa-ch-pct{font-family:'Archivo Black',sans-serif;font-size:14px;min-width:40px;text-align:right}
.sa-tasks{border-top:1px solid var(--border);padding:8px 14px 14px}
.sa-task{display:flex;align-items:center;gap:10px;padding:9px 4px;border-radius:6px;transition:background .1s}
.sa-task:hover{background:rgba(255,255,255,0.03)}
.sa-ck{width:18px;height:18px;border-radius:4px;border:2px solid var(--border2);display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:all .15s;font-size:10px;color:#fff;font-weight:700}
.sa-ck.done{border-color:var(--c);background:var(--c)}
.sa-task-name{font-size:13px;color:var(--text);flex:1;font-weight:500}
.sa-task-xp{font-family:'Barlow Condensed',sans-serif;font-size:12px;font-weight:700;color:var(--gold)}

/* ── ADMIN-SPECIFIC (extends .sa system) ── */
.sa-tabs{display:flex;gap:0;margin-bottom:24px;overflow-x:auto}
.sa-tab{padding:10px 20px;font-family:'Barlow Condensed',sans-serif;font-size:14px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:var(--text3);background:var(--card);border:1px solid var(--border);border-radius:8px 8px 0 0;cursor:pointer;position:relative;transition:all .15s;margin-right:-1px}
.sa-tab:hover{color:var(--text2)}
.sa-tab.on{color:var(--gold);background:var(--black);border-bottom-color:var(--black)}
.sa-tab.on::after{content:'';position:absolute;bottom:-1px;left:0;right:0;height:2px;background:var(--gold)}
.sa-form{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:640px){.sa-form{grid-template-columns:1fr}}
.sa-fg{display:flex;flex-direction:column;gap:4px}
.sa-fg.full{grid-column:1/-1}
.sa-fg label{font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:1px;font-weight:600;font-family:'Barlow Condensed',sans-serif}
.sa-fg input,.sa-fg select{padding:10px 12px;border:1px solid var(--border2);border-radius:6px;background:var(--black);color:var(--text);font-size:14px;font-family:inherit;outline:none;transition:border-color .15s;box-sizing:border-box}
.sa-fg input:focus,.sa-fg select:focus{border-color:var(--gold)}
.sa-btn-sm{padding:6px 14px;border:none;border-radius:6px;font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;letter-spacing:.5px;text-transform:uppercase;cursor:pointer;transition:all .15s}
.sa-btn-ghost{background:none;border:1px solid var(--border2);color:var(--text2);padding:6px 14px;border-radius:6px;font-family:'Barlow Condensed',sans-serif;font-weight:600;font-size:12px;letter-spacing:.5px;text-transform:uppercase;cursor:pointer;transition:all .15s}
.sa-btn-ghost:hover{border-color:var(--gold);color:var(--gold)}
.sa-toggle{display:flex;align-items:center;gap:8px;cursor:pointer}
.sa-toggle-track{width:36px;height:20px;border-radius:10px;background:var(--border2);position:relative;transition:background .2s}
.sa-toggle-track.on{background:var(--gold)}
.sa-toggle-knob{width:16px;height:16px;border-radius:50%;background:#fff;position:absolute;top:2px;left:2px;transition:left .2s}
.sa-toggle-track.on .sa-toggle-knob{left:18px}
.sa-detail{border-left:3px solid var(--gold);padding-left:16px;margin:12px 0}
.sa-detail-row{display:flex;gap:8px;padding:4px 0;font-size:13px}
.sa-detail-row span:first-child{color:var(--text3);min-width:100px;font-weight:500}
.sa-chip{padding:5px 14px;border-radius:20px;font-size:12px;font-weight:600;border:1px solid var(--border2);background:none;color:var(--text2);cursor:pointer;font-family:'Barlow Condensed',sans-serif;letter-spacing:.5px;text-transform:uppercase;transition:all .15s}
.sa-chip.on{border-color:var(--gold);color:var(--gold);background:rgba(200,168,78,.1)}
.sa-badge-tag{display:inline-block;padding:2px 10px;border-radius:4px;font-size:11px;font-weight:600;font-family:'Barlow Condensed',sans-serif;letter-spacing:.5px;text-transform:uppercase}
`;

export function AdminApp() {
  const [adminEmail, setAdminEmail] = useState("");
  const [pin, setPin] = useState("");
  const [authed, setAuthed] = useState(false);
  const [loginError, setLoginError] = useState("");
  const [tab, setTab] = useState<"team"|"add"|"tasks"|"settings">("team");
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [progressMap, setProgressMap] = useState<Record<string, Progress>>({});
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState("");
  const [selectedEmp, setSelectedEmp] = useState<Employee | null>(null);
  const [roleFilter, setRoleFilter] = useState("");
  const [taskRoleFilter, setTaskRoleFilter] = useState("all");
  const [expandedCat, setExpandedCat] = useState<string|null>(null);
  const [af, setAf] = useState({ name: "", email: "", role: "tech", position: "", hire_date: "", phone: "", personal_email: "", is_admin: false, manager_id: "" });

  const notify = (msg: string) => { setToast(msg); setTimeout(() => setToast(""), 3000); };

  const loadData = useCallback(async (em: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/admin?admin_email=${encodeURIComponent(em)}`);
      if (!res.ok) { const d = await res.json(); setLoginError(d.error || "Access denied"); setAuthed(false); return; }
      const data = await res.json();
      setEmployees(data.employees || []); setProgressMap(data.progressMap || {}); setAuthed(true);
    } catch { setLoginError("Connection error"); }
    setLoading(false);
  }, []);

  const loadTemplates = useCallback(async (em: string) => {
    const res = await fetch(`/api/admin/templates?admin_email=${encodeURIComponent(em)}`);
    if (res.ok) { const d = await res.json(); setTemplates(d.templates || []); }
  }, []);

  useEffect(() => { const s = typeof window !== "undefined" ? sessionStorage.getItem("sa_admin") : null; if (s) { setAdminEmail(s); loadData(s); loadTemplates(s); } }, [loadData, loadTemplates]);

  async function handleLogin() {
    if (!adminEmail || !pin) { setLoginError("Enter email and PIN"); return; }
    setLoginError("");
    const res = await fetch("/api/onboard/auth", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: adminEmail, pin }) });
    if (!res.ok) { setLoginError("Invalid credentials"); return; }
    const emp = await res.json();
    if (!emp.id) { setLoginError("Invalid credentials"); return; }
    sessionStorage.setItem("sa_admin", adminEmail); await loadData(adminEmail); await loadTemplates(adminEmail);
  }

  async function addEmployee() {
    if (!af.name || !af.email || !af.role) { notify("Name, email, and role required"); return; }
    const res = await fetch("/api/admin", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ admin_email: adminEmail, ...af }) });
    const d = await res.json();
    if (d.ok) { notify(`${af.name} added — PIN: ${d.generated_pin}`); setAf({ name: "", email: "", role: "tech", position: "", hire_date: "", phone: "", personal_email: "", is_admin: false, manager_id: "" }); loadData(adminEmail); }
    else notify(d.error || "Failed");
  }

  async function updateEmployee(id: string, fields: Record<string, unknown>) {
    const res = await fetch("/api/admin/employee", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ admin_email: adminEmail, employee_id: id, ...fields }) });
    if ((await res.json()).ok) { notify("Updated"); loadData(adminEmail); }
  }

  async function deactivateEmployee(id: string) {
    if (!confirm("Deactivate this employee?")) return;
    await fetch(`/api/admin/employee?admin_email=${encodeURIComponent(adminEmail)}&id=${id}`, { method: "DELETE" });
    notify("Deactivated"); setSelectedEmp(null); loadData(adminEmail);
  }

  async function resetPin(id: string) {
    const p = String(100000 + Math.floor(Math.random() * 900000));
    await updateEmployee(id, { pin_code: p }); notify(`New PIN: ${p}`);
  }

  /* ── LOGIN — same as onboarding ── */
  if (!authed) return (<><style>{CSS}</style>
    <div className="sa-login"><div className="sa-login-card">
      <img src={MASCOT} alt="" className="sa-login-mascot"/>
      <h1>COMMAND CENTER</h1>
      <p className="sub">Admin access required</p>
      <input className="sa-field" type="email" placeholder="admin email" value={adminEmail} onChange={e=>setAdminEmail(e.target.value)} onKeyDown={e=>e.key==="Enter"&&document.getElementById("apin")?.focus()}/>
      <input className="sa-field" id="apin" type="password" placeholder="6-digit PIN" maxLength={6} value={pin} onChange={e=>setPin(e.target.value.replace(/\D/g,""))} onKeyDown={e=>e.key==="Enter"&&handleLogin()}/>
      <button className="sa-btn" onClick={handleLogin}>Enter</button>
      <div className="sa-error">{loginError}</div>
      <p className="sa-hint">Only admins can access this area</p>
    </div></div></>);

  const active = employees.filter(e => e.status === "active");
  const admins = employees.filter(e => e.is_admin);
  const avgPct = active.length ? Math.round(active.reduce((s, e) => { const p = progressMap[e.id]; return s + (p ? Math.round(100 * p.done / (p.total || 1)) : 0); }, 0) / active.length) : 0;
  const behind = active.filter(e => { const p = progressMap[e.id]; return p && p.total > 0 && (100 * p.done / p.total) < 50; }).length;
  const filteredEmp = roleFilter ? employees.filter(e => e.role === roleFilter) : employees;
  const filteredTemplates = templates.filter(t => taskRoleFilter === "all" || t.role === taskRoleFilter);
  const taskCategories = [...new Set(filteredTemplates.map(t => t.category))];

  return (<><style>{CSS}</style><div className="sa">
    {toast && <div className="sa-toast">{toast}</div>}

    {/* HERO — same pattern as onboarding */}
    <div className="sa-hero">
      <img src={MASCOT_L} alt="" className="sa-hero-mascot"/>
      <div>
        <h2>Command Center</h2>
        <span className="sa-role">Administrator</span>
      </div>
      <div className="sa-hero-stats">
        <div style={{textAlign:"center",minWidth:50}}>
          <div style={{fontFamily:"'Archivo Black',sans-serif",fontSize:"2rem",color:"var(--gold)",lineHeight:1}}>{active.length}</div>
          <div style={{fontSize:10,color:"var(--text2)",textTransform:"uppercase",letterSpacing:1,marginTop:2,fontWeight:600}}>Active</div>
        </div>
        <div style={{width:1,height:40,background:"var(--border2)"}}/>
        <div style={{textAlign:"center",minWidth:50}}>
          <div style={{fontFamily:"'Archivo Black',sans-serif",fontSize:"2rem",color:behind>0?"#ef4444":"var(--green)",lineHeight:1}}>{behind}</div>
          <div style={{fontSize:10,color:"var(--text2)",textTransform:"uppercase",letterSpacing:1,marginTop:2,fontWeight:600}}>Behind</div>
        </div>
        <div style={{width:1,height:40,background:"var(--border2)"}}/>
        <div style={{textAlign:"center",minWidth:50}}>
          <div style={{fontFamily:"'Archivo Black',sans-serif",fontSize:"2rem",color:"var(--gold)",lineHeight:1}}>{avgPct}%</div>
          <div style={{fontSize:10,color:"var(--text2)",textTransform:"uppercase",letterSpacing:1,marginTop:2,fontWeight:600}}>Avg</div>
        </div>
        <button className="sa-out" onClick={()=>{sessionStorage.removeItem("sa_admin");setAuthed(false);}}>Sign out</button>
      </div>
    </div>

    {/* TABS — styled like the progress bar card */}
    <div className="sa-tabs sa-anim sa-anim-1">
      {(["team","add","tasks","settings"] as const).map(t=>(
        <button key={t} className={`sa-tab${tab===t?" on":""}`} onClick={()=>setTab(t)}>
          {t==="team"?"Team":t==="add"?"Add Person":t==="tasks"?"Tasks":"Settings"}
        </button>
      ))}
    </div>

    {/* ═══ TEAM ═══ */}
    {tab==="team"&&<>
      {/* Role filter chips */}
      <div style={{display:"flex",gap:8,flexWrap:"wrap",marginBottom:16}} className="sa-anim sa-anim-2">
        <button className={`sa-chip${!roleFilter?" on":""}`} onClick={()=>setRoleFilter("")}>All</button>
        {ROLES.map(r=><button key={r.value} className={`sa-chip${roleFilter===r.value?" on":""}`} onClick={()=>setRoleFilter(roleFilter===r.value?"":r.value)}>{r.label}</button>)}
      </div>

      {/* Employee cards — using sa-cat pattern with colored bars */}
      <div className="sa-section">Team Members</div>
      <div className="sa-grid">
        {filteredEmp.map((e,i)=>{
          const p=progressMap[e.id]||{total:0,done:0,totalXp:0,earnedXp:0};
          const pct=p.total>0?Math.round(100*p.done/p.total):0;
          const isOpen=selectedEmp?.id===e.id;
          const barColor=e.is_admin?"var(--gold)":e.status==="inactive"?"#ef4444":"var(--red)";
          return(
            <div key={e.id} className={`sa-cat${isOpen?" open":""}`} style={{animationDelay:`${0.15+i*0.03}s`}} onClick={()=>setSelectedEmp(isOpen?null:e)}>
              <div className="sa-ch">
                <div className="sa-ch-bar" style={{background:barColor}}/>
                <div className="sa-ch-info">
                  <div className="sa-ch-name">{e.name}</div>
                  <div className="sa-ch-count">
                    {ROLES.find(r=>r.value===e.role)?.label||e.role}
                    {e.is_admin&&<span style={{marginLeft:6,color:"var(--gold)"}}>★ Admin</span>}
                    {e.status==="inactive"&&<span style={{marginLeft:6,color:"#ef4444"}}>● Inactive</span>}
                  </div>
                </div>
                <div style={{textAlign:"right"}}>
                  <div className="sa-ch-pct" style={{color:pct===100?"var(--green)":pct>0?"var(--gold)":"var(--text3)"}}>{pct}%</div>
                  <div style={{fontSize:11,color:"var(--text3)"}}>{p.done}/{p.total}</div>
                </div>
              </div>
              {/* Expanded detail — same as sa-tasks pattern */}
              {isOpen&&<div className="sa-tasks" onClick={ev=>ev.stopPropagation()}>
                <div className="sa-detail">
                  <div className="sa-detail-row"><span>Email</span><span>{e.email}</span></div>
                  <div className="sa-detail-row"><span>Phone</span><span>{e.phone||"—"}</span></div>
                  <div className="sa-detail-row"><span>Position</span><span>{e.position||"—"}</span></div>
                  <div className="sa-detail-row"><span>Hire Date</span><span>{e.hire_date?new Date(e.hire_date).toLocaleDateString():"—"}</span></div>
                  <div className="sa-detail-row"><span>Manager</span><span>{e.manager_name||"None"}</span></div>
                  <div className="sa-detail-row"><span>PIN</span><span style={{fontFamily:"monospace",color:"var(--gold)"}}>{e.pin_code}</span></div>
                  <div className="sa-detail-row"><span>XP</span><span style={{color:"var(--gold)",fontWeight:700}}>{p.earnedXp} / {p.totalXp}</span></div>
                  {e.due_30_date&&<div className="sa-detail-row"><span>30/60/90</span><span>{e.due_30_date} / {e.due_60_date} / {e.due_90_date}</span></div>}
                </div>
                <div style={{display:"flex",gap:6,marginTop:12,flexWrap:"wrap"}}>
                  <button className="sa-btn-ghost" onClick={()=>resetPin(e.id)}>Reset PIN</button>
                  <button className="sa-btn-ghost" onClick={()=>updateEmployee(e.id,{is_admin:!e.is_admin})}>{e.is_admin?"Remove Admin":"Make Admin"}</button>
                  <button className="sa-btn-sm" style={{background:"#ef4444",color:"#fff"}} onClick={()=>deactivateEmployee(e.id)}>Deactivate</button>
                </div>
              </div>}
            </div>
          );
        })}
        {filteredEmp.length===0&&<div style={{gridColumn:"1/-1",textAlign:"center",padding:40,color:"var(--text3)"}}>No team members found</div>}
      </div>
    </>}

    {/* ═══ ADD PERSON ═══ */}
    {tab==="add"&&<>
      {/* Uses sa-next card style with red left border */}
      <div className="sa-next sa-anim sa-anim-2">
        <h3>Add New Team Member</h3>
        <div className="sa-form">
          <div className="sa-fg"><label>Full Name *</label><input value={af.name} onChange={e=>setAf({...af,name:e.target.value})} placeholder="Nick Hernandez"/></div>
          <div className="sa-fg"><label>Work Email *</label><input value={af.email} onChange={e=>setAf({...af,email:e.target.value})} placeholder="nick@spartan-plumbing.com"/></div>
          <div className="sa-fg"><label>Role *</label><select value={af.role} onChange={e=>setAf({...af,role:e.target.value})}>{ROLES.map(r=><option key={r.value} value={r.value}>{r.label}</option>)}</select></div>
          <div className="sa-fg"><label>Position</label><input value={af.position} onChange={e=>setAf({...af,position:e.target.value})} placeholder="Install Technician"/></div>
          <div className="sa-fg"><label>Hire Date</label><input type="date" value={af.hire_date} onChange={e=>setAf({...af,hire_date:e.target.value})}/></div>
          <div className="sa-fg"><label>Phone</label><input value={af.phone} onChange={e=>setAf({...af,phone:e.target.value})} placeholder="937-555-0123"/></div>
          <div className="sa-fg"><label>Personal Email</label><input value={af.personal_email} onChange={e=>setAf({...af,personal_email:e.target.value})}/></div>
          <div className="sa-fg"><label>Manager</label><select value={af.manager_id} onChange={e=>setAf({...af,manager_id:e.target.value})}><option value="">None</option>{employees.filter(e=>e.is_admin||e.role==="leadership").map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select></div>
          <div className="sa-fg">
            <label>&nbsp;</label>
            <div className="sa-toggle" onClick={()=>setAf({...af,is_admin:!af.is_admin})}>
              <div className={`sa-toggle-track${af.is_admin?" on":""}`}><div className="sa-toggle-knob"/></div>
              <span style={{fontSize:13,color:af.is_admin?"var(--gold)":"var(--text3)"}}>Admin Access</span>
            </div>
          </div>
          <div className="sa-fg full" style={{flexDirection:"row",justifyContent:"flex-end",gap:8,marginTop:8}}>
            <button className="sa-btn-ghost" onClick={()=>setAf({name:"",email:"",role:"tech",position:"",hire_date:"",phone:"",personal_email:"",is_admin:false,manager_id:""})}>Clear</button>
            <button className="sa-btn" style={{width:"auto",padding:"10px 24px"}} onClick={addEmployee} disabled={!af.name||!af.email}>Add Employee</button>
          </div>
        </div>
      </div>
      {/* Info card — same sa-progress pattern */}
      <div className="sa-progress sa-anim sa-anim-3">
        <div className="sa-progress-title">How it works</div>
        <div style={{fontSize:13,color:"var(--text2)",lineHeight:1.6,marginTop:8}}>
          A 6-digit PIN is auto-generated. The employee uses their work email + PIN to log into Spartan Academy at <span style={{color:"var(--gold)"}}>training.spartan-plumbing.com/onboard</span>. Their role determines which onboarding tasks they see. 30/60/90 day milestones are set automatically from hire date.
        </div>
      </div>
    </>}

    {/* ═══ TASKS ═══ */}
    {tab==="tasks"&&<>
      <div style={{display:"flex",gap:8,flexWrap:"wrap",marginBottom:16}} className="sa-anim sa-anim-2">
        {["all",...ROLES.map(r=>r.value)].map(r=>(
          <button key={r} className={`sa-chip${taskRoleFilter===r?" on":""}`} onClick={()=>setTaskRoleFilter(r)}>
            {r==="all"?"All Roles":ROLES.find(x=>x.value===r)?.label||r}
          </button>
        ))}
      </div>

      {/* Progress bar showing task count */}
      <div className="sa-progress sa-anim sa-anim-3">
        <div className="sa-progress-top">
          <div className="sa-progress-title">Task Library</div>
          <div className="sa-progress-pct">{filteredTemplates.length}</div>
        </div>
        <div className="sa-progress-sub">{taskCategories.length} categories — {filteredTemplates.reduce((s,t)=>s+t.xp_value,0)} total XP</div>
      </div>

      {/* Task categories — using sa-cat pattern */}
      <div className="sa-section">Categories</div>
      <div className="sa-grid">
        {taskCategories.map((cat,i)=>{
          const items=filteredTemplates.filter(t=>t.category===cat);
          const isOpen=expandedCat===cat;
          return(
            <div key={cat} className={`sa-cat${isOpen?" open":""}`} style={{animationDelay:`${0.15+i*0.03}s`}}>
              <div className="sa-ch" onClick={()=>setExpandedCat(isOpen?null:cat)}>
                <div className="sa-ch-bar" style={{background:i%2===0?"var(--gold)":"var(--red)"}}/>
                <div className="sa-ch-info">
                  <div className="sa-ch-name">{cat}</div>
                  <div className="sa-ch-count">{items.length} tasks — {items.reduce((s,t)=>s+t.xp_value,0)} XP</div>
                </div>
                <div className="sa-ch-pct" style={{color:"var(--gold)"}}>{items.length}</div>
              </div>
              {isOpen&&<div className="sa-tasks">
                {items.map(t=>(
                  <div key={t.id} className="sa-task">
                    <div className="sa-ck" style={{"--c":i%2===0?"var(--gold)":"var(--red)"} as React.CSSProperties}>
                      {t.requires_manager_approval?"★":""}
                    </div>
                    <div className="sa-task-name">{t.title}{t.description&&<span style={{color:"var(--text3)",marginLeft:6,fontSize:11}}>{t.description.substring(0,40)}{t.description.length>40?"...":""}</span>}</div>
                    <div style={{fontSize:11,color:"var(--text3)",minWidth:30}}>{t.role}</div>
                    <div className="sa-task-xp">{t.xp_value} XP</div>
                  </div>
                ))}
              </div>}
            </div>
          );
        })}
      </div>
    </>}

    {/* ═══ SETTINGS ═══ */}
    {tab==="settings"&&<>
      {/* Account card — sa-next pattern */}
      <div className="sa-next sa-anim sa-anim-2">
        <h3>Account</h3>
        <div className="sa-detail">
          <div className="sa-detail-row"><span>Logged in as</span><span>{adminEmail}</span></div>
          <div className="sa-detail-row"><span>Role</span><span style={{color:"var(--gold)"}}>Administrator</span></div>
          <div className="sa-detail-row"><span>Employees</span><span>{employees.length} total / {active.length} active</span></div>
          <div className="sa-detail-row"><span>Tasks</span><span>{templates.length} templates</span></div>
          <div className="sa-detail-row"><span>SOP Cards</span><span>282 across 7 boards</span></div>
        </div>
        <div style={{display:"flex",gap:8,marginTop:12}}>
          <button className="sa-btn-ghost" onClick={()=>{loadData(adminEmail);loadTemplates(adminEmail);notify("Refreshed");}} disabled={loading}>{loading?"...":"Refresh"}</button>
          <button className="sa-btn-ghost" style={{borderColor:"#ef4444",color:"#ef4444"}} onClick={()=>{sessionStorage.removeItem("sa_admin");setAuthed(false);}}>Sign Out</button>
        </div>
      </div>

      {/* Milestones — sa-progress pattern */}
      <div className="sa-progress sa-anim sa-anim-3">
        <div className="sa-progress-title">Milestones</div>
        <div style={{fontSize:13,color:"var(--text2)",lineHeight:1.6,marginTop:8}}>
          New hires get automatic milestone dates based on hire date. Adjustable per person in the Team tab.
        </div>
        <div className="sa-detail" style={{marginTop:12}}>
          <div className="sa-detail-row"><span>30-Day</span><span>Pre-employment + Accounts</span></div>
          <div className="sa-detail-row"><span>60-Day</span><span>All training modules</span></div>
          <div className="sa-detail-row"><span>90-Day</span><span>Full readiness</span></div>
        </div>
      </div>

      {/* Notifications — sa-progress pattern */}
      <div className="sa-progress sa-anim sa-anim-4">
        <div className="sa-progress-title">Notifications</div>
        <div style={{fontSize:13,color:"var(--text3)",lineHeight:1.6,marginTop:8}}>
          Coming soon — Slack notifications when employees complete categories, weekly digest of who is behind, milestone alerts. Will wire via n8n.
        </div>
      </div>
    </>}
  </div></>);
}
