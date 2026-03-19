'use client';
import { useEffect, useState } from 'react';
import MaterialsTab from './MaterialsTab';
import ServiceTab from './ServiceTab';
import PostInstallTab from './PostInstallTab';
import CallsTab from './CallsTab';
import IntelTab from './IntelTab';
import SalesTab from './SalesTab';

interface JobData {
  job: Record<string, any> | null;
  relatedJobs: Record<string, any>[];
  verifications: Record<string, any>[];
  appointments: Record<string, any>[];
  invoices: Record<string, any>[];
  payments: Record<string, any>[];
  estimates: Record<string, any>[];
  assignments: Record<string, any>[];
  contacts: Record<string, any>[];
  unsoldEstimates: Record<string, any>[];
  recallsAtLocation: Record<string, any>[];
  [key: string]: any;
}

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
};

function Icon({ name }: { name: string }) {
  return <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round" dangerouslySetInnerHTML={{ __html: ICONS[name] || '' }} />;
}

function fmt(d: string | null | undefined): string {
  if (!d) return '\u2014';
  try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); } catch { return d; }
}
function money(n: number | string | null | undefined): string {
  const v = parseFloat(String(n || 0));
  return v > 0 ? '$' + v.toLocaleString(undefined, { maximumFractionDigits: 0 }) : '\u2014';
}

const TAB_DESCS: Record<string, string> = {
  service: 'Live-scored Rules of the Road checklist \u2014 auto-selects the correct playbook and tracks every step in real-time.',
  sales: 'Sales process scoring from Q3 through Post Game Recap, including 3-day right to cancel enforcement on sales over $3K.',
  materials: 'AI-generated material lists from Lee Supply catalog, tech verification, staging photo verification, and 18% budget tracking.',
  permits: 'Jurisdiction-aware permit tracking with AI cold-start research for new areas and document verification.',
  cards: 'Full purchasing card lifecycle \u2014 Slack trigger detection, response time KPIs, receipt quality AI gate.',
  install: 'Day-of execution tracking with 13 checkpoints, code compliance verification, and hard gates on after photos + walkthrough video.',
  postinstall: 'Happy call SLA tracking (24hr), call scorecards, review monitoring, and recall lifecycle management.',
  blockers: 'Central blocker tracking with automated escalation (30min \u2192 1hr \u2192 2hr), AI-generated timeline risk assessment.',
  calls: '17 preset call scripts with personalization, AI script builder, call recording playback with AI scorecards.',
};

