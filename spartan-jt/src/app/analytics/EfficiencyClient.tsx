'use client';

import { useEffect, useState, useMemo } from 'react';

interface Summary {
  total_crew_days: number;
  actual_revenue: number;
  target_revenue: number;
  total_gap: number;
  avg_per_day: number;
  efficiency_pct: number;
  at_target: number;
  near_target: number;
  under_target: number;
  zero_days: number;
}

interface TechRow {
  technician_name: string;
  crew_days: number;
  avg_daily: number;
  min_day: number;
  max_day: number;
  total_rev: number;
  at_target: number;
  near_target: number;
  critical: number;
  hit_pct: number;
  gap_to_target: number;
}

interface DailyRow {
  technician_name: string;
  work_date: string;
  jobs: number;
  day_revenue: number;
}

interface ViolationRow {
  st_job_id: number;
  status: string;
  business_unit_name: string;
  work_date: string;
  technician_name: string;
  project_id: string | null;
  summary: string;
}

interface MonthlyRow {
  month: string;
  crew_days: number;
  avg_daily: number;
  total_rev: number;
  at_target: number;
  zero_days: number;
  efficiency_pct: number;
}

interface UtilRow {
  tech: string;
  weekdays_available: number;
  install_days: number;
  idle_weekdays: number;
  utilization_pct: number;
}

interface Data {
  dailyRevenue: DailyRow[];
  techSummary: TechRow[];
  chunkingViolations: ViolationRow[];
  summary: Summary;
  monthlyTrend: MonthlyRow[];
  utilization: UtilRow[];
}

const TARGET = 8824;

function fmt(n: number | null | undefined): string {
  if (n == null || isNaN(Number(n))) return '$0';
  return '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function pct(n: number | null | undefined): string {
  if (n == null || isNaN(Number(n))) return '0%';
  return Number(n).toFixed(1) + '%';
}

function dayColor(rev: number): string {
  if (rev >= TARGET) return 'var(--mint)';
  if (rev >= 5000) return 'var(--amber)';
  if (rev > 0) return 'var(--fire)';
  return 'var(--t4)';
}

function dayClass(rev: number): string {
  if (rev >= TARGET) return 'sm';
  if (rev >= 5000) return 'sv';
  if (rev > 0) return 'sf';
  return '';
}

function monthLabel(d: string): string {
  const dt = new Date(d + 'T00:00:00');
  return dt.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
}

