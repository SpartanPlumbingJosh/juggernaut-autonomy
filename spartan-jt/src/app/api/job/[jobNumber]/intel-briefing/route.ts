import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/supabase';

const OPENROUTER_KEY = process.env.OPENROUTER_API_KEY || '';
const SLACK_BOT_TOKEN = process.env.SLACK_BOT_TOKEN || '';

function stripHtml(html: string | null | undefined): string {
  if (!html) return '';
  return html.replace(/<br\s*\/?>/gi, ' ').replace(/<\/div>/gi, ' ').replace(/<\/p>/gi, ' ').replace(/<[^>]+>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/\s{2,}/g, ' ').trim();
}
function fmtDate(d: string | null | undefined): string {
  if (!d) return 'N/A';
  try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); } catch { return d; }
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
      const res = await fetch(`https://slack.com/api/users.info?user=${uid}`, { headers: { 'Authorization': `Bearer ${SLACK_BOT_TOKEN}` } });
      const data = await res.json();
      if (data.ok && data.user) names[uid] = data.user.real_name || data.user.profile?.display_name || data.user.name || uid;
    } catch { /* skip */ }
  }));
  return names;
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ jobNumber: string }> }
) {
  const { jobNumber } = await params;
  if (!/^\d+$/.test(jobNumber)) return NextResponse.json({ error: 'Invalid job number' }, { status: 400 });

  const refresh = request.nextUrl.searchParams.get('refresh') === 'true';

  // CHECK CACHE FIRST (unless ?refresh=true)
  if (!refresh) {
    try {
      const cached = await query(`
        SELECT briefing, context, generated_at FROM spartan_ops.job_briefings
        WHERE st_job_id = ${jobNumber} AND briefing_type = 'job' AND expires_at > now()
        ORDER BY generated_at DESC LIMIT 1
      `);
      if (cached.length > 0) {
        const row = cached[0] as Record<string, any>;
        return NextResponse.json({
          briefing: row.briefing,
          context: row.context,
          generated_at: row.generated_at,
          cached: true,
        });
      }
    } catch { /* cache miss, continue to generate */ }
  }

  if (!OPENROUTER_KEY) return NextResponse.json({ error: 'OpenRouter API key not configured' }, { status: 500 });

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
        WHERE j.st_job_id = ${jobNumber} LIMIT 1
      `),
      query(`
        SELECT j.st_job_id, j.job_number, j.status, j.summary, j.total,
               COALESCE(j.business_unit_name, bu.name) as business_unit_name,
               COALESCE(j.job_type_name, jt.name) as job_type_name,
               j.created_on, j.completed_on, j.recall_for_id
        FROM spartan_ops.st_jobs_v2 j
        LEFT JOIN spartan_ops.st_business_units bu ON bu.st_bu_id = j.st_business_unit_id
        LEFT JOIN spartan_ops.st_job_types jt ON jt.st_job_type_id = j.st_job_type_id
        WHERE j.st_location_id = (SELECT st_location_id FROM spartan_ops.st_jobs_v2 WHERE st_job_id = ${jobNumber})
        AND j.st_job_id != ${jobNumber}
        ORDER BY j.created_on DESC LIMIT 15
      `),
      query(`
        SELECT e.st_estimate_id, e.status_name, e.summary, e.estimate_name, e.subtotal, e.created_on, e.st_job_id
        FROM spartan_ops.st_estimates_v2 e
        JOIN spartan_ops.st_jobs_v2 j ON j.st_job_id = e.st_job_id
        WHERE j.st_location_id = (SELECT st_location_id FROM spartan_ops.st_jobs_v2 WHERE st_job_id = ${jobNumber})
        AND e.status_name NOT IN ('Sold', 'Dismissed') AND e.is_active = true
        ORDER BY e.created_on DESC LIMIT 10
      `),
      query(`SELECT verification_name, result FROM spartan_ops.job_verifications WHERE job_id = ${jobNumber} ORDER BY checked_at DESC LIMIT 30`),
      query(`SELECT direction, duration_seconds, call_type, created_on FROM spartan_ops.st_calls WHERE st_job_id = ${jobNumber} ORDER BY created_on DESC LIMIT 10`),
      query(`
        SELECT j.st_job_id, j.summary, j.created_on FROM spartan_ops.st_jobs_v2 j
        WHERE j.st_location_id = (SELECT st_location_id FROM spartan_ops.st_jobs_v2 WHERE st_job_id = ${jobNumber})
        AND j.recall_for_id IS NOT NULL ORDER BY j.created_on DESC LIMIT 5
      `),
      query(`
        SELECT type, value FROM spartan_ops.st_contacts
        WHERE st_customer_id = (SELECT st_customer_id FROM spartan_ops.st_jobs_v2 WHERE st_job_id = ${jobNumber})
        AND is_active = true LIMIT 5
      `)
    ]);

    if (jobRows.length === 0) return NextResponse.json({ error: 'Job not found' }, { status: 404 });

    const job = jobRows[0] as Record<string, any>;
    const related = relatedRows as Record<string, any>[];
    const unsold = estimateRows as Record<string, any>[];
    const verifications = verificationRows as Record<string, any>[];
    const calls = callRows as Record<string, any>[];
    const recalls = recallRows as Record<string, any>[];
    const contacts = contactRows as Record<string, any>[];

    // Slack channels
    const channelRows = await query(`
      SELECT DISTINCT channel_id, channel_name FROM spartan_ops.bookmark_tracked_channels
      WHERE channel_name LIKE '%' || LOWER(SPLIT_PART('${(job.customer_name || '').replace(/'/g, "''")}', ' ', 2)) || '%'
      AND channel_name LIKE '%' || LOWER(SPLIT_PART('${(job.customer_name || '').replace(/'/g, "''")}', ' ', 1)) || '%'
      LIMIT 5
    `) as Record<string, any>[];
    const jtChannelRows = await query(`SELECT channel_id, channel_name FROM spartan_ops.jt_deployments WHERE st_job_id = ${jobNumber} LIMIT 1`) as Record<string, any>[];

    const allChannels = new Map<string, string>();
    for (const ch of [...channelRows, ...jtChannelRows]) { if (ch.channel_id) allChannels.set(ch.channel_id, ch.channel_name); }

    let allMessages: { channel: string; user: string; text: string; ts: string }[] = [];
    for (const [chId, chName] of allChannels) {
      const msgs = await fetchSlackMessages(chId, 150);
      for (const m of msgs) allMessages.push({ channel: chName, user: m.user || 'bot', text: (m.text || '').substring(0, 500), ts: m.ts });
    }

    if (allChannels.size > 0) {
      const channelIds = [...allChannels.keys()].map(id => `'${id}'`).join(',');
      const klMessages = await query(`
        SELECT channel_name, user_name, message_text, message_date FROM knowledge_lake.slack_raw_messages
        WHERE channel_id IN (${channelIds}) AND message_text IS NOT NULL AND message_text != ''
        AND (message_subtype IS NULL OR message_subtype NOT IN ('channel_join', 'channel_leave'))
        ORDER BY message_date DESC LIMIT 100
      `) as Record<string, any>[];
      for (const m of klMessages) {
        if (!allMessages.some(am => am.text === m.message_text)) {
          allMessages.push({ channel: m.channel_name, user: m.user_name || 'unknown', text: (m.message_text || '').substring(0, 500), ts: m.message_date });
        }
      }
    }

    allMessages.sort((a, b) => (b.ts || '').localeCompare(a.ts || ''));
    allMessages = allMessages.slice(0, 150);

    const userIds = [...new Set(allMessages.filter(m => m.user && m.user.startsWith('U')).map(m => m.user))];
    const userNames = await fetchSlackUserNames(userIds);
    const formattedMessages = allMessages.map(m => {
      const name = userNames[m.user] || m.user;
      const date = m.ts?.includes('T') ? m.ts.substring(0, 10) : m.ts && parseFloat(m.ts) ? new Date(parseFloat(m.ts) * 1000).toISOString().substring(0, 10) : '';
      return `[${date}] ${name}: ${m.text}`;
    }).join('\n');

    const totalSpent = related.reduce((s, r) => s + (parseFloat(r.total) || 0), 0) + (parseFloat(job.total) || 0);
    const recallCount = recalls.length;
    const passCount = verifications.filter(v => v.result === 'pass').length;
    const failCount = verifications.filter(v => v.result === 'fail').length;
    const unsoldTotal = unsold.reduce((s, e) => s + (parseFloat(e.subtotal) || 0), 0);

    const relatedSummary = related.map((r, i) =>
      `  JOB ${i + 1}: #${r.st_job_id} | ${r.business_unit_name || 'Unknown'} | ${r.job_type_name || 'Unknown'} | ${r.status} | $${parseFloat(r.total) || 0} | ${fmtDate(r.created_on)}${r.recall_for_id ? ' | RECALL for #' + r.recall_for_id : ''}\n    Notes: ${stripHtml(r.summary) || 'None'}`
    ).join('\n');

    const unsoldSummary = unsold.map((e, i) =>
      `  EST ${i + 1}: #${e.st_estimate_id} | ${e.estimate_name || 'No name'} | $${parseFloat(e.subtotal) || 0} | ${e.status_name} | ${fmtDate(e.created_on)} | Job #${e.st_job_id}\n    Desc: ${stripHtml(e.summary) || 'None'}`
    ).join('\n');

    const contextPrompt = `You are the intelligence briefing system for Spartan Plumbing (Dayton, OH).

RULES: Only state facts from the data below. Use exact BU names, job types, dates, amounts. Never infer or make up details. Shorter accurate > longer wrong.

===== TODAY'S JOB =====
Job #${job.st_job_id} | ${job.business_unit_name || 'Unknown'} | ${job.job_type_name || 'Unknown'} | ${job.status} | $${parseFloat(job.total) || 0}
Customer: ${job.customer_name || 'Unknown'} | ${job.customer_address || 'Unknown'}
Notes: ${stripHtml(job.summary) || 'None'} | Created: ${fmtDate(job.created_on)} | Completed: ${fmtDate(job.completed_on)}

===== ${related.length} PREVIOUS JOBS ($${Math.round(totalSpent)} lifetime) =====
${relatedSummary || 'None'}

===== ${recallCount} RECALLS =====
${recallCount > 0 ? recalls.map(r => `  #${r.st_job_id}: ${stripHtml(r.summary) || 'No details'} (${fmtDate(r.created_on)})`).join('\n') : 'None'}

