import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/supabase';

const OPENROUTER_KEY = process.env.OPENROUTER_API_KEY || '';

const NOTIFICATION_MEMBERS = [
  'U06N32PKK8U', 'U06MN0CHE3G', 'U06NHDPGRA4', 'U07U4RCJX9B',
  'U06NAXE0M3S', 'U06N3S2B4GW', 'U06NKNW6CDT', 'U06NT7YQR6X'
];

function stripHtml(html: string | null | undefined): string {
  if (!html) return '';
  return html.replace(/<br\s*\/?>/gi, ' ').replace(/<\/div>/gi, ' ').replace(/<\/p>/gi, ' ').replace(/<[^>]+>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/\s{2,}/g, ' ').trim();
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ jobNumber: string }> }
) {
  const { jobNumber } = await params;
  if (!/^\d+$/.test(jobNumber)) return NextResponse.json({ error: 'Invalid job number' }, { status: 400 });

  try {
    const messages = await query(`
      SELECT id, role, message, user_id, user_name, created_at
      FROM spartan_ops.permit_chat
      WHERE st_job_id = ${jobNumber}
      ORDER BY created_at ASC
    `);
    return NextResponse.json({ messages });
  } catch (err) {
    return NextResponse.json({ error: 'Failed to load chat', detail: String(err) }, { status: 500 });
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ jobNumber: string }> }
) {
  const { jobNumber } = await params;
  if (!/^\d+$/.test(jobNumber)) return NextResponse.json({ error: 'Invalid job number' }, { status: 400 });

  const body = await request.json();
  const { message, userId, userName } = body;
  if (!message || !userId) return NextResponse.json({ error: 'Missing message or userId' }, { status: 400 });

  if (!NOTIFICATION_MEMBERS.includes(userId)) {
    return NextResponse.json({ error: 'Not authorized' }, { status: 403 });
  }

  if (!OPENROUTER_KEY) return NextResponse.json({ error: 'AI not configured' }, { status: 500 });

  try {
    await query(`
      INSERT INTO spartan_ops.permit_chat (st_job_id, role, message, user_id, user_name)
      VALUES (${jobNumber}, 'user', '${message.replace(/'/g, "''")}', '${userId}', '${(userName || '').replace(/'/g, "''")}')
    `);

    const [jobRows, packetRows, rulesRows, historyRows] = await Promise.all([
      query(`
        SELECT j.st_job_id, j.summary, j.status,
               COALESCE(j.business_unit_name, bu.name) as business_unit_name,
               COALESCE(j.job_type_name, jt.name) as job_type_name,
               c.name as customer_name,
               l.address_street, l.address_city, l.address_state, l.address_zip
        FROM spartan_ops.st_jobs_v2 j
        LEFT JOIN spartan_ops.st_customers_v2 c ON c.st_customer_id = j.st_customer_id
        LEFT JOIN spartan_ops.st_locations_v2 l ON l.st_location_id = j.st_location_id
        LEFT JOIN spartan_ops.st_business_units bu ON bu.st_bu_id = j.st_business_unit_id
        LEFT JOIN spartan_ops.st_job_types jt ON jt.st_job_type_id = j.st_job_type_id
        WHERE j.st_job_id = ${jobNumber} LIMIT 1
      `),
      query(`SELECT research, status, confidence FROM spartan_ops.permit_packets WHERE st_job_id = ${jobNumber} LIMIT 1`),
      query(`
        SELECT jurisdiction, permit_type, required, confidence_level, notes
        FROM spartan_ops.permit_rules
        WHERE jurisdiction IN (
          SELECT COALESCE(l.address_city, '') FROM spartan_ops.st_locations_v2 l
          JOIN spartan_ops.st_jobs_v2 j ON j.st_location_id = l.st_location_id
          WHERE j.st_job_id = ${jobNumber}
        )
        ORDER BY jurisdiction, permit_type
      `),
      query(`
        SELECT role, message, user_name, created_at
        FROM spartan_ops.permit_chat
        WHERE st_job_id = ${jobNumber}
        ORDER BY created_at ASC
        LIMIT 30
      `)
    ]);

    const job = jobRows[0] as Record<string, any> | undefined;
    const packet = packetRows[0] as Record<string, any> | undefined;
    const rules = rulesRows as Record<string, any>[];
    const history = historyRows as Record<string, any>[];

    const rulesContext = rules.length > 0
      ? rules.map(r => `${r.jurisdiction} | ${r.permit_type} | Required: ${r.required ? 'Yes' : 'No'} | Confidence: ${r.confidence_level || 'unknown'}${r.notes ? ' | ' + r.notes : ''}`).join('\n')
      : 'No jurisdiction rules on file for this city.';

    const researchContext = packet?.research
      ? JSON.stringify(packet.research)
      : 'No permit research has been done for this job yet.';

    const chatHistory = history.map(m =>
      `${m.role === 'user' ? (m.user_name || 'Team') : 'Pete'}: ${m.message}`
    ).join('\n');

    const systemPrompt = `You are Pete, the permit assistant for Spartan Plumbing (Dayton, OH area).

JOB CONTEXT:
Job #${job?.st_job_id || jobNumber} | ${job?.business_unit_name || 'Unknown'} | ${job?.job_type_name || 'Unknown'} | ${job?.status || 'Unknown'}
Customer: ${job?.customer_name || 'Unknown'}
Address: ${job?.address_street || ''}, ${job?.address_city || ''}, ${job?.address_state || ''} ${job?.address_zip || ''}
Work Summary: ${stripHtml(job?.summary) || 'None'}

PERMIT RESEARCH FOR THIS JOB:
${researchContext}

JURISDICTION RULES ON FILE:
${rulesContext}

CHAT HISTORY:
${chatHistory}

RULES:
- Answer permit questions using the research and rules above
- If you don't know, say so. Don't guess on permit requirements.
- Be concise and direct. Short answers are better.
- Include phone numbers, fees, and websites when you have them
- If asked about a jurisdiction not in the rules, say the system needs to research it
- Never make up phone numbers, fees, or requirements`;

    const aiRes = await fetch('https://openrouter.ai/api/v1/chat/completions', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${OPENROUTER_KEY}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'google/gemini-2.0-flash-001',
        max_tokens: 800,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: message }
        ]
      }),
    });

    if (!aiRes.ok) {
      const errText = await aiRes.text();
      return NextResponse.json({ error: 'AI service error', detail: errText }, { status: 502 });
    }

    const aiData = await aiRes.json();
    const aiResponse = aiData.choices?.[0]?.message?.content || 'Sorry, I could not generate a response.';

    await query(`
      INSERT INTO spartan_ops.permit_chat (st_job_id, role, message)
      VALUES (${jobNumber}, 'assistant', '${aiResponse.replace(/'/g, "''")}')
    `);

    const updated = await query(`
      SELECT id, role, message, user_id, user_name, created_at
      FROM spartan_ops.permit_chat
      WHERE st_job_id = ${jobNumber}
      ORDER BY created_at ASC
    `);

    return NextResponse.json({ response: aiResponse, messages: updated });
  } catch (err) {
    console.error('Permit chat error:', err);
    return NextResponse.json({ error: 'Failed to process message', detail: String(err) }, { status: 500 });
  }
}