export default function EfficiencyClient() {
  const [data, setData] = useState<Data | null>(null);
  const [err, setErr] = useState('');
  const [tab, setTab] = useState(0);
  const [dateRange] = useState({ from: '2026-01-01', to: '2026-12-31' });

  useEffect(() => {
    fetch(`/api/analytics/efficiency?from=${dateRange.from}&to=${dateRange.to}`)
      .then(r => r.json())
      .then(d => { if (d.error) setErr(d.error); else setData(d); })
      .catch(e => setErr(String(e)));
  }, [dateRange]);

  if (err) return <div className="loading-screen" style={{ color: 'var(--fire)' }}>Error: {err}</div>;
  if (!data) return <div className="loading-screen">Loading install efficiency data...</div>;

  const { summary: s, techSummary, chunkingViolations, dailyRevenue, monthlyTrend, utilization } = data;
  const tabs = ['Overview', 'By Installer', 'Violations', 'Daily'];

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '24px 20px 80px' }}>
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--t4)', marginBottom: 5, letterSpacing: '.3px' }}>
          SPARTAN JOB TRACKER / ANALYTICS
        </div>
        <h1 style={{ fontFamily: 'var(--disp)', fontSize: 26, fontWeight: 800, letterSpacing: '-.5px', lineHeight: 1.1 }}>
          Install Efficiency
        </h1>
        <div style={{ fontSize: 11.5, color: 'var(--t2)', marginTop: 4 }}>
          Crew-day revenue vs <span style={{ fontFamily: 'var(--mono)', color: 'var(--mint)' }}>{fmt(TARGET)}</span> target &middot; {dateRange.from.slice(0, 7)} to {dateRange.to.slice(0, 7)}
        </div>
      </div>

      <div className="hero" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
        <div className="st sf"><div className="num">{pct(s.efficiency_pct)}</div><div className="lbl">Efficiency</div></div>
        <div className="st sv"><div className="num">{fmt(s.avg_per_day)}</div><div className="lbl">Avg/Day</div></div>
        <div className="st sm"><div className="num">{s.at_target}</div><div className="lbl">At Target</div></div>
        <div className="st sg"><div className="num">{s.total_crew_days}</div><div className="lbl">Crew Days</div></div>
        <div className="st" style={{ background: 'var(--s2)', border: '1px solid var(--b1)' }}>
          <div className="num" style={{ color: s.zero_days > 0 ? 'var(--fire)' : 'var(--t2)' }}>{s.zero_days}</div>
          <div className="lbl" style={{ color: 'var(--t3)' }}>$0 Days</div>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', borderRadius: 10, border: '1px solid var(--b1)', background: 'var(--s2)', marginBottom: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 20, fontWeight: 800, color: 'var(--mint)' }}>{fmt(s.actual_revenue)}</div>
          <div style={{ fontSize: 11, color: 'var(--t3)', lineHeight: 1.4 }}>actual of <strong style={{ color: 'var(--t1)' }}>{fmt(s.target_revenue)}</strong> target</div>
        </div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 700, color: Number(s.total_gap) > 0 ? 'var(--fire)' : 'var(--mint)', padding: '4px 10px', borderRadius: 7, background: Number(s.total_gap) > 0 ? 'var(--firebg)' : 'var(--mintbg)', border: `1px solid ${Number(s.total_gap) > 0 ? 'var(--firebd)' : 'var(--mintbd)'}` }}>
          {Number(s.total_gap) > 0 ? '-' : '+'}{fmt(Math.abs(Number(s.total_gap)))} gap
        </div>
      </div>

      <div style={{ display: 'flex', gap: 2, marginBottom: 18, background: 'var(--s2)', padding: 3, borderRadius: 10, border: '1px solid var(--b1)' }}>
        {tabs.map((t, i) => (
          <button key={t} onClick={() => setTab(i)} style={{ flex: 1, padding: '8px 0', border: 'none', borderRadius: 8, cursor: 'pointer', fontFamily: 'var(--sans)', fontSize: 11, fontWeight: 700, letterSpacing: '.5px', textTransform: 'uppercase' as const, background: tab === i ? 'var(--firebg)' : 'transparent', color: tab === i ? 'var(--fire)' : 'var(--t3)', boxShadow: tab === i ? 'inset 0 0 0 1px var(--firebd)' : 'none', transition: 'all .15s' }}>
            {t}{i === 2 && chunkingViolations.length > 0 ? ` (${chunkingViolations.length})` : ''}
          </button>
        ))}
      </div>

      {tab === 0 && <OverviewTab monthlyTrend={monthlyTrend} utilization={utilization} />}
      {tab === 1 && <InstallerTab techSummary={techSummary} />}
      {tab === 2 && <ViolationsTab violations={chunkingViolations} />}
      {tab === 3 && <DailyTab dailyRevenue={dailyRevenue} />}
    </div>
  );
}

