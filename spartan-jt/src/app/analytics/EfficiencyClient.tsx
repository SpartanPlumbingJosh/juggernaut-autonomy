'use client';
import { useEffect, useState, useCallback } from 'react';

/* ── Types ────────────────────────────── */
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
interface Violation {
  st_job_id: number;
  status: string;
  business_unit_name: string;
  work_date: string;
  technician_name: string;
  project_id: string | null;
  summary: string;
}
interface MonthRow {
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
interface AnalyticsData {
  dailyRevenue: DailyRow[];
  techSummary: TechRow[];
  chunkingViolations: Violation[];
  summary: Summary;
  monthlyTrend: MonthRow[];
  utilization: UtilRow[];
}

/* ── Helpers ──────────────────────────── */
const $ = (n: number | string) => {
  const v = Number(n) || 0;
  return v >= 0
    ? '$' + v.toLocaleString('en-US', { maximumFractionDigits: 0 })
    : '-$' + Math.abs(v).toLocaleString('en-US', { maximumFractionDigits: 0 });
};
const pct = (n: number | string) => (Number(n) || 0).toFixed(1) + '%';
const fmtDate = (d: string) => {
  try {
    return new Date(d + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch { return d; }
};
const fmtMonth = (d: string) => {
  try {
    return new Date(d + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
  } catch { return d; }
};

const TARGET = 8824;

function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  return match ? decodeURIComponent(match[2]) : null;
}

/* ── Sub Components ──────────────────── */
function Metric({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="c" style={{ padding: '14px 16px' }}>
      <div style={{ fontSize: 11, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 600, fontFamily: 'var(--mono)', color: color || 'var(--t1)', lineHeight: 1.2 }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: 'var(--t3)', marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function StackBar({ at, near, crit, total }: { at: number; near: number; crit: number; total: number }) {
  if (total === 0) return <div style={{ height: 12, background: 'var(--t5)', borderRadius: 3 }} />;
  return (
    <div style={{ display: 'flex', height: 12, borderRadius: 3, overflow: 'hidden', background: 'var(--t5)' }}>
      {at > 0 && <div style={{ width: `${(at / total) * 100}%`, background: 'var(--mint)' }} />}
      {near > 0 && <div style={{ width: `${(near / total) * 100}%`, background: 'var(--amber)' }} />}
      {crit > 0 && <div style={{ width: `${(crit / total) * 100}%`, background: 'var(--fire)' }} />}
    </div>
  );
}

function UtilBar({ used, total }: { used: number; total: number }) {
  const w = total > 0 ? (used / total) * 100 : 0;
  const color = w >= 85 ? 'var(--mint)' : w >= 70 ? 'var(--amber)' : 'var(--fire)';
  return (
    <div style={{ flex: 1, height: 24, background: 'var(--t5)', borderRadius: 4, overflow: 'hidden', position: 'relative' }}>
      <div style={{ width: `${w}%`, height: '100%', background: color, borderRadius: 4, transition: 'width 0.6s ease' }} />
      <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 600, color: 'var(--t1)' }}>
        {used} / {total} days ({Math.round(w)}%)
      </div>
    </div>
  );
}

/* ── Gauge Ring ───────────────────────── */
function Gauge({ value, size = 100 }: { value: number; size?: number }) {
  const clamp = Math.max(0, Math.min(100, value));
  const color = clamp >= 80 ? 'var(--mint)' : clamp >= 60 ? 'var(--amber)' : 'var(--fire)';
  const deg = (clamp / 100) * 360;
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%', flexShrink: 0,
      background: `conic-gradient(${color} 0deg, ${color} ${deg}deg, var(--t5) ${deg}deg)`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{
        width: size - 16, height: size - 16, borderRadius: '50%',
        background: 'var(--bg)', display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <span style={{ fontSize: size * 0.24, fontWeight: 700, fontFamily: 'var(--mono)', color }}>{Math.round(clamp)}%</span>
      </div>
    </div>
  );
}

/* ── Violations Table ─────────────────── */
function ViolationRow({ v }: { v: Violation }) {
  const isCancel = v.status === 'Canceled';
  return (
    <tr style={{ borderBottom: '1px solid var(--t5)' }}>
      <td style={{ padding: '8px 10px', fontSize: 12, fontFamily: 'var(--mono)' }}>
        <a href={`/job/${v.st_job_id}`} style={{ color: 'var(--ice)', textDecoration: 'none' }}>#{v.st_job_id}</a>
      </td>
      <td style={{ padding: '8px 10px', fontSize: 12 }}>{fmtDate(v.work_date)}</td>
      <td style={{ padding: '8px 10px', fontSize: 12 }}>{v.technician_name}</td>
      <td style={{ padding: '8px 10px', fontSize: 12 }}>
        <span style={{
          display: 'inline-block', padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
          background: isCancel ? 'rgba(239,159,39,0.15)' : 'rgba(226,75,74,0.15)',
          color: isCancel ? 'var(--amber)' : 'var(--fire)',
        }}>
          {isCancel ? 'Canceled' : '$0 Invoice'}
        </span>
      </td>
      <td style={{ padding: '8px 10px', fontSize: 11, color: 'var(--t3)', maxWidth: 250, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {v.summary?.replace(/<[^>]+>/g, '').trim() || '\u2014'}
      </td>
    </tr>
  );
}

/* ── Main Component ───────────────────── */
export default function EfficiencyClient() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<'overview' | 'techs' | 'violations' | 'daily'>('overview');
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    const cookie = getCookie('jt_user');
    if (cookie) {
      try {
        const parsed = JSON.parse(cookie);
        if (parsed.name) setAuthed(true);
        if (parsed.theme) document.documentElement.dataset.theme = parsed.theme;
      } catch { /* */ }
    }
  }, []);

  useEffect(() => {
    fetch('/api/analytics/efficiency?from=2026-01-01&to=2026-12-31')
      .then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (!authed) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', color: 'var(--t2)' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 18, marginBottom: 8 }}>Sign in required</div>
          <a href="/" style={{ color: 'var(--ice)' }}>Go to Job Tracker</a>
        </div>
      </div>
    );
  }

  if (loading) return <div className="loading-screen">Loading efficiency data...</div>;
  if (error || !data) return <div className="loading-screen">Error: {error || 'No data'}</div>;

  const s = data.summary;
  const maxDayRev = Math.max(...(data.techSummary || []).map(t => Number(t.max_day) || 0), TARGET);

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '24px 20px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 11, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            <a href="/" style={{ color: 'var(--t3)', textDecoration: 'none' }}>Job Tracker</a> / Analytics
          </div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--t1)', margin: '4px 0 0' }}>Install Crew Efficiency</h1>
          <div style={{ fontSize: 12, color: 'var(--t3)', marginTop: 2 }}>Target: {$(TARGET)}/crew/day &middot; SOP: Daily Production Tasks Step 13</div>
        </div>
        <Gauge value={Number(s.efficiency_pct) || 0} size={80} />
      </div>

      {/* Metric cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10, marginBottom: 20 }}>
        <Metric label="Actual Revenue" value={$(s.actual_revenue)} />
        <Metric label="Target Revenue" value={$(s.target_revenue)} />
        <Metric label="Revenue Gap" value={$(Number(s.total_gap) * -1)} color="var(--fire)" />
        <Metric label="Avg / Crew Day" value={$(s.avg_per_day)} color={Number(s.avg_per_day) >= TARGET ? 'var(--mint)' : 'var(--amber)'} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10, marginBottom: 24 }}>
        <Metric label="At Target ($8,824+)" value={String(s.at_target || 0)} sub={`of ${s.total_crew_days} crew-days`} color="var(--mint)" />
        <Metric label="Near ($5K-$8.8K)" value={String(s.near_target || 0)} color="var(--amber)" />
        <Metric label="Critical (<$5K)" value={String(s.under_target || 0)} color="var(--fire)" />
        <Metric label="$0 Violations" value={String(s.zero_days || 0)} sub={`= ${$(Number(s.zero_days || 0) * TARGET)} burned`} color="var(--fire)" />
      </div>

      {/* Tab nav */}
      <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--t5)', marginBottom: 20 }}>
        {(['overview', 'techs', 'violations', 'daily'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '8px 16px', fontSize: 12, fontWeight: tab === t ? 600 : 400, cursor: 'pointer',
            color: tab === t ? 'var(--ice)' : 'var(--t3)', background: 'transparent', border: 'none',
            borderBottom: tab === t ? '2px solid var(--ice)' : '2px solid transparent',
            textTransform: 'capitalize',
          }}>{t === 'techs' ? 'By Installer' : t === 'violations' ? `Violations (${data.chunkingViolations.length})` : t}</button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'overview' && <OverviewTab data={data} />}
      {tab === 'techs' && <TechTab data={data} maxRev={maxDayRev} />}
      {tab === 'violations' && <ViolationsTab violations={data.chunkingViolations} />}
      {tab === 'daily' && <DailyTab rows={data.dailyRevenue} />}
    </div>
  );
}

