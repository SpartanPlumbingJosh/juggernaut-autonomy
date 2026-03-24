'use client';

function fmtDateTime(d: string | null | undefined): string {
  if (!d) return '\u2014';
  try {
    const dt = new Date(d);
    return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' + dt.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  } catch { return d; }
}

const quarterMeta: Record<string, { label: string; color: string; bg: string; bd: string }> = {
  Q1: { label: 'Q1 \u2014 ARRIVAL & SETUP', color: 'var(--ice)', bg: 'var(--icebg)', bd: 'var(--icebd)' },
  Q2: { label: 'Q2 \u2014 DIAGNOSTICS & OPTIONS', color: 'var(--volt)', bg: 'var(--voltbg)', bd: 'var(--voltbd)' },
  Halftime: { label: 'HALFTIME SHOW', color: 'var(--hot)', bg: 'var(--hotbg)', bd: 'var(--hotbd)' },
};

export default function ServiceTab({ job, data }: { job: any; data: any }) {
  const appointments = (data.appointments || []) as any[];
  const assignments = (data.assignments || []) as any[];
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

  const serviceSteps = (playbook.steps || []).filter((s: any) => s.playbook_key === playbook.serviceKey);
  const trackingMap: Record<string, any> = {};
  (playbook.tracking || []).forEach((t: any) => {
    trackingMap[`${t.playbook_key}-${t.step_number}`] = t;
  });

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
    <div style={{ marginBottom: 24 }}>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--t4)', marginBottom: 6 }}>Service Process</div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 800, letterSpacing: '-.5px' }}>Rules of the Road</h1>
          <div style={{ fontSize: 14, color: 'var(--t3)', marginTop: 4 }}>{playbook.serviceKey} &middot; {totalSteps} steps</div>
        </div>
        <div style={{ background: passedSteps > 0 ? 'var(--mintbg)' : 'var(--s3)', border: `1px solid ${passedSteps > 0 ? 'var(--mintbd)' : 'var(--b2)'}`, color: passedSteps > 0 ? 'var(--mint)' : 'var(--t3)', fontFamily: 'var(--mono)', fontSize: 14, fontWeight: 700, padding: '6px 14px', borderRadius: 10 }}>
          {passedSteps}/{totalSteps} VERIFIED
        </div>
      </div>
    </div>

    <div className="hero" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
      <div className="st sf"><div className="num">{totalSteps}</div><div className="lbl">Steps</div></div>
      <div className="st sm"><div className="num">{passedSteps}</div><div className="lbl">Verified</div></div>
      <div className="st sv"><div className="num">{appointments.length}</div><div className="lbl">Appts</div></div>
      <div className="st sg"><div className="num">{uniqueTechs.length}</div><div className="lbl">Techs</div></div>
    </div>

    {uniqueTechs.length > 0 && <div className="c full">
      <div className="ch"><h3>Assigned Technicians</h3><div className="tg" style={{ background: 'var(--icebg)', border: '1px solid var(--icebd)', color: 'var(--ice)' }}>{uniqueTechs.length}</div></div>
      <div className="cb" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {uniqueTechs.map((name, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px', borderRadius: 20, background: 'var(--s3)', border: '1px solid var(--b2)' }}>
            <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--voltbg)', border: '1px solid var(--voltbd)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 700, color: 'var(--volt)' }}>
              {name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)}
            </div>
            <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--t1)' }}>{name}</span>
          </div>
        ))}
      </div>
    </div>}

    {quarters.map((q) => {
      const meta = quarterMeta[q] || { label: q.toUpperCase(), color: 'var(--t2)', bg: 'var(--s3)', bd: 'var(--b2)' };
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

            return <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 12, padding: '12px 20px',
              borderBottom: i < steps.length - 1 ? '1px solid rgba(255,255,255,.04)' : 'none',
              background: step.hard_gate ? 'rgba(239,68,68,.03)' : 'transparent'
            }}>
              <div className={`ai-dot ${dotCls}`} style={{ flexShrink: 0 }} />
              <span style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--t3)', minWidth: 24, textAlign: 'right', flexShrink: 0 }}>{step.step_number}</span>
              <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--t1)' }}>{step.title}</span>
                {step.hard_gate && <span style={{ fontSize: 13, padding: '2px 8px', borderRadius: 6, background: 'var(--firebg)', border: '1px solid var(--firebd)', color: 'var(--fire)', fontWeight: 700, textTransform: 'uppercase' as const, letterSpacing: 0.5 }}>GATE</span>}
              </div>
              <div style={{ flexShrink: 0 }}>
                {status === 'pass' && <span style={{ fontSize: 14, color: 'var(--mint)', fontWeight: 700 }}>{'\u2713'}</span>}
                {status === 'fail' && <span style={{ fontSize: 14, color: 'var(--fire)', fontWeight: 700 }}>{'\u2717'}</span>}
                {status === 'pending' && <span style={{ fontSize: 14, color: 'var(--t4)' }}>&mdash;</span>}
              </div>
            </div>;
          })}
        </div>
      </div>;
    })}

    {appointments.length > 0 && <div className="c full">
      <div className="ch"><h3>Appointments</h3><div className="tg" style={{ background: 'var(--voltbg)', border: '1px solid var(--voltbd)', color: 'var(--volt)' }}>{appointments.length}</div></div>
      <div className="cb" style={{ padding: 0 }}>
        {appointments.map((appt: any, i: number) => {
          const techs = assignMap[String(appt.st_appointment_id)] || [];
          const isDone = appt.status === 'Done';
          const dotCls = isDone ? 'ai-ok' : appt.status === 'Scheduled' ? 'ai-wait' : 'ai-fail';
          return (
            <div key={i} style={{ padding: '14px 20px', borderBottom: i < appointments.length - 1 ? '1px solid rgba(255,255,255,.04)' : 'none', display: 'flex', gap: 12, alignItems: 'center' }}>
              <div className={`ai-dot ${dotCls}`} style={{ flexShrink: 0 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 600, color: 'var(--t1)', fontSize: 14 }}>
                    Appt {appt.appointment_number || appt.st_appointment_id}
                  </span>
                  <span className={`chip ${isDone ? 'c-ok' : 'c-info'}`}>{appt.status}</span>
                </div>
                <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 13, color: 'var(--t3)', marginTop: 4 }}>
                  {appt.start_time && <span>{fmtDateTime(appt.start_time)}</span>}
                  {techs.length > 0 && <span>{techs.map((t: any) => t.technician_name).join(', ')}</span>}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>}
  </>;
}
