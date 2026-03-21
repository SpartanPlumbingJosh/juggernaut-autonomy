'use client';
import { useEffect, useState, useCallback } from 'react';
import MaterialsTab from './MaterialsTab';
import ServiceTab from './ServiceTab';
import SalesTab from './SalesTab';
import InstallTab from './InstallTab';
import PostInstallTab from './PostInstallTab';
import CallsTab from './CallsTab';
import IntelTab from './IntelTab';
import FinancialsTab from './FinancialsTab';
import VerifyTab from './VerifyTab';
import PermitsTab from './PermitsTab';
import CardsTab from './CardsTab';
import BlockersTab from './BlockersTab';

/* ── Types ─────────────────────────────────────────── */

export interface JobData {
  job: Record<string, any>;
  relatedJobs: any[];
  verifications: any[];
  appointments: any[];
  invoices: any[];
  payments: any[];
  estimates: any[];
  assignments: any[];
  contacts: any[];
  unsoldEstimates: any[];
  recallsAtLocation: any[];
  calls: any[];
  recallJobs: any[];
  callScripts: any[];
  materialList: any | null;
  catalogImages: Record<string, string>;
  purchaseOrders: any[];
  verificationDefs: any[];
  companyAverages: any[];
  playbook: { serviceKey: string; salesKey: string; phoneCloseKey: string; steps: any[]; tracking: any[] };
  permits: any[];
  permitRules: any[];
  cardRequests: any[];
  blockers: any[];
  jobMedia: any[];
}

interface TeamMember { name: string; role: string | null; slack_member_id: string | null; }

/* ── Helpers ───────────────────────────────────────── */

export function fmt(d: string | null | undefined): string {
  if (!d) return '\u2014';
  try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); } catch { return d; }
}

export function fmtTime(d: string | null | undefined): string {
  if (!d) return '\u2014';
  try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }); } catch { return d; }
}

export function money(n: number | string | null | undefined): string {
  const v = parseFloat(String(n || 0));
  return v > 0 ? '$' + v.toLocaleString(undefined, { maximumFractionDigits: 0 }) : '\u2014';
}

export function moneyExact(n: number | string | null | undefined): string {
  const v = parseFloat(String(n || 0));
  return v > 0 ? '$' + v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '\u2014';
}

