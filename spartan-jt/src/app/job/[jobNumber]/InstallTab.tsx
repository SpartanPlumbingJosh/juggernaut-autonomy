'use client';

function fmt(d: string | null | undefined): string {
  if (!d) return '\u2014';
  try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }); } catch { return d; }
}

const stageMeta: Record<string, { label: string; color: string; bg: string; bd: string }> = {
  'Pre-Install': { label: 'Pre-Install', color: 'var(--ice)', bg: 'var(--icebg)', bd: 'var(--icebd)' },
  'Arrival': { label: 'Arrival', color: 'var(--volt)', bg: 'var(--voltbg)', bd: 'var(--voltbd)' },
  'Setup': { label: 'Setup', color: 'var(--grape)', bg: 'var(--grapebg)', bd: 'var(--grapebd)' },
  'Work': { label: 'Work', color: 'var(--fire)', bg: 'var(--firebg)', bd: 'var(--firebd)' },
  'Closeout': { label: 'Closeout', color: 'var(--mint)', bg: 'var(--mintbg)', bd: 'var(--mintbd)' },
};

const verifyIcons: Record<string, string> = {
  call: '\uD83D\uDCDE', photo: '\uD83D\uDCF7', st_data: '\uD83D\uDCCA', slack_text: '\uD83D\uDCAC', manager: '\uD83D\uDC64',
};

