'use client';

function fmt(d: string | null | undefined): string {
  if (!d) return '\u2014';
  try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }); } catch { return d; }
}
function money(n: number | string | null | undefined): string {
  const v = parseFloat(String(n || 0)); return v > 0 ? '$' + v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : '\u2014';
}
function responseColor(sec: number | null): { label: string; color: string; bg: string; bd: string } {
  if (!sec) return { label: 'Waiting', color: 'var(--t3)', bg: 'var(--s3)', bd: 'var(--b2)' };
  if (sec <= 180) return { label: `${Math.round(sec / 60)}m`, color: 'var(--mint)', bg: 'var(--mintbg)', bd: 'var(--mintbd)' };
  if (sec <= 300) return { label: `${Math.round(sec / 60)}m`, color: 'var(--amber)', bg: 'var(--amberbg)', bd: 'var(--amberbd)' };
  if (sec <= 480) return { label: `${Math.round(sec / 60)}m`, color: 'var(--fire)', bg: 'var(--firebg)', bd: 'var(--firebd)' };
  return { label: `${Math.round(sec / 60)}m`, color: 'var(--hot)', bg: 'var(--hotbg)', bd: 'var(--hotbd)' };
}

export default function CardsTab({ job, data }: { job: any; data: any }) {
  const requests = (data.cardRequests || []) as any[];
  const receiptsPosted = requests.filter((r: any) => r.receipt_posted).length;
  const mismatches = requests.filter((r: any) => r.mismatch_flagged).length;
  const totalSpend = requests.reduce((s: number, r: any) => s + (parseFloat(r.amount) || 0), 0);

  return <>
    <div className="tab-hdr">
      <div className="tab-icon" style={{ background: 'var(--grapebg)', border: '1px solid var(--grapebd)', color: 'var(--grape)' }}>
        <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round"><rect x="1" y="4" width="22" height="16" rx="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>
      </div>
      <div className="tab-info"><div className="tab-title">Purchasing Cards</div><div className="tab-desc">Card requests, response time KPIs, receipt quality gate, reconciliation</div></div>
      <div className="tab-badge" style={{ background: requests.length > 0 ? 'var(--grapebg)' : 'var(--s3)', border: `1px solid ${requests.length > 0 ? 'var(--grapebd)' : 'var(--b2)'}`, color: requests.length > 0 ? 'var(--grape)' : 'var(--t3)' }}>{requests.length} REQUESTS</div>
    </div>
    <div className="hero" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
      <div className="st sf"><div className="num">{requests.length}</div><div className="lbl">Requests</div></div>
      <div className="st sv"><div className="num" style={{ color: 'var(--mint)' }}>{receiptsPosted}</div><div className="lbl">Receipts</div></div>
      <div className="st" style={{ background: 'var(--grapebg)', border: '1px solid var(--grapebd)' }}><div className="num" style={{ fontSize: 18, color: 'var(--grape)' }}>{money(totalSpend)}</div><div className="lbl">Total Spend</div></div>
      <div className="st" style={{ background: mismatches > 0 ? 'var(--firebg)' : 'var(--mintbg)', border: `1px solid ${mismatches > 0 ? 'var(--firebd)' : 'var(--mintbd)'}` }}><div className="num" style={{ color: mismatches > 0 ? 'var(--fire)' : 'var(--mint)' }}>{mismatches}</div><div className="lbl">Mismatches</div></div>
    </div>
    {requests.length > 0 && <div className="c full"><div className="ch"><h3>Card Request Timeline</h3></div>
      <div className="cb" style={{ padding: 0 }}>{requests.map((r: any, i: number) => {
        const rc = responseColor(r.response_time_seconds);
        return <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '12px 16px', borderBottom: i < requests.length - 1 ? '1px solid var(--b2)' : 'none' }}>
          <div className={`ai-dot ${r.reconciled ? 'ai-ok' : r.receipt_posted ? 'ai-wait' : 'ai-fail'}`} style={{ flexShrink: 0, marginTop: 2 }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--t1)', display: 'flex', alignItems: 'center', gap: 6 }}>
              Request by {r.requested_by || 'Unknown'}
              <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: rc.bg, border: `1px solid ${rc.bd}`, color: rc.color, fontWeight: 700 }}>{rc.label}</span>
            </div>
            <div style={{ fontSize: 10, color: 'var(--t3)', marginTop: 2 }}>Requested: {fmt(r.requested_at)} {r.responded_by ? `\u00b7 Issued by: ${r.responded_by}` : ''}</div>
            <div style={{ display: 'flex', gap: 8, marginTop: 6, flexWrap: 'wrap' as const }}>
              <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 4, background: r.card_issued ? 'var(--mintbg)' : 'var(--s3)', border: `1px solid ${r.card_issued ? 'var(--mintbd)' : 'var(--b2)'}`, color: r.card_issued ? 'var(--mint)' : 'var(--t3)' }}>Card {r.card_issued ? '\u2713' : 'Pending'}</span>
              <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 4, background: r.receipt_posted ? 'var(--mintbg)' : 'var(--s3)', border: `1px solid ${r.receipt_posted ? 'var(--mintbd)' : 'var(--b2)'}`, color: r.receipt_posted ? 'var(--mint)' : 'var(--t3)' }}>Receipt {r.receipt_posted ? '\u2713' : 'Pending'}</span>
              {r.receipt_ai_pass !== null && <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 4, background: r.receipt_ai_pass ? 'var(--mintbg)' : 'var(--firebg)', border: `1px solid ${r.receipt_ai_pass ? 'var(--mintbd)' : 'var(--firebd)'}`, color: r.receipt_ai_pass ? 'var(--mint)' : 'var(--fire)' }}>AI {r.receipt_ai_pass ? '\u2713' : '\u2717'}</span>}
              {r.amount > 0 && <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 4, background: 'var(--grapebg)', border: '1px solid var(--grapebd)', color: 'var(--grape)' }}>{money(r.amount)}</span>}
              {r.mismatch_flagged && <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 4, background: 'var(--firebg)', border: '1px solid var(--firebd)', color: 'var(--fire)', fontWeight: 700 }}>MISMATCH</span>}
            </div>
            {r.receipt_ai_notes && <div style={{ fontSize: 10, color: r.receipt_ai_pass ? 'var(--mint)' : 'var(--fire)', fontStyle: 'italic', marginTop: 4 }}>{r.receipt_ai_notes}</div>}
          </div>
        </div>;
      })}</div>
    </div>}
    {requests.length === 0 && <div style={{ color: 'var(--t3)', fontSize: 12, padding: 20, textAlign: 'center' }}>No purchasing card requests for this job. When a tech requests a card in Slack, it will appear here with response time tracking.</div>}
  </>;
}