===== ${unsold.length} UNSOLD ESTIMATES ($${Math.round(unsoldTotal)} potential) =====
${unsoldSummary || 'None'}

===== SLACK (${allMessages.length} msgs, ${allChannels.size} channels) =====
${formattedMessages || 'No messages'}

===== CONTACTS =====
${contacts.map(c => `${c.type}: ${c.value}`).join('\n') || 'None'}

===== CALLS: ${calls.length} total, ${calls.filter(c => (c.duration_seconds || 0) > 60).length} substantive =====
===== VERIFICATION: ${passCount} pass, ${failCount} fail =====

Write a dispatch briefing. Respond ONLY with JSON (no markdown):
{
  "summary": "4-6 sentences, facts only from above data",
  "risk_flags": ["specific risks with evidence"],
  "upsell_opportunities": ["tied to specific unsold estimates by name and $"],
  "approach_tips": ["2-3 tips from Slack/ST data, not generic advice"],
  "customer_sentiment": "positive | neutral | cautious | negative",
  "priority_level": "routine | attention | high_priority"
}`;

    const aiRes = await fetch('https://openrouter.ai/api/v1/chat/completions', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${OPENROUTER_KEY}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: 'anthropic/claude-sonnet-4', max_tokens: 1500, messages: [{ role: 'user', content: contextPrompt }] }),
    });

    if (!aiRes.ok) {
      const errText = await aiRes.text();
      return NextResponse.json({ error: 'AI service error', detail: errText }, { status: 502 });
    }

    const aiData = await aiRes.json();
    let briefingText = aiData.choices?.[0]?.message?.content || '';
    briefingText = briefingText.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();

    let briefing;
    try { briefing = JSON.parse(briefingText); }
    catch { briefing = { summary: briefingText.substring(0, 500), risk_flags: [], upsell_opportunities: [], approach_tips: [], customer_sentiment: 'neutral', priority_level: 'routine', parse_error: true }; }

    const contextData = {
      total_jobs: related.length + 1, lifetime_spend: Math.round(totalSpent), recall_count: recallCount,
      unsold_estimate_count: unsold.length, unsold_total: Math.round(unsoldTotal),
      verification_pass: passCount, verification_fail: failCount,
      slack_channels: allChannels.size, slack_messages: allMessages.length,
    };

    // SAVE TO CACHE
    try {
      await query(`
        INSERT INTO spartan_ops.job_briefings (st_job_id, briefing_type, briefing, context, generated_at, expires_at)
        VALUES (${jobNumber}, 'job', '${JSON.stringify(briefing).replace(/'/g, "''")}', '${JSON.stringify(contextData).replace(/'/g, "''")}', now(), now() + interval '24 hours')
        ON CONFLICT (st_job_id, briefing_type) DO UPDATE SET briefing = EXCLUDED.briefing, context = EXCLUDED.context, generated_at = EXCLUDED.generated_at, expires_at = EXCLUDED.expires_at
      `);
    } catch (cacheErr) { console.error('Cache save error:', cacheErr); }

    return NextResponse.json({ briefing, context: contextData, generated_at: new Date().toISOString(), cached: false });

  } catch (err) {
    console.error('Intel briefing error:', err);
    return NextResponse.json({ error: 'Failed to generate briefing', detail: String(err) }, { status: 500 });
  }
}
