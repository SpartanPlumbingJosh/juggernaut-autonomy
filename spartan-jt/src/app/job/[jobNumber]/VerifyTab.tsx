'use client';
import { useState } from 'react';

function fmt(d: string | null | undefined): string {
  if (!d) return '\u2014';
  try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }); } catch { return d; }
}

function fmtMoney(n: number | null | undefined): string {
  if (n == null) return '\u2014';
  return '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function Icon({ name }: { name: string }) {
  const paths: Record<string, string> = {
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    grid: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
    list: '<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>',
    chevDown: '<polyline points="6 9 12 15 18 9"/>',
    chevUp: '<polyline points="18 15 12 9 6 15"/>',
    lock: '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
  };
  return <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round" dangerouslySetInnerHTML={{ __html: paths[name] || '' }} />;
}

function CompanyBar({ jobResult, companyPct }: { jobResult: string | null; companyPct: number }) {
  const barColor = companyPct >= 80 ? 'var(--mint)' : companyPct >= 50 ? 'var(--amber)' : 'var(--fire)';
  const dotColor = jobResult === 'pass' ? 'var(--mint)' : jobResult === 'fail' ? 'var(--fire)' : 'var(--t4)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 120 }}>
      <div style={{ width: 6, height: 6, borderRadius: '50%', background: dotColor, flexShrink: 0 }} />
      <div style={{ flex: 1, height: 6, borderRadius: 3, background: 'var(--s3)', overflow: 'hidden' }}>
        <div style={{ width: `${companyPct}%`, height: '100%', borderRadius: 3, background: barColor }} />
      </div>
      <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--t3)', minWidth: 32, textAlign: 'right' }}>{companyPct.toFixed(0)}%</div>
    </div>
  );
}

interface EvidenceItem { label: string; value: string; color?: string }

