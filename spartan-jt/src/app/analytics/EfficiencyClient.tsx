'use client';

import { useEffect, useState, useMemo, useCallback } from 'react';

interface JobDetail { st_job_id: string; job_number: string; customer_name: string; bu_name: string; revenue: number; status: string; scope: string; }
interface Summary { total_crew_days: number; actual_revenue: number; target_revenue: number; total_gap: number; avg_per_day: number; efficiency_pct: number; at_target: number; near_target: number; under_target: number; zero_days: number; }
interface TechRow { technician_name: string; crew_days: number; avg_daily: number; min_day: number; max_day: number; total_rev: number; at_target: number; near_target: number; critical: number; zero_days: number; hit_pct: number; gap_to_target: number; }
interface DailyRow { technician_name: string; work_date: string; jobs: number; day_revenue: number; job_details: JobDetail[]; }
interface ViolationRow { st_job_id: string; status: string; business_unit_name: string; work_date: string; technician_name: string; project_id: string | null; summary: string; customer_name: string; }
interface MonthlyRow { month: string; crew_days: number; avg_daily: number; total_rev: number; at_target: number; zero_days: number; efficiency_pct: number; zero_rev_potential: number; }
interface UtilRow { tech: string; weekdays_available: number; install_days: number; idle_weekdays: number; utilization_pct: number; }
interface Data { dailyRevenue: DailyRow[]; techSummary: TechRow[]; chunkingViolations: ViolationRow[]; summary: Summary; monthlyTrend: MonthlyRow[]; utilization: UtilRow[]; }

const TARGET = 8824;
function fmt(n: number | null | undefined): string { if (n == null || isNaN(Number(n))) return '$0'; return '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 }); }
function fmtK(n: number): string { if (n >= 1000000) return '$' + (n / 1000000).toFixed(1) + 'M'; if (n >= 1000) return '$' + Math.round(n / 1000) + 'K'; return fmt(n); }
function pct(n: number | null | undefined): string { if (n == null || isNaN(Number(n))) return '0%'; return Number(n).toFixed(1) + '%'; }
function dayColor(rev: number): string { if (rev >= TARGET) return 'var(--mint)'; if (rev >= 5000) return 'var(--amber)'; if (rev > 0) return 'var(--fire)'; return 'var(--t4)'; }
function dayBand(rev: number): 'at' | 'near' | 'critical' | 'zero' { if (rev >= TARGET) return 'at'; if (rev >= 5000) return 'near'; if (rev > 0) return 'critical'; return 'zero'; }
function dayClass(rev: number): string { if (rev >= TARGET) return 'sm'; if (rev >= 5000) return 'sv'; if (rev > 0) return 'sf'; return ''; }
function monthLabel(d: string): string { const dt = new Date(d + '-01T00:00:00'); return dt.toLocaleDateString('en-US', { month: 'short', year: '2-digit' }); }
function dateLabel(d: string): string { const dt = new Date(d + 'T00:00:00'); return dt.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }); }
function shortBU(name: string): string { return (name || '').replace(/Dayton - (Plumbing|Drain) - /g, '').replace('Replacement ', '').replace('Drain ', ''); }