/* ── Overview Tab ─────────────────────── */
function OverviewTab({ data }: { data: AnalyticsData }) {
  return (
    <>
      {/* Monthly trend */}
      <div className="c" style={{ marginBottom: 20 }}>
        <div className="ch"><h3>Monthly Trend</h3></div>
        <div className="cb" style={{ padding: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
            {data.monthlyTrend.map(m => (
              <div key={m.month} className="c" style={{ padding: 12 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--t1)', marginBottom: 8 }}>{fmtMonth(m.month)}</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--t3)', marginBottom: 4 }}>
                  <span>{Number(m.crew_days)} crew-days</span>
                  <span style={{ color: Number(m.efficiency_pct) >= 70 ? 'var(--mint)' : 'var(--amber)' }}>{pct(m.efficiency_pct)} eff.</span>
                </div>
                <StackBar at={Number(m.at_target)} near={Number(m.crew_days) - Number(m.at_target) - Number(m.zero_days)} crit={Number(m.zero_days)} total={Number(m.crew_days)} />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginTop: 6 }}>
                  <span style={{ color: 'var(--t2)' }}>Rev: {$(m.total_rev)}</span>
                  <span style={{ color: 'var(--t2)' }}>Avg: {$(m.avg_daily)}/day</span>
                </div>
                {Number(m.zero_days) > 0 && (
                  <div style={{ fontSize: 10, color: 'var(--fire)', marginTop: 4 }}>
                    {m.zero_days} zero-dollar days ({$(Number(m.zero_days) * TARGET)} potential)
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Utilization */}
      <div className="c" style={{ marginBottom: 20 }}>
        <div className="ch"><h3>Lead Installer Utilization</h3></div>
        <div className="cb" style={{ padding: 16 }}>
          {data.utilization.map(u => (
            <div key={u.tech} style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
              <div style={{ width: 110, fontSize: 13, fontWeight: 500, color: 'var(--t1)', flexShrink: 0 }}>{u.tech}</div>
              <UtilBar used={Number(u.install_days)} total={Number(u.weekdays_available)} />
              {Number(u.idle_weekdays) > 0 && (
                <div style={{ fontSize: 11, color: 'var(--fire)', whiteSpace: 'nowrap', flexShrink: 0 }}>
                  {u.idle_weekdays} idle
                </div>
              )}
            </div>
          ))}
          <div style={{ fontSize: 11, color: 'var(--t3)', marginTop: 8 }}>
            Showing weekdays with install-BU appointments. Idle days = no install work dispatched (could be PTO, service work, or scheduling gap).
          </div>
        </div>
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 16, fontSize: 11, color: 'var(--t3)', padding: '0 4px' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 10, height: 10, borderRadius: 2, background: 'var(--mint)' }} /> At target ($8,824+)</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 10, height: 10, borderRadius: 2, background: 'var(--amber)' }} /> Near ($5K-$8.8K)</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 10, height: 10, borderRadius: 2, background: 'var(--fire)' }} /> Critical (&lt;$5K / $0)</span>
      </div>
    </>
  );
}

