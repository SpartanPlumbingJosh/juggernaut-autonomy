'use client';
import { useState } from 'react';

function fmtDateTime(d: string | null | undefined): string {
  if (!d) return '\u2014';
  try {
    const dt = new Date(d);
    return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' + dt.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  } catch { return d; }
}
function durFmt(seconds: number | null | undefined): string {
  if (!seconds) return '\u2014';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

const CATEGORY_META: Record<string, { color: string; bg: string; bd: string }> = {
  booking: { color: 'var(--ice)', bg: 'var(--icebg)', bd: 'var(--icebd)' },
  dispatch: { color: 'var(--volt)', bg: 'var(--voltbg)', bd: 'var(--voltbd)' },
  service: { color: 'var(--mint)', bg: 'var(--mintbg)', bd: 'var(--mintbd)' },
  sales: { color: 'var(--fire)', bg: 'var(--firebg)', bd: 'var(--firebd)' },
  install: { color: 'var(--hot)', bg: 'var(--hotbg)', bd: 'var(--hotbd)' },
  post_install: { color: 'var(--grape)', bg: 'var(--grapebg)', bd: 'var(--grapebd)' },
  retention: { color: 'var(--amber)', bg: 'var(--amberbg)', bd: 'var(--amberbd)' },
};

function getCategoryStyle(cat: string) {
  const key = (cat || '').toLowerCase().replace(/[- ]/g, '_');
  return CATEGORY_META[key] || CATEGORY_META.service;
}

function personalize(template: string, job: any, data: any): string {
  const customerName = job.customer_name || '[Customer Name]';
  const firstName = customerName.split(' ')[0] || customerName;
  const jobNumber = job.job_number || job.st_job_id || '[Job #]';
  const jobType = job.job_type_name || '[Job Type]';
  const buName = job.business_unit_name || '[Business Unit]';
  const address = job.customer_address || '[Address]';

  const assignments = (data.assignments || []) as any[];
  const techName = assignments.length > 0 ? (assignments[0].technician_name || 'your technician') : 'your technician';

  const appointments = (data.appointments || []) as any[];
  const nextAppt = appointments.find((a: any) => a.status === 'Scheduled');
  const apptTime = nextAppt ? fmtDateTime(nextAppt.start_time) : '[Appointment Time]';

  return template
    .replace(/\{customer_name\}/gi, customerName)
    .replace(/\{first_name\}/gi, firstName)
    .replace(/\{job_number\}/gi, jobNumber)
    .replace(/\{job_type\}/gi, jobType)
    .replace(/\{business_unit\}/gi, buName)
    .replace(/\{address\}/gi, address)
    .replace(/\{tech_name\}/gi, techName)
    .replace(/\{appointment_time\}/gi, apptTime)
    .replace(/\{company\}/gi, 'Spartan Plumbing');
}

export default function CallsTab({ job, data }: { job: any; data: any }) {
  const calls = (data.calls || []) as any[];
  const callScripts = (data.callScripts || []) as any[];
  const [selectedScript, setSelectedScript] = useState<any | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  const inbound = calls.filter((c: any) => c.direction === 'Inbound').length;
  const outbound = calls.filter((c: any) => c.direction === 'Outbound').length;
  const totalDuration = calls.reduce((s: number, c: any) => s + (c.duration_seconds || 0), 0);
  const avgDuration = calls.length > 0 ? Math.round(totalDuration / calls.length) : 0;

  const scriptsByCategory: Record<string, any[]> = {};
  callScripts.forEach((s: any) => {
    const cat = s.category || 'other';
    if (!scriptsByCategory[cat]) scriptsByCategory[cat] = [];
    scriptsByCategory[cat].push(s);
  });

  return <>
    <div className="tab-hdr">
      <div className="tab-icon" style={{ background: 'var(--icebg)', border: '1px solid var(--icebd)', color: 'var(--ice)' }}>
        <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.12.96.36 1.9.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.91.34 1.85.58 2.81.7A2 2 0 0122 16.92z"/>
        </svg>
      </div>
      <div className="tab-info">
        <div className="tab-title">Calls &amp; Scripts</div>
        <div className="tab-desc">{callScripts.length} preset scripts &middot; Call history &middot; AI scorecards</div>
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button
          onClick={() => { setShowHistory(false); setSelectedScript(null); }}
          style={{
            padding: '6px 14px', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer',
            background: !showHistory ? 'var(--icebg)' : 'var(--s3)',
            border: `1px solid ${!showHistory ? 'var(--icebd)' : 'var(--b2)'}`,
            color: !showHistory ? 'var(--ice)' : 'var(--t3)',
          }}>Scripts</button>
        <button
          onClick={() => { setShowHistory(true); setSelectedScript(null); }}
          style={{
            padding: '6px 14px', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer',
            background: showHistory ? 'var(--icebg)' : 'var(--s3)',
            border: `1px solid ${showHistory ? 'var(--icebd)' : 'var(--b2)'}`,
            color: showHistory ? 'var(--ice)' : 'var(--t3)',
          }}>Call History ({calls.length})</button>
      </div>
    </div>

    <div className="hero" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
      <div className="st" style={{ background: 'var(--icebg)', border: '1px solid var(--icebd)' }}>
        <div className="num" style={{ fontSize: 28, color: 'var(--ice)' }}>{calls.length}</div>
        <div className="lbl" style={{ color: 'var(--ice)' }}>Total Calls</div>
      </div>
      <div className="st" style={{ background: 'var(--mintbg)', border: '1px solid var(--mintbd)' }}>
        <div className="num" style={{ fontSize: 28, color: 'var(--mint)' }}>{inbound}</div>
        <div className="lbl" style={{ color: 'var(--mint)' }}>Inbound</div>
      </div>
      <div className="st" style={{ background: 'var(--voltbg)', border: '1px solid var(--voltbd)' }}>
        <div className="num" style={{ fontSize: 28, color: 'var(--volt)' }}>{outbound}</div>
        <div className="lbl" style={{ color: 'var(--volt)' }}>Outbound</div>
      </div>
      <div className="st" style={{ background: 'var(--s3)', border: '1px solid var(--b2)' }}>
        <div className="num" style={{ fontSize: 28, color: 'var(--t2)' }}>{durFmt(avgDuration)}</div>
        <div className="lbl">Avg Duration</div>
      </div>
    </div>

    {!showHistory && !selectedScript && <>
      {callScripts.length === 0 && <div className="c full"><div className="cb" style={{ color: 'var(--t3)', fontSize: 12, textAlign: 'center', padding: 40 }}>No call scripts loaded. The call_scripts table may be empty.</div></div>}

      {Object.entries(scriptsByCategory).map(([category, scripts]) => {
        const style = getCategoryStyle(category);
        return <div className="c full" key={category}>
          <div className="ch">
            <h3 style={{ textTransform: 'capitalize' }}>{category.replace(/_/g, ' ')}</h3>
            <div className="tg" style={{ background: style.bg, border: `1px solid ${style.bd}`, color: style.color }}>{scripts.length}</div>
          </div>
          <div className="cb" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 8 }}>
            {scripts.map((script: any, i: number) => (
              <div key={i} onClick={() => setSelectedScript(script)} style={{
                padding: '10px 14px', borderRadius: 8, cursor: 'pointer',
                background: 'var(--s2)', border: '1px solid var(--b1)',
                transition: 'border-color 0.15s',
              }}
              onMouseOver={(e) => (e.currentTarget.style.borderColor = style.color)}
              onMouseOut={(e) => (e.currentTarget.style.borderColor = 'var(--b1)')}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--t1)', marginBottom: 4 }}>{script.title}</div>
                <div style={{ fontSize: 10, color: 'var(--t3)' }}>
                  {script.stage && <span style={{ fontFamily: 'var(--mono)', color: style.color, marginRight: 6 }}>{script.stage}</span>}
                  {script.script_key}
                </div>
              </div>
            ))}
          </div>
        </div>;
      })}
    </>}

    {!showHistory && selectedScript && <>
      <div style={{ marginBottom: 12 }}>
        <button onClick={() => setSelectedScript(null)} style={{
          padding: '4px 12px', borderRadius: 6, fontSize: 11, cursor: 'pointer',
          background: 'var(--s3)', border: '1px solid var(--b2)', color: 'var(--t3)',
        }}>&larr; Back to Scripts</button>
      </div>
      <div className="c full">
        <div className="ch">
          <h3>{selectedScript.title}</h3>
          <div style={{ display: 'flex', gap: 6 }}>
            {selectedScript.stage && <div className="tg" style={{ background: 'var(--icebg)', border: '1px solid var(--icebd)', color: 'var(--ice)' }}>{selectedScript.stage}</div>}
            <div className="tg" style={{ background: 'var(--s3)', border: '1px solid var(--b2)', color: 'var(--t3)' }}>{selectedScript.script_key}</div>
          </div>
        </div>
        <div className="cb">
          {selectedScript.personalization_fields && <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>Personalization Fields</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {(Array.isArray(selectedScript.personalization_fields) ? selectedScript.personalization_fields : []).map((f: string, i: number) => (
                <span key={i} style={{ padding: '2px 8px', borderRadius: 4, background: 'var(--icebg)', border: '1px solid var(--icebd)', color: 'var(--ice)', fontSize: 10, fontFamily: 'var(--mono)' }}>{`{${f}}`}</span>
              ))}
            </div>
          </div>}
          <div style={{
            background: 'var(--s2)', border: '1px solid var(--b1)', borderRadius: 8,
            padding: 16, fontSize: 13, lineHeight: 1.7, color: 'var(--t1)',
            whiteSpace: 'pre-wrap',
          }}>
            {personalize(selectedScript.template_text || '', job, data)}
          </div>
          <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
            <button onClick={() => {
              const text = personalize(selectedScript.template_text || '', job, data);
              navigator.clipboard?.writeText(text);
            }} style={{
              padding: '6px 14px', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer',
              background: 'var(--mintbg)', border: '1px solid var(--mintbd)', color: 'var(--mint)',
            }}>Copy Script</button>
          </div>
        </div>
      </div>
    </>}

    {showHistory && <div className="c full">
      <div className="ch"><h3>Call History</h3>
        <div className="tg" style={{ background: 'var(--icebg)', border: '1px solid var(--icebd)', color: 'var(--ice)' }}>{calls.length}</div>
      </div>
      {calls.length > 0 ? <div className="cb" style={{ padding: 0 }}>
        <table className="mt"><thead><tr><th>Date</th><th>Direction</th><th>Type</th><th>Duration</th><th>From</th><th>To</th><th>Status</th><th>Recording</th></tr></thead><tbody>
          {calls.map((c: any, i: number) => <tr key={i}>
            <td>{fmtDateTime(c.created_on)}</td>
            <td style={{ color: c.direction === 'Inbound' ? 'var(--mint)' : 'var(--ice)' }}>{c.direction || '\u2014'}</td>
            <td>{c.call_type || '\u2014'}</td>
            <td>{durFmt(c.duration_seconds)}</td>
            <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{c.from_number || '\u2014'}</td>
            <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{c.to_number || '\u2014'}</td>
            <td>{c.status || '\u2014'}</td>
            <td>{c.recording_url ? <a href={c.recording_url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--ice)', fontSize: 11 }}>Play</a> : '\u2014'}</td>
          </tr>)}
        </tbody></table>
      </div> : <div className="cb" style={{ color: 'var(--t3)', fontSize: 12, textAlign: 'center', padding: 30 }}>No calls linked to this job.</div>}
    </div>}
  </>;
}
