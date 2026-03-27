'use client';

import { useState, useRef, useEffect } from 'react';

function fmtTime(d: string | null | undefined): string {
  if (!d) return '';
  try { return new Date(d).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }); } catch { return d; }
}

const statusColors: Record<string, { color: string; bg: string; bd: string }> = {
  researching: { color: 'var(--ice)', bg: 'var(--icebg)', bd: 'var(--icebd)' },
  ready: { color: 'var(--mint)', bg: 'var(--mintbg)', bd: 'var(--mintbd)' },
  'not-required': { color: 'var(--t3)', bg: 'var(--s3)', bd: 'var(--b2)' },
  inprogress: { color: 'var(--amber)', bg: 'var(--amberbg)', bd: 'var(--amberbd)' },
  filed: { color: 'var(--ice)', bg: 'var(--icebg)', bd: 'var(--icebd)' },
  pending: { color: 'var(--amber)', bg: 'var(--amberbg)', bd: 'var(--amberbd)' },
  approved: { color: 'var(--mint)', bg: 'var(--mintbg)', bd: 'var(--mintbd)' },
  onsite: { color: 'var(--volt)', bg: 'var(--voltbg)', bd: 'var(--voltbd)' },
};

interface ChatMessage { id: number; role: string; message: string; user_id?: string; user_name?: string; created_at: string; }
interface PermitStep { step: number; action: string; phone?: string; website?: string; fee?: string; notes?: string; }