export default function InstallTab({ job, data }: { job: any; data: any }) {
  const playbook = data.playbook || { steps: [], tracking: [], installKey: 'install' };
  const jobMedia = (data.jobMedia || []) as any[];
  const installSteps = (playbook.steps || []).filter((s: any) => s.playbook_key === 'install');
  const trackingMap: Record<string, any> = {};
  (playbook.tracking || []).forEach((t: any) => { trackingMap[`${t.playbook_key}-${t.step_number}`] = t; });
  const stages: string[] = [];
  const stepsByStage: Record<string, any[]> = {};
  installSteps.forEach((s: any) => { if (!stepsByStage[s.quarter]) { stepsByStage[s.quarter] = []; stages.push(s.quarter); } stepsByStage[s.quarter].push(s); });
  const totalSteps = installSteps.length;
  const passedSteps = installSteps.filter((s: any) => { const t = trackingMap[`install-${s.step_number}`]; return t && t.status === 'pass'; }).length;
  const hardGates = installSteps.filter((s: any) => s.hard_gate === true || s.hard_gate === 'true');
  const hardGatesPassed = hardGates.filter((s: any) => { const t = trackingMap[`install-${s.step_number}`]; return t && t.status === 'pass'; }).length;
  const photos = jobMedia.filter((m: any) => m.media_type === 'image' || (m.file_name || '').match(/\.(jpg|jpeg|png|gif|webp)$/i));
  const videos = jobMedia.filter((m: any) => m.media_type === 'video' || (m.file_name || '').match(/\.(mp4|mov|avi|webm)$/i));
  const classifiedMedia = jobMedia.filter((m: any) => m.ai_classification);

  return <>
    <div className="tab-hdr">
      <div className="tab-icon" style={{ background: 'var(--voltbg)', border: '1px solid var(--voltbd)', color: 'var(--volt)' }}>
        <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/>
        </svg>
      </div>
      <div className="tab-info">
        <div className="tab-title">Install Day</div>
        <div className="tab-desc">13 checkpoints &middot; {hardGates.length} hard gates &middot; Code compliance &amp; photo verification</div>
      </div>
      <div className="tab-badge" style={{ background: passedSteps > 0 ? 'var(--mintbg)' : 'var(--s3)', border: `1px solid ${passedSteps > 0 ? 'var(--mintbd)' : 'var(--b2)'}`, color: passedSteps > 0 ? 'var(--mint)' : 'var(--t3)' }}>
        {passedSteps}/{totalSteps} VERIFIED
      </div>
    </div>
    <div className="hero" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
      <div className="st sf"><div className="num">{totalSteps}</div><div className="lbl">Checkpoints</div></div>
      <div className="st sv"><div className="num" style={{ color: 'var(--mint)' }}>{passedSteps}</div><div className="lbl">Verified</div></div>
      <div className="st" style={{ background: hardGatesPassed === hardGates.length && hardGates.length > 0 ? 'var(--mintbg)' : 'var(--firebg)', border: `1px solid ${hardGatesPassed === hardGates.length && hardGates.length > 0 ? 'var(--mintbd)' : 'var(--firebd)'}` }}>
        <div className="num" style={{ fontSize: 20, color: hardGatesPassed === hardGates.length && hardGates.length > 0 ? 'var(--mint)' : 'var(--fire)' }}>{hardGatesPassed}/{hardGates.length}</div>
        <div className="lbl">Hard Gates</div>
      </div>
      <div className="st" style={{ background: 'var(--grapebg)', border: '1px solid var(--grapebd)' }}>
        <div className="num" style={{ fontSize: 20, color: 'var(--grape)' }}>{photos.length}</div>
        <div className="lbl">Photos</div>
      </div>
    </div>
    {hardGates.length > 0 && <div style={{ background: 'rgba(204,34,68,0.03)', border: '1px solid var(--firebd)', borderRadius: 12, padding: 14, marginBottom: 16 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--fire)', textTransform: 'uppercase' as const, letterSpacing: 1, marginBottom: 10 }}>Hard Gates &mdash; Must Pass Before Closeout</div>
      {hardGates.map((g: any, i: number) => {
        const t = trackingMap[`install-${g.step_number}`];
        const status = t ? t.status : 'pending';
        return <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', borderTop: i > 0 ? '1px solid var(--b2)' : 'none' }}>
          <div style={{ width: 24, height: 24, borderRadius: '50%', background: status === 'pass' ? 'var(--mint)' : 'var(--fire)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, color: '#fff', fontWeight: 700, flexShrink: 0 }}>
            {status === 'pass' ? '\u2713' : g.step_number}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--t1)' }}>{g.title}</div>
            <div style={{ fontSize: 10, color: 'var(--t3)' }}>{g.description}</div>
          </div>
          <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, fontWeight: 700, background: status === 'pass' ? 'var(--mintbg)' : 'var(--firebg)', border: `1px solid ${status === 'pass' ? 'var(--mintbd)' : 'var(--firebd)'}`, color: status === 'pass' ? 'var(--mint)' : 'var(--fire)' }}>
            {status === 'pass' ? 'CLEARED' : 'REQUIRED'}
          </span>
        </div>;
      })}
    </div>}
    {stages.map((stage) => {
      const meta = stageMeta[stage] || { label: stage, color: 'var(--t2)', bg: 'var(--s3)', bd: 'var(--b2)' };
      const steps = stepsByStage[stage];
      const sPassed = steps.filter((s: any) => { const t = trackingMap[`install-${s.step_number}`]; return t && t.status === 'pass'; }).length;
      return <div className="c full" key={stage}><div className="ch"><h3>{meta.label}</h3><div className="tg" style={{ background: meta.bg, border: `1px solid ${meta.bd}`, color: meta.color }}>{sPassed}/{steps.length}</div></div>
        <div className="cb" style={{ padding: 0 }}>{steps.map((step: any, i: number) => {
          const t = trackingMap[`install-${step.step_number}`];
          const status = t ? t.status : 'pending';
          const dotCls = status === 'pass' ? 'ai-ok' : status === 'fail' ? 'ai-fail' : 'ai-wait';
          const icon = verifyIcons[step.verification_type] || '\u2022';
          const isHardGate = step.hard_gate === true || step.hard_gate === 'true';
          const stepMedia = jobMedia.filter((m: any) => m.matched_step_id === step.step_number && m.matched_playbook === 'install');
          return <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 16px', borderBottom: i < steps.length - 1 ? '1px solid var(--b2)' : 'none', background: isHardGate ? 'rgba(204,34,68,0.03)' : 'transparent' }}>
            <div className={`ai-dot ${dotCls}`} style={{ flexShrink: 0, marginTop: 2 }} />
            <span style={{ fontSize: 11, width: 22, textAlign: 'center', flexShrink: 0, marginTop: 1 }}>{icon}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--t1)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--t3)', minWidth: 22 }}>4.{step.step_number}</span>
                {step.title}
                {isHardGate && <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 4, background: 'var(--firebg)', border: '1px solid var(--firebd)', color: 'var(--fire)', fontWeight: 700, textTransform: 'uppercase' as const, letterSpacing: 0.5 }}>Gate</span>}
              </div>
              {step.description && <div style={{ fontSize: 10, color: 'var(--t3)', marginTop: 2 }}>{step.description}</div>}
              {t && t.notes && <div style={{ fontSize: 10, color: 'var(--mint)', fontStyle: 'italic', marginTop: 2 }}>{t.notes}</div>}
              {stepMedia.length > 0 && <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' as const }}>
                {stepMedia.slice(0, 4).map((m: any, mi: number) => <div key={mi} style={{ width: 48, height: 48, borderRadius: 6, background: 'var(--s3)', border: '1px solid var(--b2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, color: 'var(--t3)', overflow: 'hidden' }}>
                  {m.thumb_url ? <img src={m.thumb_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : '\uD83D\uDCF7'}
                </div>)}
                {stepMedia.length > 4 && <div style={{ width: 48, height: 48, borderRadius: 6, background: 'var(--s3)', border: '1px solid var(--b2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, color: 'var(--t3)' }}>+{stepMedia.length - 4}</div>}
              </div>}
            </div>
            <div style={{ flexShrink: 0 }}>
              {status === 'pass' && <span style={{ fontSize: 11, color: 'var(--mint)', fontWeight: 700 }}>{'\u2713'}</span>}
              {status === 'fail' && <span style={{ fontSize: 11, color: 'var(--fire)', fontWeight: 700 }}>{'\u2717'}</span>}
              {status === 'pending' && <span style={{ fontSize: 10, color: 'var(--t3)' }}>&mdash;</span>}
            </div>
          </div>;
        })}</div>
      </div>;
    })}
    <div className="g2">
      <div className="c"><div className="ch"><h3>Photo Evidence</h3><div className="tg" style={{ background: 'var(--grapebg)', border: '1px solid var(--grapebd)', color: 'var(--grape)' }}>{photos.length}</div></div><div className="cb">
        {photos.length === 0 && <div style={{ color: 'var(--t3)', fontSize: 12 }}>No photos posted to this job&apos;s channel yet.</div>}
        {photos.length > 0 && <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' as const }}>
          {photos.slice(0, 8).map((m: any, i: number) => <div key={i} style={{ width: 64, height: 64, borderRadius: 8, background: 'var(--s3)', border: '1px solid var(--b2)', overflow: 'hidden', position: 'relative' as const }}>
            {m.thumb_url ? <img src={m.thumb_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', fontSize: 20 }}>{'\uD83D\uDCF7'}</div>}
            {m.ai_classification && <div style={{ position: 'absolute' as const, bottom: 2, left: 2, right: 2, fontSize: 7, padding: '1px 3px', borderRadius: 3, background: 'rgba(0,0,0,0.7)', color: '#fff', textAlign: 'center', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>{m.ai_classification}</div>}
          </div>)}
        </div>}
        {photos.length > 8 && <div style={{ fontSize: 10, color: 'var(--t3)', marginTop: 6 }}>+ {photos.length - 8} more photos</div>}
      </div></div>
      <div className="c"><div className="ch"><h3>AI Verification</h3><div className="tg" style={{ background: 'var(--mintbg)', border: '1px solid var(--mintbd)', color: 'var(--mint)' }}>{classifiedMedia.length}</div></div><div className="cb">
        {classifiedMedia.length === 0 && <div style={{ color: 'var(--t3)', fontSize: 12 }}>No AI-classified media yet. Photos will be analyzed as they&apos;re posted.</div>}
        {classifiedMedia.slice(0, 6).map((m: any, i: number) => {
          const conf = parseFloat(m.ai_confidence) || 0;
          const confColor = conf >= 0.8 ? 'var(--mint)' : conf >= 0.5 ? 'var(--amber)' : 'var(--fire)';
          return <div className="vr" key={i}><div className={`ai-dot ${conf >= 0.8 ? 'ai-ok' : conf >= 0.5 ? 'ai-wait' : 'ai-fail'}`} /><span className="k" style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.ai_classification}</span><span className="v" style={{ color: confColor }}>{Math.round(conf * 100)}%</span></div>;
        })}
        {videos.length > 0 && <div style={{ marginTop: 10, padding: '8px 10px', background: 'var(--voltbg)', border: '1px solid var(--voltbd)', borderRadius: 8 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--volt)' }}>{'\uD83C\uDFA5'} {videos.length} Video{videos.length > 1 ? 's' : ''} Posted</div>
          <div style={{ fontSize: 10, color: 'var(--t3)', marginTop: 2 }}>Walkthrough video required for closeout.</div>
        </div>}
      </div></div>
    </div>
    {installSteps.length === 0 && <div style={{ color: 'var(--t3)', fontSize: 12, padding: 20, textAlign: 'center' }}>No install playbook steps loaded.</div>}
  </>;
}
