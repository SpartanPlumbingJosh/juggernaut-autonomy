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
  Q3: { label: 'Q3 \u2014 Turnover & Presentation', color: 'var(--fire)', bg: 'var(--firebg)', bd: 'var(--firebd)' },
  Q4: { label: 'Q4 \u2014 Close & Paperwork', color: 'var(--volt)', bg: 'var(--voltbg)', bd: 'var(--voltbd)' },
  PostGame: { label: 'Post Game Recap', color: 'var(--grape)', bg: 'var(--grapebg)', bd: 'var(--grapebd)' },
};

const verifyIcons: Record<string, string> = {
  slack_text: '\uD83D\uDCAC',
  photo: '\uD83D\uDCF7',
  screenshot: '\uD83D\uDDBC\uFE0F',
  call: '\uD83D\uDCDE',
  manager: '\uD83D\uDC64',
  st_data: '\uD83D\uDCCA',
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
    <div className="tab-hdr">
      <div className="tab-icon" style={{ background: 'var(--firebg)', border: '1px solid var(--firebd)', color: 'var(--fire)' }}>
        <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
          <line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/>
        </svg>
      </div>
      <div className="tab-info">
        <div className="tab-title">Sales Process</div>
        <div className="tab-desc">Q3 through Post Game Recap &mdash; {salesKey} &middot; {totalSteps} steps</div>
      </div>
      <div className="tab-badge" style={{ background: passedSteps > 0 ? 'var(--mintbg)' : 'var(--s3)', border: `1px solid ${passedSteps > 0 ? 'var(--mintbd)' : 'var(--b2)'}`, color: passedSteps > 0 ? 'var(--mint)' : 'var(--t3)' }}>
        {passedSteps}/{totalSteps} VERIFIED
      </div>
    </div>
    <div className="hero" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
      <div className="st sf"><div className="num">{totalSteps}</div><div className="lbl">Steps</div></div>
      <div className="st sv"><div className="num" style={{ color: 'var(--mint)' }}>{passedSteps}</div><div className="lbl">Verified</div></div>
      <div className="st sm"><div className="num" style={{ color: 'var(--fire)' }}>{money(amt)}</div><div className="lbl">Sale</div></div>
      <div className="st" style={{ background: depositMet ? 'var(--mintbg)' : 'var(--firebg)', border: `1px solid ${depositMet ? 'var(--mintbd)' : 'var(--firebd)'}` }}>
        <div className="num" style={{ fontSize: 20, color: depositMet ? 'var(--mint)' : 'var(--fire)' }}>{depositMet ? '\u2713' : '\u2717'}</div>
        <div className="lbl">40% Deposit</div>
      </div>
    </div>
    {needsCancel && <div style={{ background: cancelStatus === 'pass' ? 'var(--mintbg)' : 'var(--firebg)', border: `2px solid ${cancelStatus === 'pass' ? 'var(--mintbd)' : 'var(--firebd)'}`, borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <div style={{ width: 32, height: 32, borderRadius: '50%', background: cancelStatus === 'pass' ? 'var(--mint)' : 'var(--fire)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, color: '#fff', fontWeight: 700, flexShrink: 0 }}>{cancelStatus === 'pass' ? '\u2713' : '!'}</div>
        <div>
          <div style={{ fontWeight: 700, fontSize: 14, color: cancelStatus === 'pass' ? 'var(--mint)' : 'var(--fire)' }}>3-Day Right to Cancel &mdash; {cancelStatus === 'pass' ? 'CLEARED' : 'REQUIRED'}</div>
          <div style={{ fontSize: 11, color: cancelStatus === 'pass' ? 'var(--mint)' : 'var(--fire)', opacity: 0.8 }}>FTC Cooling-Off Rule &mdash; Sale over $3,000 ({money(amt)})</div>
        </div>
      </div>
      <div style={{ fontSize: 11, color: 'var(--t2)', lineHeight: 1.5, marginLeft: 42 }}>
        {cancelStatus === 'pass' ? 'Cancellation notice has been presented, signed, and verified. Install scheduling may proceed.' : 'Cancellation notice must be presented and signed BEFORE work begins. Upload signed document to the Slack channel for AI verification.'}
      </div>
      {cancelStep?.notes && <div style={{ fontSize: 11, color: 'var(--mint)', fontStyle: 'italic', marginTop: 6, marginLeft: 42 }}>{cancelStep.notes}</div>}
    </div>}
    <div className="g2">
      <div className="c"><div className="ch"><h3>Deposit Tracking</h3></div><div className="cb">
        <div className="vr"><div className={`ai-dot ${depositMet ? 'ai-ok' : 'ai-fail'}`} /><span className="k">40% Required</span><span className="v">{money(deposit40)}</span></div>
        <div className="vr"><div className={`ai-dot ${depositMet ? 'ai-ok' : 'ai-fail'}`} /><span className="k">Collected</span><span className="v" style={{ color: depositMet ? 'var(--mint)' : 'var(--fire)' }}>{money(paidTotal)}</span></div>
        <div className="vr"><div className="ai-dot ai-ok" /><span className="k">Sale Amount</span><span className="v">{money(amt)}</span></div>
      </div></div>
      <div className="c"><div className="ch"><h3>Estimates</h3><div className="tg" style={{ background: 'var(--mintbg)', border: '1px solid var(--mintbd)', color: 'var(--mint)' }}>{estimates.length}</div></div><div className="cb">
        {estimates.length === 0 && <div style={{ color: 'var(--t3)', fontSize: 12 }}>No estimates on this job.</div>}
        {estimates.slice(0, 5).map((e: any, i: number) => {
          const dot = e.status_name === 'Sold' ? 'ai-ok' : e.status_name === 'Dismissed' ? 'ai-fail' : 'ai-wait';
          return <div className="vr" key={i}><div className={`ai-dot ${dot}`} /><span className="k" style={{ maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.estimate_name || 'Estimate'}</span><span className="v" style={{ color: e.status_name === 'Sold' ? 'var(--mint)' : 'var(--t3)' }}>{money(e.subtotal)} &middot; {e.status_name}</span></div>;
        })}
      </div></div>
    </div>
    {quarters.map((q) => {
      const meta = quarterMeta[q] || { label: q, color: 'var(--t2)', bg: 'var(--s3)', bd: 'var(--b2)' };
      const steps = stepsByQuarter[q];
      const qPassed = steps.filter((s: any) => { const t = trackingMap[`${s.playbook_key}-${s.step_number}`]; return t && t.status === 'pass'; }).length;
      return <div className="c full" key={q}><div className="ch"><h3>{meta.label}</h3><div className="tg" style={{ background: meta.bg, border: `1px solid ${meta.bd}`, color: meta.color }}>{qPassed}/{steps.length}</div></div>
        <div className="cb" style={{ padding: 0 }}>{steps.map((step: any, i: number) => {
          const t = trackingMap[`${step.playbook_key}-${step.step_number}`];
          const status = t ? t.status : 'pending';
          const dotCls = status === 'pass' ? 'ai-ok' : status === 'fail' ? 'ai-fail' : 'ai-wait';
          const icon = verifyIcons[step.verification_type] || '\u2022';
          const isHardGate = step.hard_gate === true || step.hard_gate === 'true';
          const isCancelStep = step.step_number === 10 || (step.title || '').toLowerCase().includes('cancel');
          return <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 16px', borderBottom: i < steps.length - 1 ? '1px solid var(--b2)' : 'none', background: isHardGate ? 'rgba(204,34,68,0.03)' : 'transparent' }}>
            <div className={`ai-dot ${dotCls}`} style={{ flexShrink: 0 }} />
            <span style={{ fontSize: 11, width: 22, textAlign: 'center', flexShrink: 0 }}>{icon}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--t1)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--t3)', minWidth: 18 }}>{step.step_number}</span>
                {step.title}
                {isHardGate && <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 4, background: 'var(--firebg)', border: '1px solid var(--firebd)', color: 'var(--fire)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5 }}>Gate</span>}
                {isCancelStep && needsCancel && <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 4, background: 'var(--amberbg)', border: '1px solid var(--amberbd)', color: 'var(--amber)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5 }}>FTC</span>}
              </div>
              {step.description && <div style={{ fontSize: 10, color: 'var(--t3)', marginTop: 2 }}>{step.description}</div>}
              {t && t.notes && <div style={{ fontSize: 10, color: 'var(--mint)', fontStyle: 'italic', marginTop: 2 }}>{t.notes}</div>}
            </div>
            <div style={{ flexShrink: 0 }}>
              {status === 'pass' && <span style={{ fontSize: 11, color: 'var(--mint)', fontWeight: 700 }}>{'\u2713'}</span>}
              {status === 'fail' && <span style={{ fontSize: 11, color: 'var(--fire)', fontWeight: 700 }}>{'\u2717'}</span>}
              {status === 'pending' && <span style={{ fontSize: 10, color: 'var(--t3)' }}>&mdash;</span>}
            </div>
          </div>;
        })}</div>
      </div>;
    })}
    {soldEstimates.length > 0 && <div className="c full"><div className="ch"><h3>Sold Estimates</h3><div className="tg" style={{ background: 'var(--mintbg)', border: '1px solid var(--mintbd)', color: 'var(--mint)' }}>{soldEstimates.length}</div></div>
      <div className="cb" style={{ padding: 0 }}><table className="mt"><thead><tr><th>Estimate</th><th>Name</th><th>Sold By</th><th>Amount</th><th>Sold On</th></tr></thead><tbody>
        {soldEstimates.map((e: any, i: number) => <tr key={i}><td style={{ fontFamily: 'var(--mono)', color: 'var(--ice)' }}>{e.st_estimate_id}</td><td>{e.estimate_name || e.summary || '\u2014'}</td><td>{e.sold_by_name || '\u2014'}</td><td style={{ color: 'var(--mint)', fontWeight: 600 }}>{money(e.subtotal)}</td><td>{fmt(e.sold_on)}</td></tr>)}
      </tbody></table></div>
    </div>}
    {salesSteps.length === 0 && <div style={{ color: 'var(--t3)', fontSize: 12, padding: 20, textAlign: 'center' }}>No sales playbook steps loaded for this job type ({salesKey}).</div>}
  </>;
}