export default function EfficiencyClient() {
  const [data, setData] = useState<Data | null>(null);
  const [err, setErr] = useState('');
  const [tab, setTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const thisYear = new Date().getFullYear();
  const [fromDate, setFromDate] = useState(`${thisYear}-01-01`);
  const [toDate, setToDate] = useState(`${thisYear}-12-31`);
  const [techFilter, setTechFilter] = useState<string>('all');

  const fetchData = useCallback(() => {
    setLoading(true); setErr('');
    fetch(`/api/analytics/efficiency?from=${fromDate}&to=${toDate}`)
      .then(r => r.json())
      .then(d => { if (d.error) setErr(d.error); else setData(d); })
      .catch(e => setErr(String(e)))
      .finally(() => setLoading(false));
  }, [fromDate, toDate]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (err) return <div className="loading-screen" style={{ color: 'var(--fire)' }}>Error: {err}</div>;
  if (!data || loading) return <div className="loading-screen">Loading install efficiency data...</div>;

  const { summary: s, techSummary, chunkingViolations, dailyRevenue, monthlyTrend, utilization } = data;
  const filteredDaily = techFilter === 'all' ? dailyRevenue : dailyRevenue.filter(d => d.technician_name === techFilter);
  const allTechs = [...new Set(dailyRevenue.map(d => d.technician_name))].sort();
  const tabs = [{ label: 'Overview', icon: '◎' }, { label: 'By Installer', icon: '⬡' }, { label: 'Violations', icon: '⚠', count: chunkingViolations.length }, { label: 'Daily', icon: '▦' }];

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '24px 20px 80px' }}>
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--t4)', marginBottom: 5, letterSpacing: '.3px' }}>
          <a href="/" style={{ color: 'var(--t3)', textDecoration: 'none' }}>JOB TRACKER</a> / ANALYTICS
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h1 style={{ fontFamily: 'var(--disp)', fontSize: 26, fontWeight: 800, letterSpacing: '-.5px', lineHeight: 1.1 }}>Install Crew Efficiency</h1>
            <div style={{ fontSize: 11.5, color: 'var(--t2)', marginTop: 4 }}>
              Target: <span style={{ fontFamily: 'var(--mono)', color: 'var(--mint)' }}>{fmt(TARGET)}</span>/crew/day &middot; SOP: Daily Production Tasks Step 13
            </div>
          </div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 36, fontWeight: 800, color: s.efficiency_pct >= 80 ? 'var(--mint)' : s.efficiency_pct >= 60 ? 'var(--amber)' : 'var(--fire)', lineHeight: 1 }}>{pct(s.efficiency_pct)}</div>
        </div>
      </div>

      {/* Date Range */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <label style={{ fontSize: 10, fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase' as const, color: 'var(--t3)' }}>Range</label>
        <input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} style={{ background: 'var(--s3)', border: '1px solid var(--b1)', borderRadius: 7, padding: '5px 8px', color: 'var(--t1)', fontFamily: 'var(--mono)', fontSize: 11, outline: 'none' }} />
        <span style={{ color: 'var(--t4)', fontSize: 11 }}>→</span>
        <input type="date" value={toDate} onChange={e => setToDate(e.target.value)} style={{ background: 'var(--s3)', border: '1px solid var(--b1)', borderRadius: 7, padding: '5px 8px', color: 'var(--t1)', fontFamily: 'var(--mono)', fontSize: 11, outline: 'none' }} />
        <button onClick={fetchData} style={{ background: 'var(--firebg)', border: '1px solid var(--firebd)', borderRadius: 7, padding: '5px 12px', color: 'var(--fire)', fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 700, cursor: 'pointer', letterSpacing: '.5px' }}>REFRESH</button>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
          {[{ label: 'Q1', from: `${thisYear}-01-01`, to: `${thisYear}-04-01` }, { label: 'Q2', from: `${thisYear}-04-01`, to: `${thisYear}-07-01` }, { label: 'YTD', from: `${thisYear}-01-01`, to: `${thisYear}-12-31` }].map(p => (
            <button key={p.label} onClick={() => { setFromDate(p.from); setToDate(p.to); }} style={{ background: fromDate === p.from && toDate === p.to ? 'var(--voltbg)' : 'transparent', border: fromDate === p.from && toDate === p.to ? '1px solid var(--voltbd)' : '1px solid var(--b1)', borderRadius: 6, padding: '4px 10px', color: fromDate === p.from && toDate === p.to ? 'var(--volt)' : 'var(--t3)', fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 700, cursor: 'pointer' }}>{p.label}</button>
          ))}
        </div>
      </div>

      {/* Hero Stats */}
      <div className="hero" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <HC label="ACTUAL REVENUE" value={fmtK(s.actual_revenue)} cls="sv" />
        <HC label="TARGET REVENUE" value={fmtK(s.target_revenue)} cls="" />
        <HC label="REVENUE GAP" value={`-${fmtK(s.total_gap)}`} cls="sf" />
        <HC label="AVG / CREW DAY" value={fmt(s.avg_per_day)} cls={s.avg_per_day >= TARGET ? 'sm' : s.avg_per_day >= 5000 ? 'sv' : 'sf'} />
      </div>
      <div className="hero" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <HC label={`AT TARGET (${fmt(TARGET)}+)`} value={String(s.at_target)} sub={`of ${s.total_crew_days} crew-days`} cls="sm" />
        <HC label="NEAR ($5K-$8.8K)" value={String(s.near_target)} cls="sv" />
        <HC label="CRITICAL (<$5K)" value={String(s.under_target)} cls="sf" />
        <HC label="$0 VIOLATIONS" value={String(s.zero_days)} sub={s.zero_days > 0 ? `= ${fmtK(s.zero_days * TARGET)} burned` : undefined} cls={s.zero_days > 0 ? 'sf' : ''} />
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 2, marginBottom: 18, background: 'var(--s2)', padding: 3, borderRadius: 10, border: '1px solid var(--b1)' }}>
        {tabs.map((t, i) => (
          <button key={t.label} onClick={() => setTab(i)} style={{ flex: 1, padding: '8px 0', border: 'none', borderRadius: 8, cursor: 'pointer', fontFamily: 'var(--sans)', fontSize: 11, fontWeight: 700, letterSpacing: '.5px', textTransform: 'uppercase' as const, background: tab === i ? 'var(--firebg)' : 'transparent', color: tab === i ? 'var(--fire)' : 'var(--t3)', boxShadow: tab === i ? 'inset 0 0 0 1px var(--firebd)' : 'none', transition: 'all .15s' }}>
            <span style={{ marginRight: 4 }}>{t.icon}</span>{t.label}{t.count ? ` (${t.count})` : ''}
          </button>
        ))}
      </div>

      {tab === 0 && <OverviewTab monthlyTrend={monthlyTrend} utilization={utilization} />}
      {tab === 1 && <InstallerTab techSummary={techSummary} dailyRevenue={dailyRevenue} />}
      {tab === 2 && <ViolationsTab violations={chunkingViolations} />}
      {tab === 3 && <DailyTab dailyRevenue={filteredDaily} allTechs={allTechs} techFilter={techFilter} setTechFilter={setTechFilter} />}
    </div>
  );
}

