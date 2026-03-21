import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/supabase';

export const revalidate = 60;

export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const from = url.searchParams.get('from') || '2026-01-01';
  const to = url.searchParams.get('to') || '2026-12-31';

  try {
    // 1. Every individual install-BU job with all drill-down fields
    const jobs = await query(`
      SELECT j.st_job_id, j.job_number, j.status,
        c.name as customer_name,
        i.business_unit_name,
        round(sum(i.sub_total)::numeric, 2) as revenue,
        a.start_time::date as work_date,
        aa.technician_name,
        j.raw_data->>'projectId' as project_id,
        LEFT(j.summary, 120) as scope
      FROM spartan_ops.st_jobs_v2 j
      JOIN spartan_ops.st_customers_v2 c ON j.st_customer_id = c.st_customer_id
      JOIN spartan_ops.st_invoices_v2 i ON j.st_job_id = i.st_job_id
      JOIN spartan_ops.st_appointments_v2 a ON j.st_job_id = a.st_job_id
      JOIN (
        SELECT DISTINCT ON (st_job_id) st_job_id, technician_name
        FROM spartan_ops.st_appointment_assignments_v2
        ORDER BY st_job_id, assigned_on
      ) aa ON j.st_job_id = aa.st_job_id
      WHERE (i.business_unit_name LIKE '%Replacement%' OR i.business_unit_name LIKE '%Whole House%')
        AND a.start_time >= '${from}' AND a.start_time < '${to}'
      GROUP BY j.st_job_id, j.job_number, j.status, c.name, i.business_unit_name,
        a.start_time::date, aa.technician_name, j.raw_data->>'projectId', j.summary
      ORDER BY a.start_time::date DESC, aa.technician_name, j.st_job_id
    `);

    // 2. Lead installer utilization
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

    // 3. Project context for violations
    const projectJobs = await query(`
      SELECT j.st_job_id, j.job_number, j.status,
        j.raw_data->>'projectId' as project_id,
        round(i.sub_total::numeric, 2) as revenue,
        a.start_time::date as work_date,
        i.business_unit_name
      FROM spartan_ops.st_jobs_v2 j
      JOIN spartan_ops.st_invoices_v2 i ON j.st_job_id = i.st_job_id
      JOIN spartan_ops.st_appointments_v2 a ON j.st_job_id = a.st_job_id
      WHERE j.raw_data->>'projectId' IN (
        SELECT DISTINCT j2.raw_data->>'projectId'
        FROM spartan_ops.st_jobs_v2 j2
        JOIN spartan_ops.st_invoices_v2 i2 ON j2.st_job_id = i2.st_job_id
        JOIN spartan_ops.st_appointments_v2 a2 ON j2.st_job_id = a2.st_job_id
        WHERE (i2.business_unit_name LIKE '%Replacement%' OR i2.business_unit_name LIKE '%Whole House%')
          AND i2.sub_total = 0
          AND a2.start_time >= '${from}' AND a2.start_time < '${to}'
          AND j2.raw_data->>'projectId' IS NOT NULL
      )
      ORDER BY j.raw_data->>'projectId', a.start_time::date
    `);

    return NextResponse.json({ jobs, utilization, projectJobs });
  } catch (err) {
    console.error('Analytics API error:', err);
    return NextResponse.json(
      { error: 'Failed to fetch analytics', detail: String(err) },
      { status: 500 }
    );
  }
}
