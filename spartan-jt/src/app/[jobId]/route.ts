import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/supabase';
import { buildJTHtml } from '@/lib/jt-html';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ jobId: string }> }
) {
  const { jobId } = await params;

  if (!/^\d+$/.test(jobId)) {
    return new NextResponse(errorHtml('Invalid job ID', 'Use a numeric ServiceTitan job ID'), {
      status: 400,
      headers: { 'Content-Type': 'text/html; charset=utf-8' },
    });
  }

  try {
    const jobRows = await query(`
      SELECT j.*, bu.name as bu_display_name, bu.track_type, jt.name as jt_display_name
      FROM spartan_ops.st_jobs_v2 j
      LEFT JOIN spartan_ops.st_business_units bu ON bu.st_bu_id = j.st_business_unit_id
      LEFT JOIN spartan_ops.st_job_types jt ON jt.st_job_type_id = j.st_job_type_id
      WHERE j.st_job_id = ${jobId}
    `);
    if (!jobRows.length) {
      return new NextResponse(errorHtml('Job Not Found', `Job ID ${jobId} does not exist in ServiceTitan.`), {
        status: 404,
        headers: { 'Content-Type': 'text/html; charset=utf-8' },
      });
    }
    const job = jobRows[0] as Record<string, any>;

    const customer = (await query(`SELECT * FROM spartan_ops.st_customers_v2 WHERE st_customer_id = ${job.st_customer_id}`))[0] || null;
    const location = (await query(`SELECT * FROM spartan_ops.st_locations_v2 WHERE st_location_id = ${job.st_location_id}`))[0] || null;
    const contacts = await query(`SELECT type, value, memo, is_active FROM spartan_ops.st_contacts WHERE st_customer_id = ${job.st_customer_id} AND is_active = true ORDER BY type`);

    const locationJobs = await query(`
      SELECT j.st_job_id, j.job_number, j.status, j.summary, j.total, j.created_on, j.completed_on,
        j.recall_for_id, bu.name as bu_name, bu.track_type, jt.name as job_type_name
      FROM spartan_ops.st_jobs_v2 j
      LEFT JOIN spartan_ops.st_business_units bu ON bu.st_bu_id = j.st_business_unit_id
      LEFT JOIN spartan_ops.st_job_types jt ON jt.st_job_type_id = j.st_job_type_id
      WHERE j.st_location_id = ${job.st_location_id}
      ORDER BY j.created_on DESC LIMIT 50
    `);

    const estimates = await query(`
      SELECT st_estimate_id, st_job_id, estimate_name, status_name, summary,
        subtotal, tax, items, sold_on, sold_by_name, created_on, job_number
      FROM spartan_ops.st_estimates_v2
      WHERE st_customer_id = ${job.st_customer_id}
      ORDER BY created_on DESC LIMIT 30
    `);

    const jobInvoices = await query(`
      SELECT st_invoice_id, st_job_id, st_job_number, invoice_date, due_date,
        sub_total, sales_tax, total, balance, invoice_type, items, paid_on, created_on, summary
      FROM spartan_ops.st_invoices_v2 WHERE st_job_id = ${jobId} ORDER BY created_on DESC
    `);

    const payments = await query(`
      SELECT st_payment_id, payment_date, total, payment_type, memo,
        auth_code, check_number, applied_to, created_on
      FROM spartan_ops.st_payments_v2 WHERE st_customer_id = ${job.st_customer_id}
      ORDER BY payment_date DESC LIMIT 30
    `);

    const appointments = await query(`
      SELECT st_appointment_id, start_time, end_time,
        arrival_window_start, arrival_window_end, status, special_instructions
      FROM spartan_ops.st_appointments_v2 WHERE st_job_id = ${jobId} ORDER BY start_time ASC
    `);

    const assignments = await query(`
      SELECT st_assignment_id, st_appointment_id, technician_name, status, assigned_on
      FROM spartan_ops.st_appointment_assignments_v2 WHERE st_job_id = ${jobId} ORDER BY assigned_on ASC
    `);

    const calls = await query(`
      SELECT st_call_id, created_on, duration, duration_seconds,
        from_number, to_number, direction, status, call_type,
        recording_url, st_job_id, job_number, agent_name, reason_name
      FROM spartan_ops.st_calls WHERE st_customer_id = '${job.st_customer_id}'
      ORDER BY created_on DESC LIMIT 30
    `);

    const verificationDefs = await query(`
      SELECT verification_code, verification_name, phase, stage,
        is_hard_gate, applies_to_track, input_source, sort_order
      FROM spartan_ops.verification_definitions
      WHERE is_active = true ORDER BY sort_order
    `);

    const recallJobs = await query(`
      SELECT st_job_id, job_number, status, summary, total, created_on, completed_on
      FROM spartan_ops.st_jobs_v2 WHERE recall_for_id = ${jobId}
      ORDER BY created_on DESC
    `);

    // Aggregates
    const lifetimeSpend = (locationJobs as any[]).reduce((s: number, j: any) => s + (parseFloat(j.total) || 0), 0);
    const jobTotal = parseFloat(job.total as string) || 0;
    const totalInvoiced = (jobInvoices as any[]).reduce((s: number, i: any) => s + (parseFloat(i.total) || 0), 0);

    // ── Payment matching ────────────────────────────────────
    // Pass 1: Match via applied_to array (standard ST linkage)
    let totalPaid = 0;
    const matchedPaymentIds = new Set<string>();
    for (const p of payments as any[]) {
      let applied = p.applied_to;
      if (!applied) continue;
      if (typeof applied === 'string') { try { applied = JSON.parse(applied); } catch { continue; } }
      if (!Array.isArray(applied)) continue;
      for (const a of applied) {
        const invId = a.appliedTo || a.invoiceId;
        if ((jobInvoices as any[]).some((ji: any) => String(ji.st_invoice_id) === String(invId))) {
          totalPaid += parseFloat(a.appliedAmount) || 0;
          matchedPaymentIds.add(String(p.st_payment_id));
        }
      }
    }

    // Pass 2: Fallback for payments with empty applied_to arrays
    // Only runs when Pass 1 found nothing AND this job has invoices
    if (totalPaid === 0 && (jobInvoices as any[]).length > 0) {
      const jobCreated = new Date(job.created_on as string);
      const jobCompleted = job.completed_on ? new Date(job.completed_on as string) : new Date();
      const bufferMs = 7 * 24 * 60 * 60 * 1000; // 7 day buffer
      const rangeStart = new Date(jobCreated.getTime() - bufferMs);
      const rangeEnd = new Date(jobCompleted.getTime() + bufferMs);

      for (const p of payments as any[]) {
        if (matchedPaymentIds.has(String(p.st_payment_id))) continue;
        let applied = p.applied_to;
        if (typeof applied === 'string') { try { applied = JSON.parse(applied); } catch { applied = null; } }
        const isEmpty = !applied || (Array.isArray(applied) && applied.length === 0);
        if (!isEmpty) continue;

        const payDate = new Date(p.payment_date as string);
        if (payDate >= rangeStart && payDate <= rangeEnd) {
          totalPaid += parseFloat(p.total as string) || 0;
          matchedPaymentIds.add(String(p.st_payment_id));
        }
      }
    }
    // ── End payment matching ─────────────────────────────────

    let materialCost = 0;
    const materialItems: any[] = [];
    const serviceItems: any[] = [];
    for (const inv of jobInvoices as any[]) {
      let items = inv.items;
      if (!items) continue;
      if (typeof items === 'string') { try { items = JSON.parse(items); } catch { continue; } }
      if (!Array.isArray(items)) continue;
      for (const item of items) {
        if (item.type === 'Material' || item.type === 'Equipment') {
          materialCost += parseFloat(item.totalCost || item.cost || 0);
          materialItems.push(item);
        } else if (item.type === 'Service') {
          serviceItems.push(item);
        }
      }
    }

    function stripRaw(obj: any): any {
      if (!obj || typeof obj !== 'object') return obj;
      if (Array.isArray(obj)) return obj.map(stripRaw);
      const out: Record<string, any> = {};
      for (const [k, v] of Object.entries(obj)) {
        if (k === 'raw_data' || k === 'external_data' || k === 'custom_fields' || k === 'tag_type_ids') continue;
        out[k] = stripRaw(v);
      }
      return out;
    }

    // Compute job lifecycle stage
    const status = job.status as string;
    let lifecycleStage = 0;
    if (status === 'Completed') lifecycleStage = 5;
    else if (status === 'InProgress') lifecycleStage = 4;
    else if ((appointments as any[]).length > 0) lifecycleStage = 3;
    else if ((estimates as any[]).filter((e: any) => e.status_name === 'Sold').length > 0) lifecycleStage = 2;
    else if (jobTotal > 0) lifecycleStage = 1;

    // Compute blockers
    const blockers: any[] = [];
    const track = (job.track_type as string) || 'unknown';
    if (track === 'install') {
      if (totalPaid < jobTotal * 0.4 && jobTotal > 0) blockers.push({title:'40% Deposit Not Collected',severity:'high',owner:'Production'});
      if (!(assignments as any[]).length && lifecycleStage < 5) blockers.push({title:'No Crew Assigned',severity:'medium',owner:'Production'});
      if (materialItems.length === 0 && lifecycleStage >= 2 && lifecycleStage < 5) blockers.push({title:'No Material Items on Invoice',severity:'low',owner:'Production'});
    }
    if (!(jobInvoices as any[]).length && lifecycleStage >= 4) blockers.push({title:'No Invoice Created',severity:'high',owner:'Office'});
    if (jobTotal > 3000 && lifecycleStage < 5) blockers.push({title:'3-Day Cancel Notice Required (>$3K)',severity:'medium',owner:'Sales'});

    const data = stripRaw({
      job: { ...job, bu_display_name: job.bu_display_name, track_type: job.track_type, jt_display_name: job.jt_display_name },
      customer, location, contacts, locationJobs, estimates,
      jobInvoices, payments, appointments, assignments, calls,
      verificationDefs, recallJobs, materialItems, serviceItems, blockers,
      summary: {
        lifetimeSpend: lifetimeSpend.toFixed(2),
        jobCount: locationJobs.length,
        firstJob: locationJobs.length ? (locationJobs as any[])[locationJobs.length - 1].created_on : null,
        jobTotal: jobTotal.toFixed(2),
        totalInvoiced: totalInvoiced.toFixed(2),
        totalPaid: totalPaid.toFixed(2),
        materialCost: materialCost.toFixed(2),
        materialPct: jobTotal > 0 ? ((materialCost / jobTotal) * 100).toFixed(1) : '0.0',
        depositTarget: (jobTotal * 0.40).toFixed(2),
        depositMet: totalPaid >= (jobTotal * 0.40),
        lifecycleStage,
        track,
        materialItemCount: materialItems.length,
        serviceItemCount: serviceItems.length,
        blockerCount: blockers.length,
        recallCount: recallJobs.length,
        isRecall: !!job.recall_for_id,
      },
    });

    const html = buildJTHtml(data);

    return new NextResponse(html, {
      status: 200,
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
      },
    });
  } catch (err) {
    console.error('JT render error:', err);
    return new NextResponse(errorHtml('Server Error', String(err)), {
      status: 500,
      headers: { 'Content-Type': 'text/html; charset=utf-8' },
    });
  }
}

function errorHtml(title: string, desc: string): string {
  return `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Spartan JT</title></head>
<body style="background:#050609;color:#f0f2f8;font-family:'Outfit',system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0">
<div style="text-align:center"><h1 style="color:#ff2d46;font-size:28px;margin-bottom:12px">${title}</h1><p style="color:#7e85a0;font-size:14px">${desc}</p></div></body></html>`;
}