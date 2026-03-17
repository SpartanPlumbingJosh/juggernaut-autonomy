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
    // Primary lookup: st_jobs_v2 joined with customer + location
    const jobs = await query(`
      SELECT j.st_job_id, j.job_number, j.status, j.summary,
             j.total, j.business_unit_name, j.job_type_name,
             j.completed_on, j.created_on, j.recall_for_id,
             c.name as customer_name,
             CONCAT(l.address_street, ', ', l.address_city, ', ', l.address_state, ' ', l.address_zip) as customer_address
      FROM spartan_ops.st_jobs_v2 j
      LEFT JOIN spartan_ops.st_customers_v2 c ON c.st_customer_id = j.st_customer_id
      LEFT JOIN spartan_ops.st_locations_v2 l ON l.st_location_id = j.st_location_id
      WHERE j.st_job_id = ${jobNumber}
      LIMIT 1
    `);

    if (jobs.length === 0) {
      return NextResponse.json({ error: 'Job not found' }, { status: 404 });
    }

    const job = jobs[0] as Record<string, unknown>;

    // Related jobs at same location
    const relatedJobs = await query(`
      SELECT j.st_job_id, j.job_number, j.status, j.summary,
             j.total, j.business_unit_name, j.job_type_name,
             j.completed_on, j.created_on
      FROM spartan_ops.st_jobs_v2 j
      WHERE j.st_location_id = (
        SELECT st_location_id FROM spartan_ops.st_jobs_v2 WHERE st_job_id = ${jobNumber}
      )
      AND j.st_job_id != ${jobNumber}
      ORDER BY j.created_on DESC
      LIMIT 20
    `);

    // Verifications
    const verifications = await query(`
      SELECT verification_name, result, checked_at
      FROM spartan_ops.job_verifications
      WHERE job_id = ${jobNumber}
      ORDER BY checked_at DESC
      LIMIT 54
    `);

    // Appointments
    const appointments = await query(`
      SELECT st_appointment_id, status, start_time, end_time
      FROM spartan_ops.st_appointments_v2
      WHERE st_job_id = ${jobNumber}
      ORDER BY start_time DESC
      LIMIT 5
    `);

    // Invoices
    const invoices = await query(`
      SELECT st_invoice_id, reference_number, summary, sub_total, sales_tax, total, balance, invoice_date, items
      FROM spartan_ops.st_invoices_v2
      WHERE st_job_id = ${jobNumber}
      ORDER BY created_on DESC
      LIMIT 10
    `);

    // Payments (via invoices)
    const payments = await query(`
      SELECT p.st_payment_id, p.payment_date, p.total, p.payment_type, p.memo
      FROM spartan_ops.st_payments_v2 p
      WHERE p.applied_to::text LIKE '%${jobNumber}%'
      ORDER BY p.payment_date DESC
      LIMIT 10
    `);

    return NextResponse.json({
      job,
      relatedJobs,
      verifications,
      appointments,
      invoices,
      payments,
    });
  } catch (err) {
    console.error('Job API error:', err);
    return NextResponse.json(
      { error: 'Failed to fetch job data', detail: String(err) },
      { status: 500 }
    );
  }
}