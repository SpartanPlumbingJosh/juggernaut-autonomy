import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/supabase';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ jobNumber: string }> }
) {
  const { jobNumber } = await params;

  if (!/^\d+$/.test(jobNumber)) {
    return NextResponse.json({ error: 'Invalid job number' }, { status: 400 });
  }

  try {
    const deployments = await query(`
      SELECT jd.*, j.status as job_status, j.sold_amount, j.scope_summary,
             j.customer_address, j.completed_on, j.created_on as job_created,
             j.business_unit_name, j.job_type_name
      FROM spartan_ops.jt_deployments jd
      LEFT JOIN spartan_ops.jobs j ON j.st_job_number = jd.st_job_number
      WHERE jd.st_job_number = '${jobNumber}'
      LIMIT 1
    `);

    if (deployments.length === 0) {
      const jobs = await query(`
        SELECT st_job_number, st_job_id, status, sold_amount, scope_summary,
               customer_name, customer_address, business_unit_name, job_type_name,
               completed_on, created_on, track_type
        FROM spartan_ops.jobs
        WHERE st_job_number = '${jobNumber}'
        LIMIT 1
      `);
      if (jobs.length === 0) {
        return NextResponse.json({ error: 'Job not found' }, { status: 404 });
      }
      return NextResponse.json({ job: jobs[0], deployment: null, relatedJobs: [], verifications: [] });
    }

    const deployment = deployments[0] as Record<string, unknown>;

    const relatedJobs = await query(`
      SELECT jd.st_job_number, jd.job_type_category, jd.job_type_name,
             jd.customer_name, jd.jt_status, jd.created_at,
             j.status as job_status, j.sold_amount, j.scope_summary
      FROM spartan_ops.jt_deployments jd
      LEFT JOIN spartan_ops.jobs j ON j.st_job_number = jd.st_job_number
      WHERE jd.channel_id = '${deployment.channel_id}'
      ORDER BY jd.created_at
    `);

    const verifications = await query(`
      SELECT verification_name, result, ai_confidence, checked_at
      FROM spartan_ops.job_verifications
      WHERE job_id = (SELECT id FROM spartan_ops.jobs WHERE st_job_number = '${jobNumber}' LIMIT 1)
      ORDER BY checked_at DESC
      LIMIT 54
    `);

    const appointments = await query(`
      SELECT sa.st_appointment_id, sa.status, sa.start_time, sa.end_time
      FROM spartan_ops.st_appointments sa
      JOIN spartan_ops.jobs j ON j.st_job_id = sa.st_job_id::text
      WHERE j.st_job_number = '${jobNumber}'
      ORDER BY sa.start_time DESC
      LIMIT 5
    `);

    const invoices = await query(`
      SELECT si.st_invoice_id, si.number as invoice_number, si.status, 
             si.subtotal, si.tax, si.total
      FROM spartan_ops.st_invoices si
      WHERE si.st_job_id = (SELECT st_job_id::bigint FROM spartan_ops.jobs WHERE st_job_number = '${jobNumber}' LIMIT 1)
      ORDER BY si.created_on DESC
      LIMIT 10
    `);

    return NextResponse.json({
      deployment,
      job: deployment,
      relatedJobs,
      verifications,
      appointments,
      invoices,
    });
  } catch (err) {
    console.error('Job API error:', err);
    return NextResponse.json(
      { error: 'Failed to fetch job data', detail: String(err) },
      { status: 500 }
    );
  }
}