export default function JTClient({ jobNumber }: { jobNumber: string }) {
  const [data, setData] = useState<JobData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('dashboard');
  useEffect(() => {
    fetch(`/api/job/${jobNumber}`)
      .then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); })
      .then(setData).catch(e => setError(e.message)).finally(() => setLoading(false));
  }, [jobNumber]);
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
  const isInstall = (job.business_unit_name || '').toLowerCase().includes('replacement') || (job.business_unit_name || '').toLowerCase().includes('whole house');
  const events = [
    { dot: 'fire', title: `Job ${job.status || 'Created'}`, time: fmt(job.created_on), src: 'ServiceTitan', detail: `${job.business_unit_name || ''} \u00b7 ${job.job_type_name || ''} \u00b7 ${money(amt)}` },
    ...(data.appointments || []).slice(0, 2).map((a: any) => ({ dot: 'volt', title: `Appointment ${a.status}`, time: fmt(a.start_time), src: 'ServiceTitan', detail: '' })),
    ...invoices.slice(0, 2).map((i: any) => ({ dot: 'mint', title: `Invoice ${i.reference_number || i.st_invoice_id}`, time: fmt(i.invoice_date), src: 'ST Accounting', detail: `Total: ${money(i.total)}` })),
    ...payments.slice(0, 2).map((p: any) => ({ dot: 'grape', title: `Payment \u2014 ${p.payment_type || ''}`, time: fmt(p.payment_date), src: 'ST Payments', detail: money(p.total) })),
    { dot: 'hot', title: `AI Verification: ${score}%`, time: 'Latest', src: 'System', detail: `${passed} passed \u00b7 ${failed} failed \u00b7 ${total - passed - failed} pending` },
  ];
  return (
    <div className="shell">
      <nav className="rail">
        <div className="rail-logo">S</div>
        {TABS.map((t, i) => (<div key={t.id}>{(i === 1 || i === 5 || i === 10) && <div className="rsep" />}<div className={`ri${activeTab === t.id ? ' on' : ''}`} onClick={() => setActiveTab(t.id)}><Icon name={t.icon} /><span className="tip">{t.num ? t.num + '. ' : ''}{t.label}</span></div></div>))}
      </nav>
      <div className="main">
        {activeTab === 'dashboard' && <Dashboard job={job} data={data} amt={amt} score={score} passed={passed} failed={failed} total={total} invTotal={invTotal} paidTotal={paidTotal} isInstall={isInstall} jobNumber={jobNumber} />}
        {activeTab === 'intel' && <IntelTab job={job} data={data} amt={amt} />}
        {activeTab === 'service' && <ServiceTab job={job} data={data} />}
        {activeTab === 'sales' && <SalesTab job={job} data={data} />}
        {activeTab === 'materials' && <MaterialsTab job={job} data={data} amt={amt} />}
        {activeTab === 'financials' && <FinancialsTab job={job} data={data} amt={amt} invTotal={invTotal} paidTotal={paidTotal} />}
        {activeTab === 'verify' && <VerifyTab data={data} score={score} passed={passed} failed={failed} total={total} />}
        {activeTab === 'postinstall' && <PostInstallTab job={job} data={data} />}
        {activeTab === 'calls' && <CallsTab job={job} data={data} />}
        {!['dashboard', 'intel', 'service', 'sales', 'materials', 'financials', 'verify', 'postinstall', 'calls'].includes(activeTab) && <EmptyTab tab={TABS.find(t => t.id === activeTab)!} />}
      </div>
      <aside className="panel">
        <div className="panel-h"><h2>Activity</h2><div className="live">Live</div></div>
        <div className="panel-f">{events.map((e, i) => (<div className="act" key={i}><div className={`act-d ${e.dot}`} /><div className="act-b"><div className="act-t">{e.title}</div><div className="act-m"><span>{e.time}</span><span>{e.src}</span></div>{e.detail && <div className="act-box">{e.detail}</div>}</div></div>))}</div>
      </aside>
    </div>
  );
}

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
    <div className="top"><div className="top-l"><div className="crumb">Jobs / #{jobNumber} / Tracker</div><h1><span className="n">#{jobNumber}</span> {job.customer_name || 'Unknown'}</h1><div className="sub">{job.job_type_name || ''} &middot; {job.business_unit_name || ''} &middot; {fmt(job.created_on)}</div></div>
      <div className="pills">{job.status === 'Completed' && <div className="pill p-sold">Completed</div>}{job.status === 'Scheduled' && <div className="pill p-svc">Scheduled</div>}{job.status === 'InProgress' && <div className="pill p-svc">In Progress</div>}{isInstall ? <div className="pill p-inst">Install</div> : <div className="pill p-svc">Service</div>}</div></div>
    <div className="ai-sum"><div className="ai-ring" style={{ background: `conic-gradient(var(--mint) 0deg, var(--mint) ${okDeg}deg, var(--fire) ${okDeg}deg, var(--fire) ${failDeg}deg, var(--t4) ${failDeg}deg)`, WebkitMask: 'radial-gradient(farthest-side,transparent calc(100% - 4px),#000 calc(100% - 4px))', mask: 'radial-gradient(farthest-side,transparent calc(100% - 4px),#000 calc(100% - 4px))' }}><span className="pct" style={{ color: scoreColor }}>{score}%</span></div>
      <div className="ai-stats"><div className="ai-s"><div className="n" style={{ color: 'var(--mint)' }}>{passed}</div><div className="l" style={{ color: 'var(--mint2)' }}>Verified</div></div><div className="ai-s"><div className="n" style={{ color: 'var(--fire)' }}>{failed}</div><div className="l" style={{ color: 'var(--fire2)' }}>Failed</div></div>{pending > 0 && <div className="ai-s"><div className="n" style={{ color: 'var(--t3)' }}>{pending}</div><div className="l" style={{ color: 'var(--t3)' }}>Pending</div></div>}</div></div>
    <div className="hero"><div className="st sf"><div className="ai ai-ok" /><div className="num">{money(amt)}</div><div className="lbl">Sale Amount</div></div><div className="st sv"><div className="ai ai-ok" /><div className="num">{money(invTotal)}</div><div className="lbl">Invoiced</div></div><div className="st sm"><div className="ai ai-ok" /><div className="num">{money(paidTotal)}</div><div className="lbl">Paid</div></div><div className="st sg"><div className="num" style={{ fontSize: 18 }}>{job.status || '\u2014'}</div><div className="lbl">Status</div></div></div>
    <div className="pipe-wrap"><div className="pipe-top"><h2>Job Lifecycle</h2><div className="step">Stage {stageIdx + 1} / 6</div></div><div className="pipe">{stages.map((s, i) => { const cls = i < stageIdx ? 'done' : i === stageIdx ? 'now' : 'w'; return <div className={`pn ${cls}`} key={s}><div className={`pb ${cls}`} /><div className="pt">{s}</div></div>; })}</div></div>
    <div className="g2">
      <div className="c"><div className="ch"><h3>Customer</h3></div><div className="cb"><VR dot="ai-ok" k="Name" v={job.customer_name || '\u2014'} /><VR dot="ai-ok" k="Job #" v={`#${jobNumber}`} style={{ fontFamily: 'var(--mono)', color: 'var(--ice)' }} /><VR dot="ai-ok" k="Address" v={job.customer_address || '\u2014'} /><VR dot="ai-ok" k="Created" v={fmt(job.created_on)} /><VR dot={job.completed_on ? 'ai-ok' : 'ai-wait'} k="Completed" v={fmt(job.completed_on)} /></div></div>
      <div className="c"><div className="ch"><h3>Verification Checks</h3></div><div className="cb">{(data.verifications || []).slice(0, 8).map((v: any, i: number) => { const dot = v.result === 'pass' ? 'ai-ok' : v.result === 'fail' ? 'ai-fail' : 'ai-wait'; const chip = v.result === 'pass' ? 'c-ok' : v.result === 'fail' ? 'c-fail' : 'c-info'; const label = v.result === 'pass' ? '\u2713 Verified' : v.result === 'fail' ? '\u2717 Failed' : 'Pending'; return <div className="vr" key={i}><div className={`ai-dot ${dot}`} /><span className="k">{v.verification_name}</span><span className={`chip ${chip}`}>{label}</span></div>; })}{(data.verifications || []).length === 0 && <div style={{ color: 'var(--t3)', fontSize: 12 }}>No verifications yet.</div>}</div></div>
    </div>
    <div className="c full"><div className="ch"><h3>Work Scope</h3></div><div className="cb"><div className="slbl"><div className="ai-dot ai-ok" />Description</div><div className="stxt cv">{job.summary || 'No scope summary available'}</div><div className="g2" style={{ marginTop: 8, marginBottom: 0 }}><div><div className="slbl"><div className="ai-dot ai-ok" />Job Type</div><div className="stxt cg">{job.job_type_name || '\u2014'}</div></div><div><div className="slbl"><div className="ai-dot ai-ok" />Business Unit</div><div className="stxt ca">{job.business_unit_name || '\u2014'}</div></div></div></div></div>
  </>;
}

