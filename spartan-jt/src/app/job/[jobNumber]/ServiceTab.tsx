'use client';

function fmtDateTime(d: string | null | undefined): string {
  if (!d) return '\u2014';
  try {
    const dt = new Date(d);
    return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' + dt.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  } catch { return d; }
}
function fmtTime(d: string | null | undefined): string {
  if (!d) return '\u2014';
  try { return new Date(d).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }); } catch { return d; }
}

const quarterMeta: Record<string, { label: string; color: string; bg: string; bd: string }> = {
  Q1: { label: 'Q1 — Arrival & Setup', color: 'var(--ice)', bg: 'var(--icebg)', bd: 'var(--icebd)' },
  Q2: { label: 'Q2 — Diagnostics & Options', color: 'var(--volt)', bg: 'var(--voltbg)', bd: 'var(--voltbd)' },
  Halftime: { label: 'Halftime Show', color: 'var(--hot)', bg: 'var(--hotbg)', bd: 'var(--hotbd)' },
};

const verifyIcons: Record<string, string> = {
  slack_text: '\uD83D\uDCAC',
  photo: '\uD83D\uDCF7',
  screenshot: '\uD83D\uDDBC\uFE0F',
  call: '\uD83D\uDCDE',
  manager: '\uD83D\uDC64',
  st_data: '\uD83D\uDCCA',
};

