"use client";
import { useState, useEffect, useCallback } from "react";

const ROLES = [
  { value: "tech", label: "Service Technician", icon: "🛠" },
  { value: "install_tech", label: "Install Technician", icon: "🔧" },
  { value: "apprentice", label: "Apprentice", icon: "🎓" },
  { value: "office", label: "Office Staff", icon: "🖥" },
  { value: "sales", label: "Sales", icon: "💰" },
  { value: "leadership", label: "Leadership", icon: "⭐" },
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

/* Only CSS that globals.css doesn't cover — forms, toggle, tabs, progress bar */
const ADMIN_CSS = `.adm-field{width:100%;padding:12px 14px;border:1px solid var(--border);border-radius:8px;background:#0a0a0a;color:var(--text);font-size:14px;font-family:inherit;outline:none;transition:border-color .2s;box-sizing:border-box}
.adm-field:focus{border-color:var(--gold)}
.adm-field::placeholder{color:var(--text3)}
.adm-form{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:640px){.adm-form{grid-template-columns:1fr}}
.adm-fg{display:flex;flex-direction:column;gap:4px}
.adm-fg.full{grid-column:1/-1}
.adm-fg label{font-size:12px;color:var(--text2);font-weight:500}
.adm-fg select{padding:12px 14px;border:1px solid var(--border);border-radius:8px;background:#0a0a0a;color:var(--text);font-size:14px;font-family:inherit;outline:none;transition:border-color .2s;box-sizing:border-box}
.adm-fg select:focus{border-color:var(--gold)}
.adm-toggle{display:flex;align-items:center;gap:8px;cursor:pointer;user-select:none}
.adm-tg{width:36px;height:20px;border-radius:10px;background:var(--border);position:relative;transition:background .2s}
.adm-tg.on{background:var(--gold)}
.adm-tg-k{width:16px;height:16px;border-radius:50%;background:#fff;position:absolute;top:2px;left:2px;transition:left .2s}
.adm-tg.on .adm-tg-k{left:18px}
.adm-tabs{display:flex;gap:8px;margin-bottom:24px;flex-wrap:wrap}
.adm-pbar{width:100%;height:6px;border-radius:3px;background:var(--border);overflow:hidden}
.adm-pfill{height:100%;border-radius:3px;background:linear-gradient(90deg,var(--red,#b91c1c),var(--gold));transition:width .6s}
.adm-toast{position:fixed;top:70px;left:50%;transform:translateX(-50%);background:var(--gold);color:#0a0a0a;padding:10px 28px;border-radius:20px;font-weight:600;font-size:14px;z-index:400;box-shadow:0 4px 20px rgba(200,168,78,0.4)}
.adm-detail{border-left:3px solid var(--gold);padding-left:16px;margin:12px 0}
.adm-detail div{display:flex;gap:8px;padding:3px 0;font-size:13px}
.adm-detail span:first-child{color:var(--text3);min-width:90px}`;

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
  const [selectedEmp, setSelectedEmp] = useState<string|null>(null);
  const [roleFilter, setRoleFilter] = useState("");
  const [taskRoleFilter, setTaskRoleFilter] = useState("all");
  const [expandedCat, setExpandedCat] = useState<string|null>(null);
  const [af, setAf] = useState({name:"",email:"",role:"tech",position:"",hire_date:"",phone:"",personal_email:"",is_admin:false,manager_id:""});

  const notify = (msg: string) => { setToast(msg); setTimeout(() => setToast(""), 3000); };

  const loadData = useCallback(async (em: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/admin?admin_email=${encodeURIComponent(em)}`);
      if (!res.ok) { setLoginError((await res.json()).error || "Access denied"); setAuthed(false); return; }
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
    if (!(await res.json()).id) { setLoginError("Invalid credentials"); return; }
    sessionStorage.setItem("sa_admin", adminEmail); await loadData(adminEmail); await loadTemplates(adminEmail);
  }

  async function addEmployee() {
    if (!af.name || !af.email) { notify("Name and email required"); return; }
    const res = await fetch("/api/admin", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ admin_email: adminEmail, ...af }) });
    const d = await res.json();
    if (d.ok) { notify(`${af.name} added — PIN: ${d.generated_pin}`); setAf({name:"",email:"",role:"tech",position:"",hire_date:"",phone:"",personal_email:"",is_admin:false,manager_id:""}); loadData(adminEmail); }
    else notify(d.error || "Failed");
  }

  async function updateEmp(id: string, fields: Record<string, unknown>) {
    const res = await fetch("/api/admin/employee", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ admin_email: adminEmail, employee_id: id, ...fields }) });
    if ((await res.json()).ok) { notify("Updated"); loadData(adminEmail); }
  }

  async function deactivateEmp(id: string) {
    if (!confirm("Deactivate this employee?")) return;
    await fetch(`/api/admin/employee?admin_email=${encodeURIComponent(adminEmail)}&id=${id}`, { method: "DELETE" });
    notify("Deactivated"); setSelectedEmp(null); loadData(adminEmail);
  }

  async function resetPin(id: string) {
    const p = String(100000 + Math.floor(Math.random() * 900000));
    await updateEmp(id, { pin_code: p }); notify(`New PIN: ${p}`);
  }

  /* ── LOGIN ── uses global .card class */
  if (!authed) return (<><style>{ADMIN_CSS}</style>
    <div style={{minHeight:"70vh",display:"flex",alignItems:"center",justifyContent:"center"}}>
      <div className="card" style={{padding:"40px 36px",maxWidth:400,width:"100%",textAlign:"center"}}>
        <div style={{width:56,height:56,borderRadius:12,background:"rgba(200,168,78,0.1)",display:"flex",alignItems:"center",justifyContent:"center",fontSize:28,margin:"0 auto 16px"}}>🔒</div>
        <h1 style={{fontSize:"1.5rem",fontWeight:700,marginBottom:4}}>Command Center</h1>
        <p style={{color:"var(--text2)",fontSize:14,marginBottom:24}}>Admin access required</p>
        <input className="adm-field" type="email" placeholder="admin email" value={adminEmail} onChange={e=>setAdminEmail(e.target.value)} onKeyDown={e=>e.key==="Enter"&&document.getElementById("apin")?.focus()}/>
        <input className="adm-field" id="apin" type="password" placeholder="6-digit PIN" maxLength={6} value={pin} onChange={e=>setPin(e.target.value.replace(/\D/g,""))} onKeyDown={e=>e.key==="Enter"&&handleLogin()} style={{marginTop:8}}/>
        <button className="btn btn-gold" onClick={handleLogin} style={{width:"100%",marginTop:12,padding:"12px 20px"}}>Enter</button>
        {loginError && <p style={{color:"#ef4444",fontSize:13,marginTop:8}}>{loginError}</p>}
        <p style={{color:"var(--text3)",fontSize:12,marginTop:16}}>Only admins can access this area</p>
      </div>
    </div></>);

  const active = employees.filter(e => e.status === "active");
  const avgPct = active.length ? Math.round(active.reduce((s, e) => { const p = progressMap[e.id]; return s + (p ? Math.round(100 * p.done / (p.total || 1)) : 0); }, 0) / active.length) : 0;
  const behind = active.filter(e => { const p = progressMap[e.id]; return p && p.total > 0 && (100 * p.done / p.total) < 50; }).length;
  const filteredEmp = roleFilter ? employees.filter(e => e.role === roleFilter) : employees;
  const filteredTemplates = templates.filter(t => taskRoleFilter === "all" || t.role === taskRoleFilter);
  const taskCategories = [...new Set(filteredTemplates.map(t => t.category))];

  return (<><style>{ADMIN_CSS}</style>
    {toast && <div className="adm-toast">{toast}</div>}

    <div style={{marginBottom:32}}>
      <h1 style={{fontSize:"1.75rem",fontWeight:700,marginBottom:4}}>Command Center</h1>
      <p style={{color:"var(--text2)",fontSize:14}}>Manage your team, onboarding tasks, and settings.</p>
    </div>

    {/* STAT CARDS — same .card pattern as SOPs */}
    <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(140px,1fr))",gap:12,marginBottom:24}}>
      {[
        {icon:"👥",n:active.length,l:"Active",c:"var(--gold)"},
        {icon:"⚠️",n:behind,l:"Behind",c:behind>0?"#ef4444":"var(--green)"},
        {icon:"📊",n:`${avgPct}%`,l:"Avg Progress",c:"var(--gold)"},
        {icon:"🔑",n:employees.filter(e=>e.is_admin).length,l:"Admins",c:"var(--gold)"},
      ].map((s,i) => (
        <div key={i} className="card" style={{padding:16,textAlign:"center"}}>
          <div style={{fontSize:20,marginBottom:6}}>{s.icon}</div>
          <div style={{fontSize:"1.5rem",fontWeight:700,color:s.c}}>{s.n}</div>
          <div style={{fontSize:12,color:"var(--text3)",marginTop:2}}>{s.l}</div>
        </div>
      ))}
    </div>

    {/* TABS — using .badge pattern */}
    <div className="adm-tabs">
      {(["team","add","tasks","settings"] as const).map(t => (
        <button key={t} className={`badge ${tab===t?"badge-gold":""}`}
          style={{cursor:"pointer",padding:"6px 16px",fontSize:13,fontWeight:600,border:tab===t?undefined:"1px solid var(--border)",background:tab===t?undefined:"transparent",color:tab===t?undefined:"var(--text3)"}}
          onClick={()=>setTab(t)}>
          {t==="team"?"👥 Team":t==="add"?"➕ Add Person":t==="tasks"?"📋 Tasks":"⚙️ Settings"}
        </button>
      ))}
      <button className="btn btn-outline" style={{marginLeft:"auto",fontSize:12,padding:"6px 14px"}} onClick={()=>{sessionStorage.removeItem("sa_admin");setAuthed(false);}}>Sign Out</button>
    </div>

    {/* ═══ TEAM ═══ */}
    {tab==="team"&&<>
      {/* Role filters — .badge pills like SOPs library tags */}
      <div style={{display:"flex",gap:8,flexWrap:"wrap",marginBottom:16}}>
        <button className={`badge ${!roleFilter?"badge-gold":""}`} style={{cursor:"pointer",border:roleFilter?`1px solid var(--border)`:undefined,background:roleFilter?"transparent":undefined,color:roleFilter?"var(--text3)":undefined}} onClick={()=>setRoleFilter("")}>All</button>
        {ROLES.map(r=><button key={r.value} className={`badge ${roleFilter===r.value?"badge-gold":""}`} style={{cursor:"pointer",border:roleFilter!==r.value?`1px solid var(--border)`:undefined,background:roleFilter!==r.value?"transparent":undefined,color:roleFilter!==r.value?"var(--text3)":undefined}} onClick={()=>setRoleFilter(roleFilter===r.value?"":r.value)}>{r.icon} {r.label}</button>)}
      </div>

      {/* Employee cards — .card with same structure as SOP board cards */}
      <div style={{display:"grid",gap:12}}>
        {filteredEmp.map(e=>{
          const p=progressMap[e.id]||{total:0,done:0,totalXp:0,earnedXp:0};
          const pct=p.total>0?Math.round(100*p.done/p.total):0;
          const isOpen=selectedEmp===e.id;
          const role=ROLES.find(r=>r.value===e.role);
          return(
            <div key={e.id} className="card" style={{padding:0,cursor:"pointer"}} onClick={()=>setSelectedEmp(isOpen?null:e.id)}>
              <div style={{padding:"16px 20px",display:"flex",alignItems:"center",gap:14}}>
                <div style={{width:44,height:44,borderRadius:12,background:e.is_admin?"rgba(200,168,78,0.1)":"rgba(185,28,28,0.1)",display:"flex",alignItems:"center",justifyContent:"center",fontSize:20,flexShrink:0}}>
                  {role?.icon || "👤"}
                </div>
                <div style={{flex:1,minWidth:0}}>
                  <div style={{fontWeight:600,fontSize:"1rem"}}>{e.name}</div>
                  <div style={{display:"flex",gap:8,fontSize:13,color:"var(--text3)",marginTop:2}}>
                    <span>{role?.label||e.role}</span>
                    <span>·</span>
                    <span>{e.position||"No position"}</span>
                  </div>
                </div>
                <div style={{textAlign:"right",flexShrink:0}}>
                  <div style={{display:"flex",alignItems:"center",gap:8,justifyContent:"flex-end"}}>
                    <div className="adm-pbar" style={{width:80}}><div className="adm-pfill" style={{width:`${pct}%`}}/></div>
                    <span style={{fontSize:13,fontWeight:600,color:pct===100?"var(--green)":"var(--gold)",minWidth:32}}>{pct}%</span>
                  </div>
                  <div style={{display:"flex",gap:6,marginTop:4,justifyContent:"flex-end"}}>
                    {e.is_admin&&<span className="badge badge-gold">admin</span>}
                    {e.status==="inactive"&&<span className="badge" style={{background:"rgba(239,68,68,.15)",color:"#ef4444"}}>inactive</span>}
                  </div>
                </div>
              </div>

              {/* Expanded detail — gold left border like SOPs blockquote */}
              {isOpen&&<div style={{borderTop:"1px solid var(--border)",padding:"16px 20px"}} onClick={ev=>ev.stopPropagation()}>
                <div className="adm-detail">
                  <div><span>Email</span><span>{e.email}</span></div>
                  <div><span>Phone</span><span>{e.phone||"—"}</span></div>
                  <div><span>Hire Date</span><span>{e.hire_date?new Date(e.hire_date).toLocaleDateString():"—"}</span></div>
                  <div><span>Manager</span><span>{e.manager_name||"None"}</span></div>
                  <div><span>PIN</span><span style={{fontFamily:"'JetBrains Mono',monospace",color:"var(--gold)"}}>{e.pin_code}</span></div>
                  <div><span>XP</span><span style={{color:"var(--gold)",fontWeight:600}}>{p.earnedXp} / {p.totalXp}</span></div>
                  {e.due_30_date&&<div><span>30/60/90</span><span>{e.due_30_date} / {e.due_60_date} / {e.due_90_date}</span></div>}
                </div>
                <div style={{display:"flex",gap:8,marginTop:14,flexWrap:"wrap"}}>
                  <button className="btn btn-outline" style={{fontSize:12,padding:"6px 14px"}} onClick={()=>resetPin(e.id)}>Reset PIN</button>
                  <button className="btn btn-outline" style={{fontSize:12,padding:"6px 14px"}} onClick={()=>updateEmp(e.id,{is_admin:!e.is_admin})}>{e.is_admin?"Remove Admin":"Make Admin"}</button>
                  <button className="btn" style={{fontSize:12,padding:"6px 14px",background:"#ef4444",color:"#fff",border:"none"}} onClick={()=>deactivateEmp(e.id)}>Deactivate</button>
                </div>
              </div>}
            </div>
          );
        })}
        {filteredEmp.length===0&&<p style={{textAlign:"center",padding:40,color:"var(--text3)"}}>No team members found</p>}
      </div>
    </>}

    {/* ═══ ADD PERSON ═══ */}
    {tab==="add"&&<>
      <div className="card" style={{padding:0}}>
        <div style={{padding:"20px 24px",display:"flex",alignItems:"flex-start",gap:14}}>
          <div style={{width:44,height:44,borderRadius:12,background:"rgba(200,168,78,0.1)",display:"flex",alignItems:"center",justifyContent:"center",fontSize:20,flexShrink:0}}>➕</div>
          <div>
            <h2 style={{fontSize:"1.1rem",fontWeight:600,marginBottom:2}}>Add New Employee</h2>
            <p style={{fontSize:13,color:"var(--text3)",margin:0}}>A 6-digit PIN will be auto-generated. Role determines onboarding tasks.</p>
          </div>
        </div>
        <div style={{borderTop:"1px solid var(--border)",padding:"20px 24px"}}>
          <div className="adm-form">
            <div className="adm-fg"><label>Full Name *</label><input className="adm-field" value={af.name} onChange={e=>setAf({...af,name:e.target.value})} placeholder="Nick Hernandez"/></div>
            <div className="adm-fg"><label>Work Email *</label><input className="adm-field" value={af.email} onChange={e=>setAf({...af,email:e.target.value})} placeholder="nick@spartan-plumbing.com"/></div>
            <div className="adm-fg"><label>Role *</label><select value={af.role} onChange={e=>setAf({...af,role:e.target.value})}>{ROLES.map(r=><option key={r.value} value={r.value}>{r.label}</option>)}</select></div>
            <div className="adm-fg"><label>Position</label><input className="adm-field" value={af.position} onChange={e=>setAf({...af,position:e.target.value})} placeholder="Install Technician"/></div>
            <div className="adm-fg"><label>Hire Date</label><input className="adm-field" type="date" value={af.hire_date} onChange={e=>setAf({...af,hire_date:e.target.value})}/></div>
            <div className="adm-fg"><label>Phone</label><input className="adm-field" value={af.phone} onChange={e=>setAf({...af,phone:e.target.value})} placeholder="937-555-0123"/></div>
            <div className="adm-fg"><label>Personal Email</label><input className="adm-field" value={af.personal_email} onChange={e=>setAf({...af,personal_email:e.target.value})}/></div>
            <div className="adm-fg"><label>Manager</label><select value={af.manager_id} onChange={e=>setAf({...af,manager_id:e.target.value})}><option value="">None</option>{employees.filter(e=>e.is_admin||e.role==="leadership").map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select></div>
            <div className="adm-fg"><label>&nbsp;</label>
              <div className="adm-toggle" onClick={()=>setAf({...af,is_admin:!af.is_admin})}>
                <div className={`adm-tg${af.is_admin?" on":""}`}><div className="adm-tg-k"/></div>
                <span style={{fontSize:13,color:af.is_admin?"var(--gold)":"var(--text3)"}}>Admin Access</span>
              </div>
            </div>
            <div className="adm-fg full" style={{flexDirection:"row",justifyContent:"flex-end",gap:8,marginTop:8}}>
              <button className="btn btn-outline" onClick={()=>setAf({name:"",email:"",role:"tech",position:"",hire_date:"",phone:"",personal_email:"",is_admin:false,manager_id:""})}>Clear</button>
              <button className="btn btn-gold" onClick={addEmployee} disabled={!af.name||!af.email}>Add Employee</button>
            </div>
          </div>
        </div>
      </div>
    </>}

    {/* ═══ TASKS ═══ */}
    {tab==="tasks"&&<>
      <div style={{display:"flex",gap:8,flexWrap:"wrap",marginBottom:16}}>
        {["all",...ROLES.map(r=>r.value)].map(r=>(
          <button key={r} className={`badge ${taskRoleFilter===r?"badge-gold":""}`} style={{cursor:"pointer",border:taskRoleFilter!==r?`1px solid var(--border)`:undefined,background:taskRoleFilter!==r?"transparent":undefined,color:taskRoleFilter!==r?"var(--text3)":undefined}} onClick={()=>setTaskRoleFilter(r)}>
            {r==="all"?"All Roles":ROLES.find(x=>x.value===r)?.label||r}
          </button>
        ))}
      </div>

      <p style={{fontSize:13,color:"var(--text3)",marginBottom:16}}>
        {filteredTemplates.length} tasks across {taskCategories.length} categories — {filteredTemplates.reduce((s,t)=>s+t.xp_value,0)} total XP
      </p>

      {/* Task category cards — same as SOP board cards */}
      <div style={{display:"grid",gap:12}}>
        {taskCategories.map((cat,i)=>{
          const items=filteredTemplates.filter(t=>t.category===cat);
          const isOpen=expandedCat===cat;
          return(
            <div key={cat} className="card" style={{padding:0}}>
              <div style={{padding:"16px 20px",display:"flex",alignItems:"center",gap:14,cursor:"pointer"}} onClick={()=>setExpandedCat(isOpen?null:cat)}>
                <div style={{width:44,height:44,borderRadius:12,background:i%2===0?"rgba(200,168,78,0.1)":"rgba(185,28,28,0.1)",display:"flex",alignItems:"center",justifyContent:"center",fontSize:20,flexShrink:0}}>
                  {i%2===0?"📁":"📂"}
                </div>
                <div style={{flex:1}}>
                  <h2 style={{fontSize:"1.05rem",fontWeight:600,marginBottom:2}}>{cat}</h2>
                  <div style={{fontSize:13,color:"var(--text3)"}}>{items.length} tasks · {items.reduce((s,t)=>s+t.xp_value,0)} XP</div>
                </div>
              </div>
              {isOpen&&<div style={{borderTop:"1px solid var(--border)",padding:"12px 20px",display:"flex",flexWrap:"wrap",gap:8}}>
                {items.map(t=>(
                  <span key={t.id} className="badge badge-gold" style={{fontSize:12}}>
                    {t.title} ({t.xp_value} XP){t.requires_manager_approval?" ★":""}
                  </span>
                ))}
              </div>}
            </div>
          );
        })}
      </div>
    </>}

    {/* ═══ SETTINGS ═══ */}
    {tab==="settings"&&<>
      <div className="card" style={{padding:0}}>
        <div style={{padding:"20px 24px",display:"flex",alignItems:"flex-start",gap:14}}>
          <div style={{width:44,height:44,borderRadius:12,background:"rgba(200,168,78,0.1)",display:"flex",alignItems:"center",justifyContent:"center",fontSize:20,flexShrink:0}}>⚙️</div>
          <div style={{flex:1}}>
            <h2 style={{fontSize:"1.1rem",fontWeight:600,marginBottom:2}}>Account</h2>
            <p style={{fontSize:13,color:"var(--text3)",margin:0}}>{adminEmail}</p>
          </div>
          <button className="btn btn-outline" style={{fontSize:12,padding:"6px 14px"}} onClick={()=>{loadData(adminEmail);loadTemplates(adminEmail);notify("Refreshed");}} disabled={loading}>{loading?"...":"Refresh"}</button>
        </div>
        <div style={{borderTop:"1px solid var(--border)",padding:"12px 24px",display:"flex",flexWrap:"wrap",gap:8}}>
          <span className="badge badge-gold">{employees.length} employees</span>
          <span className="badge badge-gold">{active.length} active</span>
          <span className="badge badge-gold">{templates.length} tasks</span>
          <span className="badge badge-gold">282 SOPs</span>
        </div>
      </div>

      <div className="card" style={{padding:"20px 24px",marginTop:12}}>
        <h2 style={{fontSize:"1.05rem",fontWeight:600,marginBottom:8}}>Milestones</h2>
        <p style={{fontSize:13,color:"var(--text2)",lineHeight:1.6,marginBottom:12}}>
          New hires get automatic milestone dates based on hire date. Adjustable per person in the Team tab.
        </p>
        <div className="adm-detail">
          <div><span>30-Day</span><span>Pre-employment + Accounts</span></div>
          <div><span>60-Day</span><span>All training modules</span></div>
          <div><span>90-Day</span><span>Full readiness</span></div>
        </div>
      </div>

      <div className="card" style={{padding:"20px 24px",marginTop:12}}>
        <h2 style={{fontSize:"1.05rem",fontWeight:600,marginBottom:8}}>Notifications</h2>
        <p style={{fontSize:13,color:"var(--text3)",lineHeight:1.6}}>
          Coming soon — Slack notifications when employees complete categories, weekly digest of who is behind, milestone alerts. Wire via n8n.
        </p>
      </div>
    </>}
  </>);
}