function HC({ label, value, sub, cls }: { label: string; value: string; sub?: string; cls: string }) {
  return (<div className={`st ${cls}`} style={{ padding: '14px 16px' }}><div className="num" style={{ fontSize: 22 }}>{value}</div><div className="lbl">{label}</div>{sub && <div style={{ fontSize: 10, color: 'var(--t3)', marginTop: 2, fontFamily: 'var(--mono)' }}>{sub}</div>}</div>);
}

function GB({ value, max, color }: { value: number; max: number; color: string }) {
  return (<div className="gauge-bar"><div className="gauge-fill" style={{ width: `${Math.min((value / max) * 100, 100)}%`, background: color }} /></div>);
}

function OverviewTab({ monthlyTrend, utilization }: { monthlyTrend: MonthlyRow[]; utilization: UtilRow[] }) {
  const maxRev = useMemo(() => Math.max(...monthlyTrend.map(m => Number(m.avg_daily)), TARGET * 1.1), [monthlyTrend]);
  return (<>
    <div className="c" style={{ marginBottom: 16 }}>
      <div className="ch"><h3>Monthly Trend</h3><div className="tg" style={{ background: 'var(--firebg)', color: 'var(--fire)', border: '1px solid var(--firebd)' }}>Target: {fmt(TARGET)}/day</div></div>
      <div className="cb">
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 180, marginBottom: 16, position: 'relative' }}>
          <div style={{ position: 'absolute', bottom: `${(TARGET / maxRev) * 160 + 16}px`, left: 0, right: 0, height: 1, background: 'var(--firebd)', zIndex: 1 }} />
          <div style={{ position: 'absolute', bottom: `${(TARGET / maxRev) * 160 + 20}px`, right: 4, fontSize: 8, fontFamily: 'var(--mono)', color: 'var(--fire)', fontWeight: 700, letterSpacing: '.5px', zIndex: 1 }}>TARGET</div>
          {monthlyTrend.map((m, i) => {
            const h = Math.max((Number(m.avg_daily) / maxRev) * 160, 4);
            return (<div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', height: '100%' }}>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 700, color: dayColor(Number(m.avg_daily)), marginBottom: 4 }}>{fmt(Number(m.avg_daily))}</div>
              <div style={{ width: '100%', maxWidth: 52 }}>
                {(() => { const total = m.crew_days || 1; const atH = (m.at_target / total) * h; const zeroH = (m.zero_days / total) * h; const restH = h - atH - zeroH;
                  return (<div style={{ height: h, borderRadius: 4, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                    {m.at_target > 0 && <div style={{ height: atH, background: 'var(--mint)', minHeight: 2 }} />}
                    {restH > 0 && <div style={{ height: restH, background: Number(m.avg_daily) >= 5000 ? 'var(--amber)' : 'var(--fire)', minHeight: 2 }} />}
                    {m.zero_days > 0 && <div style={{ height: zeroH, background: 'var(--t4)', minHeight: 2 }} />}
                  </div>); })()}
              </div>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--t4)', marginTop: 6, fontWeight: 600 }}>{monthLabel(m.month)}</div>
            </div>);
          })}
        </div>
        <table className="mt"><thead><tr><th>Month</th><th style={{ textAlign: 'right' }}>Crew Days</th><th style={{ textAlign: 'right' }}>Revenue</th><th style={{ textAlign: 'right' }}>Avg/Day</th><th style={{ textAlign: 'right' }}>At Target</th><th style={{ textAlign: 'right' }}>$0 Days</th><th style={{ textAlign: 'right' }}>$0 Potential</th><th style={{ textAlign: 'right' }}>Eff.</th></tr></thead>
          <tbody>{monthlyTrend.map((m, i) => (<tr key={i}><td style={{ fontWeight: 600 }}>{monthLabel(m.month)}</td><td style={{ fontFamily: 'var(--mono)', textAlign: 'right' }}>{m.crew_days}</td><td style={{ fontFamily: 'var(--mono)', textAlign: 'right', color: 'var(--mint)' }}>{fmtK(m.total_rev)}</td><td style={{ fontFamily: 'var(--mono)', textAlign: 'right', color: dayColor(Number(m.avg_daily)), fontWeight: 700 }}>{fmt(Number(m.avg_daily))}</td><td style={{ fontFamily: 'var(--mono)', textAlign: 'right', color: 'var(--mint)' }}>{m.at_target}</td><td style={{ fontFamily: 'var(--mono)', textAlign: 'right', color: Number(m.zero_days) > 0 ? 'var(--fire)' : 'var(--t4)' }}>{m.zero_days}</td><td style={{ fontFamily: 'var(--mono)', textAlign: 'right', color: Number(m.zero_rev_potential) > 0 ? 'var(--fire)' : 'var(--t4)', fontSize: 10 }}>{Number(m.zero_rev_potential) > 0 ? fmtK(m.zero_rev_potential) : '—'}</td><td style={{ fontFamily: 'var(--mono)', textAlign: 'right', fontWeight: 700, color: Number(m.efficiency_pct) >= 80 ? 'var(--mint)' : Number(m.efficiency_pct) >= 60 ? 'var(--amber)' : 'var(--fire)' }}>{pct(m.efficiency_pct)}</td></tr>))}</tbody></table>
      </div>
    </div>
    <div className="c">
      <div className="ch"><h3>Lead Installer Utilization</h3><div className="tg" style={{ background: 'var(--grapebg)', color: 'var(--grape)', border: '1px solid var(--grapebd)' }}>Kade &amp; Isaac</div></div>
      <div className="cb">
        <div style={{ fontSize: 10, color: 'var(--t3)', marginBottom: 12 }}>Weekdays with install-BU appointments. Idle days = no install work dispatched.</div>
        {utilization.map((u, i) => (<div key={i} style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '10px 0', borderBottom: i < utilization.length - 1 ? '1px solid var(--b1)' : 'none' }}>
          <div style={{ fontWeight: 700, fontSize: 13, minWidth: 110 }}>{u.tech}</div>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase' as const, color: 'var(--t3)' }}>{u.install_days} / {u.weekdays_available} weekdays</span>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 800, color: Number(u.utilization_pct) >= 70 ? 'var(--mint)' : Number(u.utilization_pct) >= 40 ? 'var(--amber)' : 'var(--fire)' }}>{pct(u.utilization_pct)}</span>
            </div>
            <GB value={Number(u.utilization_pct)} max={100} color={Number(u.utilization_pct) >= 70 ? 'linear-gradient(90deg, var(--mint), var(--mint2))' : Number(u.utilization_pct) >= 40 ? 'linear-gradient(90deg, var(--amber), #ffd54f)' : 'linear-gradient(90deg, var(--fire), var(--fire2))'} />
          </div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: Number(u.idle_weekdays) > 10 ? 'var(--fire)' : 'var(--t3)', minWidth: 60, textAlign: 'right' as const }}>{u.idle_weekdays} idle</div>
        </div>))}
      </div>
    </div>
    <div style={{ display: 'flex', gap: 16, marginTop: 12, fontSize: 10, color: 'var(--t3)' }}>
      <span><span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: 'var(--mint)', verticalAlign: 'middle', marginRight: 4 }} />At target ({fmt(TARGET)}+)</span>
      <span><span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: 'var(--amber)', verticalAlign: 'middle', marginRight: 4 }} />Near ($5K-{fmtK(TARGET)})</span>
      <span><span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: 'var(--fire)', verticalAlign: 'middle', marginRight: 4 }} />Critical (&lt;$5K / $0)</span>
    </div>
  </>);
}

