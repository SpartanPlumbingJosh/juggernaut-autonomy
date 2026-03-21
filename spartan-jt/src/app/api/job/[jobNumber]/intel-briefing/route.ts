import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/supabase';

const OPENROUTER_KEY = process.env.OPENROUTER_API_KEY || '';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ jobNumber: string }> }
) {
  const { jobNumber } = await params;

  if (!/^\d+$/.test(jobNumber)) {
    return NextResponse.json({ error: 'Invalid job number' }, { status: 400 });
  }

  if (!OPENROUTER_KEY) {
    return NextResponse.json({ error: 'OpenRouter API key not configured' }, { status: 500 });
  }

  try {
    // Gather all context for the briefing
    const [jobRows, relatedRows, estimateRows, verificationRows, callRows, recallRows, contactRows] = await Promise.all([
      query(`
        SELECT j.st_job_id, j.job_number, j.status, j.summary, j.total,
               COALESCE(j.business_unit_name, bu.name) as business_unit_name,
               COALESCE(j.job_type_name, jt.name) as job_type_name,
               j.completed_on, j.created_on,
               c.name as customer_name,
               CONCAT(l.address_street, ', ', l.address_city, ', ', l.address_state, ' ', l.address_zip) as customer_address
        FROM spartan_ops.st_jobs_v2 j
        LEFT JOIN spartan_ops.st_customers_v2 c ON c.st_customer_id = j.st_customer_id
        LEFT JOIN spartan_ops.st_locations_v2 l ON l.st_location_id = j.st_location_id
        LEFT JOIN spartan_ops.st_business_units bu ON bu.st_bu_id = j.st_business_unit_id
        LEFT JOIN spartan_ops.st_job_types jt ON jt.st_job_type_id = j.st_job_type_id
        WHERE j.st_job_id = ${jobNumber}
        LIMIT 1
      `),
      query(`
        SELECT j.st_job_id, j.status, j.summary, j.total,
               COALESCE(j.business_unit_name, bu.name) as business_unit_name,
               j.created_on, j.recall_for_id
        FROM spartan_ops.st_jobs_v2 j
        LEFT JOIN spartan_ops.st_business_units bu ON bu.st_bu_id = j.st_business_unit_id
        WHERE j.st_location_id = (
          SELECT st_location_id FROM spartan_ops.st_jobs_v2 WHERE st_job_id = ${jobNumber}
        )
        AND j.st_job_id != ${jobNumber}
        ORDER BY j.created_on DESC LIMIT 15
      `),
      query(`
        SELECT e.st_estimate_id, e.status_name, e.summary, e.subtotal, e.created_on
        FROM spartan_ops.st_estimates_v2 e
        JOIN spartan_ops.st_jobs_v2 j ON j.st_job_id = e.st_job_id
        WHERE j.st_location_id = (
          SELECT st_location_id FROM spartan_ops.st_jobs_v2 WHERE st_job_id = ${jobNumber}
        )
        AND e.status_name NOT IN ('Sold', 'Dismissed')
        AND e.is_active = true
        ORDER BY e.created_on DESC LIMIT 10
      `),
      query(`
        SELECT verification_name, result
        FROM spartan_ops.job_verifications
        WHERE job_id = ${jobNumber}
        ORDER BY checked_at DESC LIMIT 30
      `),
      query(`
        SELECT direction, duration_seconds, call_type, created_on
        FROM spartan_ops.st_calls
        WHERE st_job_id = ${jobNumber}
        ORDER BY created_on DESC LIMIT 10
      `),
      query(`
        SELECT j.st_job_id, j.summary, j.created_on
        FROM spartan_ops.st_jobs_v2 j
        WHERE j.st_location_id = (
          SELECT st_location_id FROM spartan_ops.st_jobs_v2 WHERE st_job_id = ${jobNumber}
        )
        AND j.recall_for_id IS NOT NULL
        ORDER BY j.created_on DESC LIMIT 5
      `),
      query(`
        SELECT type, value FROM spartan_ops.st_contacts
        WHERE st_customer_id = (
          SELECT st_customer_id FROM spartan_ops.st_jobs_v2 WHERE st_job_id = ${jobNumber}
        )
        AND is_active = true LIMIT 5
      `)
    ]);

    if (jobRows.length === 0) {
      return NextResponse.json({ error: 'Job not found' }, { status: 404 });
    }

    const job = jobRows[0] as Record<string, any>;
    const related = relatedRows as Record<string, any>[];
    const unsold = estimateRows as Record<string, any>[];
    const verifications = verificationRows as Record<string, any>[];
    const calls = callRows as Record<string, any>[];
    const recalls = recallRows as Record<string, any>[];
    const contacts = contactRows as Record<string, any>[];

    const totalSpent = related.reduce((s, r) => s + (parseFloat(r.total) || 0), 0) + (parseFloat(job.total) || 0);
    const recallCount = recalls.length;
    const passCount = verifications.filter(v => v.result === 'pass').length;
    const failCount = verifications.filter(v => v.result === 'fail').length;
    const unsoldTotal = unsold.reduce((s, e) => s + (parseFloat(e.subtotal) || 0), 0);

    const contextPrompt = `You are an AI briefing assistant for Spartan Plumbing (Dayton, OH). Generate a concise pre-dispatch briefing for a technician heading to this job. Be direct and actionable — no fluff.

JOB DETAILS:
- Job #${job.st_job_id} | ${job.job_type_name || 'Unknown type'} | ${job.business_unit_name || 'Unknown BU'}
- Status: ${job.status} | Amount: $${parseFloat(job.total) || 0}
- Description: ${job.summary || 'No description'}
- Customer: ${job.customer_name || 'Unknown'} at ${job.customer_address || 'Unknown address'}

CUSTOMER HISTORY:
- ${related.length + 1} total jobs at this location | Lifetime spend: $${Math.round(totalSpent)}
- ${recallCount} recalls at this address${recallCount > 0 ? ' — WATCH OUT' : ''}
- ${unsold.length} unsold estimates totaling $${Math.round(unsoldTotal)}${unsold.length > 0 ? ' — upsell opportunity' : ''}
- Contact methods: ${contacts.map(c => c.type).join(', ') || 'None on file'}

VERIFICATION STATUS:
- ${passCount} checks passed, ${failCount} checks failed out of ${verifications.length} total

CALL HISTORY:
- ${calls.length} calls on this job${calls.filter(c => (c.duration_seconds || 0) > 60).length > 0 ? `, ${calls.filter(c => (c.duration_seconds || 0) > 60).length} substantive (>60s)` : ''}

Respond with ONLY a JSON object (no markdown, no backticks):
{
  "summary": "2-3 sentence overview of the situation",
  "risk_flags": ["array of specific risk factors or concerns"],
  "upsell_opportunities": ["array of specific upsell angles based on unsold estimates and history"],
  "approach_tips": ["array of 2-3 actionable tips for the tech"],
  "customer_sentiment": "positive | neutral | cautious | negative",
  "priority_level": "routine | attention | high_priority"
}`;

    const aiRes = await fetch('https://openrouter.ai/api/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${OPENROUTER_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'google/gemini-2.0-flash-001',
        max_tokens: 800,
        messages: [{ role: 'user', content: contextPrompt }],
      }),
    });

    if (!aiRes.ok) {
      const errText = await aiRes.text();
      console.error('OpenRouter error:', errText);
      return NextResponse.json({ error: 'AI service error', detail: errText }, { status: 502 });
    }

    const aiData = await aiRes.json();
    let briefingText = aiData.choices?.[0]?.message?.content || '';
    briefingText = briefingText.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();

    let briefing;
    try {
      briefing = JSON.parse(briefingText);
    } catch {
      briefing = {
        summary: briefingText.substring(0, 300),
        risk_flags: [],
        upsell_opportunities: [],
        approach_tips: [],
        customer_sentiment: 'neutral',
        priority_level: 'routine',
        parse_error: true
      };
    }

    return NextResponse.json({
      briefing,
      context: {
        total_jobs: related.length + 1,
        lifetime_spend: Math.round(totalSpent),
        recall_count: recallCount,
        unsold_estimate_count: unsold.length,
        unsold_total: Math.round(unsoldTotal),
        verification_pass: passCount,
        verification_fail: failCount,
      },
      generated_at: new Date().toISOString(),
    });

  } catch (err) {
    console.error('Intel briefing error:', err);
    return NextResponse.json({ error: 'Failed to generate briefing', detail: String(err) }, { status: 500 });
  }
}