function FinancialsTab({ job, data, amt, invTotal, paidTotal }: any) {
  const invoices = data.invoices || []; const payments = data.payments || []; const outstanding = invTotal - paidTotal; const deposit40 = amt * 0.4;
  return <>
    <div className="tab-hdr"><div className="tab-icon" style={{ background: 'var(--firebg)', border: '1px solid var(--firebd)', color: 'var(--fire)' }}><Icon name="chart" /></div><div className="tab-info"><div className="tab-title">Financials</div><div className="tab-desc">Deposits &middot; Financing &middot; Material costs &middot; Profitability</div></div></div>
    <div className="hero"><div className="st sf"><div className="ai ai-ok" /><div className="num">{money(amt)}</div><div className="lbl">Total Sale</div></div><div className="st sv"><div className="ai ai-ok" /><div className="num">{money(invTotal)}</div><div className="lbl">Invoiced</div></div><div className="st sm"><div className="ai ai-ok" /><div className="num" style={{ color: paidTotal >= deposit40 ? 'var(--mint)' : 'var(--fire)' }}>{money(paidTotal)}</div><div className="lbl">Paid</div></div><div className="st sg"><div className="num" style={{ color: outstanding <= 0 ? 'var(--mint)' : 'var(--fire)' }}>{money(outstanding > 0 ? outstanding : 0)}</div><div className="lbl">Outstanding</div></div></div>
    <div className="c full"><div className="ch"><h3>Invoices</h3><div className="tg" style={{ background: 'var(--firebg)', border: '1px solid var(--firebd)', color: 'var(--fire)' }}>{invoices.length}</div></div>{invoices.length > 0 ? <div className="cb" style={{ padding: 0 }}><table className="mt"><thead><tr><th>Invoice</th><th>Date</th><th>Subtotal</th><th>Tax</th><th>Total</th><th>Balance</th></tr></thead><tbody>{invoices.map((inv: any, i: number) => <tr key={i}><td style={{ fontFamily: 'var(--mono)', color: 'var(--ice)' }}>{inv.reference_number || inv.st_invoice_id}</td><td>{fmt(inv.invoice_date)}</td><td>${(parseFloat(inv.sub_total) || 0).toFixed(2)}</td><td>${(parseFloat(inv.sales_tax) || 0).toFixed(2)}</td><td style={{ color: 'var(--t1)' }}>${(parseFloat(inv.total) || 0).toFixed(2)}</td><td style={{ color: parseFloat(inv.balance) > 0 ? 'var(--fire)' : 'var(--mint)' }}>${(parseFloat(inv.balance) || 0).toFixed(2)}</td></tr>)}</tbody></table></div> : <div className="cb" style={{ color: 'var(--t3)', fontSize: 12 }}>No invoices found.</div>}</div>
    <div className="c full"><div className="ch"><h3>Payments</h3><div className="tg" style={{ background: 'var(--mintbg)', border: '1px solid var(--mintbd)', color: 'var(--mint)' }}>{payments.length}</div></div>{payments.length > 0 ? <div className="cb" style={{ padding: 0 }}><table className="mt"><thead><tr><th>Payment</th><th>Type</th><th>Amount</th><th>Date</th><th>Memo</th></tr></thead><tbody>{payments.map((p: any, i: number) => <tr key={i}><td style={{ fontFamily: 'var(--mono)', color: 'var(--ice)' }}>{p.st_payment_id}</td><td>{p.payment_type || '\u2014'}</td><td style={{ color: 'var(--mint)' }}>${(parseFloat(p.total) || 0).toFixed(2)}</td><td>{fmt(p.payment_date)}</td><td>{p.memo || '\u2014'}</td></tr>)}</tbody></table></div> : <div className="cb" style={{ color: 'var(--t3)', fontSize: 12 }}>No payments linked.</div>}</div>
    <div className="g2"><div className="c"><div className="ch"><h3>Deposit Tracking</h3></div><div className="cb"><VR dot={paidTotal >= deposit40 ? 'ai-ok' : 'ai-fail'} k="40% Required" v={money(deposit40)} /><VR dot={paidTotal >= deposit40 ? 'ai-ok' : 'ai-fail'} k="Collected" v={money(paidTotal)} style={{ color: paidTotal >= deposit40 ? 'var(--mint)' : 'var(--fire)' }} /></div></div><div className="c"><div className="ch"><h3>18% Material Budget</h3></div><div className="cb"><VR dot="ai-ok" k="Budget Cap" v={money(amt * 0.18)} /><VR dot="ai-wait" k="Material Spend" v="Tracking..." style={{ color: 'var(--t3)' }} /></div></div></div>
  </>;
}