function OverviewTab({ monthlyTrend, utilization }: { monthlyTrend: MonthlyRow[]; utilization: UtilRow[] }) {
  const maxRev = useMemo(() => Math.max(...monthlyTrend.map(m => Number(m.avg_daily)), TARGET * 1.1), [monthlyTrend]);
  return (
    <>
      <div className="c" style={{ marginBottom: 16 }}>
        <div className="ch"><h3>Monthly Trend</h3><div className="tg" style={{ background: 'var(--firebg)', color: 'var(--fire)', border: '1px solid var(--firebd)' }}>Target: {fmt(TARGET)}/day</div></div>
        <div className="cb">
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 160, marginBottom: 12 }}>
            {monthlyTrend.map((m, i) => {
              const h = Math.max((Number(m.avg_daily) / maxRev) * 140, 4);
              const targetH = (TARGET / maxRev) * 140;
              return (
                <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', position: 'relative', height: '100%', justifyContent: 'flex-end' }}>
                  <div style={{ position: 'absolute', bottom: targetH + 16, left: 0, right: 0, height: 1, background: 'var(--firebd)' }} />
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 700, color: dayColor(Number(m.avg_daily)), marginBottom: 4 }}>{fmt(Number(m.avg_daily))}</div>
                  <div style={{ width: '100%', maxWidth: 48, height: h, borderRadius: 4, background: Number(m.avg_daily) >= TARGET ? 'linear-gradient(180deg, var(--mint), rgba(0,232,123,.4))' : Number(m.avg_daily) >= 5000 ? 'linear-gradient(180deg, var(--volt), rgba(45,122,255,.4))' : 'linear-gradient(180deg, var(--fire), rgba(255,45,70,.4))', transition: 'height .5s ease' }} />
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--t4)', marginTop: 6, fontWeight: 600 }}>{monthLabel(m.month)}</div>
                </div>
              );
            })}
          </div>
          <table className="mt"><thead><tr><th>Month</th><th>Crew Days</th><th>Avg/Day</th><th>At Target</th><th>$0 Days</th><th>Efficiency</th></tr></thead>
            <tbody>{monthlyTrend.map((m, i) => (<tr key={i}><td style={{ fontWeight: 600 }}>{monthLabel(m.month)}</td><td style={{ fontFamily: 'var(--mono)', textAlign: 'right' }}>{m.crew_days}</td><td style={{ fontFamily: 'var(--mono)', textAlign: 'right', color: dayColor(Number(m.avg_daily)) }}>{fmt(Number(m.avg_daily))}</td><td style={{ fontFamily: 'var(--mono)', textAlign: 'right', color: 'var(--mint)' }}>{m.at_target}</td><td style={{ fontFamily: 'var(--mono)', textAlign: 'right', color: Number(m.zero_days) > 0 ? 'var(--fire)' : 'var(--t4)' }}>{m.zero_days}</td><td style={{ fontFamily: 'var(--mono)', textAlign: 'right' }}>{pct(m.efficiency_pct)}</td></tr>))}</tbody></table>
        </div>
      </div>
      <div className="c">
        <div className="ch"><h3>Lead Installer Utilization</h3><div className="tg" style={{ background: 'var(--grapebg)', color: 'var(--grape)', border: '1px solid var(--grapebd)' }}>Kade &amp; Isaac</div></div>
        <div className="cb">
          {utilization.map((u, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '10px 0', borderBottom: i < utilization.length - 1 ? '1px solid var(--b1)' : 'none' }}>
              <div style={{ fontWeight: 700, fontSize: 13, minWidth: 110 }}>{u.tech}</div>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase' as const, color: 'var(--t3)' }}>{u.install_days} install / {u.weekdays_available} weekdays</span>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 800, color: Number(u.utilization_pct) >= 70 ? 'var(--mint)' : Number(u.utilization_pct) >= 40 ? 'var(--amber)' : 'var(--fire)' }}>{pct(u.utilization_pct)}</span>
                </div>
                <div className="gauge-bar"><div className="gauge-fill" style={{ width: `${Math.min(Number(u.utilization_pct), 100)}%`, background: Number(u.utilization_pct) >= 70 ? 'linear-gradient(90deg, var(--mint), var(--mint2))' : Number(u.utilization_pct) >= 40 ? 'linear-gradient(90deg, var(--amber), #ffd54f)' : 'linear-gradient(90deg, var(--fire), var(--fire2))' }} /></div>
              </div>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: Number(u.idle_weekdays) > 10 ? 'var(--fire)' : 'var(--t3)', minWidth: 60, textAlign: 'right' as const }}>{u.idle_weekdays} idle</div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function InstallerTab({ techSummary }: { techSummary: TechRow[] }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
      {techSummary.map((t, i) => (
        <div key={i} className="c">
          <div className="ch"><h3>{t.technician_name}</h3>
            <div className="tg" style={{ background: Number(t.hit_pct) >= 50 ? 'var(--mintbg)' : Number(t.hit_pct) >= 25 ? 'var(--amberbg)' : 'var(--firebg)', color: Number(t.hit_pct) >= 50 ? 'var(--mint)' : Number(t.hit_pct) >= 25 ? 'var(--amber)' : 'var(--fire)', border: `1px solid ${Number(t.hit_pct) >= 50 ? 'var(--mintbd)' : Number(t.hit_pct) >= 25 ? 'var(--amberbd)' : 'var(--firebd)'}` }}>{pct(t.hit_pct)} hit rate</div>
          </div>
          <div className="cb">
            <div style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase' as const, color: 'var(--t3)' }}>Avg Daily Revenue</span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 14, fontWeight: 800, color: dayColor(Number(t.avg_daily)) }}>{fmt(Number(t.avg_daily))}</span>
              </div>
              <div className="gauge-bar"><div className="gauge-fill" style={{ width: `${Math.min((Number(t.avg_daily) / TARGET) * 100, 100)}%`, background: Number(t.avg_daily) >= TARGET ? 'linear-gradient(90deg, var(--mint), var(--mint2))' : Number(t.avg_daily) >= 5000 ? 'linear-gradient(90deg, var(--volt), var(--volt2))' : 'linear-gradient(90deg, var(--fire), var(--fire2))' }} /></div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
              <SB label="Crew Days" value={String(t.crew_days)} color="var(--t1)" />
              <SB label="Total Rev" value={fmt(Number(t.total_rev))} color="var(--mint)" />
              <SB label="Gap" value={fmt(Number(t.gap_to_target))} color="var(--fire)" />
              <SB label="Min Day" value={fmt(Number(t.min_day))} color="var(--t2)" />
              <SB label="Max Day" value={fmt(Number(t.max_day))} color="var(--mint)" />
              <SB label="Critical" value={String(t.critical)} color={Number(t.critical) > 0 ? 'var(--fire)' : 'var(--t4)'} />
            </div>
            <div style={{ display: 'flex', gap: 4, marginTop: 10 }}>
              {Number(t.at_target) > 0 && <DP count={Number(t.at_target)} label="AT TARGET" bg="var(--mintbg)" bd="var(--mintbd)" color="var(--mint)" />}
              {Number(t.near_target) > 0 && <DP count={Number(t.near_target)} label="NEAR" bg="var(--voltbg)" bd="var(--voltbd)" color="var(--volt)" />}
              {Number(t.critical) > 0 && <DP count={Number(t.critical)} label="CRITICAL" bg="var(--firebg)" bd="var(--firebd)" color="var(--fire)" />}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function SB({ label, value, color }: { label: string; value: string; color: string }) {
  return (<div style={{ background: 'var(--s3)', borderRadius: 8, padding: '8px 10px', textAlign: 'center' as const }}><div style={{ fontFamily: 'var(--mono)', fontSize: 14, fontWeight: 700, color, lineHeight: 1, marginBottom: 3 }}>{value}</div><div style={{ fontSize: 8, fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase' as const, color: 'var(--t4)' }}>{label}</div></div>);
}

function DP({ count, label, bg, bd, color }: { count: number; label: string; bg: string; bd: string; color: string }) {
  return (<div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '3px 8px', borderRadius: 6, fontSize: 9, fontWeight: 700, letterSpacing: '.5px', background: bg, border: `1px solid ${bd}`, color }}><span style={{ fontFamily: 'var(--mono)' }}>{count}</span> {label}</div>);
}

function ViolationsTab({ violations }: { violations: ViolationRow[] }) {
  if (violations.length === 0) return (<div className="empty"><div className="empty-icon" style={{ background: 'var(--mintbg)', border: '1px solid var(--mintbd)' }}><svg viewBox="0 0 24 24" fill="none" stroke="var(--mint)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5" /></svg></div><div className="empty-title" style={{ color: 'var(--mint)' }}>No Chunking Violations</div><div className="empty-desc">All install jobs have revenue attached.</div></div>);
  return (
    <div className="c">
      <div className="ch"><h3>$0 Install Jobs — Chunking Violations</h3><div className="tg" style={{ background: 'var(--firebg)', color: 'var(--fire)', border: '1px solid var(--firebd)' }}>{violations.length} violations</div></div>
      <div className="cb" style={{ overflowX: 'auto' as const }}>
        <table className="mt"><thead><tr><th>Date</th><th>Job</th><th>Installer</th><th>BU</th><th>Status</th><th>Summary</th></tr></thead>
          <tbody>{violations.map((v, i) => (<tr key={i}><td style={{ fontFamily: 'var(--mono)', fontSize: 10.5, whiteSpace: 'nowrap' as const }}>{v.work_date}</td><td><a href={`/job/${v.st_job_id}`} style={{ color: 'var(--volt)', textDecoration: 'none', fontFamily: 'var(--mono)', fontSize: 10.5 }}>{v.st_job_id}</a></td><td style={{ fontWeight: 600 }}>{v.technician_name}</td><td style={{ fontSize: 10.5, color: 'var(--t2)', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>{v.business_unit_name?.replace(/Dayton - /g, '')}</td><td><span className={`chip ${v.status === 'Completed' ? 'c-ok' : v.status === 'Canceled' ? 'c-fail' : 'c-warn'}`}>{v.status}</span></td><td style={{ fontSize: 10.5, color: 'var(--t2)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>{v.summary || '\u2014'}</td></tr>))}</tbody></table>
      </div>
    </div>
  );
}

function DailyTab({ dailyRevenue }: { dailyRevenue: DailyRow[] }) {
  const grouped = useMemo(() => {
    const map: Record<string, DailyRow[]> = {};
    for (const r of dailyRevenue) { if (!map[r.work_date]) map[r.work_date] = []; map[r.work_date].push(r); }
    return Object.entries(map).sort((a, b) => b[0].localeCompare(a[0]));
  }, [dailyRevenue]);
  if (grouped.length === 0) return (<div className="empty"><div className="empty-icon" style={{ background: 'var(--voltbg)', border: '1px solid var(--voltbd)' }}><svg viewBox="0 0 24 24" fill="none" stroke="var(--volt)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" /></svg></div><div className="empty-title">No Daily Data</div><div className="empty-desc">No install crew-days found in this date range.</div></div>);
  return (
    <div>
      {grouped.map(([date, rows]) => {
        const dayTotal = rows.reduce((sum, r) => sum + Number(r.day_revenue), 0);
        const dateObj = new Date(date + 'T00:00:00');
        const dayName = dateObj.toLocaleDateString('en-US', { weekday: 'short' });
        const dateDisp = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        return (
          <div key={date} className={`st ${dayClass(dayTotal)}`} style={{ marginBottom: 8, padding: '12px 16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: rows.length > 1 ? 8 : 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 700, color: 'var(--t3)', minWidth: 32 }}>{dayName}</span>
                <span style={{ fontWeight: 600, fontSize: 13 }}>{dateDisp}</span>
                <span style={{ fontSize: 10, color: 'var(--t3)' }}>{rows.length} crew{rows.length > 1 ? 's' : ''}</span>
              </div>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 16, fontWeight: 800, color: dayColor(dayTotal) }}>{fmt(dayTotal)}</div>
            </div>
            {rows.length > 1 && (<div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' as const }}>{rows.map((r, j) => (<div key={j} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '3px 8px', borderRadius: 6, background: 'rgba(255,255,255,.04)', fontSize: 10.5, fontWeight: 600 }}><span style={{ color: 'var(--t2)' }}>{r.technician_name}</span><span style={{ fontFamily: 'var(--mono)', color: dayColor(Number(r.day_revenue)), fontWeight: 700 }}>{fmt(Number(r.day_revenue))}</span><span style={{ color: 'var(--t4)', fontFamily: 'var(--mono)', fontSize: 9 }}>{r.jobs}j</span></div>))}</div>)}
            {rows.length === 1 && (<div style={{ display: 'flex', gap: 8, marginTop: -4 }}><span style={{ fontSize: 11, color: 'var(--t2)' }}>{rows[0].technician_name}</span><span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--t4)' }}>{rows[0].jobs} job{Number(rows[0].jobs) !== 1 ? 's' : ''}</span></div>)}
          </div>
        );
      })}
    </div>
  );
}