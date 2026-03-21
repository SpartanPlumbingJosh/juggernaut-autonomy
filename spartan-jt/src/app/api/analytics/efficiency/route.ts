import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/supabase';

export const revalidate = 60;

export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const from = url.searchParams.get('from') || '2026-01-01';
  const to = url.searchParams.get('to') || '2026-12-31';

  try {
    // 1. Daily revenue per tech (install BU only)
    const dailyRevenue = await query(`
      WITH daily AS (
        SELECT aa.technician_name, a.start_time::date as work_date,
          count(DISTINCT j.st_job_id) as jobs,
          round(sum(i.sub_total)::numeric, 2) as day_revenue
        FROM spartan_ops.st_jobs_v2 j
        JOIN spartan_ops.st_invoices_v2 i ON j.st_job_id = i.st_job_id
        JOIN spartan_ops.st_appointments_v2 a ON j.st_job_id = a.st_job_id
        JOIN (
          SELECT DISTINCT ON (st_job_id) st_job_id, technician_name
          FROM spartan_ops.st_appointment_assignments_v2
          ORDER BY st_job_id, assigned_on
        ) aa ON j.st_job_id = aa.st_job_id
        WHERE (i.business_unit_name LIKE '%Replacement%' OR i.business_unit_name LIKE '%Whole House%')
          AND a.start_time >= '${from}' AND a.start_time < '${to}'
        GROUP BY aa.technician_name, a.start_time::date
      )
      SELECT * FROM daily ORDER BY work_date DESC, technician_name
    `);

    // 2. Tech summary stats
    const techSummary = await query(`
      WITH daily AS (
        SELECT aa.technician_name, a.start_time::date as work_date,
          round(sum(i.sub_total)::numeric, 2) as day_revenue
        FROM spartan_ops.st_jobs_v2 j
        JOIN spartan_ops.st_invoices_v2 i ON j.st_job_id = i.st_job_id
        JOIN spartan_ops.st_appointments_v2 a ON j.st_job_id = a.st_job_id
        JOIN (
          SELECT DISTINCT ON (st_job_id) st_job_id, technician_name
          FROM spartan_ops.st_appointment_assignments_v2
          ORDER BY st_job_id, assigned_on
        ) aa ON j.st_job_id = aa.st_job_id
        WHERE (i.business_unit_name LIKE '%Replacement%' OR i.business_unit_name LIKE '%Whole House%')
          AND a.start_time >= '${from}' AND a.start_time < '${to}'
          AND i.sub_total > 0
        GROUP BY aa.technician_name, a.start_time::date
      )
      SELECT technician_name,
        count(*) as crew_days,
        round(avg(day_revenue)::numeric, 0) as avg_daily,
        round(min(day_revenue)::numeric, 0) as min_day,
        round(max(day_revenue)::numeric, 0) as max_day,
        round(sum(day_revenue)::numeric, 0) as total_rev,
        count(*) FILTER (WHERE day_revenue >= 8824) as at_target,
        count(*) FILTER (WHERE day_revenue >= 5000 AND day_revenue < 8824) as near_target,
        count(*) FILTER (WHERE day_revenue < 5000) as critical,
        round(100.0 * count(*) FILTER (WHERE day_revenue >= 8824) / NULLIF(count(*), 0), 1) as hit_pct,
        round(sum(GREATEST(8824 - day_revenue, 0))::numeric, 0) as gap_to_target
      FROM daily
      GROUP BY technician_name
      HAVING count(*) >= 2
      ORDER BY total_rev DESC
    `);

    // 3. Chunking violations ($0 install jobs)
    const chunkingViolations = await query(`
      SELECT j.st_job_id, j.status,
        i.business_unit_name,
        a.start_time::date as work_date,
        aa.technician_name,
        j.raw_data->>'projectId' as project_id,
        LEFT(j.summary, 80) as summary
      FROM spartan_ops.st_jobs_v2 j
      JOIN spartan_ops.st_invoices_v2 i ON j.st_job_id = i.st_job_id
      JOIN spartan_ops.st_appointments_v2 a ON j.st_job_id = a.st_job_id
      JOIN (
        SELECT DISTINCT ON (st_job_id) st_job_id, technician_name
        FROM spartan_ops.st_appointment_assignments_v2
        ORDER BY st_job_id, assigned_on
      ) aa ON j.st_job_id = aa.st_job_id
      WHERE (i.business_unit_name LIKE '%Replacement%' OR i.business_unit_name LIKE '%Whole House%')
        AND i.sub_total = 0
        AND a.start_time >= '${from}' AND a.start_time < '${to}'
      ORDER BY a.start_time DESC
    `);

    // 4. Overall summary
    const summary = await query(`
      WITH daily AS (
        SELECT aa.technician_name, a.start_time::date as work_date,
          round(sum(i.sub_total)::numeric, 2) as day_revenue
        FROM spartan_ops.st_jobs_v2 j
        JOIN spartan_ops.st_invoices_v2 i ON j.st_job_id = i.st_job_id
        JOIN spartan_ops.st_appointments_v2 a ON j.st_job_id = a.st_job_id
        JOIN (
          SELECT DISTINCT ON (st_job_id) st_job_id, technician_name
          FROM spartan_ops.st_appointment_assignments_v2
          ORDER BY st_job_id, assigned_on
        ) aa ON j.st_job_id = aa.st_job_id
        WHERE (i.business_unit_name LIKE '%Replacement%' OR i.business_unit_name LIKE '%Whole House%')
          AND a.start_time >= '${from}' AND a.start_time < '${to}'
        GROUP BY aa.technician_name, a.start_time::date
      )
      SELECT
        count(*) as total_crew_days,
        round(sum(day_revenue)::numeric, 0) as actual_revenue,
        round(count(*) * 8824.0, 0) as target_revenue,
        round(count(*) * 8824.0 - sum(day_revenue)::numeric, 0) as total_gap,
        round(avg(day_revenue)::numeric, 0) as avg_per_day,
        round(100.0 * sum(day_revenue)::numeric / NULLIF(count(*) * 8824.0, 0), 1) as efficiency_pct,
        count(*) FILTER (WHERE day_revenue >= 8824) as at_target,
        count(*) FILTER (WHERE day_revenue >= 5000 AND day_revenue < 8824) as near_target,
        count(*) FILTER (WHERE day_revenue < 5000 AND day_revenue > 0) as under_target,
        count(*) FILTER (WHERE day_revenue = 0) as zero_days
      FROM daily
    `);

    // 5. Monthly trend
    const monthlyTrend = await query(`
      WITH daily AS (
        SELECT aa.technician_name, a.start_time::date as work_date,
          round(sum(i.sub_total)::numeric, 2) as day_revenue
        FROM spartan_ops.st_jobs_v2 j
        JOIN spartan_ops.st_invoices_v2 i ON j.st_job_id = i.st_job_id
        JOIN spartan_ops.st_appointments_v2 a ON j.st_job_id = a.st_job_id
        JOIN (
          SELECT DISTINCT ON (st_job_id) st_job_id, technician_name
          FROM spartan_ops.st_appointment_assignments_v2
          ORDER BY st_job_id, assigned_on
        ) aa ON j.st_job_id = aa.st_job_id
        WHERE (i.business_unit_name LIKE '%Replacement%' OR i.business_unit_name LIKE '%Whole House%')
          AND a.start_time >= '${from}' AND a.start_time < '${to}'
        GROUP BY aa.technician_name, a.start_time::date
      )
      SELECT date_trunc('month', work_date)::date as month,
        count(*) as crew_days,
        round(avg(day_revenue)::numeric, 0) as avg_daily,
        round(sum(day_revenue)::numeric, 0) as total_rev,
        count(*) FILTER (WHERE day_revenue >= 8824) as at_target,
        count(*) FILTER (WHERE day_revenue = 0) as zero_days,
        round(100.0 * sum(day_revenue)::numeric / NULLIF(count(*) * 8824.0, 0), 1) as efficiency_pct
      FROM daily
      GROUP BY 1 ORDER BY 1
    `);

    // 6. Lead installer utilization (Kade + Isaac)
    const utilization = await query(`
      WITH workdays AS (
        SELECT d::date as work_date
        FROM generate_series('${from}'::date, LEAST('${to}'::date, CURRENT_DATE), '1 day') d
        WHERE EXTRACT(dow FROM d) BETWEEN 1 AND 5
      ),
      install_days AS (
        SELECT DISTINCT a.start_time::date as work_date, aa.technician_name
        FROM spartan_ops.st_appointments_v2 a
        JOIN spartan_ops.st_appointment_assignments_v2 aa ON a.st_appointment_id = aa.st_appointment_id
        JOIN spartan_ops.st_invoices_v2 i ON a.st_job_id = i.st_job_id
        WHERE (i.business_unit_name LIKE '%Replacement%' OR i.business_unit_name LIKE '%Whole House%')
          AND aa.technician_name IN ('Kade Lawson', 'Isaac Elam')
          AND a.start_time >= '${from}'
      )
      SELECT t.tech,
        count(*) as weekdays_available,
        count(id.work_date) as install_days,
        count(*) - count(id.work_date) as idle_weekdays,
        round(100.0 * count(id.work_date) / NULLIF(count(*), 0), 1) as utilization_pct
      FROM (VALUES ('Kade Lawson'), ('Isaac Elam')) t(tech)
      CROSS JOIN workdays w
      LEFT JOIN install_days id ON w.work_date = id.work_date AND id.technician_name = t.tech
      GROUP BY t.tech
    `);

    return NextResponse.json({
      dailyRevenue,
      techSummary,
      chunkingViolations,
      summary: summary[0] || {},
      monthlyTrend,
      utilization,
    });
  } catch (err) {
    console.error('Analytics API error:', err);
    return NextResponse.json(
      { error: 'Failed to fetch analytics', detail: String(err) },
      { status: 500 }
    );
  }
}
