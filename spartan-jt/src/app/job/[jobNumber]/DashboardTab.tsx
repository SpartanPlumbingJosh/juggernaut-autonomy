'use client';
import { JobData, Icon, fmt, money, moneyExact, stripHtml, isInstallTrack } from './JTClient';

function VR({ dot, k, v, style }: { dot: string; k: string; v: string; style?: React.CSSProperties }) {
  return <div className="vr"><div className={`ai-dot ${dot}`} /><span className="k">{k}</span><span className="v" style={style}>{v}</span></div>;
}

export default function DashboardTab({ job, data, amt, score, passed, failed, total, invTotal, paidTotal, isInstall, jobNumber, mode, modeInfo }: any) {
  const pending = total - passed - failed;
  const scoreColor = score >= 80 ? 'var(--mint)' : score >= 60 ? 'var(--amber)' : 'var(--fire)';
  const okDeg = total > 0 ? (passed / total) * 360 : 0;
  const failDeg = total > 0 ? okDeg + (failed / total) * 360 : 0;
  const stages: string[] = modeInfo?.stages || ['Job Sold', 'Contact', 'Pre-Install', 'Day Before', 'Install', 'Post-Install'];
  const stageIdx = job.status === 'Completed' ? stages.length - 1 : job.status === 'InProgress' ? Math.max(0, stages.length - 2) : 0;

  const verifs = data.verifications || [];
  const failedVerifs = verifs.filter((v: any) => v.result === 'fail');
  const passedVerifs = verifs.filter((v: any) => v.result === 'pass');

  // Related jobs context
  const relatedJobs = data.relatedJobs || [];
  const activeRelated = relatedJobs.filter((j: any) => j.status !== 'Canceled' && j.st_job_id !== job.st_job_id);

  // Upcoming appointments
  const appts = (data.appointments || []).filter((a: any) => {
    if (!a.start_time) return false;
    return new Date(a.start_time) >= new Date();
  }).slice(0, 2);

  // Project context
  const project = data.project;
  const siblings = data.projectSiblings || [];

  return <>
    {/* ── Header ── */}
    <div className="top">
      <div className="top-l">
        <div className="crumb">Jobs / #{jobNumber} / Tracker</div>
        <h1><span className="n">#{jobNumber}</span> {job.customer_name || 'Unknown'}</h1>
        <div className="sub">{job.job_type_name || ''} &middot; {job.business_unit_name || ''} &middot; {fmt(job.created_on)}</div>
      </div>
      <div className="pills">
        {mode && <div className={`pill p-${modeInfo?.color || 'ice'}`}>{mode}</div>}
        {job.status === 'Completed' && <div className="pill p-sold">Completed</div>}
        {job.status === 'Scheduled' && <div className="pill p-svc">Scheduled</div>}
        {job.status === 'InProgress' && <div className="pill p-svc">In Progress</div>}
        {job.status === 'Canceled' && <div className="pill p-cancel">Canceled</div>}
        {isInstall ? <div className="pill p-inst">Install</div> : <div className="pill p-svc">Service</div>}
      </div>
    </div>

    {/* ── Needs Attention (failed verifications — attention-first) ── */}
    {failedVerifs.length > 0 && (
      <div className="attn">
        <div className="attn-h">
          <h3>Needs Attention</h3>
          <div className="attn-count">{failedVerifs.length}</div>
        </div>
        <div className="attn-grid">
          {failedVerifs.map((v: any, i: number) => (
            <div className="attn-item" key={i}>
              <div className="attn-icon">{'\u2717'}</div>
              <div className="attn-name">{v.verification_name}</div>
            </div>
          ))}
        </div>
      </div>
    )}

    {/* ── Score + Stats Row ── */}
    <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: 16, marginBottom: 24 }}>
      <div className="ai-sum" style={{ marginBottom: 0 }}>
        <div className="ai-ring" style={{ background: `conic-gradient(var(--mint) 0deg, var(--mint) ${okDeg}deg, var(--fire) ${okDeg}deg, var(--fire) ${failDeg}deg, var(--t4) ${failDeg}deg)` }}>
          <div className="ai-ring-inner"><span className="pct" style={{ color: scoreColor }}>{score}%</span></div>
        </div>
        <div className="ai-stats">
          <div className="ai-s"><div className="ai-s-n" style={{ color: 'var(--mint)' }}>{passed}</div><div className="ai-s-l" style={{ color: 'var(--mint2)' }}>Verified</div></div>
          <div className="ai-s"><div className="ai-s-n" style={{ color: 'var(--fire)' }}>{failed}</div><div className="ai-s-l" style={{ color: 'var(--fire2)' }}>Failed</div></div>
          {pending > 0 && <div className="ai-s"><div className="ai-s-n" style={{ color: 'var(--t3)' }}>{pending}</div><div className="ai-s-l" style={{ color: 'var(--t3)' }}>Pending</div></div>}
        </div>
      </div>
      <div className="hero" style={{ marginBottom: 0 }}>
        <div className="st sf"><div className="ai ai-ok" /><div className="num">{money(amt)}</div><div className="lbl">Sale Amount</div></div>
        <div className="st sv"><div className="ai ai-ok" /><div className="num">{money(invTotal)}</div><div className="lbl">Invoiced</div></div>
        <div className="st sm"><div className="ai ai-ok" /><div className="num">{money(paidTotal)}</div><div className="lbl">Paid</div></div>
        <div className="st sg"><div className="num" style={{ fontSize: 18 }}>{job.status || '\u2014'}</div><div className="lbl">Status</div></div>
      </div>
    </div>

    {/* ── Lifecycle Pipeline ── */}
    <div className="pipe-wrap">
      <div className="pipe-top"><h2>Job Lifecycle</h2><div className="step">Stage {stageIdx + 1} / {stages.length}</div></div>
      <div className="pipe">
        {stages.map((s: string, i: number) => {
          const cls = i < stageIdx ? 'done' : i === stageIdx ? 'now' : 'w';
          return <div className={`pn ${cls}`} key={s}><div className={`pb ${cls}`} /><div className="pt">{s}</div></div>;
        })}
      </div>
    </div>

    {/* ── Passed Verifications (green chips) ── */}
    {passedVerifs.length > 0 && (
      <div className="passed-section">
        <div className="passed-h">
          <h3>Passed</h3>
          <div className="passed-count">{passedVerifs.length}</div>
        </div>
        <div className="passed-grid">
          {passedVerifs.map((v: any, i: number) => (
            <div className="passed-chip" key={i}>
              <div className="pc-dot" />
              {v.verification_name}
            </div>
          ))}
        </div>
      </div>
    )}

    {/* ── Quick Context: Customer + Work Scope side by side ── */}
    <div className="g2">
      <div className="c"><div className="ch"><h3>Customer</h3></div><div className="cb">
        <VR dot="ai-ok" k="Name" v={job.customer_name || '\u2014'} />
        <VR dot="ai-ok" k="Job #" v={`#${jobNumber}`} style={{ fontFamily: 'var(--mono)', color: 'var(--ice)' }} />
        <VR dot="ai-ok" k="Address" v={job.customer_address || '\u2014'} />
        <VR dot="ai-ok" k="Created" v={fmt(job.created_on)} />
        <VR dot={job.completed_on ? 'ai-ok' : 'ai-wait'} k="Completed" v={fmt(job.completed_on)} />
      </div></div>
      <div className="c"><div className="ch"><h3>Work Scope</h3></div><div className="cb">
        <div className="stxt cv scope-text" style={{ maxHeight: 120 }}>{stripHtml(job.summary || 'No scope summary available')}</div>
        <div style={{ marginTop: 8 }}>
          <VR dot="ai-ok" k="Job Type" v={job.job_type_name || '\u2014'} />
          <VR dot="ai-ok" k="Business Unit" v={job.business_unit_name || '\u2014'} />
        </div>
      </div></div>
    </div>

    {/* ── Project Context (if part of a project) ── */}
    {project && siblings.length > 0 && (
      <div className="c full"><div className="ch"><h3>Project Jobs</h3><div className="tg" style={{ background: 'var(--voltbg)', border: '1px solid var(--voltbd)', color: 'var(--volt)' }}>{siblings.length}</div></div>
        <div className="cb" style={{ padding: 0 }}>
          {siblings.slice(0, 5).map((sib: any, i: number) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 24px', borderBottom: '1px solid rgba(255,255,255,.05)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div className={`ai-dot ${sib.status === 'Completed' ? 'ai-ok' : sib.status === 'Canceled' ? 'ai-fail' : 'ai-warn'}`} />
                <span style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--ice)' }}>#{sib.job_number || sib.st_job_id}</span>
                <span style={{ fontSize: 14, fontWeight: 500 }}>{sib.job_type_name || ''}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span className={`chip ${sib.status === 'Completed' ? 'c-ok' : sib.status === 'Canceled' ? 'c-fail' : 'c-info'}`}>{sib.status}</span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--t2)' }}>{money(sib.total)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    )}

    {/* ── Upcoming Appointments ── */}
    {appts.length > 0 && (
      <div className="c full"><div className="ch"><h3>Upcoming</h3></div><div className="cb">
        {appts.map((a: any, i: number) => (
          <VR key={i} dot="ai-warn" k={`Appointment ${a.status}`} v={fmt(a.start_time)} />
        ))}
      </div></div>
    )}

    {/* ── Related Jobs at this Location ── */}
    {activeRelated.length > 0 && (
      <div className="c full"><div className="ch"><h3>Other Jobs at Location</h3><div className="tg" style={{ background: 'var(--icebg)', border: '1px solid var(--icebd)', color: 'var(--ice)' }}>{activeRelated.length}</div></div>
        <div className="cb">
          {activeRelated.slice(0, 4).map((rj: any, i: number) => (
            <VR key={i} dot={rj.status === 'Completed' ? 'ai-ok' : 'ai-warn'} k={`#${rj.job_number || rj.st_job_id} ${rj.job_type_name || ''}`} v={rj.status || '\u2014'} />
          ))}
        </div>
      </div>
    )}
  </>;
}
