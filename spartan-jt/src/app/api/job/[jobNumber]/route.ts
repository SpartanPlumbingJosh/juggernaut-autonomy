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

    const verifications = await query(`
      SELECT verification_name, result, checked_at
      FROM spartan_ops.job_verifications
      WHERE job_id = ${jobNumber}
      ORDER BY checked_at DESC
      LIMIT 54
    `);

    const appointments = await query(`
      SELECT st_appointment_id, appointment_number, status, start_time, end_time,
             arrival_window_start, arrival_window_end, special_instructions
      FROM spartan_ops.st_appointments_v2
      WHERE st_job_id = ${jobNumber}
      ORDER BY start_time DESC
      LIMIT 10
    `);

    const invoices = await query(`
      SELECT st_invoice_id, reference_number, summary, sub_total, sales_tax, total, balance, invoice_date, items
      FROM spartan_ops.st_invoices_v2
      WHERE st_job_id = ${jobNumber}
      ORDER BY created_on DESC
      LIMIT 10
    `);

    const payments = await query(`
      SELECT p.st_payment_id, p.payment_date, p.total, p.payment_type, p.memo
      FROM spartan_ops.st_payments_v2 p
      WHERE p.applied_to::text LIKE '%${jobNumber}%'
      ORDER BY p.payment_date DESC
      LIMIT 10
    `);

    const estimates = await query(`
      SELECT st_estimate_id, estimate_name, status_name, review_status, summary,
             sold_on, sold_by_name, subtotal, tax, items, is_active, created_on
      FROM spartan_ops.st_estimates_v2
      WHERE st_job_id = ${jobNumber}
      ORDER BY created_on DESC
      LIMIT 10
    `);

    const assignments = await query(`
      SELECT a.st_assignment_id, a.st_appointment_id, a.st_tech_id, a.technician_name,
             a.status, a.is_paused, a.assigned_on
      FROM spartan_ops.st_appointment_assignments_v2 a
      WHERE a.st_job_id = ${jobNumber}
      ORDER BY a.assigned_on DESC
      LIMIT 20
    `);

    // AI-generated Lee Supply material list
    const materialListRows = await query(`
      SELECT material_list_json, sold_amount, form_confirmed, confirmed_at,
             generated_at, ai_model, sold_by, track_type
      FROM spartan_ops.auto_sales_forms
      WHERE st_job_id = '${jobNumber}'
      ORDER BY generated_at DESC
      LIMIT 1
    `);
    const materialList = materialListRows.length > 0 ? materialListRows[0] : null;

    // Fetch catalog images for Lee Supply items
    let catalogImages: Record<string, string> = {};
    if (materialList && (materialList as any).material_list_json) {
      const mlJson = (materialList as any).material_list_json;
      const leeNums: string[] = [];
      for (const section of ['parts', 'tools', 'consumables']) {
        const items = (mlJson as any)[section] || [];
        for (const item of items) {
          if (item.lee_number) leeNums.push(item.lee_number);
        }
      }
      if (leeNums.length > 0) {
        const inList = leeNums.map(n => `'${n}'`).join(',');
        const imgRows = await query(`
          SELECT item_number, image_url
          FROM spartan_ops.lee_supply_catalog
          WHERE item_number IN (${inList}) AND image_url IS NOT NULL AND image_url != ''
        `);
        for (const row of imgRows) {
          catalogImages[(row as any).item_number] = (row as any).image_url;
        }
      }
    }

    return NextResponse.json({
      job,
      relatedJobs,
      verifications,
      appointments,
      invoices,
      payments,
      estimates,
      assignments,
      materialList,
      catalogImages,
    });
  } catch (err) {
    console.error('Job API error:', err);
    return NextResponse.json(
      { error: 'Failed to fetch job data', detail: String(err) },
      { status: 500 }
    );
  }
}