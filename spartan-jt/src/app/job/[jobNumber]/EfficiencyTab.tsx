'use client';
import { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';

const TARGET = 8824;
const $ = (n: number) => n >= 0 ? '$' + n.toLocaleString('en-US', { maximumFractionDigits: 0 }) : '-$' + Math.abs(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
const pct = (n: number) => n.toFixed(1) + '%';
const fmtD = (d: string) => { try { return new Date(d + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }); } catch { return d; } };
const fmtM = (d: string) => { try { return new Date(d + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', year: 'numeric' }); } catch { return d; } };
const dayName = (d: string) => { try { return new Date(d + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long' }); } catch { return ''; } };

interface Job { st_job_id: number; job_number: string; status: string; customer_name: string; business_unit_name: string; revenue: number; work_date: string; technician_name: string; project_id: string | null; scope: string; }
interface UtilRow { tech: string; weekdays_available: number; install_days: number; idle_weekdays: number; utilization_pct: number; }
interface ProjJob { st_job_id: number; job_number: string; status: string; project_id: string; revenue: number; work_date: string; business_unit_name: string; }
interface DayGroup { date: string; tech: string; jobs: Job[]; revenue: number; status: 'target' | 'near' | 'under' | 'zero'; }

function getPresets(): { label: string; from: string; to: string }[] {
  const now = new Date(); const y = now.getFullYear(); const m = now.getMonth();
  const pad = (n: number) => String(n).padStart(2, '0');
  const fmt = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const mon = new Date(now); mon.setDate(now.getDate() - now.getDay() + 1);
  const sun = new Date(mon); sun.setDate(mon.getDate() + 6);
  return [
    { label: 'This Week', from: fmt(mon), to: fmt(sun) },
    { label: 'This Month', from: fmt(new Date(y, m, 1)), to: fmt(new Date(y, m + 1, 0)) },
    { label: 'Last Month', from: fmt(new Date(y, m - 1, 1)), to: fmt(new Date(y, m, 0)) },
    { label: 'Q1 2026', from: '2026-01-01', to: '2026-03-31' },
    { label: 'YTD', from: `${y}-01-01`, to: fmt(now) },
    { label: 'Last 90d', from: fmt(new Date(now.getTime() - 90 * 86400000)), to: fmt(now) },
  ];
}
function statusOf(rev: number): 'target' | 'near' | 'under' | 'zero' { return rev >= TARGET ? 'target' : rev >= 5000 ? 'near' : rev > 0 ? 'under' : 'zero'; }
const sColor = (s: string) => s === 'target' ? 'var(--mint)' : s === 'near' ? 'var(--amber)' : 'var(--fire)';
const sLabel = (s: string) => s === 'target' ? 'At Target' : s === 'near' ? 'Near' : s === 'zero' ? '$0 VIOLATION' : 'Under';
function clean(s: string | null): string { return s ? s.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim() : ''; }

export default function EfficiencyTab() {
  const [rawJobs, setRawJobs] = useState<Job[]>([]);
  const [utilization, setUtilization] = useState<UtilRow[]>([]);
  const [projectJobs, setProjectJobs] = useState<ProjJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const presets = useMemo(() => getPresets(), []);
  const [preset, setPreset] = useState(4);
  const [dateFrom, setDateFrom] = useState(presets[4].from);
  const [dateTo, setDateTo] = useState(presets[4].to);
  const [techFilter, setTechFilter] = useState<string>('all');
  const [view, setView] = useState<'timeline' | 'violations'>('timeline');
  const [expandedDate, setExpandedDate] = useState<string | null>(null);
  const [expandedProject, setExpandedProject] = useState<string | null>(null);
  const [sortCol, setSortCol] = useState<'date' | 'revenue' | 'tech'>('date');
  const [sortDir, setSortDir] = useState<'desc' | 'asc'>('desc');

  useEffect(() => {
    setLoading(true);
    fetch(`/api/analytics/efficiency?from=${dateFrom}&to=${dateTo}`)
      .then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); })
      .then(d => {
        setRawJobs((d.jobs || []).map((j: any) => ({ ...j, revenue: Number(j.revenue) || 0 })));
        setUtilization(d.utilization || []);
        setProjectJobs((d.projectJobs || []).map((p: any) => ({ ...p, revenue: Number(p.revenue) || 0 })));
      }).catch(e => setError(e.message)).finally(() => setLoading(false));
  }, [dateFrom, dateTo]);

  function applyPreset(i: number) { setPreset(i); setDateFrom(presets[i].from); setDateTo(presets[i].to); setExpandedDate(null); setExpandedProject(null); }

  const techs = useMemo(() => Array.from(new Set(rawJobs.map(j => j.technician_name))).sort(), [rawJobs]);
  const filtered = useMemo(() => techFilter === 'all' ? rawJobs : rawJobs.filter(j => j.technician_name === techFilter), [rawJobs, techFilter]);

  const dayGroups = useMemo(() => {
    const map = new Map<string, DayGroup>();
    for (const j of filtered) { const k = `${j.technician_name}|${j.work_date}`; const g = map.get(k); if (g) { g.jobs.push(j); g.revenue += j.revenue; g.status = statusOf(g.revenue); } else map.set(k, { date: j.work_date, tech: j.technician_name, jobs: [j], revenue: j.revenue, status: statusOf(j.revenue) }); }
    const arr = Array.from(map.values());
    arr.sort((a, b) => sortCol === 'date' ? (sortDir === 'desc' ? b.date.localeCompare(a.date) : a.date.localeCompare(b.date)) : sortCol === 'revenue' ? (sortDir === 'desc' ? b.revenue - a.revenue : a.revenue - b.revenue) : (sortDir === 'desc' ? b.tech.localeCompare(a.tech) : a.tech.localeCompare(b.tech)));
    return arr;
  }, [filtered, sortCol, sortDir]);

  const sm = useMemo(() => {
    const t = dayGroups.length; const ar = dayGroups.reduce((s, g) => s + g.revenue, 0); const tr = t * TARGET;
    return { total: t, actualRev: ar, gap: tr - ar, avg: t > 0 ? ar / t : 0, eff: tr > 0 ? (ar / tr) * 100 : 0, atTarget: dayGroups.filter(g => g.status === 'target').length, zero: dayGroups.filter(g => g.status === 'zero').length };
  }, [dayGroups]);

  const violations = useMemo(() => dayGroups.filter(g => g.revenue === 0), [dayGroups]);
  const projMap = useMemo(() => { const m = new Map<string, ProjJob[]>(); for (const p of projectJobs) { const a = m.get(p.project_id) || []; a.push(p); m.set(p.project_id, a); } return m; }, [projectJobs]);

  const monthly = useMemo(() => {
    const map = new Map<string, { days: number; rev: number; at: number; z: number }>();
    for (const g of dayGroups) { const mo = g.date.substring(0, 7); const m = map.get(mo) || { days: 0, rev: 0, at: 0, z: 0 }; m.days++; m.rev += g.revenue; if (g.status === 'target') m.at++; if (g.status === 'zero') m.z++; map.set(mo, m); }
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0])).map(([mo, d]) => ({ month: mo + '-01', ...d, avg: d.days > 0 ? d.rev / d.days : 0, eff: d.days > 0 ? (d.rev / (d.days * TARGET)) * 100 : 0 }));
  }, [dayGroups]);

  function toggleSort(c: 'date' | 'revenue' | 'tech') { if (sortCol === c) setSortDir(d => d === 'desc' ? 'asc' : 'desc'); else { setSortCol(c); setSortDir('desc'); } }
  const si = (c: string) => sortCol === c ? (sortDir === 'desc' ? ' \u25BC' : ' \u25B2') : '';

  if (loading) return <div style={{ color: 'var(--t3)', padding: 40, textAlign: 'center' }}>Loading efficiency data...</div>;
  if (error) return <div style={{ color: 'var(--fire)', padding: 40 }}>Error: {error}</div>;

  const thS: React.CSSProperties = { padding: '8px 10px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.5px' };
  const thSR: React.CSSProperties = { ...thS, textAlign: 'right' };
  const thSC: React.CSSProperties = { ...thS, cursor: 'pointer', userSelect: 'none' };
  const thSCR: React.CSSProperties = { ...thSC, textAlign: 'right' };
  const subTh: React.CSSProperties = { padding: '4px 8px', textAlign: 'left', fontSize: 9, color: 'var(--t3)', fontWeight: 600, textTransform: 'uppercase' };

  return <>
    <div className="tab-hdr">
      <div className="tab-icon" style={{ background: 'var(--voltbg)', border: '1px solid var(--voltbd)', color: 'var(--volt)' }}>
        <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
      </div>
      <div className="tab-info"><div className="tab-title">Install Crew Efficiency</div><div className="tab-desc">Target: {$(TARGET)}/crew/day &middot; {sm.total} crew-days &middot; {filtered.length} jobs</div></div>
      <div style={{ textAlign: 'center' }}><div style={{ fontFamily: 'var(--mono)', fontSize: 32, fontWeight: 700, color: sm.eff >= 80 ? 'var(--mint)' : sm.eff >= 60 ? 'var(--amber)' : 'var(--fire)' }}>{pct(sm.eff)}</div><div style={{ fontSize: 9, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase' as const, color: 'var(--t3)' }}>Efficiency</div></div>
    </div>

    {/* Controls */}
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: '8px 0', alignItems: 'center' }}>
      {presets.map((p, i) => <button key={i} onClick={() => applyPreset(i)} style={{ padding: '4px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer', border: `1px solid ${preset === i ? 'var(--icebd)' : 'var(--b2)'}`, background: preset === i ? 'var(--icebg)' : 'transparent', color: preset === i ? 'var(--ice)' : 'var(--t3)' }}>{p.label}</button>)}
      <div style={{ marginLeft: 'auto', display: 'flex', gap: 6, alignItems: 'center' }}>
        <select value={techFilter} onChange={e => { setTechFilter(e.target.value); setExpandedDate(null); }} style={{ padding: '4px 8px', borderRadius: 6, border: '1px solid var(--b2)', background: 'var(--s2)', color: 'var(--t1)', fontSize: 11 }}>
          <option value="all">All Installers ({techs.length})</option>
          {techs.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <button onClick={() => setView('timeline')} style={{ padding: '4px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer', border: `1px solid ${view === 'timeline' ? 'var(--icebd)' : 'var(--b2)'}`, background: view === 'timeline' ? 'var(--icebg)' : 'transparent', color: view === 'timeline' ? 'var(--ice)' : 'var(--t3)' }}>Timeline</button>
        <button onClick={() => setView('violations')} style={{ padding: '4px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer', border: `1px solid ${view === 'violations' ? 'var(--firebd)' : 'var(--b2)'}`, background: view === 'violations' ? 'var(--firebg)' : 'transparent', color: view === 'violations' ? 'var(--fire)' : 'var(--t3)' }}>Violations ({violations.length})</button>
      </div>
    </div>

    {/* Metrics */}
    <div className="hero" style={{ gridTemplateColumns: 'repeat(5,1fr)' }}>
      <div className="st"><div className="num" style={{ fontSize: 20 }}>{$(sm.actualRev)}</div><div className="lbl">Actual Revenue</div></div>
      <div className="st sf"><div className="num" style={{ fontSize: 20, color: 'var(--fire)' }}>{$(sm.gap)}</div><div className="lbl">Gap to Target</div></div>
      <div className="st"><div className="num" style={{ fontSize: 20, color: sm.avg >= TARGET ? 'var(--mint)' : 'var(--amber)' }}>{$(Math.round(sm.avg))}</div><div className="lbl">Avg/Crew Day</div></div>
      <div className="st sm"><div className="num" style={{ fontSize: 20 }}>{sm.atTarget}<span style={{ fontSize: 12, color: 'var(--t3)' }}>/{sm.total}</span></div><div className="lbl">Hit Target</div></div>
      <div className="st" style={{ background: sm.zero > 0 ? 'var(--firebg)' : 'var(--s3)', border: sm.zero > 0 ? '1px solid var(--firebd)' : '1px solid var(--b2)' }}><div className="num" style={{ fontSize: 20, color: sm.zero > 0 ? 'var(--fire)' : 'var(--t3)' }}>{sm.zero}</div><div className="lbl">$0 Violations</div></div>
    </div>

    {/* Monthly + Utilization */}
    {monthly.length > 1 && <div className="c full"><div className="ch"><h3>Monthly Trend</h3></div><div className="cb" style={{ padding: '8px 12px' }}><div style={{ display: 'flex', gap: 8 }}>{monthly.map(m => { const w = m.days > 0 ? Math.max((m.at / m.days) * 100, 3) : 0; const zw = m.days > 0 ? (m.z / m.days) * 100 : 0; return <div key={m.month} style={{ flex: 1, minWidth: 0 }}><div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}><span style={{ fontWeight: 600, color: 'var(--t1)' }}>{fmtM(m.month)}</span><span style={{ fontFamily: 'var(--mono)', color: m.eff >= 70 ? 'var(--mint)' : 'var(--amber)' }}>{pct(m.eff)}</span></div><div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden', background: 'var(--t5)' }}>{w > 0 && <div style={{ width: `${w}%`, background: 'var(--mint)' }} />}{(100 - w - zw) > 0 && <div style={{ width: `${100 - w - zw}%`, background: 'var(--amber)' }} />}{zw > 0 && <div style={{ width: `${zw}%`, background: 'var(--fire)' }} />}</div><div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--t3)', marginTop: 2 }}><span>{m.days}d</span><span>{$(Math.round(m.avg))}/d</span></div></div>; })}</div></div></div>}
    {utilization.length > 0 && techFilter === 'all' && <div className="c full"><div className="ch"><h3>Lead Utilization</h3></div><div className="cb" style={{ padding: '8px 12px' }}><div style={{ display: 'flex', gap: 16 }}>{utilization.map(u => { const up = Number(u.utilization_pct); const c = up >= 85 ? 'var(--mint)' : up >= 70 ? 'var(--amber)' : 'var(--fire)'; return <div key={u.tech} style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ fontSize: 12, fontWeight: 500, color: 'var(--t1)', minWidth: 90 }}>{u.tech}</span><div style={{ flex: 1, height: 18, background: 'var(--t5)', borderRadius: 4, overflow: 'hidden', position: 'relative' }}><div style={{ width: `${up}%`, height: '100%', background: c, borderRadius: 4 }} /><div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 600, color: 'var(--t1)' }}>{u.install_days}/{u.weekdays_available} ({Math.round(up)}%)</div></div>{Number(u.idle_weekdays) > 0 && <span style={{ fontSize: 10, color: 'var(--fire)', whiteSpace: 'nowrap' }}>{u.idle_weekdays} idle</span>}</div>; })}</div></div></div>}

    {/* TIMELINE */}
    {view === 'timeline' && <div className="c full"><div className="ch" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><h3>Crew-Day Detail</h3><span style={{ fontSize: 10, color: 'var(--t3)' }}>{dayGroups.length} crew-days &middot; Click to expand</span></div><div className="cb" style={{ padding: 0, maxHeight: 600, overflow: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}><thead style={{ position: 'sticky', top: 0, background: 'var(--s1)', zIndex: 1 }}><tr style={{ borderBottom: '1px solid var(--b2)' }}>
        <th onClick={() => toggleSort('date')} style={thSC}>Date{si('date')}</th>
        <th onClick={() => toggleSort('tech')} style={thSC}>Installer{si('tech')}</th>
        <th style={thSR}>Jobs</th>
        <th onClick={() => toggleSort('revenue')} style={thSCR}>Revenue{si('revenue')}</th>
        <th style={thSR}>vs Target</th>
        <th style={thS}>Status</th>
      </tr></thead><tbody>
        {dayGroups.map(g => { const k = `${g.tech}|${g.date}`; const isE = expandedDate === k; const gap = g.revenue - TARGET; return (<>
          <tr key={k} onClick={() => setExpandedDate(isE ? null : k)} style={{ borderBottom: '1px solid var(--b2)', cursor: 'pointer', background: isE ? 'var(--s3)' : 'transparent' }}>
            <td style={{ padding: '6px 10px', fontSize: 12, fontFamily: 'var(--mono)' }}>{fmtD(g.date)}</td>
            <td style={{ padding: '6px 10px', fontSize: 12 }}>{g.tech}</td>
            <td style={{ padding: '6px 10px', fontSize: 12, textAlign: 'right' }}>{g.jobs.length}</td>
            <td style={{ padding: '6px 10px', fontSize: 12, textAlign: 'right', fontFamily: 'var(--mono)', fontWeight: 600, color: sColor(g.status) }}>{$(Math.round(g.revenue))}</td>
            <td style={{ padding: '6px 10px', fontSize: 11, textAlign: 'right', fontFamily: 'var(--mono)', color: gap >= 0 ? 'var(--mint)' : 'var(--fire)' }}>{gap >= 0 ? '+' : ''}{$(Math.round(gap))}</td>
            <td style={{ padding: '6px 10px' }}><span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600, background: `${sColor(g.status)}20`, color: sColor(g.status) }}>{sLabel(g.status)}</span></td>
          </tr>
          {isE && <tr key={k + '-d'}><td colSpan={6} style={{ padding: 0, background: 'var(--s2)' }}><div style={{ padding: '10px 16px' }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>{dayName(g.date)} &middot; {g.tech} &middot; {g.jobs.length} job{g.jobs.length !== 1 ? 's' : ''} &middot; {$(Math.round(g.revenue))} total</div>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}><thead><tr style={{ borderBottom: '1px solid var(--b2)' }}>
              <th style={subTh}>Job #</th><th style={subTh}>Customer</th><th style={subTh}>BU</th><th style={{ ...subTh, textAlign: 'right' }}>Revenue</th><th style={subTh}>Status</th><th style={subTh}>Project</th><th style={subTh}>Scope</th>
            </tr></thead><tbody>
              {g.jobs.map(j => <tr key={j.st_job_id} style={{ borderBottom: '1px solid var(--b2)' }}>
                <td style={{ padding: '4px 8px', fontSize: 12, fontFamily: 'var(--mono)' }}><Link href={`/job/${j.st_job_id}`} style={{ color: 'var(--ice)', textDecoration: 'none' }}>#{j.job_number}</Link></td>
                <td style={{ padding: '4px 8px', fontSize: 12 }}>{j.customer_name}</td>
                <td style={{ padding: '4px 8px', fontSize: 10, color: 'var(--t3)' }}>{j.business_unit_name.replace('Dayton - ', '').replace(' - ', ' ')}</td>
                <td style={{ padding: '4px 8px', fontSize: 12, textAlign: 'right', fontFamily: 'var(--mono)', fontWeight: 600, color: j.revenue > 0 ? 'var(--t1)' : 'var(--fire)' }}>{j.revenue > 0 ? $(Math.round(j.revenue)) : '$0'}</td>
                <td style={{ padding: '4px 8px', fontSize: 10 }}><span style={{ color: j.status === 'Completed' ? 'var(--mint)' : j.status === 'Canceled' ? 'var(--amber)' : 'var(--t2)' }}>{j.status}</span></td>
                <td style={{ padding: '4px 8px', fontSize: 10 }}>{j.project_id ? <button onClick={e => { e.stopPropagation(); setExpandedProject(expandedProject === j.project_id ? null : j.project_id); }} style={{ background: 'none', border: 'none', color: 'var(--ice)', cursor: 'pointer', fontSize: 10, fontFamily: 'var(--mono)', padding: 0, textDecoration: 'underline' }}>P-{j.project_id}</button> : <span style={{ color: 'var(--t4)' }}>&mdash;</span>}</td>
                <td style={{ padding: '4px 8px', fontSize: 10, color: 'var(--t3)', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{clean(j.scope)}</td>
              </tr>)}
            </tbody></table>
            {expandedProject && g.jobs.some(j => j.project_id === expandedProject) && projMap.has(expandedProject) && <div style={{ marginTop: 8, padding: '8px 10px', borderRadius: 6, background: 'var(--icebg)', border: '1px solid var(--icebd)' }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--ice)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 4 }}>Project Chain &middot; {expandedProject}</div>
              {(projMap.get(expandedProject) || []).map(p => <div key={`${p.st_job_id}-${p.work_date}`} style={{ display: 'flex', gap: 12, fontSize: 11, padding: '2px 0' }}>
                <Link href={`/job/${p.st_job_id}`} style={{ color: 'var(--ice)', textDecoration: 'none', fontFamily: 'var(--mono)', minWidth: 80 }}>#{p.job_number}</Link>
                <span style={{ color: 'var(--t3)', minWidth: 70 }}>{fmtD(p.work_date)}</span>
                <span style={{ fontFamily: 'var(--mono)', fontWeight: 600, color: p.revenue > 0 ? 'var(--t1)' : 'var(--fire)', minWidth: 60, textAlign: 'right' }}>{p.revenue > 0 ? $(Math.round(p.revenue)) : '$0'}</span>
                <span style={{ color: 'var(--t3)', fontSize: 10 }}>{p.business_unit_name.replace('Dayton - ', '')}</span>
              </div>)}
            </div>}
          </div></td></tr>}
        </>); })}
      </tbody></table>
      {dayGroups.length === 0 && <div style={{ padding: 24, textAlign: 'center', color: 'var(--t3)' }}>No install crew-days found.</div>}
    </div></div>}

    {/* VIOLATIONS */}
    {view === 'violations' && <div className="c full"><div className="ch" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><h3>Chunking Violations</h3><span style={{ fontSize: 11, color: 'var(--fire)', fontWeight: 600 }}>{violations.length} &middot; {$(violations.length * TARGET)} burned</span></div><div className="cb" style={{ padding: 0, maxHeight: 600, overflow: 'auto' }}>
      {violations.length === 0 ? <div style={{ padding: 24, textAlign: 'center', color: 'var(--mint)', fontWeight: 600 }}>No violations. Clean.</div> : violations.map(g => { const k = `v-${g.tech}|${g.date}`; const isE = expandedDate === k; return <div key={k} style={{ borderBottom: '1px solid var(--b2)' }}>
        <div onClick={() => setExpandedDate(isE ? null : k)} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px', cursor: 'pointer', background: isE ? 'var(--s3)' : 'transparent' }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--fire)', flexShrink: 0 }} />
          <span style={{ fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--t2)', minWidth: 90 }}>{fmtD(g.date)}</span>
          <span style={{ fontSize: 12, color: 'var(--t1)', flex: 1 }}>{g.tech}</span>
          <span style={{ fontSize: 11, color: 'var(--fire)', fontWeight: 600 }}>{g.jobs.length} job{g.jobs.length !== 1 ? 's' : ''} &middot; $0</span>
          <span style={{ fontSize: 11, color: 'var(--t3)' }}>{$(TARGET)} opp cost</span>
        </div>
        {isE && <div style={{ padding: '8px 16px 12px 30px', background: 'var(--s2)' }}>
          {g.jobs.map(j => <div key={j.st_job_id} style={{ display: 'flex', gap: 12, alignItems: 'center', padding: '4px 0', borderBottom: '1px solid var(--b2)' }}>
            <Link href={`/job/${j.st_job_id}`} style={{ color: 'var(--ice)', textDecoration: 'none', fontFamily: 'var(--mono)', fontSize: 12 }}>#{j.job_number}</Link>
            <span style={{ fontSize: 12, color: 'var(--t1)' }}>{j.customer_name}</span>
            <span style={{ fontSize: 10, color: 'var(--t3)' }}>{j.business_unit_name.replace('Dayton - ', '').replace(' - ', ' ')}</span>
            <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: j.status === 'Canceled' ? 'var(--amberbg)' : 'var(--firebg)', color: j.status === 'Canceled' ? 'var(--amber)' : 'var(--fire)', fontWeight: 600 }}>{j.status === 'Canceled' ? 'Canceled' : '$0 Invoice'}</span>
            {j.project_id && <button onClick={() => setExpandedProject(expandedProject === j.project_id ? null : j.project_id)} style={{ background: 'none', border: 'none', color: 'var(--ice)', cursor: 'pointer', fontSize: 10, fontFamily: 'var(--mono)', padding: 0, textDecoration: 'underline' }}>Project chain</button>}
          </div>)}
          {expandedProject && g.jobs.some(j => j.project_id === expandedProject) && projMap.has(expandedProject) && <div style={{ marginTop: 8, padding: '8px 10px', borderRadius: 6, background: 'var(--icebg)', border: '1px solid var(--icebd)' }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--ice)', marginBottom: 4 }}>Full Project &middot; {expandedProject}</div>
            {(projMap.get(expandedProject) || []).map(p => <div key={`${p.st_job_id}-${p.work_date}`} style={{ display: 'flex', gap: 12, fontSize: 11, padding: '2px 0' }}>
              <Link href={`/job/${p.st_job_id}`} style={{ color: 'var(--ice)', textDecoration: 'none', fontFamily: 'var(--mono)', minWidth: 80 }}>#{p.job_number}</Link>
              <span style={{ color: 'var(--t3)', minWidth: 70 }}>{fmtD(p.work_date)}</span>
              <span style={{ fontFamily: 'var(--mono)', fontWeight: 600, color: p.revenue > 0 ? 'var(--mint)' : 'var(--fire)', minWidth: 60, textAlign: 'right' }}>{p.revenue > 0 ? $(Math.round(p.revenue)) : '$0'}</span>
            </div>)}
          </div>}
        </div>}
      </div>; })}
    </div></div>}

    <div style={{ display: 'flex', gap: 16, fontSize: 10, color: 'var(--t3)', padding: '4px 0' }}>
      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--mint)' }} /> At target</span>
      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--amber)' }} /> Near ($5K+)</span>
      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--fire)' }} /> Under / $0</span>
      <span style={{ marginLeft: 'auto', fontFamily: 'var(--mono)' }}>SOP: Daily Production Tasks Step 13</span>
    </div>
  </>;
}
