'use client';

import { useState, useCallback, useEffect } from 'react';

function fmt(d: string | null | undefined): string {
  if (!d) return '\u2014';
  try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); } catch { return d; }
}
function money(n: number | string | null | undefined): string {
  const v = parseFloat(String(n || 0));
  return v > 0 ? '$' + v.toLocaleString(undefined, { maximumFractionDigits: 0 }) : '\u2014';
}

const sentimentMeta: Record<string, { label: string; color: string; bg: string; bd: string }> = {
  positive: { label: 'Positive', color: 'var(--mint)', bg: 'var(--mintbg)', bd: 'var(--mintbd)' },
  neutral: { label: 'Neutral', color: 'var(--ice)', bg: 'var(--icebg)', bd: 'var(--icebd)' },
  cautious: { label: 'Cautious', color: 'var(--amber)', bg: 'var(--amberbg)', bd: 'var(--amberbd)' },
  negative: { label: 'Negative', color: 'var(--fire)', bg: 'var(--firebg)', bd: 'var(--firebd)' },
};
const priorityMeta: Record<string, { label: string; color: string; bg: string; bd: string }> = {
  routine: { label: 'Routine', color: 'var(--mint)', bg: 'var(--mintbg)', bd: 'var(--mintbd)' },
  attention: { label: 'Attention', color: 'var(--amber)', bg: 'var(--amberbg)', bd: 'var(--amberbd)' },
  high_priority: { label: 'High Priority', color: 'var(--fire)', bg: 'var(--firebg)', bd: 'var(--firebd)' },
};

