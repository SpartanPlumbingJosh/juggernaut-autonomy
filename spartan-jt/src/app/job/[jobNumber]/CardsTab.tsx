'use client';
import { fmtTime, moneyExact, Icon } from './JTClient';

function responseColor(seconds: number | null): { cls: string; label: string } {
  if (seconds == null) return { cls: 'c-info', label: 'Pending' };
  const min = seconds / 60;
  if (min <= 3) return { cls: 'c-ok', label: `${min.toFixed(1)}m` };
  if (min <= 5) return { cls: 'c-warn', label: `${min.toFixed(1)}m` };
  if (min <= 8) return { cls: 'c-fail', label: `${min.toFixed(1)}m` };
  return { cls: 'c-fail', label: `${min.toFixed(1)}m` };
}

export default function CardsTab({ job, data }: { job: any; data: any }) {
  const requests = data.cardRequests || [];
  const totalSpend = requests.reduce((s: number, r: any) => s + (parseFloat(r.amount) || 0), 0);
  const receipts = requests.filter((r: any) => r.receipt_posted).length;
  const mismatches = requests.filter((r: any) => r.mismatch_flagged).length;

  return <>
    <div className="tab-hdr">
      <div className="tab-icon" style={{ background: 'var(--grapebg)', border: '1px solid var(--grapebd)', color: 'var(--grape)' }}><Icon name="creditcard" size={20} /></div>
      <div className="tab-info"><div className="tab-title">Purchasing Cards</div><div className="tab-desc">Card request lifecycle &middot; {requests.length} requests</div></div>
    </div>
    <div className="hero" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
      <div className="st sg"><div className="num" style={{ fontSize: 22 }}>{requests.length}</div><div className="lbl">Requests</div></div>
      <div className="st sm"><div className="num" style={{ fontSize: 22 }}>{receipts}</div><div className="lbl">Receipts</div></div>
      <div className="st sf"><div className="num" style={{ fontSize: 22 }}>{moneyExact(totalSpend)}</div><div className="lbl">Total Spend</div></div>
      <div className="st" style={{ background: mismatches > 0 ? 'var(--firebg)' : 'var(--mintbg)', border: `1px solid ${mismatches > 0 ? 'var(--firebd)' : 'var(--mintbd)'}` }}>
        <div className="num" style={{ fontSize: 22, color: mismatches > 0 ? 'var(--fire)' : 'var(--mint)' }}>{mismatches}</div>
        <div className="lbl" style={{ color: mismatches > 0 ? 'var(--fire2)' : 'var(--mint2)' }}>Mismatches</div>
      </div>
    </div>
    {requests.length > 0 && <div className="c full">
      <div className="ch"><h3>Card Request Timeline</h3></div>
      <div className="cb">
        {requests.map((r: any, i: number) => {
          const resp = responseColor(r.response_time_seconds);
          return <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '12px 0', borderBottom: i < requests.length - 1 ? '1px solid var(--b1)' : 'none' }}>
            <div className={`ai-dot ${r.card_issued ? 'ai-ok' : 'ai-wait'}`} style={{ marginTop: 4 }} />
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>{r.requested_by || 'Unknown'}</span>
                <span className={`chip ${resp.cls}`}>{resp.label}</span>
                {r.card_issued && <span className="chip c-ok">Card Issued</span>}
                {r.receipt_posted && <span className="chip c-ok">Receipt ✓</span>}
                {r.receipt_ai_pass != null && <span className={`chip ${r.receipt_ai_pass ? 'c-ok' : 'c-fail'}`}>AI {r.receipt_ai_pass ? 'Pass' : 'Fail'}</span>}
                {r.mismatch_flagged && <span className="chip c-fail">MISMATCH</span>}
              </div>
              <div style={{ display: 'flex', gap: 16, marginTop: 4, fontSize: 11, color: 'var(--t3)' }}>
                <span>Requested: {fmtTime(r.requested_at)}</span>
                {r.responded_at && <span>Issued: {fmtTime(r.responded_at)}</span>}
                {r.amount && <span style={{ fontFamily: 'var(--mono)', color: 'var(--t1)' }}>{moneyExact(r.amount)}</span>}
              </div>
              {r.receipt_ai_notes && <div style={{ fontSize: 11, color: 'var(--t2)', marginTop: 4, fontStyle: 'italic' }}>{r.receipt_ai_notes}</div>}
            </div>
          </div>;
        })}
      </div>
    </div>}
    {requests.length === 0 && <div style={{ color: 'var(--t3)', fontSize: 12, textAlign: 'center', padding: 40 }}>No purchasing card requests for this job.</div>}
  </>;
}