function InstallerTab({ techSummary, dailyRevenue }: { techSummary: TechRow[]; dailyRevenue: DailyRow[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  return (<div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 12 }}>
    {techSummary.map((t, i) => {
      const isOpen = expanded === t.technician_name;
      const techDays = isOpen ? dailyRevenue.filter(d => d.technician_name === t.technician_name).sort((a, b) => b.work_date.localeCompare(a.work_date)) : [];
      return (<div key={i} className="c" style={{ gridColumn: isOpen ? '1 / -1' : undefined }}>
        <div className="ch" style={{ cursor: 'pointer' }} onClick={() => setExpanded(isOpen ? null : t.technician_name)}>
          <h3>{t.technician_name}</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div className="tg" style={{ background: Number(t.hit_pct) >= 50 ? 'var(--mintbg)' : Number(t.hit_pct) >= 25 ? 'var(--amberbg)' : 'var(--firebg)', color: Number(t.hit_pct) >= 50 ? 'var(--mint)' : Number(t.hit_pct) >= 25 ? 'var(--amber)' : 'var(--fire)', border: `1px solid ${Number(t.hit_pct) >= 50 ? 'var(--mintbd)' : Number(t.hit_pct) >= 25 ? 'var(--amberbd)' : 'var(--firebd)'}` }}>{pct(t.hit_pct)} hit rate</div>
            <span style={{ color: 'var(--t4)', fontSize: 11, transition: 'transform .15s', display: 'inline-block', transform: isOpen ? 'rotate(180deg)' : 'none' }}>▼</span>
          </div>
        </div>
        <div className="cb">
          <div style={{ marginBottom: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase' as const, color: 'var(--t3)' }}>Avg Daily Revenue</span>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 16, fontWeight: 800, color: dayColor(Number(t.avg_daily)) }}>{fmt(Number(t.avg_daily))}</span>
            </div>
            <GB value={Number(t.avg_daily)} max={TARGET} color={Number(t.avg_daily) >= TARGET ? 'linear-gradient(90deg, var(--mint), var(--mint2))' : Number(t.avg_daily) >= 5000 ? 'linear-gradient(90deg, var(--amber), #ffd54f)' : 'linear-gradient(90deg, var(--fire), var(--fire2))'} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 10 }}>
            <SB label="Crew Days" value={String(t.crew_days)} color="var(--t1)" />
            <SB label="Total Rev" value={fmtK(Number(t.total_rev))} color="var(--mint)" />
            <SB label="Gap" value={fmtK(Number(t.gap_to_target))} color="var(--fire)" />
            <SB label="Min Day" value={fmt(Number(t.min_day))} color="var(--t2)" />
            <SB label="Max Day" value={fmt(Number(t.max_day))} color="var(--mint)" />
            <SB label="$0 Days" value={String(t.zero_days)} color={Number(t.zero_days) > 0 ? 'var(--fire)' : 'var(--t4)'} />
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            {Number(t.at_target) > 0 && <DP count={Number(t.at_target)} label="AT TARGET" bg="var(--mintbg)" bd="var(--mintbd)" color="var(--mint)" />}
            {Number(t.near_target) > 0 && <DP count={Number(t.near_target)} label="NEAR" bg="var(--voltbg)" bd="var(--voltbd)" color="var(--volt)" />}
            {Number(t.critical) > 0 && <DP count={Number(t.critical)} label="CRITICAL" bg="var(--firebg)" bd="var(--firebd)" color="var(--fire)" />}
          </div>
          {isOpen && techDays.length > 0 && (<div style={{ marginTop: 14, borderTop: '1px solid var(--b1)', paddingTop: 12 }}>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase' as const, color: 'var(--t3)', marginBottom: 8 }}>Day-by-day breakdown</div>
            {techDays.map((day, di) => (<DayRow key={di} day={day} showTech={false} />))}
          </div>)}
        </div>
      </div>);
    })}
  </div>);
}

