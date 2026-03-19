'use client';

function fmt(d: string | null | undefined): string {
  if (!d) return '\u2014';
  try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); } catch { return d; }
}
function money(n: number | string | null | undefined): string {
  const v = parseFloat(String(n || 0));
  return v > 0 ? '$' + v.toLocaleString(undefined, { maximumFractionDigits: 0 }) : '\u2014';
}

function ContactIcon({ type }: { type: string }) {
  const t = (type || '').toLowerCase();
  if (t.includes('email')) return <span style={{ fontSize: 14 }}>{'\u2709'}</span>;
  if (t.includes('mobile')) return <span style={{ fontSize: 14 }}>{'\uD83D\uDCF1'}</span>;
  if (t.includes('fax')) return <span style={{ fontSize: 14 }}>{'\uD83D\uDCE0'}</span>;
  return <span style={{ fontSize: 14 }}>{'\u260E'}</span>;
}

function formatPhone(val: string): string {
  const d = val.replace(/\D/g, '');
  if (d.length === 10) return `(${d.slice(0,3)}) ${d.slice(3,6)}-${d.slice(6)}`;
  if (d.length === 11 && d[0] === '1') return `(${d.slice(1,4)}) ${d.slice(4,7)}-${d.slice(7)}`;
  return val;
}

