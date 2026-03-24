'use client';

function fmt(d: string | null | undefined): string {
  if (!d) return '\u2014';
  try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); } catch { return d; }
}
function money(n: number | string | null | undefined): string {
  const v = parseFloat(String(n || 0));
  return v > 0 ? '$' + v.toLocaleString(undefined, { maximumFractionDigits: 0 }) : '\u2014';
}

const quarterMeta: Record<string, { label: string; color: string; bg: string; bd: string }> = {
  Q3: { label: 'Q3 \u2014 TURNOVER & PRESENTATION', color: 'var(--fire)', bg: 'var(--firebg)', bd: 'var(--firebd)' },
  Q4: { label: 'Q4 \u2014 CLOSE & PAPERWORK', color: 'var(--volt)', bg: 'var(--voltbg)', bd: 'var(--voltbd)' },
  PostGame: { label: 'POST GAME RECAP', color: 'var(--grape)', bg: 'var(--grapebg)', bd: 'var(--grapebd)' },
};

export default function SalesTab({ job, data }: { job: any; data: any }) {
  const playbook = data.playbook || { steps: [], tracking: [], salesKey: 'plsales' };
  const estimates = (data.estimates || []) as any[];
  const payments = (data.payments || []) as any[];
  const amt = parseFloat(job.total) || 0;
  const salesKey = playbook.salesKey || 'plsales';
  const salesSteps = (playbook.steps || []).filter((s: any) => s.playbook_key === salesKey);
  const trackingMap: Record<string, any> = {};
  (playbook.tracking || []).forEach((t: any) => { trackingMap[`${t.playbook_key}-${t.step_number}`] = t; });
  const quarters: string[] = [];
  const stepsByQuarter: Record<string, any[]> = {};
  salesSteps.forEach((s: any) => { if (!stepsByQuarter[s.quarter]) { stepsByQuarter[s.quarter] = []; quarters.push(s.quarter); } stepsByQuarter[s.quarter].push(s); });
  const totalSteps = salesSteps.length;
  const passedSteps = salesSteps.filter((s: any) => { const t = trackingMap[`${s.playbook_key}-${s.step_number}`]; return t && t.status === 'pass'; }).length;
  const needsCancel = amt > 3000;
  const cancelStep = trackingMap[`${salesKey}-10`];
  const cancelStatus = cancelStep ? cancelStep.status : 'pending';
  const paidTotal = payments.reduce((s: number, p: any) => s + (parseFloat(p.total) || 0), 0);
  const deposit40 = amt * 0.4;
  const depositMet = paidTotal >= deposit40;
  const soldEstimates = estimates.filter((e: any) => e.status_name === 'Sold');

  return <>
    {/* Header */}
    <div style={{ marginBottom: 24 }}>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--t4)', marginBottom: 6 }}>Sales Process</div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 800, letterSpacing: '-.5px' }}>Close the Deal</h1>
          <div style={{ fontSize: 14, color: 'var(--t3)', marginTop: 4 }}>{salesKey} &middot; {totalSteps} steps</div>
        </div>
        <div style={{ background: passedSteps > 0 ? 'var(--mintbg)' : 'var(--s3)', border: `1px solid ${passedSteps > 0 ? 'var(--mintbd)' : 'var(--b2)'}`, color: passedSteps > 0 ? 'var(--mint)' : 'var(--t3)', fontFamily: 'var(--mono)', fontSize: 14, fontWeight: 700, padding: '6px 14px', borderRadius: 10 }}>
          {passedSteps}/{totalSteps} VERIFIED
        </div>
      </div>
    </div>

    {/* Hero Stats */}
    <div className="hero" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
      <div className="st sf"><div className="num">{totalSteps}</div><div className="lbl">Steps</div></div>
      <div className="st sm"><div className="num">{passedSteps}</div><div className="lbl">Verified</div></div>
      <div className="st" style={{ background: 'linear-gradient(150deg,rgba(239,68,68,.08),transparent 60%)', border: '1px solid rgba(239,68,68,.12)', borderRadius: 'var(--r)', padding: 22, position: 'relative', overflow: 'hidden' }}><div className="num" style={{ fontFamily: 'var(--mono)', fontSize: 34, fontWeight: 700, letterSpacing: -1, lineHeight: 1, marginBottom: 6, color: 'var(--red)' }}>{money(amt)}</div><div className="lbl" style={{ fontSize: 13, fontWeight: 600, letterSpacing: '.8px', textTransform: 'uppercase' as const, color: '#f87171' }}>Sale</div></div>
      <div className="st" style={{ background: depositMet ? 'linear-gradient(150deg,rgba(34,197,94,.07),transparent 60%)' : 'linear-gradient(150deg,rgba(239,68,68,.08),transparent 60%)', border: `1px solid ${depositMet ? 'rgba(34,197,94,.12)' : 'rgba(239,68,68,.12)'}`, borderRadius: 'var(--r)', padding: 22, position: 'relative', overflow: 'hidden' }}>
        <div className="num" style={{ fontFamily: 'var(--mono)', fontSize: 34, fontWeight: 700, letterSpacing: -1, lineHeight: 1, marginBottom: 6, color: depositMet ? 'var(--grn)' : 'var(--red)' }}>{depositMet ? '\u2713' : '\u2717'}</div>
        <div className="lbl" style={{ fontSize: 13, fontWeight: 600, letterSpacing: '.8px', textTransform: 'uppercase' as const, color: depositMet ? '#4ade80' : '#f87171' }}>40% Deposit</div>
      </div>
    </div>

    {/* 3-Day Cancel Gate */}
    {needsCancel && <div className="c full" style={{ borderColor: cancelStatus === 'pass' ? 'rgba(34,197,94,.2)' : 'rgba(239,68,68,.2)' }}>
      <div className="ch">
        <h3 style={{ color: cancelStatus === 'pass' ? 'var(--grn)' : 'var(--red)' }}>3-Day Cancel {cancelStatus === 'pass' ? 'CLEARED' : 'REQUIRED'}</h3>
        <div className="tg" style={{ background: cancelStatus === 'pass' ? 'var(--mintbg)' : 'var(--firebg)', border: `1px solid ${cancelStatus === 'pass' ? 'var(--mintbd)' : 'var(--firebd)'}`, color: cancelStatus === 'pass' ? 'var(--mint)' : 'var(--fire)' }}>FTC</div>
      </div>
      <div className="cb">
        <div className="vr"><span className="k">Sale Amount</span><span className="v">{money(amt)}</span></div>
        <div className="vr"><span className="k">Status</span><span className="v" style={{ color: cancelStatus === 'pass' ? 'var(--mint)' : 'var(--fire)' }}>{cancelStatus === 'pass' ? 'Signed & Verified' : 'Pending Signature'}</span></div>
      </div>
    </div>}

    {/* Deposit + Estimates side by side */}
    <div className="g2">
      <div className="c"><div className="ch"><h3>Deposit</h3></div><div className="cb">
        <div className="vr"><div className={`ai-dot ${depositMet ? 'ai-ok' : 'ai-fail'}`} /><span className="k">Required (40%)</span><span className="v">{money(deposit40)}</span></div>
        <div className="vr"><div className={`ai-dot ${depositMet ? 'ai-ok' : 'ai-fail'}`} /><span className="k">Collected</span><span className="v" style={{ color: depositMet ? 'var(--mint)' : 'var(--fire)' }}>{money(paidTotal)}</span></div>
        <div className="vr"><div className="ai-dot ai-ok" /><span className="k">Sale</span><span className="v">{money(amt)}</span></div>
      </div></div>
      <div className="c"><div className="ch"><h3>Estimates</h3><div className="tg" style={{ background: 'var(--mintbg)', border: '1px solid var(--mintbd)', color: 'var(--mint)' }}>{estimates.length}</div></div><div className="cb">
        {estimates.length === 0 && <div style={{ color: 'var(--t3)', fontSize: 14 }}>No estimates on this job.</div>}
        {estimates.slice(0, 5).map((e: any, i: number) => {
          const dot = e.status_name === 'Sold' ? 'ai-ok' : e.status_name === 'Dismissed' ? 'ai-fail' : 'ai-wait';
          return <div className="vr" key={i}><div className={`ai-dot ${dot}`} /><span className="k" style={{ maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.estimate_name || 'Estimate'}</span><span className="v" style={{ color: e.status_name === 'Sold' ? 'var(--mint)' : 'var(--t3)' }}>{money(e.subtotal)} &middot; {e.status_name}</span></div>;
        })}
      </div></div>
    </div>

    {/* Playbook Steps by Quarter */}
    {quarters.map((q) => {
      const meta = quarterMeta[q] || { label: q.toUpperCase(), color: 'var(--t2)', bg: 'var(--s3)', bd: 'var(--b2)' };
      const steps = stepsByQuarter[q];
      const qPassed = steps.filter((s: any) => { const t = trackingMap[`${s.playbook_key}-${s.step_number}`]; return t && t.status === 'pass'; }).length;
      return <div className="c full" key={q}><div className="ch"><h3>{meta.label}</h3><div className="tg" style={{ background: meta.bg, border: `1px solid ${meta.bd}`, color: meta.color }}>{qPassed}/{steps.length}</div></div>
        <div className="cb" style={{ padding: 0 }}>{steps.map((step: any, i: number) => {
          const t = trackingMap[`${step.playbook_key}-${step.step_number}`];
          const status = t ? t.status : 'pending';
          const dotCls = status === 'pass' ? 'ai-ok' : status === 'fail' ? 'ai-fail' : 'ai-wait';
          const isHardGate = step.hard_gate === true || step.hard_gate === 'true';
          const isCancelStep = step.step_number === 10 || (step.title || '').toLowerCase().includes('cancel');

          return <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 20px', borderBottom: i < steps.length - 1 ? '1px solid rgba(255,255,255,.04)' : 'none', background: isHardGate ? 'rgba(239,68,68,.03)' : 'transparent' }}>
            <div className={`ai-dot ${dotCls}`} style={{ flexShrink: 0 }} />
            <span style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--t3)', minWidth: 24, textAlign: 'right', flexShrink: 0 }}>{step.step_number}</span>
            <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--t1)' }}>{step.title}</span>
              {isHardGate && <span style={{ fontSize: 13, padding: '2px 8px', borderRadius: 6, background: 'var(--firebg)', border: '1px solid var(--firebd)', color: 'var(--fire)', fontWeight: 700, textTransform: 'uppercase' as const, letterSpacing: 0.5 }}>GATE</span>}
              {isCancelStep && needsCancel && <span style={{ fontSize: 13, padding: '2px 8px', borderRadius: 6, background: 'var(--amberbg)', border: '1px solid var(--amberbd)', color: 'var(--amber)', fontWeight: 700, textTransform: 'uppercase' as const, letterSpacing: 0.5 }}>FTC</span>}
            </div>
            <div style={{ flexShrink: 0 }}>
              {status === 'pass' && <span style={{ fontSize: 14, color: 'var(--mint)', fontWeight: 700 }}>{'\u2713'}</span>}
              {status === 'fail' && <span style={{ fontSize: 14, color: 'var(--fire)', fontWeight: 700 }}>{'\u2717'}</span>}
              {status === 'pending' && <span style={{ fontSize: 14, color: 'var(--t4)' }}>&mdash;</span>}
            </div>
          </div>;
        })}</div>
      </div>;
    })}

    {/* Sold Estimates Table */}
    {soldEstimates.length > 0 && <div className="c full"><div className="ch"><h3>Sold Estimates</h3><div className="tg" style={{ background: 'var(--mintbg)', border: '1px solid var(--mintbd)', color: 'var(--mint)' }}>{soldEstimates.length}</div></div>
      <div className="cb" style={{ padding: 0 }}><table className="mt"><thead><tr><th>Estimate</th><th>Name</th><th>Sold By</th><th>Amount</th><th>Sold On</th></tr></thead><tbody>
        {soldEstimates.map((e: any, i: number) => <tr key={i}><td style={{ fontFamily: 'var(--mono)', color: 'var(--ice)' }}>{e.st_estimate_id}</td><td>{e.estimate_name || e.summary || '\u2014'}</td><td>{e.sold_by_name || '\u2014'}</td><td style={{ color: 'var(--mint)', fontWeight: 600 }}>{money(e.subtotal)}</td><td>{fmt(e.sold_on)}</td></tr>)}
      </tbody></table></div>
    </div>}
  </>;
}