function getEvidence(cn: string, data: any): EvidenceItem[] {
  const j = data.job || {}, ap = data.appointments || [], iv = data.invoices || [], py = data.payments || [];
  const es = data.estimates || [], as2 = data.assignments || [], ct = data.contacts || [];
  const cl = data.calls || [], rj = data.recallJobs || [], ml = data.materialList, po = data.purchaseOrders || [];
  const m: Record<string, () => EvidenceItem[]> = {
    'Booking Call Recorded': () => [{ label: 'Lead Call ID', value: j.lead_call_id ? String(j.lead_call_id) : 'None', color: j.lead_call_id ? 'var(--mint)' : 'var(--fire)' }, { label: 'Total Calls', value: String(cl.length) }],
    'Customer Info Captured': () => [{ label: 'Contacts', value: String(ct.length), color: ct.length > 0 ? 'var(--mint)' : 'var(--fire)' }, ...ct.slice(0, 3).map((c: any) => ({ label: c.type || 'Contact', value: c.value || '\u2014' }))],
    'Job Type Correctly Set': () => [{ label: 'Job Type', value: j.job_type_name || 'Not set', color: j.job_type_name ? 'var(--mint)' : 'var(--fire)' }, { label: 'Business Unit', value: j.business_unit_name || '\u2014' }],
    'Dispatch Zone Assigned': () => [{ label: 'Address', value: j.customer_address || '\u2014' }],
    'Service Call Recorded': () => [{ label: 'Total Calls', value: String(cl.length), color: cl.length > 0 ? 'var(--mint)' : 'var(--fire)' }, ...cl.slice(0, 2).map((c: any) => ({ label: `${c.direction || ''} ${c.call_type || ''}`.trim(), value: `${fmt(c.created_on)} \u2022 ${c.duration_seconds || 0}s` }))],
    'Estimate Presented': () => [{ label: 'Estimates', value: String(es.length), color: es.length > 0 ? 'var(--mint)' : 'var(--fire)' }, ...es.slice(0, 3).map((e: any) => ({ label: e.estimate_name || 'Estimate', value: `${e.status_name || '\u2014'} \u2022 ${fmtMoney(e.subtotal)}` }))],
    'Options Presented': () => [{ label: 'Active Estimates', value: String(es.length), color: es.length >= 2 ? 'var(--mint)' : 'var(--fire)' }, { label: 'Required', value: '2+ options', color: 'var(--t3)' }, ...es.slice(0, 4).map((e: any) => ({ label: e.estimate_name || 'Option', value: fmtMoney(e.subtotal) }))],
    'Job Sold in ServiceTitan': () => [{ label: 'Status', value: j.status || '\u2014', color: j.status === 'Completed' ? 'var(--mint)' : 'var(--fire)' }, { label: 'Total', value: fmtMoney(j.total) }, { label: 'Sold Estimates', value: String(es.filter((e: any) => e.status_name === 'Sold').length) }],
    'Sales to Install Form Submitted': () => [{ label: 'Sales Form', value: ml ? 'Submitted' : 'Not found', color: ml ? 'var(--mint)' : 'var(--fire)' }, ...(ml ? [{ label: 'Generated', value: fmt((ml as any).generated_at) }] : [])],
    'Deposit Collected': () => { const st = (iv[0] as any)?.sub_total || 0; const pd = py.reduce((s: number, p: any) => s + (Number(p.total) || 0), 0); const rq = st * 0.4; return [{ label: 'Sale Subtotal', value: fmtMoney(st) }, { label: '40% Required', value: fmtMoney(rq) }, { label: 'Collected', value: fmtMoney(pd), color: pd >= rq ? 'var(--mint)' : 'var(--fire)' }, ...py.slice(0, 2).map((p: any) => ({ label: p.payment_type || 'Payment', value: `${fmtMoney(p.total)} \u2022 ${fmt(p.payment_date)}` }))]; },
    'Job Description Complete': () => [{ label: 'Length', value: j.summary ? `${j.summary.length} chars` : '0', color: j.summary?.trim().length > 10 ? 'var(--mint)' : 'var(--fire)' }, { label: 'Summary', value: j.summary ? (j.summary.length > 80 ? j.summary.substring(0, 80) + '...' : j.summary) : 'Empty' }],
    'Correct Business Unit': () => [{ label: 'BU', value: j.business_unit_name || 'Not set' }],
    'Customer Confirmation Call Made': () => { const ob = cl.filter((c: any) => c.direction === 'Outbound'); return [{ label: 'Outbound Calls', value: String(ob.length), color: ob.length > 0 ? 'var(--mint)' : 'var(--fire)' }, ...ob.slice(0, 2).map((c: any) => ({ label: `To ${c.to_number || '\u2014'}`, value: `${fmt(c.created_on)} \u2022 ${c.duration_seconds || 0}s` }))]; },
    'Install Date Scheduled': () => [{ label: 'Appointments', value: String(ap.length), color: ap.length > 0 ? 'var(--mint)' : 'var(--fire)' }, ...ap.slice(0, 2).map((a: any) => ({ label: `Appt ${a.appointment_number || ''}`, value: `${a.status || '\u2014'} \u2022 ${fmt(a.start_time)}` }))],
    'Material List Created': () => { const h = iv.some((i: any) => (i.items || []).some((t: any) => t.type === 'Material')); return [{ label: 'Material Items', value: h ? 'Yes' : 'No', color: h ? 'var(--mint)' : 'var(--fire)' }, { label: 'Sales Form', value: ml ? 'Generated' : 'None' }]; },
    'Materials Ordered/Sourced': () => [{ label: 'POs', value: String(po.length), color: po.length > 0 ? 'var(--mint)' : 'var(--fire)' }, ...po.slice(0, 2).map((p: any) => ({ label: `PO ${p.po_number || ''}`, value: `${p.status || '\u2014'} \u2022 ${fmtMoney(p.total)}` }))],
    'Crew Assigned': () => [{ label: 'Assignments', value: String(as2.length), color: as2.length > 0 ? 'var(--mint)' : 'var(--fire)' }, ...as2.slice(0, 3).map((a: any) => ({ label: a.technician_name || 'Tech', value: `${a.status || '\u2014'} \u2022 ${fmt(a.assigned_on)}` }))],
    'On-Time Arrival': () => [{ label: 'Appointments', value: String(ap.length) }, ...ap.slice(0, 2).map((a: any) => ({ label: `Appt ${a.appointment_number || ''}`, value: `Start: ${fmt(a.start_time)}${a.arrival_window_end ? ` \u2022 Window: ${fmt(a.arrival_window_end)}` : ''}` }))],
    'Follow-Up Call (48-72hr)': () => { const cd = j.completed_on ? new Date(j.completed_on) : null; const fu = cd ? cl.filter((c: any) => { if (c.direction !== 'Outbound' || !c.created_on) return false; const d = (new Date(c.created_on).getTime() - cd.getTime()) / 3600000; return d >= 24 && d <= 96; }) : []; return [{ label: 'Completed', value: fmt(j.completed_on) }, { label: 'Follow-ups in Window', value: String(fu.length), color: fu.length > 0 ? 'var(--mint)' : 'var(--fire)' }]; },
    'Job Completed in ST': () => [{ label: 'Status', value: j.status || '\u2014', color: j.status === 'Completed' ? 'var(--mint)' : 'var(--fire)' }, { label: 'Completed', value: fmt(j.completed_on) }, { label: 'Created', value: fmt(j.created_on) }],
    'Invoice Created': () => [{ label: 'Invoices', value: String(iv.length), color: iv.length > 0 ? 'var(--mint)' : 'var(--fire)' }, ...iv.slice(0, 2).map((i: any) => ({ label: `#${i.reference_number || i.st_invoice_id}`, value: `${fmtMoney(i.total)} \u2022 ${fmt(i.invoice_date)}` }))],
    'Material Cost Under 18%': () => { const st = Number((iv[0] as any)?.sub_total) || 0; let mc = 0; iv.forEach((i: any) => { (i.items || []).forEach((t: any) => { if (t.type === 'Material') mc += Number(t.cost) || 0; }); }); const pc = st > 0 ? (mc / st * 100) : 0; return [{ label: 'Subtotal', value: fmtMoney(st) }, { label: 'Material Cost', value: fmtMoney(mc) }, { label: 'Material %', value: `${pc.toFixed(1)}%`, color: pc > 0 && pc < 18 ? 'var(--mint)' : pc >= 18 ? 'var(--fire)' : 'var(--t3)' }]; },
    'Payment Collected': () => { const pt = py.reduce((s: number, p: any) => s + (Number(p.total) || 0), 0); return [{ label: 'Collected', value: fmtMoney(pt), color: pt > 0 ? 'var(--mint)' : 'var(--fire)' }, ...py.slice(0, 3).map((p: any) => ({ label: p.payment_type || 'Payment', value: `${fmtMoney(p.total)} \u2022 ${fmt(p.payment_date)}` }))]; },
    'Service Call Completed Same Day': () => { const sd = j.created_on && j.completed_on && new Date(j.created_on).toDateString() === new Date(j.completed_on).toDateString(); return [{ label: 'Created', value: fmt(j.created_on) }, { label: 'Completed', value: fmt(j.completed_on) }, { label: 'Same Day', value: sd ? 'Yes' : 'No', color: sd ? 'var(--mint)' : 'var(--fire)' }]; },
    'Turnover Opportunity Flagged': () => [{ label: 'Estimates', value: String(es.length), color: es.length > 0 ? 'var(--mint)' : 'var(--fire)' }, ...es.slice(0, 3).map((e: any) => ({ label: e.estimate_name || 'Estimate', value: `${e.status_name || '\u2014'} \u2022 ${fmtMoney(e.subtotal)}` }))],
    'Recall Check (30 day)': () => [{ label: 'Recall Jobs', value: String(rj.length), color: rj.length === 0 ? 'var(--mint)' : 'var(--fire)' }, ...rj.slice(0, 2).map((r: any) => ({ label: `#${r.job_number || r.st_job_id}`, value: `${r.status || '\u2014'} \u2022 ${fmt(r.created_on)}` }))],
  };
  return (m[cn] || (() => [{ label: 'Evidence', value: 'Not available', color: 'var(--t3)' }]))();
}

