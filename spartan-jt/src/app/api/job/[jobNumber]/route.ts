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
             j.total, COALESCE(j.business_unit_name, bu.name) as business_unit_name,
             COALESCE(j.job_type_name, jt.name) as job_type_name,
             j.completed_on, j.created_on, j.recall_for_id,
             j.st_customer_id, j.st_location_id,
             c.name as customer_name,
             CONCAT(l.address_street, ', ', l.address_city, ', ', l.address_state, ' ', l.address_zip) as customer_address
      FROM spartan_ops.st_jobs_v2 j
      LEFT JOIN spartan_ops.st_customers_v2 c ON c.st_customer_id = j.st_customer_id
      LEFT JOIN spartan_ops.st_locations_v2 l ON l.st_location_id = j.st_location_id
      LEFT JOIN spartan_ops.st_business_units bu ON bu.st_bu_id = j.st_business_unit_id
      LEFT JOIN spartan_ops.st_job_types jt ON jt.st_job_type_id = j.st_job_type_id
      WHERE j.st_job_id = ${jobNumber}
      LIMIT 1
    `);

    if (jobs.length === 0) {
      return NextResponse.json({ error: 'Job not found' }, { status: 404 });
    }

    const job = jobs[0] as Record<string, unknown>;

    const relatedJobs = await query(`
      SELECT j.st_job_id, j.job_number, j.status, j.summary,
             j.total, COALESCE(j.business_unit_name, bu.name) as business_unit_name,
             COALESCE(j.job_type_name, jt.name) as job_type_name,
             j.completed_on, j.created_on, j.recall_for_id
      FROM spartan_ops.st_jobs_v2 j
      LEFT JOIN spartan_ops.st_business_units bu ON bu.st_bu_id = j.st_business_unit_id
      LEFT JOIN spartan_ops.st_job_types jt ON jt.st_job_type_id = j.st_job_type_id
      WHERE j.st_location_id = (
        SELECT st_location_id FROM spartan_ops.st_jobs_v2 WHERE st_job_id = ${jobNumber}
      )
      AND j.st_job_id != ${jobNumber}
      ORDER BY j.created_on DESC
      LIMIT 20
    `);

    const verifications = await query(`
      SELECT verification_code, verification_name, result, checked_at
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

    const custId = (job as any).st_customer_id;
    const contacts = custId ? await query(`
      SELECT type, value, memo
      FROM spartan_ops.st_contacts
      WHERE st_customer_id = ${custId}
      AND is_active = true
      ORDER BY type
      LIMIT 10
    `) : [];

    const locId = (job as any).st_location_id;
    const unsoldEstimates = locId ? await query(`
      SELECT e.st_estimate_id, e.estimate_name, e.status_name, e.summary,
             e.subtotal, e.created_on, j.job_number, j.st_job_id
      FROM spartan_ops.st_estimates_v2 e
      JOIN spartan_ops.st_jobs_v2 j ON j.st_job_id = e.st_job_id
      WHERE j.st_location_id = ${locId}
      AND e.status_name NOT IN ('Sold', 'Dismissed')
      AND e.is_active = true
      ORDER BY e.created_on DESC
      LIMIT 10
    `) : [];

    const recallsAtLocation = locId ? await query(`
      SELECT j.st_job_id, j.job_number, j.status, j.summary, j.created_on,
             j.completed_on, j.recall_for_id
      FROM spartan_ops.st_jobs_v2 j
      WHERE j.st_location_id = ${locId}
      AND j.recall_for_id IS NOT NULL
      ORDER BY j.created_on DESC
      LIMIT 10
    `) : [];

    const calls = await query(`
      SELECT st_call_id, created_on, duration_seconds, from_number, to_number,
             direction, status, call_type, recording_url, customer_name
      FROM spartan_ops.st_calls
      WHERE st_job_id = ${jobNumber}
      ORDER BY created_on DESC
      LIMIT 50
    `);

    const recallJobs = await query(`
      SELECT st_job_id, job_number, status, summary, created_on, completed_on
      FROM spartan_ops.st_jobs_v2
      WHERE recall_for_id = ${jobNumber}
      ORDER BY created_on DESC
      LIMIT 10
    `);

    const callScripts = await query(`
      SELECT script_key, title, category, stage, template_text, personalization_fields
      FROM spartan_ops.call_scripts
      ORDER BY id
    `);

    const materialListRows = await query(`
      SELECT material_list_json, sold_amount, form_confirmed, confirmed_at,
             generated_at, ai_model, sold_by, track_type
      FROM spartan_ops.auto_sales_forms
      WHERE st_job_id = '${jobNumber}'
      ORDER BY generated_at DESC
      LIMIT 1
    `);
    const materialList = materialListRows.length > 0 ? materialListRows[0] : null;

    let catalogImages: Record<string, string> = {};
    if (materialList && (materialList as any).material_list_json) {
      const mlJson = (materialList as any).material_list_json;
      const leeNums: string[] = [];
      for (const section of ['parts', 'tools']) {
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

    const buName = String(job.business_unit_name || '').toLowerCase();
    const isDrain = buName.includes('drain');
    const playbookKey = isDrain ? 'drservice' : 'plservice';
    const salesPlaybookKey = isDrain ? 'drsales' : 'plsales';
    const phoneCloseKey = isDrain ? 'drphone' : 'plphone';

    const playbookSteps = await query(`
      SELECT playbook_key, step_number, quarter, title, description, verification_type, hard_gate
      FROM spartan_ops.playbook_definitions
      WHERE playbook_key IN ('${playbookKey}', '${salesPlaybookKey}', '${phoneCloseKey}', 'install')
      ORDER BY playbook_key, step_number
    `);

    const stepTracking = await query(`
      SELECT playbook_key, step_number, status, evidence_type, evidence_ref, verified_at, score, notes
      FROM spartan_ops.playbook_step_tracking
      WHERE st_job_id = ${jobNumber}
    `);

    const purchaseOrders = await query(`
      SELECT st_po_id, po_number, vendor_id, status, total, tax, po_date, items, summary, received_on
      FROM spartan_ops.st_purchase_orders_v2
      WHERE job_id = ${jobNumber}
      ORDER BY po_date DESC
      LIMIT 20
    `);

    const verificationDefs = await query(`
      SELECT verification_code, verification_name, phase, stage, is_hard_gate, applies_to_track, is_active, sort_order
      FROM spartan_ops.verification_definitions
      ORDER BY sort_order
    `);

    const companyAverages = await query(`
      SELECT verification_code, verification_name,
        round(100.0 * sum(case when result = 'pass' then 1 else 0 end) / count(*), 1) as pass_pct,
        count(*) as total_checks
      FROM spartan_ops.job_verifications
      GROUP BY verification_code, verification_name
    `);

    const permits = await query(`
      SELECT permit_type, status, filed_date, approved_date, expires_date,
             ai_verified, ai_notes, document_url, jurisdiction
      FROM spartan_ops.permit_documents
      WHERE st_job_id = ${jobNumber}
      ORDER BY created_at DESC
    `);

    const permitRules = locId ? await query(`
      SELECT pr.jurisdiction, pr.permit_type, pr.required, pr.confidence_level, pr.reviewed
      FROM spartan_ops.permit_rules pr
      WHERE pr.jurisdiction IN (
        SELECT COALESCE(l2.address_city, '') FROM spartan_ops.st_locations_v2 l2 WHERE l2.st_location_id = ${locId}
        UNION
        SELECT COALESCE(l2.address_zip, '') FROM spartan_ops.st_locations_v2 l2 WHERE l2.st_location_id = ${locId}
      )
      ORDER BY pr.jurisdiction, pr.permit_type
    `) : [];

    const cardRequests = await query(`
      SELECT id, requested_by, requested_by_name, requested_at, responded_by, responded_at, response_time_seconds,
             card_issued, receipt_posted, receipt_ai_pass, receipt_ai_notes,
             amount, mismatch_flagged, reconciled, vendor_name, purchase_description
      FROM spartan_ops.job_card_requests
      WHERE st_job_id = ${jobNumber}
      ORDER BY requested_at DESC
    `);

    const blockers = await query(`
      SELECT category, escalation_level, description, owner, auto_detected,
             source, impact_assessment, resolved_at, resolution_notes, created_at
      FROM spartan_ops.job_blockers
      WHERE st_job_id = ${jobNumber}
      ORDER BY resolved_at NULLS FIRST, created_at DESC
    `);

    const jobMedia = await query(`
      SELECT media_type, file_name, thumb_url, media_url as full_url, ai_classification,
             ai_confidence, matched_step_id, matched_playbook, posted_by, posted_at as created_at
      FROM spartan_ops.job_media
      WHERE st_job_id = ${jobNumber}
      ORDER BY posted_at DESC NULLS LAST
      LIMIT 50
    `);

    const projectRows = await query(`
      SELECT st_project_id, name, status, job_ids, contract_value,
             start_date, target_completion_date, actual_completion_date
      FROM spartan_ops.st_projects_v2
      WHERE job_ids::text LIKE '%${jobNumber}%'
      LIMIT 1
    `);
    const project = projectRows.length > 0 ? projectRows[0] : null;

    let projectSiblings: unknown[] = [];
    let projectContext: any = null;

    // Classify job role from BU/job type
    function classifyJobRole(bu: string, jt: string): string {
      const b = (bu || '').toLowerCase();
      const j = (jt || '').toLowerCase();
      if (b.includes('service sj') || j.includes('service (sj)') || j.includes('demand/service')) return 'sj';
      if (b.includes('sales') || j.includes('turnover') || j.includes('(to)')) return 'to';
      if (b.includes('replacement') || b.includes('whole house') || j.includes('install (prj)') || j.includes('install')) return 'install';
      if (b.includes('admin')) return 'admin';
      return 'service';
    }

    const currentJobRole = classifyJobRole(
      String(job.business_unit_name || ''),
      String(job.job_type_name || '')
    );

    if (project && (project as any).job_ids) {
      const sibIds = ((project as any).job_ids as number[]).filter((id: number) => String(id) !== jobNumber);
      if (sibIds.length > 0) {
        projectSiblings = await query(`
          SELECT j.st_job_id, j.job_number, j.status, j.total,
                 COALESCE(j.job_type_name, jt.name) as job_type_name,
                 COALESCE(j.business_unit_name, bu.name) as business_unit_name,
                 j.created_on, j.completed_on
          FROM spartan_ops.st_jobs_v2 j
          LEFT JOIN spartan_ops.st_business_units bu ON bu.st_bu_id = j.st_business_unit_id
          LEFT JOIN spartan_ops.st_job_types jt ON jt.st_job_type_id = j.st_job_type_id
          WHERE j.st_job_id IN (${sibIds.join(',')})
          ORDER BY j.created_on
        `);

        // Classify all project jobs
        const allProjectJobs = [
          { st_job_id: (job as any).st_job_id, business_unit_name: String(job.business_unit_name || ''), job_type_name: String(job.job_type_name || ''), total: (job as any).total, status: (job as any).status, created_on: (job as any).created_on },
          ...(projectSiblings as any[])
        ].map((j: any) => ({ ...j, role: classifyJobRole(j.business_unit_name || '', j.job_type_name || '') }));

        const sjJobs = allProjectJobs.filter(j => j.role === 'sj');
        const toJobs = allProjectJobs.filter(j => j.role === 'to');
        const installJobs = allProjectJobs.filter(j => j.role === 'install');
        const sjJob = sjJobs[0] || null;
        const toJob = toJobs[0] || null;
        const isInstallProject = installJobs.length > 0;
        const totalProjectRevenue = allProjectJobs.reduce((s, j) => s + (parseFloat(j.total) || 0), 0);

        // Pull cross-job data from SJ and TO siblings
        let sjTracking: unknown[] = [];
        let sjAppointments: unknown[] = [];
        let sjAssignments: unknown[] = [];
        let sjCalls: unknown[] = [];

        let sjVerifications: unknown[] = [];

        if (sjJob && String(sjJob.st_job_id) !== jobNumber) {
          [sjTracking, sjAppointments, sjAssignments, sjCalls, sjVerifications] = await Promise.all([
            query(`SELECT playbook_key, step_number, status, evidence_type, evidence_ref, verified_at, score, notes FROM spartan_ops.playbook_step_tracking WHERE st_job_id = ${sjJob.st_job_id}`),
            query(`SELECT st_appointment_id, appointment_number, status, start_time, end_time, arrival_window_start, arrival_window_end, special_instructions FROM spartan_ops.st_appointments_v2 WHERE st_job_id = ${sjJob.st_job_id} ORDER BY start_time DESC LIMIT 10`),
            query(`SELECT st_assignment_id, st_appointment_id, st_tech_id, technician_name, status, is_paused, assigned_on FROM spartan_ops.st_appointment_assignments_v2 WHERE st_job_id = ${sjJob.st_job_id} ORDER BY assigned_on DESC LIMIT 20`),
            query(`SELECT st_call_id, created_on, duration_seconds, direction, status, call_type, recording_url FROM spartan_ops.st_calls WHERE st_job_id = ${sjJob.st_job_id} ORDER BY created_on DESC LIMIT 20`),
            query(`SELECT verification_code, verification_name, result, checked_at FROM spartan_ops.job_verifications WHERE job_id = ${sjJob.st_job_id} ORDER BY checked_at DESC LIMIT 30`),
          ]);
        }

        let toTracking: unknown[] = [];
        let toEstimates: unknown[] = [];
        let toPayments: unknown[] = [];

        if (toJob && String(toJob.st_job_id) !== jobNumber) {
          [toTracking, toEstimates, toPayments] = await Promise.all([
            query(`SELECT playbook_key, step_number, status, evidence_type, evidence_ref, verified_at, score, notes FROM spartan_ops.playbook_step_tracking WHERE st_job_id = ${toJob.st_job_id}`),
            query(`SELECT st_estimate_id, estimate_name, status_name, review_status, summary, sold_on, sold_by_name, subtotal, tax, items, is_active, created_on FROM spartan_ops.st_estimates_v2 WHERE st_job_id = ${toJob.st_job_id} ORDER BY created_on DESC LIMIT 10`),
            query(`SELECT st_payment_id, payment_date, total, payment_type, memo FROM spartan_ops.st_payments_v2 WHERE applied_to::text LIKE '%${toJob.st_job_id}%' ORDER BY payment_date DESC LIMIT 10`),
          ]);
        }

        // Aggregate invoices/payments across all project jobs
        const allIds = allProjectJobs.map(j => j.st_job_id).join(',');
        const projectInvoices = await query(`
          SELECT st_invoice_id, st_job_id, reference_number, summary, sub_total, sales_tax, total, balance, invoice_date
          FROM spartan_ops.st_invoices_v2
          WHERE st_job_id IN (${allIds})
          ORDER BY created_on DESC LIMIT 30
        `);

        projectContext = {
          projectId: (project as any).st_project_id,
          currentJobRole,
          isInstallProject,
          allJobs: allProjectJobs,
          sjJob, toJob,
          sjTracking, sjAppointments, sjAssignments, sjCalls, sjVerifications,
          toTracking, toEstimates, toPayments,
          projectInvoices,
          totalProjectRevenue,
          installCount: installJobs.length,
          jobCount: allProjectJobs.length,
        };
      }
    }

    return NextResponse.json({
      job, relatedJobs, verifications, appointments, invoices, payments,
      estimates, assignments, contacts, unsoldEstimates, recallsAtLocation,
      calls, recallJobs, callScripts, materialList, catalogImages,
      purchaseOrders, verificationDefs, companyAverages,
      playbook: { serviceKey: playbookKey, salesKey: salesPlaybookKey, phoneCloseKey, steps: playbookSteps, tracking: stepTracking },
      permits, permitRules, cardRequests, blockers, jobMedia,
      project, projectSiblings, projectContext,
    });
  } catch (err) {
    console.error('Job API error:', err);
    return NextResponse.json(
      { error: 'Failed to fetch job data', detail: String(err) },
      { status: 500 }
    );
  }
}