export default function IntelTab({ job, data, amt }: { job: any; data: any; amt: number }) {
  const related = data.relatedJobs || [];
  const appts = data.appointments || [];
  const contacts = (data.contacts || []) as any[];
  const unsoldEstimates = (data.unsoldEstimates || []) as any[];
  const recallsAtLocation = (data.recallsAtLocation || []) as any[];
  const estimates = (data.estimates || []) as any[];

  const phones = contacts.filter((c: any) => c.type === 'Phone' || c.type === 'MobilePhone');
  const emails = contacts.filter((c: any) => c.type === 'Email');
  const recallCount = related.filter((r: any) => r.recall_for_id).length;
  const totalSpent = related.reduce((s: number, r: any) => s + (parseFloat(r.total) || 0), 0) + amt;

  return <>
    <div className="tab-hdr">
      <div className="tab-icon" style={{ background: 'var(--icebg)', border: '1px solid var(--icebd)', color: 'var(--ice)' }}>
        <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
      </div>
      <div className="tab-info"><div className="tab-title">Customer Intel</div><div className="tab-desc">Pre-dispatch briefing &mdash; know everything before you knock</div></div>
      <div className="tab-badge" style={{ background: 'var(--icebg)', border: '1px solid var(--icebd)', color: 'var(--ice)' }}>READ-ONLY</div>
    </div>

    {/* Hero Stats */}
    <div className="hero" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
      <div className="st sf"><div className="num">{related.length + 1}</div><div className="lbl">Total Jobs</div></div>
      <div className="st sv"><div className="num">{money(totalSpent)}</div><div className="lbl">Lifetime Spend</div></div>
      <div className="st sm"><div className="num">{money(amt)}</div><div className="lbl">Current Job</div></div>
      <div className="st" style={{ background: recallCount > 0 ? 'var(--amberbg)' : 'var(--s3)', border: `1px solid ${recallCount > 0 ? 'var(--amberbd)' : 'var(--b2)'}` }}>
        <div className="num" style={{ color: recallCount > 0 ? 'var(--amber)' : 'var(--t3)' }}>{recallCount}</div>
        <div className="lbl">Recalls</div>
      </div>
    </div>

    {/* Contact Info + Customer Profile side by side */}
    <div className="g2">
      <div className="intel" style={{ borderColor: 'var(--icebd)' }}>
        <div className="intel-h">
          <div className="intel-icon" style={{ background: 'var(--voltbg)', color: 'var(--volt)' }}>
            <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>
          </div>
          <div className="intel-title">Customer Profile</div>
        </div>
        <div className="intel-body">
          <strong>{job.customer_name || 'Unknown'}</strong><br />
          {job.customer_address && <>{job.customer_address}<br /></>}
          Current job: <strong style={{ color: 'var(--fire)' }}>{money(amt)}</strong> &middot; {job.business_unit_name || ''}
        </div>
      </div>

      <div className="intel" style={{ borderColor: 'var(--voltbd)' }}>
        <div className="intel-h">
          <div className="intel-icon" style={{ background: 'var(--icebg)', color: 'var(--ice)' }}>
            <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.12.96.36 1.9.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.91.34 1.85.58 2.81.7A2 2 0 0122 16.92z"/>
            </svg>
          </div>
          <div className="intel-title">Contact Info</div>
        </div>
        <div className="intel-body">
          {contacts.length === 0 && <span style={{ color: 'var(--t3)', fontSize: 12 }}>No contacts on file.</span>}
          {phones.map((c: any, i: number) => (
            <div key={`p${i}`} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <ContactIcon type={c.type} />
              <span style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--t1)' }}>
                {formatPhone(c.value)}
              </span>
              <span style={{ fontSize: 10, color: 'var(--t3)', textTransform: 'capitalize' }}>{c.type === 'MobilePhone' ? 'Mobile' : 'Phone'}</span>
              {c.memo && <span style={{ fontSize: 10, color: 'var(--t3)' }}>({c.memo})</span>}
            </div>
          ))}
          {emails.map((c: any, i: number) => (
            <div key={`e${i}`} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <ContactIcon type={c.type} />
              <span style={{ fontSize: 12, color: 'var(--ice)' }}>{c.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>

    {/* Work Scope */}
    <div className="intel" style={{ borderColor: 'var(--mintbd)' }}>
      <div className="intel-h">
        <div className="intel-icon" style={{ background: 'var(--mintbg)', color: 'var(--mint)' }}>
          <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/>
          </svg>
        </div>
        <div className="intel-title">Work Scope</div>
      </div>
      <div className="intel-body">
        {job.summary ? <><strong>Description:</strong> {job.summary}<br /></> : 'No scope available'}
        {job.job_type_name && <><strong>Type:</strong> {job.job_type_name} &middot; </>}
        {job.business_unit_name && <><strong>BU:</strong> {job.business_unit_name}</>}
      </div>
    </div>

    {/* Unsold Estimates — Opportunities */}
    {unsoldEstimates.length > 0 && <div className="c full">
      <div className="ch">
        <h3>Unsold Estimates &mdash; Opportunities</h3>
        <div className="tg" style={{ background: 'var(--firebg)', border: '1px solid var(--firebd)', color: 'var(--fire)' }}>{unsoldEstimates.length}</div>
      </div>
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

    {/* Previous Jobs at Location */}
    <div className="c full"><div className="ch"><h3>Previous Jobs at Location</h3><div className="tg" style={{ background: 'var(--voltbg)', border: '1px solid var(--voltbd)', color: 'var(--volt)' }}>{related.length}</div></div>
      {related.length > 0 ? <div className="cb" style={{ padding: 0 }}><table className="mt"><thead><tr><th>Job #</th><th>Type</th><th>Status</th><th>Amount</th><th>Date</th></tr></thead><tbody>
        {related.map((r: any, i: number) => <tr key={i}><td style={{ fontFamily: 'var(--mono)', color: 'var(--ice)' }}>{r.job_number || r.st_job_id}</td><td>{r.job_type_name || r.business_unit_name || '\u2014'}</td><td><span className={`chip ${r.status === 'Completed' ? 'c-ok' : 'c-info'}`}>{r.status}</span></td><td>{money(r.total)}</td><td>{fmt(r.created_on)}</td></tr>)}
      </tbody></table></div> : <div className="cb" style={{ color: 'var(--t3)', fontSize: 12 }}>No prior jobs at this location.</div>}
    </div>

    {/* Recall History at Location */}
    {recallsAtLocation.length > 0 && <div className="c full">
      <div className="ch">
        <h3>Recall History at Location</h3>
        <div className="tg" style={{ background: 'var(--amberbg)', border: '1px solid var(--amberbd)', color: 'var(--amber)' }}>{recallsAtLocation.length}</div>
      </div>
      <div className="cb" style={{ padding: 0 }}>
        <table className="mt"><thead><tr><th>Recall Job</th><th>Status</th><th>For Job #</th><th>Summary</th><th>Date</th></tr></thead><tbody>
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

    {/* Appointments */}
    {appts.length > 0 && <div className="c full"><div className="ch"><h3>Appointments</h3><div className="tg" style={{ background: 'var(--grapebg)', border: '1px solid var(--grapebd)', color: 'var(--grape)' }}>{appts.length}</div></div>
      <div className="cb" style={{ padding: 0 }}><table className="mt"><thead><tr><th>ID</th><th>Status</th><th>Start</th><th>End</th></tr></thead><tbody>
        {appts.map((a: any, i: number) => <tr key={i}><td style={{ fontFamily: 'var(--mono)', color: 'var(--ice)' }}>{a.st_appointment_id}</td><td><span className={`chip ${a.status === 'Done' ? 'c-ok' : 'c-info'}`}>{a.status}</span></td><td>{fmt(a.start_time)}</td><td>{fmt(a.end_time)}</td></tr>)}
      </tbody></table></div>
    </div>}

    {/* Current Job Estimates */}
    {estimates.length > 0 && <div className="c full">
      <div className="ch"><h3>Estimates on This Job</h3><div className="tg" style={{ background: 'var(--mintbg)', border: '1px solid var(--mintbd)', color: 'var(--mint)' }}>{estimates.length}</div></div>
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
  </>;
}