function AiBriefing({ jobId }: { jobId: string }) {
  const [briefing, setBriefing] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isCached, setIsCached] = useState(false);

  const load = useCallback(async (forceRefresh = false) => {
    setLoading(true);
    setError(null);
    try {
      const url = `/api/job/${jobId}/intel-briefing${forceRefresh ? '?refresh=true' : ''}`;
      const res = await fetch(url);
      if (!res.ok) { const err = await res.json(); throw new Error(err.error || 'Failed'); }
      const data = await res.json();
      setBriefing(data);
      setIsCached(!!data.cached);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }, [jobId]);

  // Load on mount (will return cached if available — fast)
  useEffect(() => { load(false); }, [load]);

  if (loading && !briefing) {
    return <div className="intel" style={{ borderColor: 'var(--grapebd)' }}>
      <div className="intel-h">
        <div className="intel-icon" style={{ background: 'var(--grapebg)', color: 'var(--grape)' }}>
          <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
        </div>
        <div className="intel-title">AI Briefing</div>
      </div>
      <div className="intel-body" style={{ textAlign: 'center', padding: 20, fontSize: 14, color: 'var(--grape)' }}>Analyzing customer data...</div>
    </div>;
  }

  if (error && !briefing) {
    return <div className="intel" style={{ borderColor: 'var(--firebd)' }}>
      <div className="intel-h">
        <div className="intel-icon" style={{ background: 'var(--firebg)', color: 'var(--fire)' }}>
          <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
        </div>
        <div className="intel-title">AI Briefing</div>
      </div>
      <div className="intel-body">
        <div style={{ fontSize: 14, color: 'var(--fire)', marginBottom: 8 }}>{error}</div>
        <button onClick={() => load(true)} style={{ padding: '8px 16px', borderRadius: 8, border: '1px solid var(--grapebd)', background: 'var(--grapebg)', color: 'var(--grape)', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>Retry</button>
      </div>
    </div>;
  }

  if (!briefing) return null;
  const b = briefing?.briefing || {};
  const sM = sentimentMeta[b.customer_sentiment] || sentimentMeta.neutral;
  const pM = priorityMeta[b.priority_level] || priorityMeta.routine;

  return <div className="intel" style={{ borderColor: 'var(--grapebd)' }}>
    <div className="intel-h">
      <div className="intel-icon" style={{ background: 'var(--grapebg)', color: 'var(--grape)' }}>
        <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
      </div>
      <div className="intel-title">AI Briefing</div>
      <div style={{ display: 'flex', gap: 6, marginLeft: 'auto', alignItems: 'center' }}>
        <span style={{ fontSize: 13, padding: '3px 10px', borderRadius: 6, fontWeight: 700, background: sM.bg, border: `1px solid ${sM.bd}`, color: sM.color }}>{sM.label}</span>
        <span style={{ fontSize: 13, padding: '3px 10px', borderRadius: 6, fontWeight: 700, background: pM.bg, border: `1px solid ${pM.bd}`, color: pM.color }}>{pM.label}</span>
      </div>
    </div>
    <div className="intel-body">
      <div style={{ fontSize: 14, color: 'var(--t1)', lineHeight: 1.6, marginBottom: 12 }}>{b.summary}</div>

      {(b.risk_flags || []).length > 0 && <div style={{ marginBottom: 10 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--fire)', textTransform: 'uppercase' as const, letterSpacing: 0.5, marginBottom: 4 }}>Risk Flags</div>
        {(b.risk_flags as string[]).map((f: string, i: number) => (
          <div key={i} style={{ fontSize: 14, color: 'var(--t2)', padding: '3px 0', display: 'flex', gap: 6 }}>
            <span style={{ color: 'var(--fire)', flexShrink: 0 }}>{'\u2022'}</span>{f}
          </div>
        ))}
      </div>}

      {(b.upsell_opportunities || []).length > 0 && <div style={{ marginBottom: 10 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--volt)', textTransform: 'uppercase' as const, letterSpacing: 0.5, marginBottom: 4 }}>Upsell Opportunities</div>
        {(b.upsell_opportunities as string[]).map((u: string, i: number) => (
          <div key={i} style={{ fontSize: 14, color: 'var(--t2)', padding: '3px 0', display: 'flex', gap: 6 }}>
            <span style={{ color: 'var(--volt)', flexShrink: 0 }}>{'\u2022'}</span>{u}
          </div>
        ))}
      </div>}

      {(b.approach_tips || []).length > 0 && <div>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ice)', textTransform: 'uppercase' as const, letterSpacing: 0.5, marginBottom: 4 }}>Approach</div>
        {(b.approach_tips as string[]).map((t: string, i: number) => (
          <div key={i} style={{ fontSize: 14, color: 'var(--t2)', padding: '3px 0', display: 'flex', gap: 6 }}>
            <span style={{ color: 'var(--ice)', flexShrink: 0 }}>{'\u2192'}</span>{t}
          </div>
        ))}
      </div>}

      <div style={{ marginTop: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 13, color: 'var(--t3)' }}>
          {isCached ? 'Cached' : 'Generated'} {briefing?.generated_at ? new Date(briefing.generated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' + new Date(briefing.generated_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }) : ''}
        </span>
        <button onClick={() => load(true)} disabled={loading} style={{
          padding: '6px 14px', borderRadius: 8, border: '1px solid var(--b2)',
          background: 'var(--s3)', color: loading ? 'var(--t4)' : 'var(--t2)', fontSize: 13, fontWeight: 600, cursor: loading ? 'default' : 'pointer'
        }}>{loading ? 'Refreshing...' : 'Refresh'}</button>
      </div>
    </div>
  </div>;
}

export default function IntelTab({ job, data, amt }: { job: any; data: any; amt: number }) {
  const related = data.relatedJobs || [];
  const unsoldEstimates = (data.unsoldEstimates || []) as any[];
  const recallsAtLocation = (data.recallsAtLocation || []) as any[];
  const estimates = (data.estimates || []) as any[];
  const recallCount = related.filter((r: any) => r.recall_for_id).length;
  const totalSpent = related.reduce((s: number, r: any) => s + (parseFloat(r.total) || 0), 0) + amt;
  const customerName = job.customer_name || 'Customer';

  return <>
    {/* Header */}
    <div style={{ marginBottom: 24 }}>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--t4)', marginBottom: 6 }}>Customer Intel</div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 800, letterSpacing: '-.5px' }}>{customerName}</h1>
          <div style={{ fontSize: 14, color: 'var(--t3)', marginTop: 4 }}>Know everything before you knock</div>
        </div>
        <div style={{ background: 'var(--icebg)', border: '1px solid var(--icebd)', color: 'var(--ice)', fontFamily: 'var(--mono)', fontSize: 14, fontWeight: 700, padding: '6px 14px', borderRadius: 10 }}>READ-ONLY</div>
      </div>
    </div>

    {/* Hero */}
    <div className="hero" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
      <div className="st sf"><div className="num">{related.length + 1}</div><div className="lbl">Jobs</div></div>
      <div className="st sv"><div className="num">{money(totalSpent)}</div><div className="lbl">Lifetime</div></div>
      <div className="st sm"><div className="num">{money(amt)}</div><div className="lbl">This Job</div></div>
      <div className="st" style={{ background: recallCount > 0 ? 'var(--amberbg)' : 'var(--s3)', border: `1px solid ${recallCount > 0 ? 'var(--amberbd)' : 'var(--b2)'}` }}>
        <div className="num" style={{ color: recallCount > 0 ? 'var(--amber)' : 'var(--t3)' }}>{recallCount}</div>
        <div className="lbl">Recalls</div>
      </div>
    </div>

    {/* AI Briefing — loads cached first, only regenerates on Refresh click */}
    <AiBriefing jobId={String(job.st_job_id)} />

    {/* Open Opportunities */}
    {unsoldEstimates.length > 0 && <div className="c full">
      <div className="ch"><h3>Open Opportunities</h3><div className="tg" style={{ background: 'var(--firebg)', border: '1px solid var(--firebd)', color: 'var(--fire)' }}>{unsoldEstimates.length}</div></div>
      <div className="cb" style={{ padding: 0 }}>
        <table className="mt"><thead><tr><th>Estimate</th><th>Status</th><th>Summary</th><th>Amount</th><th>Job #</th><th>Date</th></tr></thead><tbody>
          {unsoldEstimates.map((e: any, i: number) => <tr key={i}>
            <td style={{ fontFamily: 'var(--mono)', color: 'var(--fire)' }}>{e.st_estimate_id}</td>
            <td><span className="chip c-info">{e.status_name || '\u2014'}</span></td>
            <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.summary || e.estimate_name || '\u2014'}</td>
            <td style={{ color: 'var(--fire)', fontWeight: 600 }}>{money(e.subtotal)}</td>
            <td style={{ fontFamily: 'var(--mono)', color: 'var(--ice)' }}>{e.job_number || e.st_job_id}</td>
            <td>{fmt(e.created_on)}</td>
          </tr>)}
        </tbody></table>
      </div>
    </div>}

    {/* Estimates on This Job */}
    {estimates.length > 0 && <div className="c full">
      <div className="ch"><h3>Estimates</h3><div className="tg" style={{ background: 'var(--mintbg)', border: '1px solid var(--mintbd)', color: 'var(--mint)' }}>{estimates.length}</div></div>
      <div className="cb" style={{ padding: 0 }}>
        <table className="mt"><thead><tr><th>Estimate</th><th>Status</th><th>Name</th><th>Amount</th><th>Sold By</th><th>Date</th></tr></thead><tbody>
          {estimates.map((e: any, i: number) => <tr key={i}>
            <td style={{ fontFamily: 'var(--mono)', color: 'var(--ice)' }}>{e.st_estimate_id}</td>
            <td><span className={`chip ${e.status_name === 'Sold' ? 'c-ok' : e.status_name === 'Dismissed' ? 'c-fail' : 'c-info'}`}>{e.status_name || '\u2014'}</span></td>
            <td>{e.estimate_name || e.summary || '\u2014'}</td>
            <td style={{ fontWeight: 600 }}>{money(e.subtotal)}</td>
            <td>{e.sold_by_name || '\u2014'}</td>
            <td>{fmt(e.sold_on || e.created_on)}</td>
          </tr>)}
        </tbody></table>
      </div>
    </div>}

    {/* Previous Jobs */}
    <div className="c full"><div className="ch"><h3>Previous Jobs</h3><div className="tg" style={{ background: 'var(--voltbg)', border: '1px solid var(--voltbd)', color: 'var(--volt)' }}>{related.length}</div></div>
      {related.length > 0 ? <div className="cb" style={{ padding: 0 }}><table className="mt"><thead><tr><th>Job #</th><th>Type</th><th>Status</th><th>Amount</th><th>Date</th></tr></thead><tbody>
        {related.map((r: any, i: number) => <tr key={i}><td style={{ fontFamily: 'var(--mono)', color: 'var(--ice)' }}>{r.job_number || r.st_job_id}</td><td>{r.job_type_name || r.business_unit_name || '\u2014'}</td><td><span className={`chip ${r.status === 'Completed' ? 'c-ok' : 'c-info'}`}>{r.status}</span></td><td>{money(r.total)}</td><td>{fmt(r.created_on)}</td></tr>)}
      </tbody></table></div> : <div className="cb" style={{ color: 'var(--t3)', fontSize: 14 }}>No prior jobs at this location.</div>}
    </div>

    {/* Recall History */}
    {recallsAtLocation.length > 0 && <div className="c full">
      <div className="ch"><h3>Recalls</h3><div className="tg" style={{ background: 'var(--amberbg)', border: '1px solid var(--amberbd)', color: 'var(--amber)' }}>{recallsAtLocation.length}</div></div>
      <div className="cb" style={{ padding: 0 }}>
        <table className="mt"><thead><tr><th>Job</th><th>Status</th><th>For Job</th><th>Summary</th><th>Date</th></tr></thead><tbody>
          {recallsAtLocation.map((r: any, i: number) => <tr key={i}>
            <td style={{ fontFamily: 'var(--mono)', color: 'var(--amber)' }}>{r.job_number || r.st_job_id}</td>
            <td><span className={`chip ${r.status === 'Completed' ? 'c-ok' : 'c-info'}`}>{r.status}</span></td>
            <td style={{ fontFamily: 'var(--mono)', color: 'var(--ice)' }}>{r.recall_for_id}</td>
            <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.summary || '\u2014'}</td>
            <td>{fmt(r.created_on)}</td>
          </tr>)}
        </tbody></table>
      </div>
    </div>}
  </>;
}