export default function ServiceTab({ job, data }: { job: any; data: any }) {
  const appointments = (data.appointments || []) as any[];
  const assignments = (data.assignments || []) as any[];
  const verifications = (data.verifications || []) as any[];
  const playbook = data.playbook || { steps: [], tracking: [], serviceKey: 'plservice' };

  const assignMap: Record<string, any[]> = {};
  assignments.forEach((a: any) => {
    const key = String(a.st_appointment_id);
    if (!assignMap[key]) assignMap[key] = [];
    assignMap[key].push(a);
  });

  const techMap = new Map<string, string>();
  assignments.forEach((a: any) => {
    if (a.st_tech_id && a.technician_name) techMap.set(String(a.st_tech_id), a.technician_name);
  });
  const uniqueTechs = Array.from(techMap.values());

  const completedAppts = appointments.filter((a: any) => a.status === 'Done').length;
  const scheduledAppts = appointments.filter((a: any) => a.status === 'Scheduled').length;

  // Build playbook step view
  const serviceSteps = (playbook.steps || []).filter((s: any) => s.playbook_key === playbook.serviceKey);
  const trackingMap: Record<string, any> = {};
  (playbook.tracking || []).forEach((t: any) => {
    trackingMap[`${t.playbook_key}-${t.step_number}`] = t;
  });

  // Group steps by quarter
  const quarters: string[] = [];
  const stepsByQuarter: Record<string, any[]> = {};
  serviceSteps.forEach((s: any) => {
    if (!stepsByQuarter[s.quarter]) {
      stepsByQuarter[s.quarter] = [];
      quarters.push(s.quarter);
    }
    stepsByQuarter[s.quarter].push(s);
  });

  const totalSteps = serviceSteps.length;
  const passedSteps = serviceSteps.filter((s: any) => {
    const t = trackingMap[`${s.playbook_key}-${s.step_number}`];
    return t && t.status === 'pass';
  }).length;

  return <>
    <div className="tab-hdr">
      <div className="tab-icon" style={{ background: 'var(--voltbg)', border: '1px solid var(--voltbd)', color: 'var(--volt)' }}>
        <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
          <polygon points="5 3 19 12 5 21 5 3"/>
        </svg>
      </div>
      <div className="tab-info">
        <div className="tab-title">Service Process</div>
        <div className="tab-desc">Rules of the Road &mdash; {playbook.serviceKey} playbook &middot; {totalSteps} steps</div>
      </div>
      <div className="tab-badge" style={{ background: passedSteps > 0 ? 'var(--mintbg)' : 'var(--s3)', border: `1px solid ${passedSteps > 0 ? 'var(--mintbd)' : 'var(--b2)'}`, color: passedSteps > 0 ? 'var(--mint)' : 'var(--t3)' }}>
        {passedSteps}/{totalSteps} VERIFIED
      </div>
    </div>

    <div className="hero" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
      <div className="st sf"><div className="num">{totalSteps}</div><div className="lbl">Playbook Steps</div></div>
      <div className="st sv"><div className="num" style={{ color: 'var(--mint)' }}>{passedSteps}</div><div className="lbl">Verified</div></div>
      <div className="st sm"><div className="num" style={{ color: scheduledAppts > 0 ? 'var(--volt)' : 'var(--t3)' }}>{appointments.length}</div><div className="lbl">Appointments</div></div>
      <div className="st sg"><div className="num">{uniqueTechs.length}</div><div className="lbl">Technicians</div></div>
    </div>

    {uniqueTechs.length > 0 && <div className="c full">
      <div className="ch"><h3>Assigned Technicians</h3><div className="tg" style={{ background: 'var(--icebg)', border: '1px solid var(--icebd)', color: 'var(--ice)' }}>{uniqueTechs.length}</div></div>
      <div className="cb" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {uniqueTechs.map((name, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 20, background: 'var(--s3)', border: '1px solid var(--b2)' }}>
            <div style={{ width: 24, height: 24, borderRadius: '50%', background: 'var(--voltbg)', border: '1px solid var(--voltbd)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700, color: 'var(--volt)' }}>
              {name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)}
            </div>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--t1)' }}>{name}</span>
          </div>
        ))}
      </div>
    </div>}

    {/* Playbook Steps by Quarter */}
    {quarters.map((q) => {
      const meta = quarterMeta[q] || { label: q, color: 'var(--t2)', bg: 'var(--s3)', bd: 'var(--b2)' };
      const steps = stepsByQuarter[q];
      const qPassed = steps.filter((s: any) => {
        const t = trackingMap[`${s.playbook_key}-${s.step_number}`];
        return t && t.status === 'pass';
      }).length;

      return <div className="c full" key={q}>
        <div className="ch">
          <h3>{meta.label}</h3>
          <div className="tg" style={{ background: meta.bg, border: `1px solid ${meta.bd}`, color: meta.color }}>{qPassed}/{steps.length}</div>
        </div>
        <div className="cb" style={{ padding: 0 }}>
          {steps.map((step: any, i: number) => {
            const t = trackingMap[`${step.playbook_key}-${step.step_number}`];
            const status = t ? t.status : 'pending';
            const dotCls = status === 'pass' ? 'ai-ok' : status === 'fail' ? 'ai-fail' : 'ai-wait';
            const icon = verifyIcons[step.verification_type] || '\u2022';

            return <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '10px 16px',
              borderBottom: i < steps.length - 1 ? '1px solid var(--b2)' : 'none',
              background: step.hard_gate ? 'rgba(204,34,68,0.03)' : 'transparent'
            }}>
              <div className={`ai-dot ${dotCls}`} style={{ flexShrink: 0 }} />
              <span style={{ fontSize: 11, width: 22, textAlign: 'center', flexShrink: 0 }}>{icon}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--t1)', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--t3)', minWidth: 18 }}>{step.step_number}</span>
                  {step.title}
                  {step.hard_gate && <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 4, background: 'var(--firebg)', border: '1px solid var(--firebd)', color: 'var(--fire)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5 }}>Gate</span>}
                </div>
                {step.description && <div style={{ fontSize: 10, color: 'var(--t3)', marginTop: 2 }}>{step.description}</div>}
                {t && t.notes && <div style={{ fontSize: 10, color: 'var(--mint)', fontStyle: 'italic', marginTop: 2 }}>{t.notes}</div>}
              </div>
              <div style={{ flexShrink: 0 }}>
                {status === 'pass' && <span style={{ fontSize: 11, color: 'var(--mint)', fontWeight: 700 }}>{'\u2713'}</span>}
                {status === 'fail' && <span style={{ fontSize: 11, color: 'var(--fire)', fontWeight: 700 }}>{'\u2717'}</span>}
                {status === 'pending' && <span style={{ fontSize: 10, color: 'var(--t3)' }}>&mdash;</span>}
              </div>
            </div>;
          })}
        </div>
      </div>;
    })}

    {/* Appointment Timeline */}
    <div className="c full">
      <div className="ch"><h3>Appointment Timeline</h3><div className="tg" style={{ background: 'var(--voltbg)', border: '1px solid var(--voltbd)', color: 'var(--volt)' }}>{appointments.length}</div></div>
      {appointments.length > 0 ? <div className="cb" style={{ padding: 0 }}>
        {appointments.map((appt: any, i: number) => {
          const techs = assignMap[String(appt.st_appointment_id)] || [];
          const isDone = appt.status === 'Done';
          const dotCls = isDone ? 'ai-ok' : appt.status === 'Scheduled' ? 'ai-wait' : 'ai-fail';
          return (
            <div key={i} style={{ padding: '12px 16px', borderBottom: i < appointments.length - 1 ? '1px solid var(--b2)' : 'none', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
              <div className={`ai-dot ${dotCls}`} style={{ marginTop: 4, flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <span style={{ fontWeight: 600, color: 'var(--t1)', fontSize: 13 }}>
                    Appointment {appt.appointment_number || appt.st_appointment_id}
                  </span>
                  <span className={`chip ${isDone ? 'c-ok' : 'c-info'}`}>{appt.status}</span>
                </div>
                <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 12, color: 'var(--t3)', marginBottom: techs.length > 0 || appt.special_instructions ? 6 : 0 }}>
                  {appt.start_time && <span><strong style={{ color: 'var(--t2)' }}>Start:</strong> {fmtDateTime(appt.start_time)}</span>}
                  {appt.end_time && <span><strong style={{ color: 'var(--t2)' }}>End:</strong> {fmtDateTime(appt.end_time)}</span>}
                  {appt.arrival_window_start && <span><strong style={{ color: 'var(--t2)' }}>Window:</strong> {fmtTime(appt.arrival_window_start)} &ndash; {fmtTime(appt.arrival_window_end)}</span>}
                </div>
                {techs.length > 0 && <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: appt.special_instructions ? 6 : 0 }}>
                  {techs.map((t: any, j: number) => (
                    <span key={j} style={{ fontSize: 11, padding: '2px 8px', borderRadius: 12, background: 'var(--voltbg)', border: '1px solid var(--voltbd)', color: 'var(--volt)', fontWeight: 600 }}>
                      {t.technician_name} {t.status === 'Done' ? '\u2713' : ''}
                    </span>
                  ))}
                </div>}
                {appt.special_instructions && <div style={{ fontSize: 11, color: 'var(--t3)', fontStyle: 'italic', marginTop: 2 }}>
                  {appt.special_instructions}
                </div>}
              </div>
            </div>
          );
        })}
      </div> : <div className="cb" style={{ color: 'var(--t3)', fontSize: 12 }}>No appointments found for this job.</div>}
    </div>

    {appointments.length === 0 && serviceSteps.length === 0 && <div style={{ color: 'var(--t3)', fontSize: 12, padding: 20, textAlign: 'center' }}>No service process data available for this job yet.</div>}
  </>;
}