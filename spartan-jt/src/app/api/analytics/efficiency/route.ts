import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/supabase';

export const revalidate = 60;
const TARGET = 8824;

function sanitizeDate(d: string): string {
  return /^\d{4}-\d{2}-\d{2}$/.test(d) ? d : '2026-01-01';
}

export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const from = sanitizeDate(url.searchParams.get('from') || '2026-01-01');
  const to = sanitizeDate(url.searchParams.get('to') || '2026-12-31');

  try {
    // ── 1. Base: every install crew-day with job-level detail ──
    const rawJobs = await query<{
      st_job_id: string; job_number: string; status: string;
      customer_name: string; bu_name: string; revenue: string;
      work_date: string; technician_name: string; project_id: string | null;
      scope: string;
    }>(`
      WITH install_bus AS (
        SELECT st_bu_id FROM spartan_ops.st_business_units
        WHERE name ILIKE '%replacement%' OR name ILIKE '%whole house%'
      ),
      install_jobs AS (
        SELECT j.st_job_id, j.job_number, j.status, j.summary,
          j.st_customer_id, j.raw_data->>'projectId' as project_id
        FROM spartan_ops.st_jobs_v2 j
        WHERE j.st_business_unit_id IN (SELECT st_bu_id FROM install_bus)
      ),
      lead_tech AS (
        SELECT DISTINCT ON (aa.st_job_id) aa.st_job_id, aa.technician_name
        FROM spartan_ops.st_appointment_assignments_v2 aa
        WHERE aa.st_job_id IN (SELECT st_job_id FROM install_jobs)
        ORDER BY aa.st_job_id, aa.assigned_on
      ),
      job_revenue AS (
        SELECT st_job_id, round(sum(sub_total::numeric), 2) as revenue,
          min(business_unit_name) as bu_name
        FROM spartan_ops.st_invoices_v2
        WHERE st_job_id IN (SELECT st_job_id FROM install_jobs)
        GROUP BY st_job_id
      ),
      job_appt AS (
        SELECT st_job_id, min(start_time::date) as work_date
        FROM spartan_ops.st_appointments_v2
        WHERE st_job_id IN (SELECT st_job_id FROM install_jobs)
          AND status IN ('Dispatched','Done','Working')
        GROUP BY st_job_id
      )
      SELECT ij.st_job_id::text, ij.job_number, ij.status,
        c.name as customer_name,
        coalesce(jr.bu_name, '') as bu_name,
        coalesce(jr.revenue, 0) as revenue,
        ja.work_date::text,
        coalesce(lt.technician_name, 'Unassigned') as technician_name,
        ij.project_id,
        LEFT(ij.summary, 140) as scope
      FROM install_jobs ij
      JOIN job_appt ja ON ij.st_job_id = ja.st_job_id
      LEFT JOIN spartan_ops.st_customers_v2 c ON ij.st_customer_id = c.st_customer_id
      LEFT JOIN lead_tech lt ON ij.st_job_id = lt.st_job_id
      LEFT JOIN job_revenue jr ON ij.st_job_id = jr.st_job_id
      WHERE ja.work_date >= '${from}' AND ja.work_date < '${to}'
      ORDER BY ja.work_date DESC, lt.technician_name, ij.st_job_id
    `);

    // ── 2. Compute crew-day revenue (per tech per date) ──
    interface CrewDay {
      technician_name: string; work_date: string; jobs: number;
      day_revenue: number;
      job_details: { st_job_id: string; job_number: string; customer_name: string; bu_name: string; revenue: number; status: string; scope: string }[];
    }

    const crewDayMap = new Map<string, CrewDay>();
    for (const j of rawJobs) {
      const key = `${j.technician_name}|${j.work_date}`;
      const rev = Number(j.revenue) || 0;
      if (!crewDayMap.has(key)) {
        crewDayMap.set(key, { technician_name: j.technician_name, work_date: j.work_date, jobs: 0, day_revenue: 0, job_details: [] });
      }
      const cd = crewDayMap.get(key)!;
      cd.jobs++;
      cd.day_revenue += rev;
      cd.job_details.push({ st_job_id: j.st_job_id, job_number: j.job_number, customer_name: j.customer_name, bu_name: j.bu_name, revenue: rev, status: j.status, scope: j.scope });
    }

    const crewDays = Array.from(crewDayMap.values());

    // ── 3. Summary stats ──
    const totalCrewDays = crewDays.length;
    const actualRevenue = crewDays.reduce((s, d) => s + d.day_revenue, 0);
    const targetRevenue = totalCrewDays * TARGET;
    const totalGap = targetRevenue - actualRevenue;
    const avgPerDay = totalCrewDays > 0 ? Math.round(actualRevenue / totalCrewDays) : 0;
    const efficiencyPct = targetRevenue > 0 ? Math.round((actualRevenue / targetRevenue) * 1000) / 10 : 0;
    const atTarget = crewDays.filter(d => d.day_revenue >= TARGET).length;
    const nearTarget = crewDays.filter(d => d.day_revenue >= 5000 && d.day_revenue < TARGET).length;
    const underTarget = crewDays.filter(d => d.day_revenue > 0 && d.day_revenue < 5000).length;
    const zeroDays = crewDays.filter(d => d.day_revenue === 0).length;

    const summary = {
      total_crew_days: totalCrewDays, actual_revenue: Math.round(actualRevenue),
      target_revenue: targetRevenue, total_gap: Math.round(totalGap),
      avg_per_day: avgPerDay, efficiency_pct: efficiencyPct,
      at_target: atTarget, near_target: nearTarget,
      under_target: underTarget, zero_days: zeroDays,
    };

    // ── 4. Per-tech summary ──
    const techMap = new Map<string, CrewDay[]>();
    for (const cd of crewDays) {
      if (!techMap.has(cd.technician_name)) techMap.set(cd.technician_name, []);
      techMap.get(cd.technician_name)!.push(cd);
    }

    const techSummary = Array.from(techMap.entries()).map(([name, days]) => {
      const totalRev = days.reduce((s, d) => s + d.day_revenue, 0);
      const at = days.filter(d => d.day_revenue >= TARGET).length;
      const near = days.filter(d => d.day_revenue >= 5000 && d.day_revenue < TARGET).length;
      const crit = days.filter(d => d.day_revenue > 0 && d.day_revenue < 5000).length;
      const zeros = days.filter(d => d.day_revenue === 0).length;
      const revDays = days.filter(d => d.day_revenue > 0);
      return {
        technician_name: name, crew_days: days.length,
        avg_daily: days.length > 0 ? Math.round(totalRev / days.length) : 0,
        min_day: Math.round(revDays.length > 0 ? Math.min(...revDays.map(d => d.day_revenue)) : 0),
        max_day: Math.round(days.length > 0 ? Math.max(...days.map(d => d.day_revenue)) : 0),
        total_rev: Math.round(totalRev), at_target: at, near_target: near,
        critical: crit, zero_days: zeros,
        hit_pct: days.length > 0 ? Math.round((at / days.length) * 1000) / 10 : 0,
        gap_to_target: Math.round(days.length * TARGET - totalRev),
      };
    }).sort((a, b) => b.crew_days - a.crew_days);

    // ── 5. Daily revenue rows ──
    const dailyRevenue = crewDays.map(cd => ({
      technician_name: cd.technician_name, work_date: cd.work_date,
      jobs: cd.jobs, day_revenue: Math.round(cd.day_revenue), job_details: cd.job_details,
    })).sort((a, b) => b.work_date.localeCompare(a.work_date) || a.technician_name.localeCompare(b.technician_name));

    // ── 6. Monthly trend ──
    const monthMap = new Map<string, CrewDay[]>();
    for (const cd of crewDays) {
      const m = cd.work_date.slice(0, 7);
      if (!monthMap.has(m)) monthMap.set(m, []);
      monthMap.get(m)!.push(cd);
    }
    const monthlyTrend = Array.from(monthMap.entries()).map(([month, days]) => {
      const totalRev = days.reduce((s, d) => s + d.day_revenue, 0);
      const at = days.filter(d => d.day_revenue >= TARGET).length;
      const zeros = days.filter(d => d.day_revenue === 0).length;
      return {
        month, crew_days: days.length,
        avg_daily: days.length > 0 ? Math.round(totalRev / days.length) : 0,
        total_rev: Math.round(totalRev), at_target: at, zero_days: zeros,
        efficiency_pct: days.length > 0 ? Math.round((totalRev / (days.length * TARGET)) * 1000) / 10 : 0,
        zero_rev_potential: Math.round(zeros * TARGET),
      };
    }).sort((a, b) => a.month.localeCompare(b.month));

    // ── 7. $0 chunking violations ──
    const chunkingViolations = rawJobs.filter(j => Number(j.revenue) === 0).map(j => ({
      st_job_id: j.st_job_id, status: j.status, business_unit_name: j.bu_name,
      work_date: j.work_date, technician_name: j.technician_name,
      project_id: j.project_id, summary: j.scope || '', customer_name: j.customer_name,
    }));

    // ── 8. Lead installer utilization ──
    const utilization = await query(`
      WITH workdays AS (
        SELECT d::date as work_date FROM generate_series('${from}'::date, LEAST('${to}'::date, CURRENT_DATE), '1 day') d
        WHERE EXTRACT(dow FROM d) BETWEEN 1 AND 5
      ),
      install_bus AS (
        SELECT st_bu_id FROM spartan_ops.st_business_units WHERE name ILIKE '%replacement%' OR name ILIKE '%whole house%'
      ),
      install_days AS (
        SELECT DISTINCT a.start_time::date as work_date, aa.technician_name
        FROM spartan_ops.st_appointments_v2 a
        JOIN spartan_ops.st_appointment_assignments_v2 aa ON a.st_appointment_id = aa.st_appointment_id
        JOIN spartan_ops.st_jobs_v2 j ON a.st_job_id = j.st_job_id
        WHERE j.st_business_unit_id IN (SELECT st_bu_id FROM install_bus)
          AND aa.technician_name IN ('Kade Lawson', 'Isaac Elam')
          AND a.start_time >= '${from}' AND a.start_time < '${to}'
      )
      SELECT t.tech, count(*) as weekdays_available,
        count(id.work_date) as install_days,
        count(*) - count(id.work_date) as idle_weekdays,
        round(100.0 * count(id.work_date) / NULLIF(count(*), 0), 1) as utilization_pct
      FROM (VALUES ('Kade Lawson'), ('Isaac Elam')) t(tech)
      CROSS JOIN workdays w
      LEFT JOIN install_days id ON w.work_date = id.work_date AND id.technician_name = t.tech
      GROUP BY t.tech
    `);

    return NextResponse.json({ summary, techSummary, dailyRevenue, chunkingViolations, monthlyTrend, utilization });
  } catch (err) {
    console.error('Analytics API error:', err);
    return NextResponse.json({ error: 'Failed to fetch analytics', detail: String(err) }, { status: 500 });
  }
}
