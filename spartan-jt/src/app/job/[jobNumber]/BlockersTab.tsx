'use client';

function fmt(d: string | null | undefined): string {
  if (!d) return '\u2014';
  try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }); } catch { return d; }
}
function age(d: string | null | undefined): string {
  if (!d) return '\u2014';
  const ms = Date.now() - new Date(d).getTime();
  const mins = Math.floor(ms / 60000); if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60); if (hrs < 24) return `${hrs}h ${mins % 60}m`;
  return `${Math.floor(hrs / 24)}d ${hrs % 24}h`;
}
function escLevel(level: number | null): { label: string; color: string; bg: string; bd: string } {
  if (!level || level === 0) return { label: 'None', color: 'var(--t3)', bg: 'var(--s3)', bd: 'var(--b2)' };
  if (level === 1) return { label: 'L1 \u2014 30min', color: 'var(--amber)', bg: 'var(--amberbg)', bd: 'var(--amberbd)' };
  if (level === 2) return { label: 'L2 \u2014 1hr', color: 'var(--fire)', bg: 'var(--firebg)', bd: 'var(--firebd)' };
  return { label: 'L3 \u2014 Ownership', color: 'var(--hot)', bg: 'var(--hotbg)', bd: 'var(--hotbd)' };
}
const catColors: Record<string, string> = { permit: 'amber', material: 'mint', scheduling: 'volt', customer: 'ice', internal: 'grape', weather: 'ice', inspection: 'amber' };

export default function BlockersTab({ job, data }: { job: any; data: any }) {
  const blockers = (data.blockers || []) as any[];
  const active = blockers.filter((b: any) => !b.resolved_at);
  const resolved = blockers.filter((b: any) => b.resolved_at);
  const autoDetected = blockers.filter((b: any) => b.auto_detected).length;
  const maxEsc = active.reduce((m: number, b: any) => Math.max(m, b.escalation_level || 0), 0);
  const riskColor = active.length === 0 ? 'var(--mint)' : maxEsc >= 3 ? 'var(--hot)' : maxEsc >= 2 ? 'var(--fire)' : maxEsc >= 1 ? 'var(--amber)' : 'var(--volt)';
  const riskLabel = active.length === 0 ? 'On Track' : maxEsc >= 3 ? 'Critical' : maxEsc >= 2 ? 'High Risk' : maxEsc >= 1 ? 'At Risk' : 'Minor';

  return <>
    <div className="tab-hdr">
      <div className="tab-icon" style={{ background: 'var(--amberbg)', border: '1px solid var(--amberbd)', color: 'var(--amber)' }}>
        <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
      </div>
      <div className="tab-info"><div className="tab-title">Blockers &amp; Risk</div><div className="tab-desc">Automated escalation (30min &rarr; 1hr &rarr; 2hr) &middot; AI timeline risk assessment</div></div>
      <div style={{ textAlign: 'center' }}><div style={{ fontSize: 18, fontWeight: 700, color: riskColor }}>{riskLabel}</div><div style={{ fontSize: 9, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase' as const, color: 'var(--t3)' }}>Timeline Risk</div></div>
    </div>
    <div className="hero" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
      <div className="st" style={{ background: active.length > 0 ? 'var(--firebg)' : 'var(--mintbg)', border: `1px solid ${active.length > 0 ? 'var(--firebd)' : 'var(--mintbd)'}` }}><div className="num" style={{ color: active.length > 0 ? 'var(--fire)' : 'var(--mint)' }}>{active.length}</div><div className="lbl">Active</div></div>
      <div className="st sv"><div className="num" style={{ color: 'var(--mint)' }}>{resolved.length}</div><div className="lbl">Resolved</div></div>
      <div className="st" style={{ background: 'var(--amberbg)', border: '1px solid var(--amberbd)' }}><div className="num" style={{ color: 'var(--amber)' }}>{autoDetected}</div><div className="lbl">Auto-Detected</div></div>
      <div className="st" style={{ background: maxEsc >= 2 ? 'var(--firebg)' : 'var(--s3)', border: `1px solid ${maxEsc >= 2 ? 'var(--firebd)' : 'var(--b2)'}` }}><div className="num" style={{ color: maxEsc >= 2 ? 'var(--fire)' : 'var(--t3)' }}>L{maxEsc}</div><div className="lbl">Max Escalation</div></div>
    </div>
    {active.length > 0 && <div className="c full"><div className="ch"><h3>Active Blockers</h3><div className="tg" style={{ background: 'var(--firebg)', border: '1px solid var(--firebd)', color: 'var(--fire)' }}>{active.length}</div></div>
      <div className="cb" style={{ padding: 0 }}>{active.map((b: any, i: number) => {
        const esc = escLevel(b.escalation_level);
        const cc = catColors[b.category] || 'grape';
        return <div key={i} style={{ padding: '12px 16px', borderBottom: i < active.length - 1 ? '1px solid var(--b2)' : 'none' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <div className="ai-dot ai-fail" style={{ flexShrink: 0 }} />
            <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 4, background: `var(--${cc}bg)`, border: `1px solid var(--${cc}bd)`, color: `var(--${cc})`, fontWeight: 700, textTransform: 'uppercase' as const }}>{b.category || 'Other'}</span>
            <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 4, background: esc.bg, border: `1px solid ${esc.bd}`, color: esc.color, fontWeight: 700 }}>{esc.label}</span>
            <span style={{ fontSize: 10, color: 'var(--fire)', fontWeight: 600, marginLeft: 'auto' }}>{age(b.created_at)} old</span>
          </div>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--t1)', marginLeft: 18 }}>{b.description}</div>
          <div style={{ fontSize: 10, color: 'var(--t3)', marginTop: 2, marginLeft: 18 }}>Owner: {b.owner || 'Unassigned'} {b.auto_detected ? '\u00b7 Auto-detected' : ''} {b.source ? `\u00b7 Source: ${b.source}` : ''}</div>
          {b.impact_assessment && <div style={{ fontSize: 10, color: 'var(--amber)', fontStyle: 'italic', marginTop: 4, marginLeft: 18 }}>{b.impact_assessment}</div>}
        </div>;
      })}</div>
    </div>}
    {resolved.length > 0 && <div className="c full"><div className="ch"><h3>Resolved</h3><div className="tg" style={{ background: 'var(--mintbg)', border: '1px solid var(--mintbd)', color: 'var(--mint)' }}>{resolved.length}</div></div>
      <div className="cb" style={{ padding: 0 }}>{resolved.map((b: any, i: number) => <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 16px', borderBottom: i < resolved.length - 1 ? '1px solid var(--b2)' : 'none' }}>
        <div className="ai-dot ai-ok" style={{ flexShrink: 0 }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12, color: 'var(--t2)' }}>{b.description}</div>
          <div style={{ fontSize: 10, color: 'var(--t3)', marginTop: 2 }}>Resolved: {fmt(b.resolved_at)} {b.resolution_notes ? `\u00b7 ${b.resolution_notes}` : ''}</div>
        </div>
      </div>)}</div>
    </div>}
    {blockers.length === 0 && <div style={{ color: 'var(--t3)', fontSize: 12, padding: 20, textAlign: 'center' }}>No blockers recorded for this job. Blockers can be auto-detected (permit denied, material unavailable, tech called off) or manually reported.</div>}
  </>;
}
