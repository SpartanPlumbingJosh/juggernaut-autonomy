import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/supabase';

const OPENROUTER_KEY = process.env.OPENROUTER_API_KEY || '';
const SLACK_BOT_TOKEN = process.env.SLACK_BOT_TOKEN || '';

function stripHtml(html: string | null | undefined): string {
  if (!html) return '';
  return html
    .replace(/<br\s*\/?>/gi, ' ')
    .replace(/<\/div>/gi, ' ')
    .replace(/<\/p>/gi, ' ')
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    .replace(/\s{2,}/g, ' ')
    .trim();
}

function fmtDate(d: string | null | undefined): string {
  if (!d) return 'N/A';
  try {
    return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch { return d; }
}

async function fetchSlackMessages(channelId: string, limit = 200): Promise<any[]> {
  if (!SLACK_BOT_TOKEN) return [];
  try {
    const res = await fetch(`https://slack.com/api/conversations.history?channel=${channelId}&limit=${limit}`, {
      headers: { 'Authorization': `Bearer ${SLACK_BOT_TOKEN}` },
    });
    const data = await res.json();
    if (!data.ok) return [];
    return (data.messages || []).filter((m: any) => m.type === 'message' && m.text && !m.subtype?.includes('channel_join'));
  } catch { return []; }
}

async function fetchSlackUserNames(userIds: string[]): Promise<Record<string, string>> {
  if (!SLACK_BOT_TOKEN || userIds.length === 0) return {};
  const names: Record<string, string> = {};
  const unique = [...new Set(userIds)].slice(0, 15);
  await Promise.all(unique.map(async (uid) => {
    try {
      const res = await fetch(`https://slack.com/api/users.info?user=${uid}`, {
        headers: { 'Authorization': `Bearer ${SLACK_BOT_TOKEN}` },
      });
      const data = await res.json();
      if (data.ok && data.user) {
        names[uid] = data.user.real_name || data.user.profile?.display_name || data.user.name || uid;
      }
    } catch { /* skip */ }
  }));
  return names;
}

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
    const [jobRows, relatedRows, estimateRows, verificationRows, callRows, recallRows, contactRows] = await Promise.all([
      query(`
        SELECT j.st_job_id, j.job_number, j.status, j.summary, j.total,
               COALESCE(j.business_unit_name, bu.name) as business_unit_name,
               COALESCE(j.job_type_name, jt.name) as job_type_name,
               j.completed_on, j.created_on, j.st_customer_id, j.st_location_id,
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
        SELECT j.st_job_id, j.job_number, j.status, j.summary, j.total,
               COALESCE(j.business_unit_name, bu.name) as business_unit_name,
               COALESCE(j.job_type_name, jt.name) as job_type_name,
               j.created_on, j.completed_on, j.recall_for_id
        FROM spartan_ops.st_jobs_v2 j
        LEFT JOIN spartan_ops.st_business_units bu ON bu.st_bu_id = j.st_business_unit_id
        LEFT JOIN spartan_ops.st_job_types jt ON jt.st_job_type_id = j.st_job_type_id
        WHERE j.st_location_id = (
          SELECT st_location_id FROM spartan_ops.st_jobs_v2 WHERE st_job_id = ${jobNumber}
        )
        AND j.st_job_id != ${jobNumber}
        ORDER BY j.created_on DESC LIMIT 15
      `),
      query(`
        SELECT e.st_estimate_id, e.status_name, e.summary, e.estimate_name, e.subtotal, e.created_on, e.st_job_id
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

    // Find Slack channels
    const channelRows = await query(`
      SELECT DISTINCT channel_id, channel_name
      FROM spartan_ops.bookmark_tracked_channels
      WHERE channel_name LIKE '%' || LOWER(SPLIT_PART('${(job.customer_name || '').replace(/'/g, "''")}', ' ', 2)) || '%'
      AND channel_name LIKE '%' || LOWER(SPLIT_PART('${(job.customer_name || '').replace(/'/g, "''")}', ' ', 1)) || '%'
      LIMIT 5
    `) as Record<string, any>[];

    const jtChannelRows = await query(`
      SELECT channel_id, channel_name FROM spartan_ops.jt_deployments
      WHERE st_job_id = ${jobNumber}
      LIMIT 1
    `) as Record<string, any>[];

    const allChannels = new Map<string, string>();
    for (const ch of [...channelRows, ...jtChannelRows]) {
      if (ch.channel_id) allChannels.set(ch.channel_id, ch.channel_name);
    }

    // Pull LIVE Slack messages
    let allMessages: { channel: string; user: string; text: string; ts: string }[] = [];
    
    for (const [chId, chName] of allChannels) {
      const msgs = await fetchSlackMessages(chId, 150);
      for (const m of msgs) {
        allMessages.push({
          channel: chName,
          user: m.user || 'bot',
          text: (m.text || '').substring(0, 500),
          ts: m.ts,
        });
      }
    }

    // Also check knowledge_lake
    if (allChannels.size > 0) {
      const channelIds = [...allChannels.keys()].map(id => `'${id}'`).join(',');
      const klMessages = await query(`
        SELECT channel_name, user_name, message_text, message_date
        FROM knowledge_lake.slack_raw_messages
        WHERE channel_id IN (${channelIds})
        AND message_text IS NOT NULL AND message_text != ''
        AND (message_subtype IS NULL OR message_subtype NOT IN ('channel_join', 'channel_leave'))
        ORDER BY message_date DESC LIMIT 100
      `) as Record<string, any>[];
      
      for (const m of klMessages) {
        if (!allMessages.some(am => am.text === m.message_text)) {
          allMessages.push({
            channel: m.channel_name,
            user: m.user_name || 'unknown',
            text: (m.message_text || '').substring(0, 500),
            ts: m.message_date,
          });
        }
      }
    }

    allMessages.sort((a, b) => (b.ts || '').localeCompare(a.ts || ''));
    allMessages = allMessages.slice(0, 150);

    // Resolve user names
    const userIds = [...new Set(allMessages.filter(m => m.user && m.user.startsWith('U')).map(m => m.user))];
    const userNames = await fetchSlackUserNames(userIds);

    const formattedMessages = allMessages.map(m => {
      const name = userNames[m.user] || m.user;
      const date = m.ts?.includes('T') ? m.ts.substring(0, 10) : 
        m.ts && parseFloat(m.ts) ? new Date(parseFloat(m.ts) * 1000).toISOString().substring(0, 10) : '';
      return `[${date}] ${name}: ${m.text}`;
    }).join('\n');

    // Build STRUCTURED data with clear labels and HTML stripped
    const totalSpent = related.reduce((s, r) => s + (parseFloat(r.total) || 0), 0) + (parseFloat(job.total) || 0);
    const recallCount = recalls.length;
    const passCount = verifications.filter(v => v.result === 'pass').length;
    const failCount = verifications.filter(v => v.result === 'fail').length;
    const unsoldTotal = unsold.reduce((s, e) => s + (parseFloat(e.subtotal) || 0), 0);

    // Format each related job with EXPLICIT field labels
    const relatedSummary = related.map((r, i) => 
      `  JOB ${i + 1}:
    Job #: ${r.st_job_id}
    Business Unit: ${r.business_unit_name || 'Unknown'}
    Job Type: ${r.job_type_name || 'Unknown'}
    Status: ${r.status}
    Amount: $${parseFloat(r.total) || 0}
    Created: ${fmtDate(r.created_on)}
    Completed: ${fmtDate(r.completed_on)}
    Is Recall: ${r.recall_for_id ? 'YES — recall for job #' + r.recall_for_id : 'No'}
    ST Notes: ${stripHtml(r.summary) || 'None'}`
    ).join('\n\n');

    const unsoldSummary = unsold.map((e, i) =>
      `  ESTIMATE ${i + 1}:
    Estimate #: ${e.st_estimate_id}
    Name: ${e.estimate_name || 'No name'}
    Description: ${stripHtml(e.summary) || 'None'}
    Amount: $${parseFloat(e.subtotal) || 0}
    Status: ${e.status_name}
    Created: ${fmtDate(e.created_on)}
    On Job #: ${e.st_job_id}`
    ).join('\n\n');

    const contextPrompt = `You are the intelligence briefing system for Spartan Plumbing (Dayton, OH).

CRITICAL ACCURACY RULES — FOLLOW THESE OR THE BRIEFING IS WORTHLESS:
1. ONLY state facts that appear in the data below. Do NOT infer, assume, or fill in gaps.
2. When referencing a job, use its EXACT Business Unit name and Job Type — do NOT rename or paraphrase them.
3. Use EXACT dollar amounts from the data. Do not round unless the source is rounded.
4. Use EXACT dates from the data. "Completed: Mar 19, 2026" means it was completed March 19 — not March 18.
5. If something was discussed in Slack but is not in the structured ST data, attribute it clearly: "Per Slack discussion, ..." or "The channel mentions..."
6. NEVER conflate two different jobs. Each job has its own BU, type, amount, and dates. Keep them separate.
7. If you're not sure about something, leave it out. A shorter accurate briefing beats a longer wrong one.

===== TODAY'S JOB (THE ONE BEING DISPATCHED) =====
Job #: ${job.st_job_id}
Business Unit: ${job.business_unit_name || 'Unknown'}
Job Type: ${job.job_type_name || 'Unknown'}
Status: ${job.status}
Amount: $${parseFloat(job.total) || 0}
ST Notes: ${stripHtml(job.summary) || 'No description'}
Customer: ${job.customer_name || 'Unknown'}
Address: ${job.customer_address || 'Unknown'}
Created: ${fmtDate(job.created_on)}
Completed: ${fmtDate(job.completed_on)}

===== PREVIOUS JOBS AT THIS ADDRESS (${related.length} jobs, $${Math.round(totalSpent)} total lifetime revenue) =====
${relatedSummary || 'No previous jobs at this location'}

===== RECALLS AT THIS ADDRESS: ${recallCount} =====
${recallCount > 0 ? recalls.map(r => `  Job #${r.st_job_id}: ${stripHtml(r.summary) || 'No details'} (${fmtDate(r.created_on)})`).join('\n') : 'None'}

===== UNSOLD ESTIMATES AT THIS LOCATION (${unsold.length} estimates, $${Math.round(unsoldTotal)} total potential) =====
${unsoldSummary || 'None'}

===== SLACK CHANNEL CONVERSATIONS (${allMessages.length} messages from ${allChannels.size} channel(s)) =====
These are real messages from the customer's Slack job channel(s). They contain what was actually discussed, promised, discovered on-site, and decided.

${formattedMessages || 'No Slack messages available for this customer'}

===== CONTACT INFO =====
${contacts.map(c => `${c.type}: ${c.value}`).join('\n') || 'None on file'}

===== CALL HISTORY =====
${calls.length} calls on this job${calls.filter(c => (c.duration_seconds || 0) > 60).length > 0 ? `, ${calls.filter(c => (c.duration_seconds || 0) > 60).length} substantive (>60s)` : ''}

===== VERIFICATION: ${passCount} passed, ${failCount} failed of ${verifications.length} checks =====

===== WHAT TO WRITE =====
Write a briefing for someone heading to this job. Include:
- What this job actually is (use the EXACT BU name and job type from the data)
- Key facts from previous jobs (using correct BU names, dates, and amounts)
- Who the customer is and any special relationship details (from ST notes or Slack)
- What Slack conversations reveal: scope details, promises, issues discovered, customer preferences, access info
- Specific upsell angles tied to the real unsold estimates by name and dollar amount
- Real risk flags based on actual data (recalls, scope creep evidence, scheduling issues from channel)

DO NOT:
- Rename business units or job types (if the BU says "Replacement Water Filtration" don't call it "bathtub repair")
- State dates that aren't in the data
- Make up details not present in the Slack messages or ST data
- Give generic advice like "confirm scope" or "build rapport" — those are obvious and useless

Respond with ONLY a JSON object (no markdown, no backticks):
{
  "summary": "4-6 sentence briefing using ONLY facts from the data above",
  "risk_flags": ["specific risks with evidence from the data"],
  "upsell_opportunities": ["tied to specific unsold estimate names and amounts"],
  "approach_tips": ["2-3 tips based on specific details from Slack conversations or ST notes"],
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
        model: 'anthropic/claude-sonnet-4',
        max_tokens: 1500,
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
        summary: briefingText.substring(0, 500),
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
        slack_channels: allChannels.size,
        slack_messages: allMessages.length,
      },
      generated_at: new Date().toISOString(),
    });

  } catch (err) {
    console.error('Intel briefing error:', err);
    return NextResponse.json({ error: 'Failed to generate briefing', detail: String(err) }, { status: 500 });
  }
}