function ViolationsTab({ violations }: { violations: ViolationRow[] }) {
  if (violations.length === 0) return (<div className="empty"><div className="empty-icon" style={{ background: 'var(--mintbg)', border: '1px solid var(--mintbd)' }}><svg viewBox="0 0 24 24" fill="none" stroke="var(--mint)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5" /></svg></div><div className="empty-title" style={{ color: 'var(--mint)' }}>No Chunking Violations</div><div className="empty-desc">All install jobs have revenue attached.</div></div>);
  return (<div className="c">
    <div className="ch"><h3>$0 Install Jobs — Chunking Violations</h3><div className="tg" style={{ background: 'var(--firebg)', color: 'var(--fire)', border: '1px solid var(--firebd)' }}>{violations.length} violations = {fmtK(violations.length * TARGET)} burned</div></div>
    <div className="cb">
      <div style={{ fontSize: 11, color: 'var(--t2)', marginBottom: 12, lineHeight: 1.5 }}>Chunking SOP: ¼ day=$2,500 · ½ day=$5,000 · ¾ day=$7,500 · full day=$10,000+. $0 install-BU jobs mean revenue wasn&apos;t attached before crew rolled.</div>
      <div style={{ overflowX: 'auto' as const }}>
        <table className="mt"><thead><tr><th>Date</th><th>Job</th><th>Customer</th><th>Installer</th><th>BU</th><th>Status</th><th>Summary</th></tr></thead>
          <tbody>{violations.map((v, i) => (<tr key={i}><td style={{ fontFamily: 'var(--mono)', fontSize: 10.5, whiteSpace: 'nowrap' as const }}>{v.work_date}</td><td><a href={`/job/${v.st_job_id}`} style={{ color: 'var(--volt)', textDecoration: 'none', fontFamily: 'var(--mono)', fontSize: 10.5 }}>{v.st_job_id}</a></td><td style={{ fontSize: 11, maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>{v.customer_name || '—'}</td><td style={{ fontWeight: 600 }}>{v.technician_name}</td><td style={{ fontSize: 10, color: 'var(--t2)', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>{shortBU(v.business_unit_name)}</td><td><span className={`chip ${v.status === 'Completed' ? 'c-ok' : v.status === 'Canceled' ? 'c-fail' : 'c-warn'}`}>{v.status}</span></td><td style={{ fontSize: 10, color: 'var(--t2)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>{v.summary || '—'}</td></tr>))}</tbody></table>
      </div>
    </div>
  </div>);
}

function DailyTab({ dailyRevenue, allTechs, techFilter, setTechFilter }: { dailyRevenue: DailyRow[]; allTechs: string[]; techFilter: string; setTechFilter: (v: string) => void }) {
  const grouped = useMemo(() => {
    const map: Record<string, DailyRow[]> = {};
    for (const r of dailyRevenue) { if (!map[r.work_date]) map[r.work_date] = []; map[r.work_date].push(r); }
    return Object.entries(map).sort((a, b) => b[0].localeCompare(a[0]));
  }, [dailyRevenue]);

  return (<div>
    <div style={{ display: 'flex', gap: 4, marginBottom: 14, flexWrap: 'wrap' }}>
      <button onClick={() => setTechFilter('all')} style={{ background: techFilter === 'all' ? 'var(--voltbg)' : 'transparent', border: techFilter === 'all' ? '1px solid var(--voltbd)' : '1px solid var(--b1)', borderRadius: 6, padding: '4px 10px', color: techFilter === 'all' ? 'var(--volt)' : 'var(--t3)', fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 700, cursor: 'pointer' }}>ALL</button>
      {allTechs.map(t => (<button key={t} onClick={() => setTechFilter(t)} style={{ background: techFilter === t ? 'var(--voltbg)' : 'transparent', border: techFilter === t ? '1px solid var(--voltbd)' : '1px solid var(--b1)', borderRadius: 6, padding: '4px 10px', color: techFilter === t ? 'var(--volt)' : 'var(--t3)', fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 700, cursor: 'pointer' }}>{t.split(' ')[1] || t}</button>))}
    </div>
    {grouped.length === 0 ? (<div className="empty"><div className="empty-title">No Daily Data</div><div className="empty-desc">No install crew-days found for this filter.</div></div>) : grouped.map(([date, rows]) => {
      const dayTotal = rows.reduce((sum, r) => sum + Number(r.day_revenue), 0);
      return (<div key={date} style={{ marginBottom: 6 }}>
        <div className={`st ${dayClass(dayTotal)}`} style={{ padding: '10px 16px', marginBottom: 2 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontWeight: 700, fontSize: 13 }}>{dateLabel(date)}</span>
              <span style={{ fontSize: 10, color: 'var(--t3)' }}>{rows.length} crew{rows.length > 1 ? 's' : ''}</span>
            </div>
            <div style={{ fontFamily: 'var(--mono)', fontSize: 18, fontWeight: 800, color: dayColor(dayTotal) }}>{fmt(dayTotal)}</div>
          </div>
        </div>
        {rows.map((r, j) => (<DayRow key={j} day={r} showTech={true} />))}
      </div>);
    })}
  </div>);
}

function DayRow({ day, showTech }: { day: DailyRow; showTech: boolean }) {
  const [open, setOpen] = useState(false);
  const band = dayBand(day.day_revenue);
  return (<div style={{ marginBottom: 2 }}>
    <div onClick={() => day.job_details?.length > 0 && setOpen(!open)} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 16px', background: 'var(--s2)', border: '1px solid var(--b1)', borderRadius: open ? '8px 8px 0 0' : 8, cursor: day.job_details?.length > 0 ? 'pointer' : 'default', transition: 'all .1s' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {showTech && <span style={{ fontWeight: 600, fontSize: 12, minWidth: 110 }}>{day.technician_name}</span>}
        {!showTech && <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--t3)', minWidth: 80 }}>{dateLabel(day.work_date)}</span>}
        <span style={{ fontSize: 10, color: 'var(--t3)', fontFamily: 'var(--mono)' }}>{day.jobs}j</span>
        <span className={`chip ${band === 'at' ? 'c-ok' : band === 'near' ? 'c-warn' : band === 'critical' ? 'c-fail' : ''}`} style={band === 'zero' ? { background: 'var(--s3)', border: '1px solid var(--b1)', color: 'var(--t4)' } : {}}>{band === 'at' ? 'AT TARGET' : band === 'near' ? 'NEAR' : band === 'critical' ? 'CRITICAL' : '$0'}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 14, fontWeight: 800, color: dayColor(day.day_revenue) }}>{fmt(day.day_revenue)}</span>
        {day.job_details?.length > 0 && <span style={{ color: 'var(--t4)', fontSize: 9, transition: 'transform .15s', display: 'inline-block', transform: open ? 'rotate(180deg)' : 'none' }}>▼</span>}
      </div>
    </div>
    {open && day.job_details && (<div style={{ background: 'var(--s3)', border: '1px solid var(--b1)', borderTop: 'none', borderRadius: '0 0 8px 8px', padding: '8px 12px' }}>
      {day.job_details.map((j, ji) => (<div key={ji} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 4px', borderBottom: ji < day.job_details.length - 1 ? '1px solid var(--b1)' : 'none', fontSize: 11 }}>
        <a href={`/job/${j.st_job_id}`} style={{ color: 'var(--volt)', textDecoration: 'none', fontFamily: 'var(--mono)', fontSize: 10, minWidth: 70, flexShrink: 0 }}>#{j.job_number || j.st_job_id}</a>
        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const, color: 'var(--t2)' }}>{j.customer_name || '—'}</span>
        <span style={{ fontSize: 9, color: 'var(--t3)', maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>{shortBU(j.bu_name)}</span>
        <span className={`chip ${j.status === 'Completed' ? 'c-ok' : j.status === 'Canceled' ? 'c-fail' : 'c-warn'}`} style={{ fontSize: 8, padding: '2px 6px' }}>{j.status}</span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700, color: j.revenue > 0 ? 'var(--mint)' : 'var(--fire)', minWidth: 60, textAlign: 'right' as const }}>{fmt(j.revenue)}</span>
      </div>))}
    </div>)}
  </div>);
}

function SB({ label, value, color }: { label: string; value: string; color: string }) {
  return (<div style={{ background: 'var(--s3)', borderRadius: 8, padding: '8px 10px', textAlign: 'center' as const }}><div style={{ fontFamily: 'var(--mono)', fontSize: 14, fontWeight: 700, color, lineHeight: 1, marginBottom: 3 }}>{value}</div><div style={{ fontSize: 8, fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase' as const, color: 'var(--t4)' }}>{label}</div></div>);
}

function DP({ count, label, bg, bd, color }: { count: number; label: string; bg: string; bd: string; color: string }) {
  return (<div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '3px 8px', borderRadius: 6, fontSize: 9, fontWeight: 700, letterSpacing: '.5px', background: bg, border: `1px solid ${bd}`, color }}><span style={{ fontFamily: 'var(--mono)' }}>{count}</span> {label}</div>);
}
