'use client';

function fmt(d: string | null | undefined): string {
  if (!d) return '\u2014';
  try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); } catch { return d; }
}
function fmtDateTime(d: string | null | undefined): string {
  if (!d) return '\u2014';
  try {
    const dt = new Date(d);
    return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' + dt.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  } catch { return d; }
}
function money(n: number | string | null | undefined): string {
  const v = parseFloat(String(n || 0));
  return v > 0 ? '$' + v.toLocaleString(undefined, { maximumFractionDigits: 0 }) : '\u2014';
}
function durFmt(seconds: number | null | undefined): string {
  if (!seconds) return '\u2014';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

const RECALL_STEPS = [
  { num: '6.1', label: 'Reason Documented', desc: 'Why the recall was needed' },
  { num: '6.2', label: 'Original Tech Notified', desc: '' },
  { num: '6.3', label: 'Customer Contacted', desc: '' },
  { num: '6.4', label: 'Visit Scheduled', desc: '' },
  { num: '6.5', label: 'Tech Assigned', desc: '' },
  { num: '6.6', label: 'Check-In During Recall', desc: '' },
  { num: '6.7', label: 'Resolution Confirmed', desc: '' },
  { num: '6.8', label: 'Root Cause Analysis', desc: '' },
];

const POST_CHECKS = [
  { num: '5.1', label: 'Happy Call SLA', desc: 'Within 24 hours of completion' },
  { num: '5.2', label: 'Happy Call Scorecard', desc: 'AI scores call against script' },
  { num: '5.3', label: 'Missed Opportunity Flag', desc: 'Spartan Shield, review ask, referral' },
  { num: '5.4', label: 'Review Posted', desc: 'Google/Yelp review posted' },
  { num: '5.5', label: 'Financing Finalization', desc: 'Final financing status confirmed' },
];

export default function PostInstallTab({ job, data }: { job: any; data: any }) {
  const calls = (data.calls || []) as any[];
  const recallJobs = (data.recallJobs || []) as any[];
  const verifications = (data.verifications || []) as any[];

  // Happy call SLA: 24hr from completion
  const completedOn = job.completed_on ? new Date(job.completed_on) : null;
  const now = new Date();
  const slaDeadline = completedOn ? new Date(completedOn.getTime() + 24 * 60 * 60 * 1000) : null;
  const slaHoursLeft = slaDeadline ? Math.max(0, (slaDeadline.getTime() - now.getTime()) / (1000 * 60 * 60)) : null;
  const slaExpired = slaDeadline ? now > slaDeadline : false;

  // Find happy calls (outbound calls after completion)
  const happyCalls = completedOn ? calls.filter((c: any) => {
    const callDate = c.created_on ? new Date(c.created_on) : null;
    return callDate && callDate > completedOn && c.direction === 'Outbound';
  }) : [];
  const happyCallMade = happyCalls.length > 0;

  // Callback monitoring: count of inbound calls after completion
  const callbacks = completedOn ? calls.filter((c: any) => {
    const callDate = c.created_on ? new Date(c.created_on) : null;
    return callDate && callDate > completedOn && c.direction === 'Inbound';
  }) : [];
  const callbackCount = callbacks.length;
  const callbackFlag = callbackCount >= 3;

  // Is this job a recall FOR another job?
  const isRecallJob = !!job.recall_for_id;

  // Post-install verifications
  const postVerifs = verifications.filter((v: any) => {
    const nm = v.verification_name || '';
    return nm.startsWith('S5-') || nm.startsWith('S6-');
  });
  const s5Verifs = postVerifs.filter((v: any) => (v.verification_name || '').startsWith('S5-'));
  const s6Verifs = postVerifs.filter((v: any) => (v.verification_name || '').startsWith('S6-'));

  // SLA status
  let slaStatus: 'pass' | 'fail' | 'pending' = 'pending';
  let slaLabel = 'Awaiting completion';
  if (completedOn && happyCallMade) {
    slaStatus = 'pass';
    slaLabel = 'Happy call completed';
  } else if (slaExpired) {
    slaStatus = 'fail';
    slaLabel = 'SLA expired \u2014 24hr window missed';
  } else if (completedOn) {
    slaLabel = slaHoursLeft !== null ? `${slaHoursLeft.toFixed(1)}h remaining` : 'Clock running';
  }

  return <>
    <div className="tab-hdr">
      <div className="tab-icon" style={{ background: 'var(--mintbg)', border: '1px solid var(--mintbd)', color: 'var(--mint)' }}>
        <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
        </svg>
      </div>
      <div className="tab-info">
        <div className="tab-title">Post-Install / Recall</div>
        <div className="tab-desc">Happy call SLA &middot; Call scorecards &middot; Review monitoring &middot; Recall lifecycle</div>
      </div>
    </div>

    {/* Hero Stats */}
    <div className="hero" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
      <div className="st" style={{ background: happyCallMade ? 'var(--mintbg)' : slaExpired ? 'var(--firebg)' : 'var(--s3)', border: `1px solid ${happyCallMade ? 'var(--mintbd)' : slaExpired ? 'var(--firebd)' : 'var(--b2)'}` }}>
        <div className="num" style={{ fontSize: 20, color: happyCallMade ? 'var(--mint)' : slaExpired ? 'var(--fire)' : 'var(--t3)' }}>
          {happyCallMade ? '\u2713' : slaExpired ? '\u2717' : '\u23F1'}
        </div>
        <div className="lbl">Happy Call</div>
      </div>
      <div className="st" style={{ background: callbackFlag ? 'var(--firebg)' : 'var(--s3)', border: `1px solid ${callbackFlag ? 'var(--firebd)' : 'var(--b2)'}` }}>
        <div className="num" style={{ fontSize: 28, color: callbackFlag ? 'var(--fire)' : 'var(--t2)' }}>{callbackCount}</div>
        <div className="lbl" style={{ color: callbackFlag ? 'var(--fire)' : undefined }}>Callbacks</div>
      </div>
      <div className="st" style={{ background: recallJobs.length > 0 ? 'var(--amberbg)' : 'var(--s3)', border: `1px solid ${recallJobs.length > 0 ? 'var(--amberbd)' : 'var(--b2)'}` }}>
        <div className="num" style={{ fontSize: 28, color: recallJobs.length > 0 ? 'var(--amber)' : 'var(--t3)' }}>{recallJobs.length}</div>
        <div className="lbl">Recalls</div>
      </div>
      <div className="st" style={{ background: 'var(--s3)', border: '1px solid var(--b2)' }}>
        <div className="num" style={{ fontSize: 28, color: 'var(--t2)' }}>{calls.length}</div>
        <div className="lbl">Total Calls</div>
      </div>
    </div>

    {/* Happy Call SLA */}
    <div className="c full">
      <div className="ch"><h3>Happy Call SLA</h3>
        <div className="tg" style={{
          background: slaStatus === 'pass' ? 'var(--mintbg)' : slaStatus === 'fail' ? 'var(--firebg)' : 'var(--amberbg)',
          border: `1px solid ${slaStatus === 'pass' ? 'var(--mintbd)' : slaStatus === 'fail' ? 'var(--firebd)' : 'var(--amberbd)'}`,
          color: slaStatus === 'pass' ? 'var(--mint)' : slaStatus === 'fail' ? 'var(--fire)' : 'var(--amber)',
        }}>{slaStatus === 'pass' ? 'PASSED' : slaStatus === 'fail' ? 'MISSED' : 'PENDING'}</div>
      </div>
      <div className="cb">
        <div className="vr"><div className={`ai-dot ${slaStatus === 'pass' ? 'ai-ok' : slaStatus === 'fail' ? 'ai-fail' : 'ai-wait'}`} /><span className="k">Status</span><span className="v" style={{ color: slaStatus === 'pass' ? 'var(--mint)' : slaStatus === 'fail' ? 'var(--fire)' : 'var(--amber)' }}>{slaLabel}</span></div>
        <div className="vr"><div className="ai-dot ai-ok" /><span className="k">Job Completed</span><span className="v">{completedOn ? fmtDateTime(job.completed_on) : 'Not yet'}</span></div>
        <div className="vr"><div className="ai-dot ai-ok" /><span className="k">24hr Deadline</span><span className="v">{slaDeadline ? fmtDateTime(slaDeadline.toISOString()) : '\u2014'}</span></div>
        {happyCalls.length > 0 && <div className="vr"><div className="ai-dot ai-ok" /><span className="k">Happy Call Made</span><span className="v" style={{ color: 'var(--mint)' }}>{fmtDateTime(happyCalls[0].created_on)} ({durFmt(happyCalls[0].duration_seconds)})</span></div>}
      </div>
    </div>

    {/* Stage 5 Checks */}
    <div className="c full">
      <div className="ch"><h3>Stage 5 — Post-Install Checks</h3>
        <div className="tg" style={{ background: 'var(--icebg)', border: '1px solid var(--icebd)', color: 'var(--ice)' }}>
          {s5Verifs.filter((v: any) => v.result === 'pass').length}/{POST_CHECKS.length}
        </div>
      </div>
      <div className="cb">
        {POST_CHECKS.map((check, i) => {
          const v = s5Verifs.find((x: any) => (x.verification_name || '').includes(check.num));
          const dot = v?.result === 'pass' ? 'ai-ok' : v?.result === 'fail' ? 'ai-fail' : 'ai-wait';
          return <div className="vg-item" key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', borderBottom: '1px solid var(--b1)' }}>
            <div className={`vg-dot ${dot}`} />
            <div style={{ flex: 1 }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--t3)', marginRight: 6 }}>{check.num}</span>
              <span style={{ fontSize: 12, color: 'var(--t1)' }}>{check.label}</span>
              {check.desc && <span style={{ fontSize: 10, color: 'var(--t3)', marginLeft: 6 }}>{check.desc}</span>}
            </div>
          </div>;
        })}
      </div>
    </div>

    {/* Callback Monitoring */}
    <div className="c full">
      <div className="ch"><h3>Callback Monitoring</h3>
        {callbackFlag && <div className="tg" style={{ background: 'var(--firebg)', border: '1px solid var(--firebd)', color: 'var(--fire)' }}>{'\u26A0'} Quality Signal</div>}
      </div>
      <div className="cb">
        {callbackFlag && <div style={{ background: 'var(--firebg)', border: '1px solid var(--firebd)', borderRadius: 8, padding: '8px 12px', marginBottom: 12, fontSize: 11, color: 'var(--fire)' }}>
          {callbackCount} callbacks detected — 3+ callbacks is a quality signal regardless of happy call score.
        </div>}
        {callbacks.length > 0 ? <div style={{ padding: 0 }}>
          <table className="mt"><thead><tr><th>Date</th><th>Direction</th><th>Duration</th><th>From</th><th>Status</th></tr></thead><tbody>
            {callbacks.slice(0, 10).map((c: any, i: number) => <tr key={i}>
              <td>{fmtDateTime(c.created_on)}</td>
              <td style={{ color: 'var(--ice)' }}>{c.direction || '\u2014'}</td>
              <td>{durFmt(c.duration_seconds)}</td>
              <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{c.from_number || '\u2014'}</td>
              <td>{c.status || '\u2014'}</td>
            </tr>)}
          </tbody></table>
        </div> : <div style={{ color: 'var(--t3)', fontSize: 12 }}>No callbacks recorded after job completion.</div>}
      </div>
    </div>

    {/* Recall Jobs */}
    {(recallJobs.length > 0 || isRecallJob) && <div className="c full">
      <div className="ch"><h3>Recall Lifecycle</h3>
        <div className="tg" style={{ background: 'var(--amberbg)', border: '1px solid var(--amberbd)', color: 'var(--amber)' }}>Stage 6</div>
      </div>
      <div className="cb">
        {isRecallJob && <div style={{ background: 'var(--amberbg)', border: '1px solid var(--amberbd)', borderRadius: 8, padding: '8px 12px', marginBottom: 12, fontSize: 11, color: 'var(--amber)' }}>
          This job IS a recall for job #{job.recall_for_id}
        </div>}
        {recallJobs.length > 0 && <>
          <div style={{ fontSize: 11, color: 'var(--t3)', marginBottom: 8 }}>Jobs that are recalls for this job:</div>
          <table className="mt"><thead><tr><th>Job #</th><th>Status</th><th>Summary</th><th>Created</th><th>Completed</th></tr></thead><tbody>
            {recallJobs.map((rj: any, i: number) => <tr key={i}>
              <td style={{ fontFamily: 'var(--mono)', color: 'var(--amber)' }}>{rj.job_number || rj.st_job_id}</td>
              <td>{rj.status || '\u2014'}</td>
              <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{rj.summary || '\u2014'}</td>
              <td>{fmt(rj.created_on)}</td>
              <td>{fmt(rj.completed_on)}</td>
            </tr>)}
          </tbody></table>
        </>}

        {/* Recall Steps Checklist */}
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--t2)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 1 }}>Recall Steps</div>
          {RECALL_STEPS.map((step, i) => {
            const v = s6Verifs.find((x: any) => (x.verification_name || '').includes(step.num));
            const dot = v?.result === 'pass' ? 'ai-ok' : v?.result === 'fail' ? 'ai-fail' : 'ai-wait';
            return <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', borderBottom: '1px solid var(--b1)' }}>
              <div className={`vg-dot ${dot}`} />
              <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--t3)' }}>{step.num}</span>
              <span style={{ fontSize: 12, color: 'var(--t1)' }}>{step.label}</span>
              {step.desc && <span style={{ fontSize: 10, color: 'var(--t3)' }}>{step.desc}</span>}
            </div>;
          })}
        </div>
      </div>
    </div>}

    {/* Recent Calls (all) */}
    <div className="c full">
      <div className="ch"><h3>Call History</h3>
        <div className="tg" style={{ background: 'var(--icebg)', border: '1px solid var(--icebd)', color: 'var(--ice)' }}>{calls.length}</div>
      </div>
      {calls.length > 0 ? <div className="cb" style={{ padding: 0 }}>
        <table className="mt"><thead><tr><th>Date</th><th>Direction</th><th>Type</th><th>Duration</th><th>From</th><th>To</th><th>Status</th></tr></thead><tbody>
          {calls.slice(0, 20).map((c: any, i: number) => <tr key={i}>
            <td>{fmtDateTime(c.created_on)}</td>
            <td style={{ color: c.direction === 'Inbound' ? 'var(--mint)' : 'var(--ice)' }}>{c.direction || '\u2014'}</td>
            <td>{c.call_type || '\u2014'}</td>
            <td>{durFmt(c.duration_seconds)}</td>
            <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{c.from_number || '\u2014'}</td>
            <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{c.to_number || '\u2014'}</td>
            <td>{c.status || '\u2014'}</td>
          </tr>)}
        </tbody></table>
      </div> : <div className="cb" style={{ color: 'var(--t3)', fontSize: 12 }}>No calls linked to this job.</div>}
    </div>
  </>;
}