export function stripHtml(html: string): string {
  if (!html) return '';
  return html
    .replace(/<br\s*\/?>/gi, '\n').replace(/<\/li>/gi, '\n').replace(/<\/p>/gi, '\n')
    .replace(/<[^>]+>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    .replace(/&middot;/g, '\u00b7').replace(/\n{3,}/g, '\n\n').trim();
}

export function isInstallTrack(buName: string | null | undefined): boolean {
  const bu = (buName || '').toLowerCase();
  return bu.includes('replacement') || bu.includes('whole house');
}

/* ── Icons ─────────────────────────────────────────── */

const ICONS: Record<string, string> = {
  flag: '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/>',
  search: '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
  play: '<polygon points="5 3 19 12 5 21 5 3"/>',
  dollar: '<line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/>',
  box: '<path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>',
  clipboard: '<path d="M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/>',
  creditcard: '<rect x="1" y="4" width="22" height="16" rx="2"/><line x1="1" y1="10" x2="23" y2="10"/>',
  wrench: '<path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/>',
  chart: '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
  star: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
  alert: '<path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  phone: '<path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.12.96.36 1.9.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.91.34 1.85.58 2.81.7A2 2 0 0122 16.92z"/>',
  chevronRight: '<polyline points="9 18 15 12 9 6"/>',
  chevronLeft: '<polyline points="15 18 9 12 15 6"/>',
  sun: '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>',
  moon: '<path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>',
  user: '<path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/>',
};

export function Icon({ name, size = 17 }: { name: string; size?: number }) {
  return <svg width={size} height={size} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round" dangerouslySetInnerHTML={{ __html: ICONS[name] || '' }} />;
}

/* ── Tab Config ────────────────────────────────────── */

const TABS = [
  { id: 'dashboard', icon: 'flag', label: 'Dashboard', color: 'fire', num: '' },
  { id: 'intel', icon: 'search', label: 'Customer Intel', color: 'ice', num: '1' },
  { id: 'service', icon: 'play', label: 'Service Process', color: 'volt', num: '2' },
  { id: 'sales', icon: 'dollar', label: 'Sales Process', color: 'fire', num: '3' },
  { id: 'materials', icon: 'box', label: 'Materials', color: 'mint', num: '4' },
  { id: 'permits', icon: 'clipboard', label: 'Permits', color: 'amber', num: '5' },
  { id: 'cards', icon: 'creditcard', label: 'Purchasing Cards', color: 'grape', num: '6' },
  { id: 'install', icon: 'wrench', label: 'Install', color: 'volt', num: '7' },
  { id: 'financials', icon: 'chart', label: 'Financials', color: 'fire', num: '8' },
  { id: 'postinstall', icon: 'star', label: 'Post-Install', color: 'mint', num: '9' },
  { id: 'blockers', icon: 'alert', label: 'Blockers & Risk', color: 'amber', num: '10' },
  { id: 'verify', icon: 'shield', label: 'Verification', color: 'hot', num: '11' },
  { id: 'calls', icon: 'phone', label: 'Calls & Scripts', color: 'ice', num: '12' },
] as const;

/* ── User Picker Modal ────────────────────────────── */

function UserPicker({ onSelect }: { onSelect: (name: string) => void }) {
  const [roster, setRoster] = useState<TeamMember[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/user/roster')
      .then(r => r.json())
      .then(setRoster)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="picker-overlay">
      <div className="picker-card">
        <div className="picker-logo">S</div>
        <h2 className="picker-title">Spartan Job Tracker</h2>
        <p className="picker-desc">Select your name to continue</p>
        {loading ? (
          <div className="picker-loading">Loading team...</div>
        ) : (
          <div className="picker-list">
            {roster.map(u => (
              <button key={u.name} className="picker-btn" onClick={() => onSelect(u.name)}>
                <span className="picker-avatar">{u.name.charAt(0)}</span>
                <span className="picker-name">{u.name}</span>
                {u.role && <span className="picker-role">{u.role.replace(/_/g, ' ')}</span>}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Main Component ────────────────────────────────── */

export default function JTClient({ jobNumber }: { jobNumber: string }) {
  const [data, setData] = useState<JobData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('dashboard');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [currentUser, setCurrentUser] = useState<string | null>(null);
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [showPicker, setShowPicker] = useState(false);

  // Load saved user from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('jt_user');
    if (saved) {
      setCurrentUser(saved);
    } else {
      setShowPicker(true);
    }
  }, []);

  // When user is set, fetch their theme preference
  useEffect(() => {
    if (!currentUser) return;
    fetch(`/api/user/preferences?user=${encodeURIComponent(currentUser)}`)
      .then(r => r.json())
      .then(pref => {
        const t = pref.theme === 'light' ? 'light' : 'dark';
        setTheme(t);
        document.documentElement.dataset.theme = t;
      })
      .catch(() => {});
  }, [currentUser]);

  // Apply theme to DOM whenever it changes
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  // Fetch job data
  useEffect(() => {
    fetch(`/api/job/${jobNumber}`)
      .then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); })
      .then(setData).catch(e => setError(e.message)).finally(() => setLoading(false));
  }, [jobNumber]);

  const handleUserSelect = useCallback((name: string) => {
    localStorage.setItem('jt_user', name);
    setCurrentUser(name);
    setShowPicker(false);
  }, []);

  const toggleTheme = useCallback(() => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    document.documentElement.dataset.theme = next;
    if (currentUser) {
      fetch('/api/user/preferences', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_name: currentUser, theme: next }),
      }).catch(() => {});
    }
  }, [theme, currentUser]);

  const switchUser = useCallback(() => {
    setShowPicker(true);
  }, []);

  // Show user picker
  if (showPicker) {
    return <UserPicker onSelect={handleUserSelect} />;
  }

  if (loading) return <div className="loading-screen">Loading job data...</div>;
  if (error || !data?.job) return <div className="loading-screen">Error: {error || 'Job not found'} (#{jobNumber})</div>;

  const job = data.job;
  const amt = parseFloat(job.total) || 0;
  const verifs = data.verifications || [];
  const passed = verifs.filter(v => v.result === 'pass').length;
  const failed = verifs.filter(v => v.result === 'fail').length;
  const total = verifs.length;
  const score = total > 0 ? Math.round((passed / total) * 100) : 0;
  const invoices = data.invoices || [];
  const payments = data.payments || [];
  const invTotal = invoices.reduce((s: number, i: any) => s + (parseFloat(i.total) || 0), 0);
  const paidTotal = payments.reduce((s: number, p: any) => s + (parseFloat(p.total) || 0), 0);
  const install = isInstallTrack(job.business_unit_name);

  const events = [
    { dot: 'fire', title: `Job ${job.status || 'Created'}`, time: fmt(job.created_on), src: 'ServiceTitan', detail: `${job.business_unit_name || ''} \u00b7 ${job.job_type_name || ''} \u00b7 ${money(amt)}` },
    ...(data.appointments || []).slice(0, 2).map((a: any) => ({ dot: 'volt', title: `Appointment ${a.status}`, time: fmt(a.start_time), src: 'ServiceTitan', detail: '' })),
    ...invoices.slice(0, 2).map((i: any) => ({ dot: 'mint', title: `Invoice ${i.reference_number || i.st_invoice_id}`, time: fmt(i.invoice_date), src: 'ST Accounting', detail: `Total: ${money(i.total)}` })),
    ...payments.slice(0, 2).map((p: any) => ({ dot: 'grape', title: `Payment \u2014 ${p.payment_type || ''}`, time: fmt(p.payment_date), src: 'ST Payments', detail: money(p.total) })),
    { dot: 'hot', title: `AI Verification: ${score}%`, time: 'Latest', src: 'System', detail: `${passed} passed \u00b7 ${failed} failed \u00b7 ${total - passed - failed} pending` },
  ];

  return (
    <div className={`shell${sidebarOpen ? ' rail-open' : ''}`}>
      <nav className={`rail${sidebarOpen ? ' expanded' : ''}`}>
        <div className="rail-top">
          <div className="rail-logo">S</div>
          {sidebarOpen && <span className="rail-brand">Spartan</span>}
        </div>
        <div className="rail-toggle" onClick={() => setSidebarOpen(!sidebarOpen)}>
          <Icon name={sidebarOpen ? 'chevronLeft' : 'chevronRight'} size={14} />
        </div>
        <div className="rail-items">
          {TABS.map((t, i) => (
            <div key={t.id}>
              {(i === 1 || i === 5 || i === 10) && <div className="rsep" />}
              <div className={`ri${activeTab === t.id ? ' on' : ''}`} onClick={() => setActiveTab(t.id)} title={!sidebarOpen ? (t.num ? t.num + '. ' : '') + t.label : undefined}>
                <Icon name={t.icon} />
                {sidebarOpen && <span className="ri-label">{t.num ? t.num + '. ' : ''}{t.label}</span>}
                {!sidebarOpen && <span className="tip">{t.num ? t.num + '. ' : ''}{t.label}</span>}
              </div>
            </div>
          ))}
        </div>
        <div className="rail-bottom">
          <div className="rsep" />
          <div className="ri" onClick={toggleTheme} title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}>
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
            {sidebarOpen && <span className="ri-label">{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>}
            {!sidebarOpen && <span className="tip">{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>}
          </div>
          <div className="ri ri-user" onClick={switchUser} title={currentUser || 'Switch User'}>
            <Icon name="user" />
            {sidebarOpen && <span className="ri-label">{currentUser}</span>}
            {!sidebarOpen && <span className="tip">{currentUser}</span>}
          </div>
        </div>
      </nav>

      <div className="main">
        {activeTab === 'dashboard' && <Dashboard job={job} data={data} amt={amt} score={score} passed={passed} failed={failed} total={total} invTotal={invTotal} paidTotal={paidTotal} isInstall={install} jobNumber={jobNumber} />}
        {activeTab === 'intel' && <IntelTab job={job} data={data} amt={amt} />}
        {activeTab === 'service' && <ServiceTab job={job} data={data} />}
        {activeTab === 'sales' && <SalesTab job={job} data={data} />}
        {activeTab === 'materials' && <MaterialsTab job={job} data={data} amt={amt} />}
        {activeTab === 'permits' && <PermitsTab job={job} data={data} />}
        {activeTab === 'cards' && <CardsTab job={job} data={data} />}
        {activeTab === 'install' && <InstallTab job={job} data={data} />}
        {activeTab === 'financials' && <FinancialsTab job={job} data={data} amt={amt} invTotal={invTotal} paidTotal={paidTotal} />}
        {activeTab === 'postinstall' && <PostInstallTab job={job} data={data} />}
        {activeTab === 'blockers' && <BlockersTab job={job} data={data} />}
        {activeTab === 'verify' && <VerifyTab data={data} score={score} passed={passed} failed={failed} total={total} />}
        {activeTab === 'calls' && <CallsTab job={job} data={data} />}
      </div>

      <aside className="panel">
        <div className="panel-h"><h2>Activity</h2><div className="live">Live</div></div>
        <div className="panel-f">
          {events.map((e, i) => (
            <div className="act" key={i}>
              <div className={`act-d ${e.dot}`} />
              <div className="act-b">
                <div className="act-t">{e.title}</div>
                <div className="act-m"><span>{e.time}</span><span>{e.src}</span></div>
                {e.detail && <div className="act-box">{e.detail}</div>}
              </div>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}

/* ── Dashboard Sub-Component ───────────────────────── */

function VR({ dot, k, v, style }: { dot: string; k: string; v: string; style?: React.CSSProperties }) {
  return <div className="vr"><div className={`ai-dot ${dot}`} /><span className="k">{k}</span><span className="v" style={style}>{v}</span></div>;
}

function Dashboard({ job, data, amt, score, passed, failed, total, invTotal, paidTotal, isInstall, jobNumber }: any) {
  const pending = total - passed - failed;
  const scoreColor = score >= 80 ? 'var(--mint)' : score >= 60 ? 'var(--amber)' : 'var(--fire)';
  const okDeg = total > 0 ? (passed / total) * 360 : 0;
  const failDeg = total > 0 ? okDeg + (failed / total) * 360 : 0;
  const stages = ['Job Sold', 'Contact', 'Pre-Install', 'Day Before', 'Install', 'Post-Install'];
  const stageIdx = job.status === 'Completed' ? 5 : job.status === 'InProgress' ? 4 : 0;

  return <>
    <div className="top">
      <div className="top-l">
        <div className="crumb">Jobs / #{jobNumber} / Tracker</div>
        <h1><span className="n">#{jobNumber}</span> {job.customer_name || 'Unknown'}</h1>
        <div className="sub">{job.job_type_name || ''} &middot; {job.business_unit_name || ''} &middot; {fmt(job.created_on)}</div>
      </div>
      <div className="pills">
        {job.status === 'Completed' && <div className="pill p-sold">Completed</div>}
        {job.status === 'Scheduled' && <div className="pill p-svc">Scheduled</div>}
        {job.status === 'InProgress' && <div className="pill p-svc">In Progress</div>}
        {job.status === 'Canceled' && <div className="pill p-cancel">Canceled</div>}
        {isInstall ? <div className="pill p-inst">Install</div> : <div className="pill p-svc">Service</div>}
      </div>
    </div>
    <div className="ai-sum">
      <div className="ai-ring" style={{ background: `conic-gradient(var(--mint) 0deg, var(--mint) ${okDeg}deg, var(--fire) ${okDeg}deg, var(--fire) ${failDeg}deg, var(--t4) ${failDeg}deg)` }}>
        <div className="ai-ring-inner"><span className="pct" style={{ color: scoreColor }}>{score}%</span></div>
      </div>
      <div className="ai-stats">
        <div className="ai-s"><div className="ai-s-n" style={{ color: 'var(--mint)' }}>{passed}</div><div className="ai-s-l" style={{ color: 'var(--mint2)' }}>Verified</div></div>
        <div className="ai-s"><div className="ai-s-n" style={{ color: 'var(--fire)' }}>{failed}</div><div className="ai-s-l" style={{ color: 'var(--fire2)' }}>Failed</div></div>
        {pending > 0 && <div className="ai-s"><div className="ai-s-n" style={{ color: 'var(--t3)' }}>{pending}</div><div className="ai-s-l" style={{ color: 'var(--t3)' }}>Pending</div></div>}
      </div>
    </div>
    <div className="hero">
      <div className="st sf"><div className="ai ai-ok" /><div className="num">{money(amt)}</div><div className="lbl">Sale Amount</div></div>
      <div className="st sv"><div className="ai ai-ok" /><div className="num">{money(invTotal)}</div><div className="lbl">Invoiced</div></div>
      <div className="st sm"><div className="ai ai-ok" /><div className="num">{money(paidTotal)}</div><div className="lbl">Paid</div></div>
      <div className="st sg"><div className="num" style={{ fontSize: 18 }}>{job.status || '\u2014'}</div><div className="lbl">Status</div></div>
    </div>
    <div className="pipe-wrap">
      <div className="pipe-top"><h2>Job Lifecycle</h2><div className="step">Stage {stageIdx + 1} / 6</div></div>
      <div className="pipe">
        {stages.map((s, i) => {
          const cls = i < stageIdx ? 'done' : i === stageIdx ? 'now' : 'w';
          return <div className={`pn ${cls}`} key={s}><div className={`pb ${cls}`} /><div className="pt">{s}</div></div>;
        })}
      </div>
    </div>
    <div className="g2">
      <div className="c"><div className="ch"><h3>Customer</h3></div><div className="cb">
        <VR dot="ai-ok" k="Name" v={job.customer_name || '\u2014'} />
        <VR dot="ai-ok" k="Job #" v={`#${jobNumber}`} style={{ fontFamily: 'var(--mono)', color: 'var(--ice)' }} />
        <VR dot="ai-ok" k="Address" v={job.customer_address || '\u2014'} />
        <VR dot="ai-ok" k="Created" v={fmt(job.created_on)} />
        <VR dot={job.completed_on ? 'ai-ok' : 'ai-wait'} k="Completed" v={fmt(job.completed_on)} />
      </div></div>
      <div className="c"><div className="ch"><h3>Verification Checks</h3></div><div className="cb">
        {(data.verifications || []).slice(0, 8).map((v: any, i: number) => {
          const dot = v.result === 'pass' ? 'ai-ok' : v.result === 'fail' ? 'ai-fail' : 'ai-wait';
          const chip = v.result === 'pass' ? 'c-ok' : v.result === 'fail' ? 'c-fail' : 'c-info';
          const label = v.result === 'pass' ? '\u2713 Verified' : v.result === 'fail' ? '\u2717 Failed' : 'Pending';
          return <div className="vr" key={i}><div className={`ai-dot ${dot}`} /><span className="k">{v.verification_name}</span><span className={`chip ${chip}`}>{label}</span></div>;
        })}
        {(data.verifications || []).length === 0 && <div style={{ color: 'var(--t3)', fontSize: 12 }}>No verifications yet.</div>}
      </div></div>
    </div>
    <div className="c full"><div className="ch"><h3>Work Scope</h3></div><div className="cb">
      <div className="slbl"><div className="ai-dot ai-ok" />Description</div>
      <div className="stxt cv scope-text">{stripHtml(job.summary || 'No scope summary available')}</div>
      <div className="g2" style={{ marginTop: 8, marginBottom: 0 }}>
        <div><div className="slbl"><div className="ai-dot ai-ok" />Job Type</div><div className="stxt cg">{job.job_type_name || '\u2014'}</div></div>
        <div><div className="slbl"><div className="ai-dot ai-ok" />Business Unit</div><div className="stxt ca">{job.business_unit_name || '\u2014'}</div></div>
      </div>
    </div></div>
  </>;
}