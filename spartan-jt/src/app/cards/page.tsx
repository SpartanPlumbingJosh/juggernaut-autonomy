'use client';
import { useEffect, useState } from 'react';

function fmt(d: string | null | undefined): string {
  if (!d) return '\u2014';
  try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }); } catch { return d; }
}

function money(n: number | string | null | undefined): string {
  const v = parseFloat(String(n || 0));
  return v > 0 ? '$' + v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '\u2014';
}

function fmtDuration(seconds: number | null): string {
  if (seconds == null) return '\u2014';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function receiptTimeColor(seconds: number | null): string {
  if (seconds == null) return 'var(--t3)';
  const hrs = seconds / 3600;
  if (hrs <= 2) return 'var(--mint)';
  if (hrs <= 8) return 'var(--amber)';
  return 'var(--fire)';
}

export default function CardsPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/cards')
      .then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: 'var(--s0)', color: 'var(--t2)', fontFamily: 'var(--sans)' }}>Loading card requests...</div>;
  if (error) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: 'var(--s0)', color: 'var(--fire)', fontFamily: 'var(--sans)' }}>Error: {error}</div>;

  const { requests, stats, byPerson } = data || { requests: [], stats: {}, byPerson: {} };
  const receiptPct = stats.total > 0 ? Math.round((stats.withReceipt / stats.total) * 100) : 0;
  const people = Object.entries(byPerson || {}).sort((a: any, b: any) => b[1].total - a[1].total);

  return (
    <div style={{ background: 'var(--s0)', minHeight: '100vh', fontFamily: 'var(--sans)', color: 'var(--t1)' }}>
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 20px' }}>
        {/* Header */}
        <div style={{ marginBottom: 28 }}>
          <div style={{ fontSize: 12, color: 'var(--t3)', marginBottom: 4 }}>Spartan Job Tracker</div>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 10 }}>
            <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round"><rect x="1" y="4" width="22" height="16" rx="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>
            Credit Card Requests
          </h1>
          <div style={{ fontSize: 13, color: 'var(--t3)', marginTop: 4 }}>All card requests across all jobs &middot; Receipt compliance tracking</div>
        </div>

        {/* Hero Stats */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 24 }}>
          <div style={{ background: 'var(--s1)', border: '1px solid var(--b1)', borderRadius: 10, padding: '16px 14px', textAlign: 'center' }}>
            <div style={{ fontSize: 26, fontWeight: 700 }}>{stats.total || 0}</div>
            <div style={{ fontSize: 11, color: 'var(--t3)', marginTop: 2 }}>Total Requests</div>
          </div>
          <div style={{ background: 'var(--s1)', border: '1px solid var(--b1)', borderRadius: 10, padding: '16px 14px', textAlign: 'center' }}>
            <div style={{ fontSize: 26, fontWeight: 700, color: receiptPct >= 80 ? 'var(--mint)' : receiptPct >= 50 ? 'var(--amber)' : 'var(--fire)' }}>{receiptPct}%</div>
            <div style={{ fontSize: 11, color: 'var(--t3)', marginTop: 2 }}>Receipt Compliance</div>
          </div>
          <div style={{ background: stats.missing > 0 ? 'var(--firebg)' : 'var(--mintbg)', border: `1px solid ${stats.missing > 0 ? 'var(--firebd)' : 'var(--mintbd)'}`, borderRadius: 10, padding: '16px 14px', textAlign: 'center' }}>
            <div style={{ fontSize: 26, fontWeight: 700, color: stats.missing > 0 ? 'var(--fire)' : 'var(--mint)' }}>{stats.missing || 0}</div>
            <div style={{ fontSize: 11, color: stats.missing > 0 ? 'var(--fire2)' : 'var(--mint2)', marginTop: 2 }}>Missing Receipts</div>
          </div>
          <div style={{ background: 'var(--s1)', border: '1px solid var(--b1)', borderRadius: 10, padding: '16px 14px', textAlign: 'center' }}>
            <div style={{ fontSize: 22, fontWeight: 700, fontFamily: 'var(--mono)' }}>{money(stats.totalSpend)}</div>
            <div style={{ fontSize: 11, color: 'var(--t3)', marginTop: 2 }}>Total Spend</div>
          </div>
          <div style={{ background: 'var(--s1)', border: '1px solid var(--b1)', borderRadius: 10, padding: '16px 14px', textAlign: 'center' }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: receiptTimeColor(stats.avgReceiptSeconds) }}>{fmtDuration(stats.avgReceiptSeconds)}</div>
            <div style={{ fontSize: 11, color: 'var(--t3)', marginTop: 2 }}>Avg Receipt Time</div>
          </div>
        </div>

        {/* Per-Person Breakdown */}
        {people.length > 0 && (
          <div style={{ background: 'var(--s1)', border: '1px solid var(--b1)', borderRadius: 10, padding: 16, marginBottom: 24 }}>
            <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 12px 0' }}>By Team Member</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 10 }}>
              {people.map(([name, s]: [string, any]) => {
                const pct = s.total > 0 ? Math.round((s.receipts / s.total) * 100) : 0;
                return (
                  <div key={name} style={{ background: 'var(--s0)', border: '1px solid var(--b1)', borderRadius: 8, padding: '10px 12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                      <span style={{ fontSize: 13, fontWeight: 600 }}>{name}</span>
                      <span style={{ fontSize: 11, fontWeight: 600, color: pct === 100 ? 'var(--mint)' : pct >= 50 ? 'var(--amber)' : 'var(--fire)' }}>{pct}%</span>
                    </div>
                    <div style={{ display: 'flex', gap: 12, fontSize: 11, color: 'var(--t3)' }}>
                      <span>{s.total} requests</span>
                      <span style={{ color: 'var(--mint)' }}>{s.receipts} receipts</span>
                      {s.missing > 0 && <span style={{ color: 'var(--fire)' }}>{s.missing} missing</span>}
                    </div>
                    <div style={{ marginTop: 6, height: 4, background: 'var(--b1)', borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${pct}%`, background: pct === 100 ? 'var(--mint)' : pct >= 50 ? 'var(--amber)' : 'var(--fire)', borderRadius: 2, transition: 'width 0.3s' }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Request Table */}
        <div style={{ background: 'var(--s1)', border: '1px solid var(--b1)', borderRadius: 10, overflow: 'hidden' }}>
          <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--b1)' }}>
            <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>All Card Requests</h3>
          </div>
          {requests.length === 0 ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--t3)', fontSize: 13 }}>
              No card requests yet. Requests will appear here when techs use the card request form in the Job Tracker.
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--b1)' }}>
                    <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 11, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Status</th>
                    <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 11, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Job</th>
                    <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 11, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Requested By</th>
                    <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 11, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Vendor</th>
                    <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 11, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Amount</th>
                    <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 11, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Requested</th>
                    <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: 600, fontSize: 11, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Receipt</th>
                    <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: 600, fontSize: 11, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Time to Receipt</th>
                  </tr>
                </thead>
                <tbody>
                  {requests.map((r: any, i: number) => {
                    let receiptSeconds: number | null = null;
                    if (r.receipt_posted && r.receipt_message_ts && r.requested_at) {
                      const reqTime = new Date(r.requested_at).getTime() / 1000;
                      const receiptTs = parseFloat(r.receipt_message_ts);
                      if (receiptTs > reqTime) receiptSeconds = receiptTs - reqTime;
                    }
                    const isOld = !r.receipt_posted && r.requested_at && (Date.now() - new Date(r.requested_at).getTime()) > 24 * 3600 * 1000;
                    return (
                      <tr key={r.id || i} style={{ borderBottom: i < requests.length - 1 ? '1px solid var(--b1)' : 'none', background: isOld ? 'rgba(255,59,48,0.04)' : 'transparent' }}>
                        <td style={{ padding: '10px 12px' }}>
                          <div style={{
                            width: 10, height: 10, borderRadius: '50%',
                            background: r.receipt_posted ? 'var(--mint)' : isOld ? 'var(--fire)' : 'var(--amber)',
                            boxShadow: `0 0 6px ${r.receipt_posted ? 'var(--mint)' : isOld ? 'var(--fire)' : 'var(--amber)'}`,
                          }} />
                        </td>
                        <td style={{ padding: '10px 12px' }}>
                          <a href={`/job/${r.st_job_id}`} style={{ color: 'var(--ice)', textDecoration: 'none', fontFamily: 'var(--mono)', fontWeight: 600 }}>
                            #{r.st_job_id}
                          </a>
                          {r.customer_name && <div style={{ fontSize: 11, color: 'var(--t3)' }}>{r.customer_name}</div>}
                        </td>
                        <td style={{ padding: '10px 12px', fontWeight: 500 }}>{r.requested_by_name || r.requested_by || '\u2014'}</td>
                        <td style={{ padding: '10px 12px' }}>
                          <div>{r.vendor_name || '\u2014'}</div>
                          {r.purchase_description && <div style={{ fontSize: 11, color: 'var(--t3)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.purchase_description}</div>}
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'right', fontFamily: 'var(--mono)', fontWeight: 600 }}>{money(r.amount)}</td>
                        <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--t2)' }}>{fmt(r.requested_at)}</td>
                        <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                          {r.receipt_posted ? (
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, fontWeight: 600, color: 'var(--mint)', background: 'var(--mintbg)', border: '1px solid var(--mintbd)', borderRadius: 6, padding: '3px 8px' }}>&#10003; Posted</span>
                          ) : (
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, fontWeight: 600, color: isOld ? 'var(--fire)' : 'var(--amber)', background: isOld ? 'var(--firebg)' : 'var(--amberbg)', border: `1px solid ${isOld ? 'var(--firebd)' : 'var(--amberbd)'}`, borderRadius: 6, padding: '3px 8px' }}>{isOld ? '! Overdue' : 'Waiting'}</span>
                          )}
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'center', fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 600, color: receiptTimeColor(receiptSeconds) }}>
                          {r.receipt_posted ? fmtDuration(receiptSeconds) : '\u2014'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}