'use client';

function fmt(d: string | null | undefined): string {
  if (!d) return '\u2014';
  try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); } catch { return d; }
}

const statusColors: Record<string, { color: string; bg: string; bd: string }> = {
  Filed: { color: 'var(--ice)', bg: 'var(--icebg)', bd: 'var(--icebd)' },
  Pending: { color: 'var(--amber)', bg: 'var(--amberbg)', bd: 'var(--amberbd)' },
  Approved: { color: 'var(--mint)', bg: 'var(--mintbg)', bd: 'var(--mintbd)' },
  'On-site': { color: 'var(--volt)', bg: 'var(--voltbg)', bd: 'var(--voltbd)' },
  Denied: { color: 'var(--fire)', bg: 'var(--firebg)', bd: 'var(--firebd)' },
  Resubmit: { color: 'var(--fire)', bg: 'var(--firebg)', bd: 'var(--firebd)' },
};

export default function PermitsTab({ job, data }: { job: any; data: any }) {
  const permits = (data.permits || []) as any[];
  const permitRules = (data.permitRules || []) as any[];
  const approved = permits.filter((p: any) => p.status === 'Approved' || p.status === 'On-site').length;
  const pending = permits.filter((p: any) => p.status === 'Filed' || p.status === 'Pending').length;
  const aiVerified = permits.filter((p: any) => p.ai_verified).length;

  return <>
    <div className="tab-hdr">
      <div className="tab-icon" style={{ background: 'var(--amberbg)', border: '1px solid var(--amberbd)', color: 'var(--amber)' }}>
        <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round"><path d="M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/></svg>
      </div>
      <div className="tab-info"><div className="tab-title">Permits</div><div className="tab-desc">Jurisdiction-aware permit tracking with AI document verification</div></div>
      <div className="tab-badge" style={{ background: approved > 0 ? 'var(--mintbg)' : 'var(--s3)', border: `1px solid ${approved > 0 ? 'var(--mintbd)' : 'var(--b2)'}`, color: approved > 0 ? 'var(--mint)' : 'var(--t3)' }}>{approved}/{permits.length} APPROVED</div>
    </div>
    <div className="hero" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
      <div className="st sf"><div className="num">{permits.length}</div><div className="lbl">Total Permits</div></div>
      <div className="st sv"><div className="num" style={{ color: 'var(--mint)' }}>{approved}</div><div className="lbl">Approved</div></div>
      <div className="st" style={{ background: 'var(--amberbg)', border: '1px solid var(--amberbd)' }}><div className="num" style={{ color: 'var(--amber)' }}>{pending}</div><div className="lbl">Pending</div></div>
      <div className="st" style={{ background: 'var(--icebg)', border: '1px solid var(--icebd)' }}><div className="num" style={{ color: 'var(--ice)' }}>{aiVerified}</div><div className="lbl">AI Verified</div></div>
    </div>
    {permits.length > 0 && <div className="c full"><div className="ch"><h3>Permit Documents</h3><div className="tg" style={{ background: 'var(--amberbg)', border: '1px solid var(--amberbd)', color: 'var(--amber)' }}>{permits.length}</div></div>
      <div className="cb" style={{ padding: 0 }}>{permits.map((p: any, i: number) => {
        const sc = statusColors[p.status] || { color: 'var(--t3)', bg: 'var(--s3)', bd: 'var(--b2)' };
        return <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px', borderBottom: i < permits.length - 1 ? '1px solid var(--b2)' : 'none' }}>
          <div className={`ai-dot ${p.ai_verified ? 'ai-ok' : p.status === 'Denied' ? 'ai-fail' : 'ai-wait'}`} style={{ flexShrink: 0 }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--t1)' }}>{p.permit_type || 'Permit'}</div>
            <div style={{ fontSize: 10, color: 'var(--t3)', marginTop: 2 }}>Filed: {fmt(p.filed_date)} {p.approved_date ? `\u00b7 Approved: ${fmt(p.approved_date)}` : ''} {p.expires_date ? `\u00b7 Expires: ${fmt(p.expires_date)}` : ''}</div>
            {p.ai_notes && <div style={{ fontSize: 10, color: 'var(--mint)', fontStyle: 'italic', marginTop: 2 }}>{p.ai_notes}</div>}
          </div>
          <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, fontWeight: 700, background: sc.bg, border: `1px solid ${sc.bd}`, color: sc.color }}>{p.status}</span>
          {p.ai_verified && <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 4, background: 'var(--mintbg)', border: '1px solid var(--mintbd)', color: 'var(--mint)', fontWeight: 700 }}>AI \u2713</span>}
        </div>;
      })}</div>
    </div>}
    {permitRules.length > 0 && <div className="c full"><div className="ch"><h3>Jurisdiction Rules</h3><div className="tg" style={{ background: 'var(--icebg)', border: '1px solid var(--icebd)', color: 'var(--ice)' }}>{permitRules.length}</div></div>
      <div className="cb" style={{ padding: 0 }}><table className="mt"><thead><tr><th>Jurisdiction</th><th>Type</th><th>Required</th><th>Confidence</th><th>Reviewed</th></tr></thead><tbody>
        {permitRules.map((r: any, i: number) => <tr key={i}><td>{r.jurisdiction}</td><td>{r.permit_type}</td><td style={{ color: r.required ? 'var(--fire)' : 'var(--mint)' }}>{r.required ? 'Yes' : 'No'}</td><td>{r.confidence_level || '\u2014'}</td><td>{r.reviewed ? '\u2713' : '\u2014'}</td></tr>)}
      </tbody></table></div>
    </div>}
    {permits.length === 0 && permitRules.length === 0 && <div style={{ color: 'var(--t3)', fontSize: 12, padding: 20, textAlign: 'center' }}>No permits filed for this job yet. When the job type and jurisdiction are known, AI will research permit requirements automatically.</div>}
  </>;
}
