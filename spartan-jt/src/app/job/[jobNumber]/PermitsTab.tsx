'use client';

import { useState, useRef, useEffect } from 'react';

function fmt(d: string | null | undefined): string {
  if (!d) return '\u2014';
  try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); } catch { return d; }
}

const statusColors: Record&lt;string, { color: string; bg: string; bd: string }&gt; = {
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
  const [chatMessages, setChatMessages] = useState&lt;ChatMessage[]&gt;(data.permitChat || []);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [localPacket, setLocalPacket] = useState(packet);
  const [noteInput, setNoteInput] = useState&lt;Record&lt;number, string&gt;&gt;({});
  const [expandedNotes, setExpandedNotes] = useState&lt;Record&lt;number, boolean&gt;&gt;({});
  const chatEndRef = useRef&lt;HTMLDivElement&gt;(null);
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
  const checkedSteps = (typeof localPacket?.checked_steps === 'object' &amp;&amp; localPacket?.checked_steps) ? localPacket.checked_steps : {};
  const notes = (typeof localPacket?.notes === 'object' &amp;&amp; localPacket?.notes) ? localPacket.notes : {};
  const completedCount = Object.keys(checkedSteps).length;
  const pkgStatus = localPacket?.status || 'researching';
  const sc = statusColors[pkgStatus] || statusColors.researching;

  if (!localPacket) {
    return &lt;&gt;
      &lt;div className="tab-hdr"&gt;
        &lt;div className="tab-icon" style={{ background: 'var(--amberbg)', border: '1px solid var(--amberbd)', color: 'var(--amber)' }}&gt;
          &lt;svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round"&gt;&lt;path d="M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2"/&gt;&lt;rect x="8" y="2" width="8" height="4" rx="1"/&gt;&lt;/svg&gt;
        &lt;/div&gt;
        &lt;div className="tab-info"&gt;&lt;div className="tab-title"&gt;Permits&lt;/div&gt;&lt;div className="tab-desc"&gt;AI permit research with interactive checklist&lt;/div&gt;&lt;/div&gt;
      &lt;/div&gt;
      &lt;div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '60px 20px', gap: 16 }}&gt;
        &lt;div style={{ width: 56, height: 56, borderRadius: 16, background: 'var(--s2)', border: '1px solid var(--b2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}&gt;
          &lt;svg width="28" height="28" fill="none" stroke="var(--t3)" strokeWidth="1.5" viewBox="0 0 24 24"&gt;&lt;path d="M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2" strokeLinecap="round" strokeLinejoin="round"/&gt;&lt;rect x="8" y="2" width="8" height="4" rx="1"/&gt;&lt;/svg&gt;
        &lt;/div&gt;
        &lt;div style={{ color: 'var(--t2)', fontSize: 15, fontWeight: 600 }}&gt;No permits requested yet&lt;/div&gt;
        &lt;div style={{ color: 'var(--t3)', fontSize: 13, maxWidth: 340, textAlign: 'center', lineHeight: 1.5 }}&gt;When a sold estimate is detected, Pete will automatically research permit requirements for this job.&lt;/div&gt;
      &lt;/div&gt;
    &lt;/&gt;;
  }