function EvidencePanel({ items }: { items: EvidenceItem[] }) {
  if (!items.length) return null;
  return (
    <div style={{ marginTop: 12, padding: '10px 12px', borderRadius: 8, background: 'var(--s2)', border: '1px solid var(--b2)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <Icon name="info" />
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase' as const, color: 'var(--t3)' }}>Evidence</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {items.map((item, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12, padding: '2px 0' }}>
            <span style={{ fontSize: 11, color: 'var(--t3)', flexShrink: 0 }}>{item.label}</span>
            <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: item.color || 'var(--t1)', textAlign: 'right', wordBreak: 'break-word' }}>{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function VerifyTab({ data, score, passed, failed, total }: {
  data: any; score: number; passed: number; failed: number; total: number;
}) {
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [expanded, setExpanded] = useState<string | null>(null);
  const verifs = data.verifications || [], defs = data.verificationDefs || [], averages = data.companyAverages || [];
  const pending = total - passed - failed;
  const scoreColor = score >= 80 ? 'var(--mint)' : score >= 60 ? 'var(--amber)' : 'var(--fire)';
  const verifMap: Record<string, any> = {};
  verifs.forEach((v: any) => { verifMap[v.verification_name] = v; });
  const avgMap: Record<string, number> = {};
  averages.forEach((a: any) => { avgMap[a.verification_name] = parseFloat(a.pass_pct) || 0; });
  const stageGroups: { stage: string; phase: string; checks: any[] }[] = [];
  const stageMap: Record<string, any[]> = {}, stagePhase: Record<string, string> = {};
  defs.forEach((d: any) => { const k = d.stage || 'Unknown'; if (!stageMap[k]) { stageMap[k] = []; stagePhase[k] = d.phase; } stageMap[k].push({ ...d, result: verifMap[d.verification_name]?.result || null, checked_at: verifMap[d.verification_name]?.checked_at || null, companyAvg: avgMap[d.verification_name] ?? null }); });
  Object.entries(stageMap).forEach(([stage, checks]) => { stageGroups.push({ stage, phase: stagePhase[stage], checks }); });
  const phaseColor: Record<string, string> = { pre_sale: 'volt', stage_1: 'fire', stage_2: 'ice', stage_3: 'grape', stage_4: 'mint', stage_5: 'ice', stage_6: 'amber' };
  const verifGrouped: Record<string, any[]> = {};
  verifs.forEach((v: any) => { const nm = v.verification_name || ''; const phase = nm.startsWith('A-') || nm.startsWith('B-') || nm.startsWith('C-') ? 'PRE-SALE' : nm.startsWith('S3-') ? 'STAGE 3 \u2014 PRE-INSTALL' : nm.startsWith('S5-') ? 'STAGE 5 \u2014 POST-INSTALL' : nm.startsWith('S6-') ? 'STAGE 6 \u2014 RECALL' : 'STAGE 1 \u2014 JOB SOLD'; if (!verifGrouped[phase]) verifGrouped[phase] = []; verifGrouped[phase].push({ ...v, companyAvg: avgMap[v.verification_name] ?? null }); });
  const useDefs = defs.length > 0;

  return <>
    <div className="tab-hdr">
      <div className="tab-icon" style={{ background: 'var(--hotbg)', border: '1px solid var(--hotbd)', color: 'var(--hot)' }}><Icon name="shield" /></div>
      <div className="tab-info"><div className="tab-title">Verification Dashboard</div><div className="tab-desc">Bird&apos;s-eye scorecard &middot; Company averages &middot; {useDefs ? defs.length : total} checks</div></div>
      <div style={{ textAlign: 'center' }}><div style={{ fontFamily: 'var(--mono)', fontSize: 36, fontWeight: 700, color: scoreColor }}>{score}%</div><div style={{ fontSize: 9, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase' as const, color: 'var(--t3)' }}>Overall Score</div></div>
    </div>
    <div className="hero" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
      <div className="st sm"><div className="num" style={{ fontSize: 28 }}>{passed}</div><div className="lbl">Passed</div></div>
      <div className="st sf"><div className="num" style={{ fontSize: 28 }}>{failed}</div><div className="lbl">Failed</div></div>
      <div className="st" style={{ background: 'var(--amberbg)', border: '1px solid var(--amberbd)' }}><div className="num" style={{ fontSize: 28, color: 'var(--amber)' }}>0</div><div className="lbl" style={{ color: 'var(--amber)' }}>Warnings</div></div>
      <div className="st" style={{ background: 'var(--s3)', border: '1px solid var(--b2)' }}><div className="num" style={{ fontSize: 28, color: 'var(--t3)' }}>{pending}</div><div className="lbl">Pending</div></div>
    </div>
    <div style={{ display: 'flex', gap: 4, padding: '8px 0', justifyContent: 'flex-end' }}>
      <button onClick={() => setViewMode('grid')} style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '4px 10px', borderRadius: 6, border: `1px solid ${viewMode === 'grid' ? 'var(--icebd)' : 'var(--b2)'}`, background: viewMode === 'grid' ? 'var(--icebg)' : 'transparent', color: viewMode === 'grid' ? 'var(--ice)' : 'var(--t3)', fontSize: 11, fontWeight: 600, cursor: 'pointer' }}><Icon name="grid" /> Grid</button>
      <button onClick={() => setViewMode('list')} style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '4px 10px', borderRadius: 6, border: `1px solid ${viewMode === 'list' ? 'var(--icebd)' : 'var(--b2)'}`, background: viewMode === 'list' ? 'var(--icebg)' : 'transparent', color: viewMode === 'list' ? 'var(--ice)' : 'var(--t3)', fontSize: 11, fontWeight: 600, cursor: 'pointer' }}><Icon name="list" /> List</button>
    </div>
    {viewMode === 'grid' && useDefs && (<div className="c full"><div className="ch"><h3>Verification Matrix</h3><span style={{ fontSize: 10, color: 'var(--t3)' }}>{defs.length} checks across {stageGroups.length} stages</span></div><div className="cb" style={{ padding: '12px' }}>
      {stageGroups.map((sg) => { const color = phaseColor[sg.phase] || 'ice'; const stgP = sg.checks.filter(c => c.result === 'pass').length; return (<div key={sg.stage} style={{ marginBottom: 16 }}><div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}><div style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase' as const, color: `var(--${color})` }}>{sg.stage}</div><span style={{ padding: '1px 6px', borderRadius: 8, fontSize: 9, fontWeight: 600, background: `var(--${color}bg)`, border: `1px solid var(--${color}bd)`, color: `var(--${color})` }}>{stgP}/{sg.checks.length}</span></div><div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>{sg.checks.map((chk: any) => { const bg = chk.result === 'pass' ? 'var(--mint)' : chk.result === 'fail' ? 'var(--fire)' : 'var(--t4)'; return (<div key={chk.verification_code} style={{ position: 'relative' }}><div onClick={() => setExpanded(expanded === chk.verification_code ? null : chk.verification_code)} title={`${chk.verification_code}: ${chk.verification_name}${chk.is_hard_gate ? ' (HARD GATE)' : ''}`} style={{ width: 32, height: 32, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', background: `${bg}20`, border: `2px solid ${bg}`, cursor: 'pointer', position: 'relative', fontSize: 8, fontWeight: 700, color: bg === 'var(--t4)' ? 'var(--t3)' : bg, fontFamily: 'var(--mono)' }}>{chk.verification_code}{chk.is_hard_gate && <div style={{ position: 'absolute', top: -3, right: -3, width: 8, height: 8, borderRadius: '50%', background: 'var(--fire)', border: '1px solid var(--s1)' }} />}</div></div>); })}</div></div>); })}
      <div style={{ display: 'flex', gap: 16, marginTop: 12, fontSize: 10, color: 'var(--t3)' }}><span><span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 3, background: 'var(--mint)', marginRight: 4, verticalAlign: 'middle' }} />Pass</span><span><span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 3, background: 'var(--fire)', marginRight: 4, verticalAlign: 'middle' }} />Fail</span><span><span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 3, background: 'var(--t4)', marginRight: 4, verticalAlign: 'middle' }} />Pending</span><span><span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: 'var(--fire)', marginRight: 4, verticalAlign: 'middle' }} />Hard Gate</span></div>
    </div></div>)}
    {viewMode === 'grid' && !useDefs && verifs.length > 0 && (<div className="c full"><div className="ch"><h3>Verification Matrix</h3></div><div className="cb" style={{ padding: '12px' }}><div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>{verifs.map((v: any, i: number) => { const bg = v.result === 'pass' ? 'var(--mint)' : v.result === 'fail' ? 'var(--fire)' : 'var(--t4)'; return <div key={i} title={v.verification_name} style={{ width: 28, height: 28, borderRadius: 5, background: `${bg}20`, border: `2px solid ${bg}`, cursor: 'pointer' }} onClick={() => setExpanded(expanded === v.verification_name ? null : v.verification_name)} />; })}</div></div></div>)}
    {expanded && (() => {
      const def = defs.find((d: any) => d.verification_code === expanded);
      const verif = def ? verifMap[def.verification_name] : verifs.find((v: any) => v.verification_name === expanded);
      const compAvg = def ? avgMap[def.verification_name] : (verif ? avgMap[verif.verification_name] : null);
      const name = def?.verification_name || expanded;
      const result = verif?.result || def?.result || null;
      const checkedAt = verif?.checked_at || def?.checked_at || null;
      const evidence = getEvidence(name, data);
      return (
        <div className="c full" style={{ border: '1px solid var(--icebd)', background: 'var(--icebg)' }}>
          <div className="cb" style={{ padding: '12px 16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {def && <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700, color: 'var(--ice)' }}>{def.verification_code}</span>}
                  <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--t1)' }}>{name}</span>
                  {def?.is_hard_gate && <span style={{ display: 'flex', alignItems: 'center', gap: 3, padding: '1px 6px', borderRadius: 8, fontSize: 9, fontWeight: 700, background: 'var(--firebg)', border: '1px solid var(--firebd)', color: 'var(--fire)' }}><Icon name="lock" /> HARD GATE</span>}
                </div>
                {def && <div style={{ fontSize: 11, color: 'var(--t3)', marginTop: 4 }}>{def.phase?.replace('_', ' ').toUpperCase()} &middot; {def.stage} &middot; Track: {def.applies_to_track}</div>}
              </div>
              <button onClick={() => setExpanded(null)} style={{ background: 'none', border: 'none', color: 'var(--t3)', cursor: 'pointer', fontSize: 18 }}>&times;</button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12, marginTop: 12 }}>
              <div style={{ textAlign: 'center', padding: 8, borderRadius: 8, background: 'var(--s2)' }}><div style={{ fontSize: 10, color: 'var(--t3)', fontWeight: 600, textTransform: 'uppercase' as const }}>This Job</div><div style={{ fontSize: 16, fontWeight: 700, marginTop: 4, color: result === 'pass' ? 'var(--mint)' : result === 'fail' ? 'var(--fire)' : 'var(--t3)' }}>{result ? result.toUpperCase() : 'PENDING'}</div></div>
              <div style={{ textAlign: 'center', padding: 8, borderRadius: 8, background: 'var(--s2)' }}><div style={{ fontSize: 10, color: 'var(--t3)', fontWeight: 600, textTransform: 'uppercase' as const }}>Company Avg</div><div style={{ fontSize: 16, fontWeight: 700, marginTop: 4, fontFamily: 'var(--mono)', color: compAvg !== null ? (compAvg >= 80 ? 'var(--mint)' : compAvg >= 50 ? 'var(--amber)' : 'var(--fire)') : 'var(--t3)' }}>{compAvg !== null ? `${compAvg}%` : 'N/A'}</div></div>
              <div style={{ textAlign: 'center', padding: 8, borderRadius: 8, background: 'var(--s2)' }}><div style={{ fontSize: 10, color: 'var(--t3)', fontWeight: 600, textTransform: 'uppercase' as const }}>Checked</div><div style={{ fontSize: 12, fontWeight: 600, marginTop: 6, color: 'var(--t2)' }}>{checkedAt ? fmt(checkedAt) : '\u2014'}</div></div>
            </div>
            {compAvg !== null && (<div style={{ marginTop: 12 }}><div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--t3)', marginBottom: 4 }}><span>Company pass rate</span><span style={{ fontFamily: 'var(--mono)' }}>{compAvg}%</span></div><div style={{ height: 8, borderRadius: 4, background: 'var(--s3)', overflow: 'hidden' }}><div style={{ width: `${compAvg}%`, height: '100%', borderRadius: 4, background: compAvg >= 80 ? 'var(--mint)' : compAvg >= 50 ? 'var(--amber)' : 'var(--fire)' }} /></div></div>)}
            <EvidencePanel items={evidence} />
          </div>
        </div>
      );
    })()}
    {viewMode === 'list' && useDefs && stageGroups.map((sg) => { const color = phaseColor[sg.phase] || 'ice'; const stgP = sg.checks.filter(c => c.result === 'pass').length; return (<div className="sec" key={sg.stage}><div className="sec-h">{sg.stage}<span className="sec-score" style={{ background: `var(--${color}bg)`, border: `1px solid var(--${color}bd)`, color: `var(--${color})` }}>{stgP}/{sg.checks.length}</span></div><div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>{sg.checks.map((chk: any) => { const dot = chk.result === 'pass' ? 'ai-ok' : chk.result === 'fail' ? 'ai-fail' : 'ai-wait'; const isExp = expanded === chk.verification_code; return (<div key={chk.verification_code}><div onClick={() => setExpanded(isExp ? null : chk.verification_code)} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px', borderRadius: 6, cursor: 'pointer', background: isExp ? 'var(--s3)' : 'transparent' }}><div className={`vg-dot ${dot}`} /><span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--t3)', minWidth: 28 }}>{chk.verification_code}</span><span style={{ flex: 1, fontSize: 12, color: 'var(--t1)' }}>{chk.verification_name}</span>{chk.is_hard_gate && <span style={{ fontSize: 8, padding: '1px 4px', borderRadius: 4, background: 'var(--firebg)', color: 'var(--fire)', fontWeight: 700 }}>GATE</span>}{chk.companyAvg !== null && <CompanyBar jobResult={chk.result} companyPct={chk.companyAvg} />}<Icon name={isExp ? 'chevUp' : 'chevDown'} /></div></div>); })}</div></div>); })}
    {viewMode === 'list' && !useDefs && Object.entries(verifGrouped).map(([phase, checks]) => { const pP = checks.filter((c: any) => c.result === 'pass').length; const color = phase.includes('PRE-SALE') ? 'volt' : phase.includes('3') ? 'grape' : phase.includes('5') ? 'ice' : phase.includes('6') ? 'amber' : 'fire'; return (<div className="sec" key={phase}><div className="sec-h">{phase}<span className="sec-score" style={{ background: `var(--${color}bg)`, border: `1px solid var(--${color}bd)`, color: `var(--${color})` }}>{pP}/{checks.length}</span></div><div className="vg">{checks.map((c: any, i: number) => { const dot = c.result === 'pass' ? 'ai-ok' : c.result === 'fail' ? 'ai-fail' : 'ai-wait'; return (<div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }} key={i}><div className={`vg-dot ${dot}`} /><div style={{ flex: 1 }} className="vg-label">{c.verification_name}</div>{c.companyAvg !== null && <CompanyBar jobResult={c.result} companyPct={c.companyAvg} />}</div>); })}</div></div>); })}
    {averages.length > 0 && (<div className="c full"><div className="ch"><h3>Company Averages</h3><span style={{ fontSize: 10, color: 'var(--t3)' }}>All jobs</span></div><div className="cb" style={{ padding: 0 }}><table className="mt"><thead><tr><th>Check</th><th>Pass Rate</th><th style={{ width: 120 }}>Distribution</th></tr></thead><tbody>{averages.sort((a: any, b: any) => (parseFloat(b.pass_pct) || 0) - (parseFloat(a.pass_pct) || 0)).map((avg: any, i: number) => { const pct = parseFloat(avg.pass_pct) || 0; const thisJob = verifMap[avg.verification_name]?.result; const barColor = pct >= 80 ? 'var(--mint)' : pct >= 50 ? 'var(--amber)' : 'var(--fire)'; return (<tr key={i}><td style={{ fontSize: 12 }}><span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', marginRight: 6, background: thisJob === 'pass' ? 'var(--mint)' : thisJob === 'fail' ? 'var(--fire)' : 'var(--t4)' }} />{avg.verification_name}</td><td style={{ fontFamily: 'var(--mono)', fontWeight: 600, color: barColor }}>{pct.toFixed(1)}%</td><td><div style={{ height: 8, borderRadius: 4, background: 'var(--s3)', overflow: 'hidden' }}><div style={{ width: `${pct}%`, height: '100%', borderRadius: 4, background: barColor }} /></div></td></tr>); })}</tbody></table></div></div>)}
    {verifs.length === 0 && defs.length === 0 && <div style={{ color: 'var(--t3)', fontSize: 12, padding: 20, textAlign: 'center' }}>No verifications recorded for this job yet.</div>}
  </>;
}
