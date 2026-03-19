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

export default function ServiceTab({ job, data }: { job: any; data: any }) {
  const appointments = (data.appointments || []) as any[];
  const assignments = (data.assignments || []) as any[];
  const verifications = (data.verifications || []) as any[];

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

  const serviceChecks = verifications.filter((v: any) => {
    const nm = (v.verification_name || '').toLowerCase();
    return nm.includes('arrival') || nm.includes('booking') || nm.includes('crew') || nm.includes('completed') || nm.includes('same day') || nm.includes('customer info') || nm.includes('job type');
  });

  const completedAppts = appointments.filter((a: any) => a.status === 'Done').length;
  const scheduledAppts = appointments.filter((a: any) => a.status === 'Scheduled').length;

  return <>
    <div className="tab-hdr">
      <div className="tab-icon" style={{ background: 'var(--voltbg)', border: '1px solid var(--voltbd)', color: 'var(--volt)' }}>
        <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
          <polygon points="5 3 19 12 5 21 5 3"/>
        </svg>
      </div>
      <div className="tab-info">
        <div className="tab-title">Service Process</div>
        <div className="tab-desc">Appointment timeline, technician assignments, and dispatch tracking</div>
      </div>
      <div className="tab-badge" style={{ background: 'var(--voltbg)', border: '1px solid var(--voltbd)', color: 'var(--volt)' }}>
        {completedAppts}/{appointments.length} COMPLETE
      </div>
    </div>

    <div className="hero" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
      <div className="st sf"><div className="num">{appointments.length}</div><div className="lbl">Appointments</div></div>
      <div className="st sv"><div className="num" style={{ color: 'var(--mint)' }}>{completedAppts}</div><div className="lbl">Completed</div></div>
      <div className="st sm"><div className="num" style={{ color: scheduledAppts > 0 ? 'var(--volt)' : 'var(--t3)' }}>{scheduledAppts}</div><div className="lbl">Scheduled</div></div>
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
                  {appt.arrival_window_start && <span><strong style={{ color: 'var(--t2)' }}>Window:</strong> {fmtTime(appt.arrival_window_start)} – {fmtTime(appt.arrival_window_end)}</span>}
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

    {serviceChecks.length > 0 && <div className="c full">
      <div className="ch"><h3>Service Verification Checks</h3><div className="tg" style={{ background: 'var(--hotbg)', border: '1px solid var(--hotbd)', color: 'var(--hot)' }}>{serviceChecks.filter((v: any) => v.result === 'pass').length}/{serviceChecks.length}</div></div>
      <div className="cb">
        {serviceChecks.map((v: any, i: number) => {
          const dot = v.result === 'pass' ? 'ai-ok' : v.result === 'fail' ? 'ai-fail' : 'ai-wait';
          const chip = v.result === 'pass' ? 'c-ok' : v.result === 'fail' ? 'c-fail' : 'c-info';
          const label = v.result === 'pass' ? '\u2713 Verified' : v.result === 'fail' ? '\u2717 Failed' : 'Pending';
          return <div className="vr" key={i}><div className={`ai-dot ${dot}`} /><span className="k">{v.verification_name}</span><span className={`chip ${chip}`}>{label}</span></div>;
        })}
      </div>
    </div>}

    {appointments.length === 0 && assignments.length === 0 && <div style={{ color: 'var(--t3)', fontSize: 12, padding: 20, textAlign: 'center' }}>No service process data available for this job yet.</div>}
  </>;
}