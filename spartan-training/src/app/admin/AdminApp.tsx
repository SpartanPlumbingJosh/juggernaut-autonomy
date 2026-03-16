"use client";
import { useState, useEffect, useCallback } from "react";

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

const CSS = `@import url('https://fonts.googleapis.com/css2?family=Archivo+Black&family=Barlow+Condensed:wght@400;500;600;700&family=Barlow:wght@400;500;600&display=swap');
:root{--black:#0a0a0a;--card:#111;--border:#222;--border2:#333;--gold:#c8a84e;--red:#b91c1c;--text:#e8e8e8;--text2:#888;--text3:#555;--green:#22c55e}
.adm{font-family:'Barlow',sans-serif;color:var(--text);max-width:1100px;margin:0 auto;padding:0 16px 80px}
.adm h1{font-family:'Archivo Black',sans-serif;font-size:1.6rem;color:var(--gold);letter-spacing:1px;margin:24px 0 4px}
.adm-sub{color:var(--text3);font-size:14px;margin:0 0 24px}
.adm-tabs{display:flex;gap:0;border-bottom:2px solid var(--border);margin-bottom:24px}
.adm-tab{padding:12px 24px;font-family:'Barlow Condensed',sans-serif;font-size:15px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:var(--text3);background:none;border:none;cursor:pointer;position:relative;transition:color .15s}
.adm-tab:hover{color:var(--text2)}
.adm-tab.on{color:var(--gold)}
.adm-tab.on::after{content:'';position:absolute;bottom:-2px;left:0;right:0;height:2px;background:var(--gold)}
@media(max-width:640px){.adm-tab{padding:10px 14px;font-size:13px}}
.adm-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px 24px;margin-bottom:16px}
.adm-card h3{font-family:'Archivo Black',sans-serif;font-size:13px;color:var(--text2);letter-spacing:2px;text-transform:uppercase;margin:0 0 16px}
.adm-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:24px}
.adm-stat{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px;text-align:center}
.adm-stat-n{font-family:'Archivo Black',sans-serif;font-size:1.8rem;color:var(--gold);line-height:1}
.adm-stat-l{font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:1px;margin-top:4px}
.adm-tbl{width:100%;border-collapse:collapse;font-size:13px}
.adm-tbl th{text-align:left;padding:8px 10px;color:var(--text3);font-family:'Barlow Condensed',sans-serif;font-weight:600;text-transform:uppercase;letter-spacing:1px;font-size:11px;border-bottom:1px solid var(--border)}
.adm-tbl td{padding:10px;border-bottom:1px solid var(--border);vertical-align:middle}
.adm-tbl tr:hover td{background:rgba(255,255,255,0.02)}
.adm-pbar{width:100%;height:6px;border-radius:3px;background:var(--border2);overflow:hidden;min-width:60px}
.adm-pfill{height:100%;border-radius:3px;background:linear-gradient(90deg,var(--red),var(--gold));transition:width .5s}
.adm-badge{display:inline-block;padding:2px 10px;border-radius:4px;font-size:11px;font-weight:600;font-family:'Barlow Condensed',sans-serif;letter-spacing:.5px;text-transform:uppercase}
.adm-badge.active{background:rgba(34,197,94,.15);color:var(--green)}
.adm-badge.inactive{background:rgba(239,68,68,.15);color:#ef4444}
.adm-badge.admin{background:rgba(200,168,78,.15);color:var(--gold)}
.adm-form{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:640px){.adm-form{grid-template-columns:1fr}}
.adm-fg{display:flex;flex-direction:column;gap:4px}
.adm-fg.full{grid-column:1/-1}
.adm-fg label{font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:1px;font-weight:600;font-family:'Barlow Condensed',sans-serif}
.adm-fg input,.adm-fg select{padding:10px 12px;border:1px solid var(--border2);border-radius:6px;background:var(--black);color:var(--text);font-size:14px;font-family:inherit;outline:none;transition:border-color .15s}
.adm-fg input:focus,.adm-fg select:focus{border-color:var(--gold)}
.adm-btn{padding:10px 20px;border:none;border-radius:6px;font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:14px;letter-spacing:1px;text-transform:uppercase;cursor:pointer;transition:all .15s}
.adm-btn.primary{background:var(--red);color:#fff}
.adm-btn.primary:hover{background:#d32f2f;transform:translateY(-1px)}
.adm-btn.ghost{background:none;border:1px solid var(--border2);color:var(--text2)}
.adm-btn.ghost:hover{border-color:var(--gold);color:var(--gold)}
.adm-btn.sm{padding:5px 12px;font-size:12px}
.adm-btn:disabled{opacity:.5;cursor:not-allowed}
.adm-toggle{display:flex;align-items:center;gap:8px;cursor:pointer}
.adm-toggle-track{width:36px;height:20px;border-radius:10px;background:var(--border2);position:relative;transition:background .2s}
.adm-toggle-track.on{background:var(--gold)}
.adm-toggle-knob{width:16px;height:16px;border-radius:50%;background:#fff;position:absolute;top:2px;left:2px;transition:left .2s}
.adm-toggle-track.on .adm-toggle-knob{left:18px}
.adm-login{min-height:60vh;display:flex;align-items:center;justify-content:center}
.adm-login-box{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:40px;text-align:center;max-width:380px;width:100%;position:relative;overflow:hidden}
.adm-login-box::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--red),var(--gold))}
.adm-login-box h2{font-family:'Archivo Black',sans-serif;font-size:1.3rem;color:var(--gold);margin:0 0 4px}
.adm-login-box p{color:var(--text3);font-size:13px;margin:0 0 20px}
.adm-toast{position:fixed;top:60px;right:24px;background:var(--gold);color:var(--black);padding:10px 24px;border-radius:8px;font-weight:700;font-size:13px;z-index:600;font-family:'Barlow Condensed',sans-serif;letter-spacing:.5px;animation:adm-slide .3s ease}
@keyframes adm-slide{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:translateY(0)}}
.adm-detail{border-left:3px solid var(--gold);padding-left:16px;margin:12px 0}
.adm-detail-row{display:flex;gap:8px;padding:4px 0;font-size:13px}
.adm-detail-row span:first-child{color:var(--text3);min-width:100px;font-weight:500}
.adm-filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.adm-chip{padding:5px 14px;border-radius:20px;font-size:12px;font-weight:600;border:1px solid var(--border2);background:none;color:var(--text2);cursor:pointer;font-family:'Barlow Condensed',sans-serif;letter-spacing:.5px;text-transform:uppercase;transition:all .15s}
.adm-chip.on{border-color:var(--gold);color:var(--gold);background:rgba(200,168,78,.1)}`;

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

  useEffect(() => {
    const s = typeof window !== "undefined" ? sessionStorage.getItem("sa_admin") : null;
    if (s) { setAdminEmail(s); loadData(s); loadTemplates(s); }
  }, [loadData, loadTemplates]);

  async function handleLogin() {
    if (!adminEmail || !pin) { setLoginError("Enter email and PIN"); return; }
    setLoginError("");
    const res = await fetch("/api/onboard/auth", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: adminEmail, pin }) });
    if (!res.ok) { setLoginError("Invalid credentials"); return; }
    const emp = await res.json();
    if (!emp.id) { setLoginError("Invalid credentials"); return; }
    sessionStorage.setItem("sa_admin", adminEmail);
    await loadData(adminEmail); await loadTemplates(adminEmail);
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
    const d = await res.json();
    if (d.ok) { notify("Updated"); loadData(adminEmail); }
  }

  async function deactivateEmployee(id: string) {
    if (!confirm("Deactivate this employee?")) return;
    const res = await fetch(`/api/admin/employee?admin_email=${encodeURIComponent(adminEmail)}&id=${id}`, { method: "DELETE" });
    if (res.ok) { notify("Deactivated"); setSelectedEmp(null); loadData(adminEmail); }
  }

  async function resetPin(id: string) {
    const newPin = String(100000 + Math.floor(Math.random() * 900000));
    await updateEmployee(id, { pin_code: newPin });
    notify(`New PIN: ${newPin}`);
  }

  if (!authed) return (<><style>{CSS}</style>
    <div className="adm"><div className="adm-login"><div className="adm-login-box">
      <h2>ADMIN ACCESS</h2><p>Spartan Academy management</p>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <input style={{ padding: "12px 14px", border: "1px solid var(--border2)", borderRadius: 6, background: "var(--black)", color: "var(--text)", fontSize: 14, fontFamily: "inherit", outline: "none" }}
          placeholder="admin email" value={adminEmail} onChange={e => setAdminEmail(e.target.value)} onKeyDown={e => e.key === "Enter" && document.getElementById("admin-pin")?.focus()} />
        <input id="admin-pin" type="password" maxLength={6} style={{ padding: "12px 14px", border: "1px solid var(--border2)", borderRadius: 6, background: "var(--black)", color: "var(--text)", fontSize: 14, fontFamily: "inherit", outline: "none" }}
          placeholder="6-digit PIN" value={pin} onChange={e => setPin(e.target.value.replace(/\D/g, ""))} onKeyDown={e => e.key === "Enter" && handleLogin()} />
        <button className="adm-btn primary" onClick={handleLogin} style={{ width: "100%", padding: 14 }}>Enter</button>
        {loginError && <div style={{ color: "#f87171", fontSize: 13, textAlign: "center" }}>{loginError}</div>}
      </div>
    </div></div></div></>);

  const active = employees.filter(e => e.status === "active");
  const admins = employees.filter(e => e.is_admin);
  const avgPct = active.length ? Math.round(active.reduce((s, e) => { const p = progressMap[e.id]; return s + (p ? Math.round(100 * p.done / (p.total || 1)) : 0); }, 0) / active.length) : 0;
  const behind = active.filter(e => { const p = progressMap[e.id]; return p && p.total > 0 && (100 * p.done / p.total) < 50; }).length;
  const filteredEmp = roleFilter ? employees.filter(e => e.role === roleFilter) : employees;
  const filteredTemplates = templates.filter(t => taskRoleFilter === "all" || t.role === taskRoleFilter);
  const taskCategories = [...new Set(filteredTemplates.map(t => t.category))];

  return (<><style>{CSS}</style>
    {toast && <div className="adm-toast">{toast}</div>}
    <div className="adm">
      <h1>SPARTAN COMMAND CENTER</h1>
      <p className="adm-sub">Academy administration — manage people, tasks, and settings</p>

      <div className="adm-tabs">
        {(["team", "add", "tasks", "settings"] as const).map(t => (
          <button key={t} className={`adm-tab${tab === t ? " on" : ""}`} onClick={() => setTab(t)}>
            {t === "team" ? "Team" : t === "add" ? "Add Person" : t === "tasks" ? "Tasks" : "Settings"}
          </button>
        ))}
      </div>

      {tab === "team" && <>
        <div className="adm-stats">
          <div className="adm-stat"><div className="adm-stat-n">{active.length}</div><div className="adm-stat-l">Active</div></div>
          <div className="adm-stat"><div className="adm-stat-n">{admins.length}</div><div className="adm-stat-l">Admins</div></div>
          <div className="adm-stat"><div className="adm-stat-n">{avgPct}%</div><div className="adm-stat-l">Avg Progress</div></div>
          <div className="adm-stat"><div className="adm-stat-n" style={{ color: behind > 0 ? "#ef4444" : "var(--green)" }}>{behind}</div><div className="adm-stat-l">Behind (&lt;50%)</div></div>
        </div>

        <div className="adm-filters">
          <button className={`adm-chip${!roleFilter ? " on" : ""}`} onClick={() => setRoleFilter("")}>All</button>
          {ROLES.map(r => <button key={r.value} className={`adm-chip${roleFilter === r.value ? " on" : ""}`} onClick={() => setRoleFilter(roleFilter === r.value ? "" : r.value)}>{r.label}</button>)}
        </div>

        <div className="adm-card" style={{ padding: 0, overflow: "auto" }}>
          <table className="adm-tbl"><thead><tr><th>Name</th><th>Role</th><th>Progress</th><th>XP</th><th>Status</th><th>Last Active</th><th></th></tr></thead>
            <tbody>{filteredEmp.map(e => {
              const p = progressMap[e.id] || { total: 0, done: 0, totalXp: 0, earnedXp: 0 };
              const pct = p.total > 0 ? Math.round(100 * p.done / p.total) : 0;
              return (<tr key={e.id} style={{ cursor: "pointer" }} onClick={() => setSelectedEmp(selectedEmp?.id === e.id ? null : e)}>
                <td><div style={{ fontWeight: 600 }}>{e.name}</div><div style={{ fontSize: 11, color: "var(--text3)" }}>{e.email}</div></td>
                <td><span style={{ fontSize: 12, color: "var(--text2)" }}>{ROLES.find(r => r.value === e.role)?.label || e.role}</span></td>
                <td><div style={{ display: "flex", alignItems: "center", gap: 8 }}><div className="adm-pbar"><div className="adm-pfill" style={{ width: `${pct}%` }} /></div><span style={{ fontSize: 12, fontWeight: 700, color: pct === 100 ? "var(--green)" : "var(--gold)", minWidth: 32 }}>{pct}%</span></div><div style={{ fontSize: 11, color: "var(--text3)" }}>{p.done}/{p.total}</div></td>
                <td style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700, color: "var(--gold)" }}>{p.earnedXp || 0}</td>
                <td><span className={`adm-badge ${e.status}`}>{e.status}</span>{e.is_admin && <span className="adm-badge admin" style={{ marginLeft: 4 }}>admin</span>}</td>
                <td style={{ fontSize: 12, color: "var(--text3)" }}>{e.last_activity_at ? new Date(e.last_activity_at).toLocaleDateString() : "—"}</td>
                <td><button className="adm-btn ghost sm" onClick={ev => { ev.stopPropagation(); setSelectedEmp(e); }}>Edit</button></td>
              </tr>);
            })}{filteredEmp.length === 0 && <tr><td colSpan={7} style={{ textAlign: "center", padding: 40, color: "var(--text3)" }}>No employees found</td></tr>}</tbody>
          </table>
        </div>

        {selectedEmp && <div className="adm-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
            <h3 style={{ margin: 0 }}>{selectedEmp.name}</h3>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              <button className="adm-btn ghost sm" onClick={() => resetPin(selectedEmp.id)}>Reset PIN</button>
              <button className="adm-btn ghost sm" onClick={() => updateEmployee(selectedEmp.id, { is_admin: !selectedEmp.is_admin })}>{selectedEmp.is_admin ? "Remove Admin" : "Make Admin"}</button>
              <button className="adm-btn sm" style={{ background: "#ef4444", color: "#fff" }} onClick={() => deactivateEmployee(selectedEmp.id)}>Deactivate</button>
              <button className="adm-btn ghost sm" onClick={() => setSelectedEmp(null)}>Close</button>
            </div>
          </div>
          <div className="adm-detail">
            <div className="adm-detail-row"><span>Email</span><span>{selectedEmp.email}</span></div>
            <div className="adm-detail-row"><span>Phone</span><span>{selectedEmp.phone || "—"}</span></div>
            <div className="adm-detail-row"><span>Position</span><span>{selectedEmp.position || "—"}</span></div>
            <div className="adm-detail-row"><span>Role</span><span>{ROLES.find(r => r.value === selectedEmp.role)?.label || selectedEmp.role}</span></div>
            <div className="adm-detail-row"><span>Hire Date</span><span>{selectedEmp.hire_date ? new Date(selectedEmp.hire_date).toLocaleDateString() : "—"}</span></div>
            <div className="adm-detail-row"><span>Manager</span><span>{selectedEmp.manager_name || "None assigned"}</span></div>
            <div className="adm-detail-row"><span>PIN</span><span style={{ fontFamily: "monospace", color: "var(--gold)" }}>{selectedEmp.pin_code}</span></div>
            <div className="adm-detail-row"><span>30-Day</span><span>{selectedEmp.due_30_date || "—"}</span></div>
            <div className="adm-detail-row"><span>60-Day</span><span>{selectedEmp.due_60_date || "—"}</span></div>
            <div className="adm-detail-row"><span>90-Day</span><span>{selectedEmp.due_90_date || "—"}</span></div>
          </div>
        </div>}
      </>}

      {tab === "add" && <div className="adm-card">
        <h3>Add New Employee</h3>
        <div className="adm-form">
          <div className="adm-fg"><label>Full Name *</label><input value={af.name} onChange={e => setAf({ ...af, name: e.target.value })} placeholder="Nick Hernandez" /></div>
          <div className="adm-fg"><label>Work Email *</label><input value={af.email} onChange={e => setAf({ ...af, email: e.target.value })} placeholder="nick@spartan-plumbing.com" /></div>
          <div className="adm-fg"><label>Role *</label><select value={af.role} onChange={e => setAf({ ...af, role: e.target.value })}>{ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}</select></div>
          <div className="adm-fg"><label>Position</label><input value={af.position} onChange={e => setAf({ ...af, position: e.target.value })} placeholder="Install Technician" /></div>
          <div className="adm-fg"><label>Hire Date</label><input type="date" value={af.hire_date} onChange={e => setAf({ ...af, hire_date: e.target.value })} /></div>
          <div className="adm-fg"><label>Phone</label><input value={af.phone} onChange={e => setAf({ ...af, phone: e.target.value })} placeholder="937-555-0123" /></div>
          <div className="adm-fg"><label>Personal Email</label><input value={af.personal_email} onChange={e => setAf({ ...af, personal_email: e.target.value })} /></div>
          <div className="adm-fg"><label>Manager</label><select value={af.manager_id} onChange={e => setAf({ ...af, manager_id: e.target.value })}><option value="">None</option>{employees.filter(e => e.is_admin || e.role === "leadership").map(e => <option key={e.id} value={e.id}>{e.name}</option>)}</select></div>
          <div className="adm-fg" style={{ justifyContent: "center" }}><label>&nbsp;</label>
            <div className="adm-toggle" onClick={() => setAf({ ...af, is_admin: !af.is_admin })}>
              <div className={`adm-toggle-track${af.is_admin ? " on" : ""}`}><div className="adm-toggle-knob" /></div>
              <span style={{ fontSize: 13, color: af.is_admin ? "var(--gold)" : "var(--text3)" }}>Admin Access</span>
            </div>
          </div>
          <div className="adm-fg full" style={{ flexDirection: "row", justifyContent: "flex-end", gap: 8, marginTop: 8 }}>
            <button className="adm-btn ghost" onClick={() => setAf({ name: "", email: "", role: "tech", position: "", hire_date: "", phone: "", personal_email: "", is_admin: false, manager_id: "" })}>Clear</button>
            <button className="adm-btn primary" onClick={addEmployee} disabled={!af.name || !af.email}>Add Employee</button>
          </div>
        </div>
        <div style={{ marginTop: 16, padding: "12px 16px", background: "rgba(200,168,78,.08)", borderRadius: 8, fontSize: 13, color: "var(--text2)", lineHeight: 1.5 }}>
          A 6-digit PIN will be auto-generated. The employee uses their work email + PIN to log into Spartan Academy. Their role determines which onboarding tasks they see.
        </div>
      </div>}

      {tab === "tasks" && <>
        <div className="adm-filters" style={{ marginBottom: 16 }}>
          {["all", ...ROLES.map(r => r.value)].map(r => (
            <button key={r} className={`adm-chip${taskRoleFilter === r ? " on" : ""}`} onClick={() => setTaskRoleFilter(r)}>
              {r === "all" ? "All Roles" : ROLES.find(x => x.value === r)?.label || r}
            </button>
          ))}
        </div>
        <div style={{ fontSize: 13, color: "var(--text3)", marginBottom: 16 }}>{filteredTemplates.length} tasks across {taskCategories.length} categories — {filteredTemplates.reduce((s, t) => s + t.xp_value, 0)} total XP</div>
        {taskCategories.map(cat => (
          <div key={cat} className="adm-card">
            <h3>{cat} <span style={{ color: "var(--gold)", fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}>({filteredTemplates.filter(t => t.category === cat).length})</span></h3>
            <table className="adm-tbl"><thead><tr><th>#</th><th>Task</th><th>Role</th><th>XP</th><th>Manager?</th></tr></thead>
              <tbody>{filteredTemplates.filter(t => t.category === cat).map(t => (
                <tr key={t.id}>
                  <td style={{ color: "var(--text3)", fontSize: 11 }}>{t.sort_order}</td>
                  <td><div style={{ fontWeight: 500 }}>{t.title}</div>{t.description && <div style={{ fontSize: 11, color: "var(--text3)", marginTop: 2 }}>{t.description.substring(0, 80)}{t.description.length > 80 ? "..." : ""}</div>}</td>
                  <td style={{ fontSize: 12, color: "var(--text2)" }}>{t.role}</td>
                  <td style={{ fontWeight: 700, color: "var(--gold)", fontFamily: "'Barlow Condensed', sans-serif" }}>{t.xp_value}</td>
                  <td>{t.requires_manager_approval ? <span style={{ color: "var(--gold)" }}>Yes</span> : <span style={{ color: "var(--text3)" }}>No</span>}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ))}
      </>}

      {tab === "settings" && <>
        <div className="adm-card"><h3>Account</h3>
          <div className="adm-detail"><div className="adm-detail-row"><span>Logged in as</span><span>{adminEmail}</span></div><div className="adm-detail-row"><span>Role</span><span>Administrator</span></div></div>
          <button className="adm-btn ghost" style={{ marginTop: 12 }} onClick={() => { sessionStorage.removeItem("sa_admin"); setAuthed(false); }}>Sign Out</button>
        </div>
        <div className="adm-card"><h3>Quick Actions</h3>
          <button className="adm-btn ghost" onClick={() => { loadData(adminEmail); loadTemplates(adminEmail); notify("Data refreshed"); }} disabled={loading}>{loading ? "Refreshing..." : "Refresh All Data"}</button>
        </div>
        <div className="adm-card"><h3>System Info</h3>
          <div className="adm-detail">
            <div className="adm-detail-row"><span>Total employees</span><span>{employees.length}</span></div>
            <div className="adm-detail-row"><span>Active</span><span>{active.length}</span></div>
            <div className="adm-detail-row"><span>Templates</span><span>{templates.length} tasks</span></div>
            <div className="adm-detail-row"><span>SOP Cards</span><span>282 across 7 boards</span></div>
            <div className="adm-detail-row"><span>Database</span><span>Supabase (knowledge_lake)</span></div>
          </div>
        </div>
        <div className="adm-card"><h3>Milestones</h3>
          <div style={{ fontSize: 13, color: "var(--text2)", lineHeight: 1.6 }}>New hires get automatic 30/60/90 day milestone dates based on hire date.</div>
          <div className="adm-detail" style={{ marginTop: 12 }}>
            <div className="adm-detail-row"><span>30-Day</span><span>Pre-employment + Accounts complete</span></div>
            <div className="adm-detail-row"><span>60-Day</span><span>All training modules complete</span></div>
            <div className="adm-detail-row"><span>90-Day</span><span>Full readiness — all tasks done</span></div>
          </div>
        </div>
        <div className="adm-card"><h3>Notifications (Coming Soon)</h3>
          <div style={{ fontSize: 13, color: "var(--text3)", lineHeight: 1.6 }}>Slack notifications when employees complete categories, weekly digest of who is behind, and milestone alerts. Wire via n8n.</div>
        </div>
      </>}
    </div>
  </>);
}