function VerifyTab({ data, score, passed, failed, total }: any) {
  const verifs = data.verifications || []; const pending = total - passed - failed;
  const scoreColor = score >= 80 ? 'var(--mint)' : score >= 60 ? 'var(--amber)' : 'var(--fire)';
  const grouped: Record<string, any[]> = {};
  verifs.forEach((v: any) => { const nm = v.verification_name || ''; const phase = nm.startsWith('A-') || nm.startsWith('B-') || nm.startsWith('C-') ? 'PRE-SALE' : nm.startsWith('S3-') ? 'STAGE 3 \u2014 PRE-INSTALL' : nm.startsWith('S5-') ? 'STAGE 5 \u2014 POST-INSTALL' : nm.startsWith('S6-') ? 'STAGE 6 \u2014 RECALL' : 'STAGE 1 \u2014 JOB SOLD'; if (!grouped[phase]) grouped[phase] = []; grouped[phase].push(v); });
  return <>
    <div className="tab-hdr"><div className="tab-icon" style={{ background: 'var(--hotbg)', border: '1px solid var(--hotbd)', color: 'var(--hot)' }}><Icon name="shield" /></div><div className="tab-info"><div className="tab-title">Verification Dashboard</div><div className="tab-desc">Bird&apos;s-eye scorecard of ALL checks</div></div><div style={{ textAlign: 'center' }}><div style={{ fontFamily: 'var(--mono)', fontSize: 36, fontWeight: 700, color: scoreColor }}>{score}%</div><div style={{ fontSize: 9, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase' as const, color: 'var(--t3)' }}>Overall Score</div></div></div>
    <div className="hero" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}><div className="st sm"><div className="num" style={{ fontSize: 28 }}>{passed}</div><div className="lbl">Passed</div></div><div className="st sf"><div className="num" style={{ fontSize: 28 }}>{failed}</div><div className="lbl">Failed</div></div><div className="st" style={{ background: 'var(--amberbg)', border: '1px solid var(--amberbd)' }}><div className="num" style={{ fontSize: 28, color: 'var(--amber)' }}>0</div><div className="lbl" style={{ color: 'var(--amber)' }}>Warnings</div></div><div className="st" style={{ background: 'var(--s3)', border: '1px solid var(--b2)' }}><div className="num" style={{ fontSize: 28, color: 'var(--t3)' }}>{pending}</div><div className="lbl">Pending</div></div></div>
    {Object.entries(grouped).map(([phase, checks]) => { const pPass = checks.filter((c: any) => c.result === 'pass').length; const color = phase.includes('PRE-SALE') ? 'volt' : phase.includes('3') ? 'grape' : phase.includes('5') ? 'ice' : phase.includes('6') ? 'amber' : 'fire'; return <div className="sec" key={phase}><div className="sec-h">{phase}<span className="sec-score" style={{ background: `var(--${color}bg)`, border: `1px solid var(--${color}bd)`, color: `var(--${color})` }}>{pPass}/{checks.length}</span></div><div className="vg">{checks.map((c: any, i: number) => { const dot = c.result === 'pass' ? 'ai-ok' : c.result === 'fail' ? 'ai-fail' : 'ai-wait'; return <div className="vg-item" key={i}><div className={`vg-dot ${dot}`} /><div className="vg-label">{c.verification_name}</div></div>; })}</div></div>; })}
    {verifs.length === 0 && <div style={{ color: 'var(--t3)', fontSize: 12, padding: 20, textAlign: 'center' }}>No verifications recorded for this job yet.</div>}
  </>;
}

function EmptyTab({ tab }: { tab: typeof TABS[number] }) {
  return <div className="empty"><div className="empty-icon" style={{ background: `var(--${tab.color}bg)`, color: `var(--${tab.color})` }}><Icon name={tab.icon} /></div><div className="empty-title">{tab.label}</div><div className="empty-desc">{TAB_DESCS[tab.id] || 'This tab is under development.'}</div><div style={{ marginTop: 16, padding: '4px 12px', borderRadius: 20, background: 'var(--s3)', border: '1px solid var(--b2)', fontSize: 10, color: 'var(--t3)', fontWeight: 600 }}>Coming Soon</div></div>;
}
