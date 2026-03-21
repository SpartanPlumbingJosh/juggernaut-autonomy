'use client';
import { useState, useEffect } from 'react';
import { fmtTime, moneyExact, Icon } from './JTClient';

function responseColor(seconds: number | null): { cls: string; label: string } {
  if (seconds == null) return { cls: 'c-info', label: 'Pending' };
  const min = seconds / 60;
  if (min <= 3) return { cls: 'c-ok', label: `${min.toFixed(1)}m` };
  if (min <= 5) return { cls: 'c-warn', label: `${min.toFixed(1)}m` };
  return { cls: 'c-fail', label: `${min.toFixed(1)}m` };
}

function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  return match ? decodeURIComponent(match[2]) : null;
}

export default function CardsTab({ job, data }: { job: any; data: any }) {
  const [requests, setRequests] = useState(data.cardRequests || []);
  const [showForm, setShowForm] = useState(false);
  const [vendor, setVendor] = useState('');
  const [description, setDescription] = useState('');
  const [amount, setAmount] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitMsg, setSubmitMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null);
  const [userName, setUserName] = useState('');
  const [userSlackId, setUserSlackId] = useState('');

  useEffect(() => {
    const cookie = getCookie('jt_user');
    if (cookie) {
      try {
        const parsed = JSON.parse(cookie);
        setUserName(parsed.name || '');
        setUserSlackId(parsed.slack_user_id || '');
      } catch { /* */ }
    }
  }, []);

  const totalSpend = requests.reduce((s: number, r: any) => s + (parseFloat(r.amount) || 0), 0);
  const receipts = requests.filter((r: any) => r.receipt_posted).length;
  const mismatches = requests.filter((r: any) => r.mismatch_flagged).length;
  const pending = requests.filter((r: any) => !r.card_issued).length;

  async function handleSubmit() {
    if (!vendor.trim() || !description.trim() || !amount.trim()) {
      setSubmitMsg({ type: 'err', text: 'All fields are required.' });
      return;
    }
    const amt = parseFloat(amount);
    if (isNaN(amt) || amt <= 0) {
      setSubmitMsg({ type: 'err', text: 'Enter a valid dollar amount.' });
      return;
    }
    setSubmitting(true);
    setSubmitMsg(null);
    try {
      const res = await fetch(`/api/job/${job.st_job_id}/card-request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          vendor_name: vendor.trim(),
          purchase_description: description.trim(),
          amount: amt,
          requested_by_name: userName,
          requested_by_slack_id: userSlackId,
        }),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.error || 'Failed');

      // Add new request to local state
      setRequests((prev: any[]) => [{
        ...result.request,
        card_issued: false,
        receipt_posted: false,
        response_time_seconds: null,
      }, ...prev]);
      setVendor('');
      setDescription('');
      setAmount('');
      setShowForm(false);
      setSubmitMsg({ type: 'ok', text: 'Card request submitted! Notification sent to the team.' });
      setTimeout(() => setSubmitMsg(null), 5000);
    } catch (err: any) {
      setSubmitMsg({ type: 'err', text: err.message || 'Something went wrong.' });
    } finally {
      setSubmitting(false);
    }
  }

  return <>
    <div className="tab-hdr">
      <div className="tab-icon" style={{ background: 'var(--grapebg)', border: '1px solid var(--grapebd)', color: 'var(--grape)' }}><Icon name="creditcard" size={20} /></div>
      <div className="tab-info"><div className="tab-title">Purchasing Cards</div><div className="tab-desc">Card request lifecycle &middot; {requests.length} requests</div></div>
    </div>
    <div className="hero" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
      <div className="st sg"><div className="num" style={{ fontSize: 22 }}>{requests.length}</div><div className="lbl">Requests</div></div>
      <div className="st" style={{ background: pending > 0 ? 'var(--amberbg)' : 'var(--mintbg)', border: `1px solid ${pending > 0 ? 'var(--amberbd)' : 'var(--mintbd)'}` }}>
        <div className="num" style={{ fontSize: 22, color: pending > 0 ? 'var(--amber)' : 'var(--mint)' }}>{pending}</div>
        <div className="lbl" style={{ color: pending > 0 ? 'var(--amber2)' : 'var(--mint2)' }}>Pending</div>
      </div>
      <div className="st sf"><div className="num" style={{ fontSize: 22 }}>{moneyExact(totalSpend)}</div><div className="lbl">Total Spend</div></div>
      <div className="st" style={{ background: mismatches > 0 ? 'var(--firebg)' : 'var(--mintbg)', border: `1px solid ${mismatches > 0 ? 'var(--firebd)' : 'var(--mintbd)'}` }}>
        <div className="num" style={{ fontSize: 22, color: mismatches > 0 ? 'var(--fire)' : 'var(--mint)' }}>{mismatches}</div>
        <div className="lbl" style={{ color: mismatches > 0 ? 'var(--fire2)' : 'var(--mint2)' }}>Mismatches</div>
      </div>
    </div>

    {/* Request Card Button */}
    <div className="c full">
      <div className="ch" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3>Request a Card</h3>
        {!showForm && (
          <button onClick={() => setShowForm(true)} style={{
            background: 'var(--grape)', color: '#fff', border: 'none', borderRadius: 8,
            padding: '8px 16px', fontSize: 13, fontWeight: 600, cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <span style={{ fontSize: 16, lineHeight: 1 }}>+</span> New Request
          </button>
        )}
      </div>
      <div className="cb">
        {submitMsg && (
          <div style={{
            padding: '10px 14px', borderRadius: 8, marginBottom: 12, fontSize: 13,
            background: submitMsg.type === 'ok' ? 'var(--mintbg)' : 'var(--firebg)',
            border: `1px solid ${submitMsg.type === 'ok' ? 'var(--mintbd)' : 'var(--firebd)'}`,
            color: submitMsg.type === 'ok' ? 'var(--mint)' : 'var(--fire)',
          }}>
            {submitMsg.text}
          </div>
        )}

        {showForm && (
          <div style={{
            background: 'var(--s1)', border: '1px solid var(--b1)', borderRadius: 10,
            padding: 20, display: 'flex', flexDirection: 'column', gap: 14,
          }}>
            {userName && (
              <div style={{ fontSize: 12, color: 'var(--t3)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <Icon name="user" size={14} /> Requesting as <strong style={{ color: 'var(--t1)' }}>{userName}</strong>
              </div>
            )}

            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--t2)', marginBottom: 4, display: 'block' }}>
                Vendor Name *
              </label>
              <input
                type="text"
                value={vendor}
                onChange={e => setVendor(e.target.value)}
                placeholder="e.g. Lee Supply, Home Depot, Ferguson..."
                style={{
                  width: '100%', padding: '10px 12px', borderRadius: 8, fontSize: 14,
                  background: 'var(--s0)', border: '1px solid var(--b2)', color: 'var(--t1)',
                  outline: 'none', boxSizing: 'border-box',
                }}
              />
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--t2)', marginBottom: 4, display: 'block' }}>
                What do you need to purchase? *
              </label>
              <textarea
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="Describe what materials or items you need to buy..."
                rows={3}
                style={{
                  width: '100%', padding: '10px 12px', borderRadius: 8, fontSize: 14,
                  background: 'var(--s0)', border: '1px solid var(--b2)', color: 'var(--t1)',
                  outline: 'none', resize: 'vertical', fontFamily: 'inherit', boxSizing: 'border-box',
                }}
              />
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--t2)', marginBottom: 4, display: 'block' }}>
                Card Amount Needed *
              </label>
              <div style={{ position: 'relative' }}>
                <span style={{
                  position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)',
                  color: 'var(--t3)', fontSize: 14, fontWeight: 600,
                }}>$</span>
                <input
                  type="number"
                  value={amount}
                  onChange={e => setAmount(e.target.value)}
                  placeholder="0.00"
                  min="0"
                  step="0.01"
                  style={{
                    width: '100%', padding: '10px 12px 10px 28px', borderRadius: 8, fontSize: 14,
                    background: 'var(--s0)', border: '1px solid var(--b2)', color: 'var(--t1)',
                    outline: 'none', fontFamily: 'var(--mono)', boxSizing: 'border-box',
                  }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
              <button
                onClick={handleSubmit}
                disabled={submitting}
                style={{
                  background: submitting ? 'var(--t4)' : 'var(--grape)',
                  color: '#fff', border: 'none', borderRadius: 8,
                  padding: '10px 24px', fontSize: 14, fontWeight: 600, cursor: submitting ? 'wait' : 'pointer',
                  flex: 1,
                }}
              >
                {submitting ? 'Submitting...' : 'Submit Card Request'}
              </button>
              <button
                onClick={() => { setShowForm(false); setVendor(''); setDescription(''); setAmount(''); }}
                style={{
                  background: 'transparent', color: 'var(--t3)', border: '1px solid var(--b2)',
                  borderRadius: 8, padding: '10px 16px', fontSize: 13, cursor: 'pointer',
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {!showForm && requests.length === 0 && (
          <div style={{ color: 'var(--t3)', fontSize: 13, textAlign: 'center', padding: '20px 0' }}>
            No card requests yet. Click &quot;New Request&quot; to get started.
          </div>
        )}
      </div>
    </div>

    {/* Card Request Timeline */}
    {requests.length > 0 && <div className="c full">
      <div className="ch"><h3>Card Request Timeline</h3></div>
      <div className="cb">
        {requests.map((r: any, i: number) => {
          const resp = responseColor(r.response_time_seconds);
          return <div key={r.id || i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '12px 0', borderBottom: i < requests.length - 1 ? '1px solid var(--b1)' : 'none' }}>
            <div className={`ai-dot ${r.card_issued ? 'ai-ok' : 'ai-wait'}`} style={{ marginTop: 4 }} />
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>{r.requested_by_name || r.requested_by || 'Unknown'}</span>
                <span className={`chip ${resp.cls}`}>{resp.label}</span>
                {r.card_issued && <span className="chip c-ok">Card Issued</span>}
                {r.receipt_posted && <span className="chip c-ok">Receipt &#10003;</span>}
                {r.receipt_ai_pass != null && <span className={`chip ${r.receipt_ai_pass ? 'c-ok' : 'c-fail'}`}>AI {r.receipt_ai_pass ? 'Pass' : 'Fail'}</span>}
                {r.mismatch_flagged && <span className="chip c-fail">MISMATCH</span>}
              </div>
              {(r.vendor_name || r.purchase_description) && (
                <div style={{ marginTop: 6, padding: '8px 10px', background: 'var(--s1)', borderRadius: 6, border: '1px solid var(--b1)' }}>
                  {r.vendor_name && (
                    <div style={{ fontSize: 12, color: 'var(--t2)' }}>
                      <span style={{ fontWeight: 600, color: 'var(--t1)' }}>Vendor:</span> {r.vendor_name}
                    </div>
                  )}
                  {r.purchase_description && (
                    <div style={{ fontSize: 12, color: 'var(--t2)', marginTop: 2 }}>
                      <span style={{ fontWeight: 600, color: 'var(--t1)' }}>Need:</span> {r.purchase_description}
                    </div>
                  )}
                </div>
              )}
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
  </>;
}