export default function PermitsTab({ job, data }: { job: any; data: any }) {
  const packet = data.permitPacket as any | null;
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(data.permitChat || []);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [localPacket, setLocalPacket] = useState(packet);
  const [noteInput, setNoteInput] = useState<Record<number, string>>({});
  const [expandedNotes, setExpandedNotes] = useState<Record<number, boolean>>({});
  const chatEndRef = useRef<HTMLDivElement>(null);
  const userId = (data as any)?.userId || '';
  const userName = (data as any)?.userName || '';

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [chatMessages]);

  const isAuthorized = ['U06N32PKK8U','U06MN0CHE3G','U06NHDPGRA4','U07U4RCJX9B','U06NAXE0M3S','U06N3S2B4GW','U06NKNW6CDT','U06NT7YQR6X'].includes(userId);

  async function sendChat() {
    if (!chatInput.trim() || chatLoading) return;
    const msg = chatInput.trim();
    setChatInput('');
    setChatLoading(true);
    setChatMessages(prev => [...prev, { id: Date.now(), role: 'user', message: msg, user_name: userName, created_at: new Date().toISOString() }]);
    try {
      const res = await fetch(`/api/job/${job.st_job_id}/permit-chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: msg, userId, userName }) });
      const result = await res.json();
      if (result.messages) setChatMessages(result.messages);
    } catch { /* keep optimistic */ }
    setChatLoading(false);
  }

  async function toggleStep(stepNum: number) {
    if (!isAuthorized) return;
    try {
      const res = await fetch(`/api/job/${job.st_job_id}/permit-action`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'toggleStep', stepNum, userId, userName }) });
      const result = await res.json();
      if (result.packet) setLocalPacket(result.packet);
    } catch { /* silent */ }
  }

  async function saveNote(stepNum: number) {
    if (!isAuthorized || !noteInput[stepNum]?.trim()) return;
    try {
      const res = await fetch(`/api/job/${job.st_job_id}/permit-action`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'saveNote', stepNum, value: noteInput[stepNum].trim(), userId, userName }) });
      const result = await res.json();
      if (result.packet) setLocalPacket(result.packet);
      setNoteInput(prev => ({ ...prev, [stepNum]: '' }));
    } catch { /* silent */ }
  }

  const research = localPacket?.research || {};
  const steps: PermitStep[] = research.steps || [];
  const checkedSteps = (typeof localPacket?.checked_steps === 'object' && localPacket?.checked_steps) ? localPacket.checked_steps : {};
  const notes = (typeof localPacket?.notes === 'object' && localPacket?.notes) ? localPacket.notes : {};
  const completedCount = Object.keys(checkedSteps).length;
  const pkgStatus = localPacket?.status || 'researching';
  const sc = statusColors[pkgStatus] || statusColors.researching;

  const clipIcon = <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round"><path d="M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/></svg>;

  if (!localPacket) {
    return <>
      <div className="tab-hdr">
        <div className="tab-icon" style={{ background: 'var(--amberbg)', border: '1px solid var(--amberbd)', color: 'var(--amber)' }}>{clipIcon}</div>
        <div className="tab-info"><div className="tab-title">Permits</div><div className="tab-desc">AI permit research with interactive checklist</div></div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '60px 20px', gap: 16 }}>
        <div style={{ width: 56, height: 56, borderRadius: 16, background: 'var(--s2)', border: '1px solid var(--b2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <svg width="28" height="28" fill="none" stroke="var(--t3)" strokeWidth="1.5" viewBox="0 0 24 24"><path d="M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2" strokeLinecap="round" strokeLinejoin="round"/><rect x="8" y="2" width="8" height="4" rx="1"/></svg>
        </div>
        <div style={{ color: 'var(--t2)', fontSize: 15, fontWeight: 600 }}>No permits requested yet</div>
        <div style={{ color: 'var(--t3)', fontSize: 13, maxWidth: 340, textAlign: 'center', lineHeight: 1.5 }}>When a sold estimate is detected, permit requirements will be automatically researched for this job.</div>
      </div>
    </>;
  }

  return <>
    <div className="tab-hdr">
      <div className="tab-icon" style={{ background: sc.bg, border: `1px solid ${sc.bd}`, color: sc.color }}>{clipIcon}</div>
      <div className="tab-info">
        <div className="tab-title">Permits</div>
        <div className="tab-desc">{research.jurisdiction || 'AI permit research'}{research.confidence ? ` | ${research.confidence} confidence` : ''}</div>
      </div>
      <div className="tab-badge" style={{ background: sc.bg, border: `1px solid ${sc.bd}`, color: sc.color }}>{completedCount}/{steps.length} done</div>
    </div>

    {research.summary && (
      <div className="c full"><div className="cb" style={{ padding: '12px 16px', fontSize: 13, color: 'var(--t2)', lineHeight: 1.6 }}>{research.summary}</div></div>
    )}

    <div className="c full">
      <div className="ch"><h3>Permit Checklist</h3></div>
      <div className="cb" style={{ padding: 0 }}>
        {steps.map((step: PermitStep, i: number) => {
          const checked = !!checkedSteps[String(step.step)];
          const stepNotes: any[] = notes[String(step.step)] || [];
          const isExpanded = expandedNotes[step.step];
          return (
            <div key={i} style={{ padding: '14px 16px', borderBottom: '1px solid var(--b1)', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
              <div
                onClick={() => isAuthorized && toggleStep(step.step)}
                style={{
                  width: 22, height: 22, minWidth: 22, borderRadius: 6, marginTop: 1,
                  border: checked ? 'none' : '2px solid var(--b3)',
                  background: checked ? 'var(--mint)' : 'transparent',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  cursor: isAuthorized ? 'pointer' : 'default', transition: 'all .15s'
                }}
              >
                {checked && <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#000" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, color: checked ? 'var(--t3)' : 'var(--t1)', fontWeight: 500, textDecoration: checked ? 'line-through' : 'none' }}>{step.action}</div>
                <div style={{ display: 'flex', gap: 12, marginTop: 6, flexWrap: 'wrap' }}>
                  {step.phone && <a href={`tel:${step.phone}`} style={{ fontSize: 12, color: 'var(--ice)', textDecoration: 'none' }}>{step.phone}</a>}
                  {step.website && <a href={step.website.startsWith('http') ? step.website : `https://${step.website}`} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, color: 'var(--ice)', textDecoration: 'none' }}>Website</a>}
                  {step.fee && <span style={{ fontSize: 12, color: 'var(--amber)' }}>{step.fee}</span>}
                </div>
                {checked && checkedSteps[String(step.step)] && (
                  <div style={{ fontSize: 11, color: 'var(--t4)', marginTop: 4 }}>{checkedSteps[String(step.step)].user_name} {fmtTime(checkedSteps[String(step.step)].completed_at)}</div>
                )}
                {stepNotes.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    <div onClick={() => setExpandedNotes(p => ({ ...p, [step.step]: !p[step.step] }))} style={{ fontSize: 11, color: 'var(--t4)', cursor: 'pointer' }}>
                      {stepNotes.length} note{stepNotes.length > 1 ? 's' : ''} {isExpanded ? '\u25B2' : '\u25BC'}
                    </div>
                    {isExpanded && stepNotes.map((n: any, ni: number) => (
                      <div key={ni} style={{ fontSize: 12, color: 'var(--t3)', marginTop: 4, padding: '4px 8px', background: 'var(--s2)', borderRadius: 6 }}>
                        <span style={{ color: 'var(--t4)' }}>{n.user_name}</span> {n.text}
                      </div>
                    ))}
                  </div>
                )}
                {isAuthorized && (
                  <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                    <input
                      value={noteInput[step.step] || ''}
                      onChange={e => setNoteInput(p => ({ ...p, [step.step]: e.target.value }))}
                      onKeyDown={e => e.key === 'Enter' && saveNote(step.step)}
                      placeholder="Add a note..."
                      style={{ flex: 1, fontSize: 12, padding: '5px 8px', background: 'var(--s2)', border: '1px solid var(--b2)', borderRadius: 6, color: 'var(--t2)', outline: 'none' }}
                    />
                    {noteInput[step.step]?.trim() && (
                      <button onClick={() => saveNote(step.step)} style={{ fontSize: 11, padding: '4px 10px', background: 'var(--icebg)', border: '1px solid var(--icebd)', color: 'var(--ice)', borderRadius: 6, cursor: 'pointer' }}>Save</button>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
        {steps.length === 0 && (
          <div style={{ padding: '24px 16px', textAlign: 'center', color: 'var(--t4)', fontSize: 13 }}>Research in progress. Steps will appear here once complete.</div>
        )}
      </div>
    </div>

    <div className="c full" style={{ marginTop: 16 }}>
      <div className="ch"><h3>Permit Chat</h3></div>
      <div className="cb" style={{ padding: 0 }}>
        <div style={{ maxHeight: 360, overflowY: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {chatMessages.length === 0 && (
            <div style={{ textAlign: 'center', color: 'var(--t4)', fontSize: 13, padding: '20px 0' }}>No messages yet. Ask a question about permits for this job.</div>
          )}
          {chatMessages.map((m) => (
            <div key={m.id} style={{ display: 'flex', flexDirection: 'column', alignItems: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
              <div style={{
                maxWidth: '85%', padding: '10px 14px', borderRadius: 12, fontSize: 13, lineHeight: 1.5,
                background: m.role === 'user' ? 'var(--icebg)' : 'var(--s3)',
                border: `1px solid ${m.role === 'user' ? 'var(--icebd)' : 'var(--b2)'}`,
                color: 'var(--t1)', whiteSpace: 'pre-wrap'
              }}>{m.message}</div>
              <div style={{ fontSize: 10, color: 'var(--t5)', marginTop: 3, padding: '0 4px' }}>
                {m.role === 'user' ? (m.user_name || 'You') : 'Spartan AI'} {fmtTime(m.created_at)}
              </div>
            </div>
          ))}
          {chatLoading && (
            <div style={{ display: 'flex', alignItems: 'flex-start' }}>
              <div style={{ padding: '10px 14px', borderRadius: 12, background: 'var(--s3)', border: '1px solid var(--b2)', fontSize: 13, color: 'var(--t3)' }}>Thinking...</div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>
        {isAuthorized ? (
          <div style={{ padding: '10px 16px', borderTop: '1px solid var(--b1)', display: 'flex', gap: 8 }}>
            <input
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendChat()}
              placeholder="Ask about permits for this job..."
              disabled={chatLoading}
              style={{ flex: 1, fontSize: 13, padding: '8px 12px', background: 'var(--s2)', border: '1px solid var(--b2)', borderRadius: 8, color: 'var(--t1)', outline: 'none' }}
            />
            <button
              onClick={sendChat}
              disabled={chatLoading || !chatInput.trim()}
              style={{
                padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600,
                cursor: chatLoading ? 'not-allowed' : 'pointer',
                background: chatInput.trim() ? 'var(--icebg)' : 'var(--s2)',
                border: `1px solid ${chatInput.trim() ? 'var(--icebd)' : 'var(--b2)'}`,
                color: chatInput.trim() ? 'var(--ice)' : 'var(--t4)',
              }}
            >Send</button>
          </div>
        ) : (
          <div style={{ padding: '12px 16px', borderTop: '1px solid var(--b1)', textAlign: 'center', fontSize: 12, color: 'var(--t4)' }}>
            Chat is available to authorized team members only.
          </div>
        )}
      </div>
    </div>
  </>;
}