/* ── Tech Tab ─────────────────────────── */
function TechTab({ data, maxRev }: { data: AnalyticsData; maxRev: number }) {
  return (
    <div className="c">
      <div className="ch"><h3>Installer Performance</h3></div>
      <div className="cb" style={{ padding: 16 }}>
        {data.techSummary.map(t => {
          const avgColor = Number(t.avg_daily) >= TARGET ? 'var(--mint)' : Number(t.avg_daily) >= 5000 ? 'var(--amber)' : 'var(--fire)';
          return (
            <div key={t.technician_name} style={{ marginBottom: 20, paddingBottom: 16, borderBottom: '1px solid var(--t5)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--t1)' }}>{t.technician_name}</div>
                <div style={{ display: 'flex', gap: 16, fontSize: 12 }}>
                  <span style={{ color: 'var(--t3)' }}>{t.crew_days} days</span>
                  <span style={{ color: avgColor, fontFamily: 'var(--mono)', fontWeight: 600 }}>{$(t.avg_daily)}/day</span>
                  <span style={{ color: 'var(--t3)' }}>Total: {$(t.total_rev)}</span>
                </div>
              </div>
              <StackBar at={Number(t.at_target)} near={Number(t.near_target)} crit={Number(t.critical)} total={Number(t.crew_days)} />
              <div style={{ display: 'flex', gap: 16, marginTop: 6, fontSize: 11 }}>
                <span style={{ color: 'var(--mint)' }}>{t.at_target} at target ({pct(t.hit_pct)})</span>
                <span style={{ color: 'var(--amber)' }}>{t.near_target} near</span>
                <span style={{ color: 'var(--fire)' }}>{t.critical} critical</span>
                <span style={{ color: 'var(--t3)', marginLeft: 'auto' }}>Gap: {$(Number(t.gap_to_target) * -1)}</span>
              </div>
              <div style={{ display: 'flex', gap: 16, marginTop: 4, fontSize: 11, color: 'var(--t3)' }}>
                <span>Low: {$(t.min_day)}</span>
                <span>High: {$(t.max_day)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Violations Tab ───────────────────── */
function ViolationsTab({ violations }: { violations: Violation[] }) {
  return (
    <div className="c">
      <div className="ch" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3>Chunking Violations ($0 Install Days)</h3>
        <span style={{ fontSize: 11, color: 'var(--fire)', fontWeight: 600 }}>
          {violations.length} violations &middot; ={$(violations.length * TARGET)} burned capacity
        </span>
      </div>
      <div className="cb" style={{ padding: 0, overflow: 'auto' }}>
        {violations.length === 0 ? (
          <div style={{ padding: 24, textAlign: 'center', color: 'var(--mint)' }}>No chunking violations found. Clean.</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--t5)' }}>
                <th style={{ padding: '8px 10px', textAlign: 'left', fontSize: 10, color: 'var(--t3)', fontWeight: 600, textTransform: 'uppercase' }}>Job</th>
                <th style={{ padding: '8px 10px', textAlign: 'left', fontSize: 10, color: 'var(--t3)', fontWeight: 600, textTransform: 'uppercase' }}>Date</th>
                <th style={{ padding: '8px 10px', textAlign: 'left', fontSize: 10, color: 'var(--t3)', fontWeight: 600, textTransform: 'uppercase' }}>Installer</th>
                <th style={{ padding: '8px 10px', textAlign: 'left', fontSize: 10, color: 'var(--t3)', fontWeight: 600, textTransform: 'uppercase' }}>Issue</th>
                <th style={{ padding: '8px 10px', textAlign: 'left', fontSize: 10, color: 'var(--t3)', fontWeight: 600, textTransform: 'uppercase' }}>Summary</th>
              </tr>
            </thead>
            <tbody>
              {violations.map(v => <ViolationRow key={v.st_job_id} v={v} />)}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

/* ── Daily Tab ────────────────────────── */
function DailyTab({ rows }: { rows: DailyRow[] }) {
  return (
    <div className="c">
      <div className="ch"><h3>Daily Revenue Detail</h3></div>
      <div className="cb" style={{ padding: 0, overflow: 'auto', maxHeight: 600 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead style={{ position: 'sticky', top: 0, background: 'var(--bg)' }}>
            <tr style={{ borderBottom: '1px solid var(--t5)' }}>
              <th style={{ padding: '8px 10px', textAlign: 'left', fontSize: 10, color: 'var(--t3)', fontWeight: 600, textTransform: 'uppercase' }}>Date</th>
              <th style={{ padding: '8px 10px', textAlign: 'left', fontSize: 10, color: 'var(--t3)', fontWeight: 600, textTransform: 'uppercase' }}>Installer</th>
              <th style={{ padding: '8px 10px', textAlign: 'right', fontSize: 10, color: 'var(--t3)', fontWeight: 600, textTransform: 'uppercase' }}>Jobs</th>
              <th style={{ padding: '8px 10px', textAlign: 'right', fontSize: 10, color: 'var(--t3)', fontWeight: 600, textTransform: 'uppercase' }}>Revenue</th>
              <th style={{ padding: '8px 10px', textAlign: 'left', fontSize: 10, color: 'var(--t3)', fontWeight: 600, textTransform: 'uppercase' }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const rev = Number(r.day_revenue);
              const statusColor = rev >= TARGET ? 'var(--mint)' : rev >= 5000 ? 'var(--amber)' : 'var(--fire)';
              const statusText = rev >= TARGET ? 'At target' : rev >= 5000 ? 'Near target' : rev > 0 ? 'Under target' : '$0 VIOLATION';
              return (
                <tr key={`${r.work_date}-${r.technician_name}-${i}`} style={{ borderBottom: '1px solid var(--t5)' }}>
                  <td style={{ padding: '6px 10px', fontFamily: 'var(--mono)', fontSize: 11 }}>{fmtDate(r.work_date)}</td>
                  <td style={{ padding: '6px 10px' }}>{r.technician_name}</td>
                  <td style={{ padding: '6px 10px', textAlign: 'right' }}>{r.jobs}</td>
                  <td style={{ padding: '6px 10px', textAlign: 'right', fontFamily: 'var(--mono)', fontWeight: 600, color: statusColor }}>{$(rev)}</td>
                  <td style={{ padding: '6px 10px' }}>
                    <span style={{ fontSize: 10, fontWeight: 600, color: statusColor }}>{statusText}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
