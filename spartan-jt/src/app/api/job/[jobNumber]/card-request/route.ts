import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/supabase';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ jobNumber: string }> }
) {
  const { jobNumber } = await params;

  if (!/^\d+$/.test(jobNumber)) {
    return NextResponse.json({ error: 'Invalid job number' }, { status: 400 });
  }

  let body: {
    vendor_name: string;
    purchase_description: string;
    amount: number;
    requested_by_name: string;
    requested_by_slack_id?: string;
  };

  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  if (!body.vendor_name || !body.purchase_description || !body.amount || !body.requested_by_name) {
    return NextResponse.json({ error: 'Missing required fields: vendor_name, purchase_description, amount, requested_by_name' }, { status: 400 });
  }

  // Sanitize inputs to prevent SQL injection
  const esc = (s: string) => s.replace(/'/g, "''").substring(0, 500);
  const vendor = esc(body.vendor_name);
  const desc = esc(body.purchase_description);
  const amt = parseFloat(String(body.amount)) || 0;
  const name = esc(body.requested_by_name);
  const slackId = body.requested_by_slack_id ? esc(body.requested_by_slack_id) : '';

  try {
    // Look up the Slack channel for this job
    const channels = await query(`
      SELECT channel_id, channel_name
      FROM spartan_ops.bookmark_tracked_channels
      WHERE channel_name LIKE '${jobNumber}-%'
      LIMIT 1
    `);

    const channelId = channels.length > 0 ? (channels[0] as any).channel_id : '';
    const channelName = channels.length > 0 ? (channels[0] as any).channel_name : '';

    // Insert the card request
    const result = await query(`
      INSERT INTO spartan_ops.job_card_requests
        (st_job_id, channel_id, requested_by, requested_by_name, requested_at, vendor_name, purchase_description, amount, card_issued, receipt_posted, reconciled, mismatch_flagged, created_at)
      VALUES
        (${jobNumber}, '${channelId}', '${slackId}', '${name}', now(), '${vendor}', '${desc}', ${amt}, false, false, false, false, now())
      RETURNING id, st_job_id, channel_id, requested_by, requested_by_name, requested_at, vendor_name, purchase_description, amount
    `);

    const newRequest = result.length > 0 ? result[0] : null;

    // Fire-and-forget: trigger n8n webhook for Slack notification
    if (channelId && newRequest) {
      const N8N_WEBHOOK = process.env.N8N_CARD_REQUEST_WEBHOOK || 'https://n8n.thejuggernaut.org/webhook/card-request-notify';
      fetch(N8N_WEBHOOK, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'CF-Access-Client-Id': process.env.CF_ACCESS_CLIENT_ID || '',
          'CF-Access-Client-Secret': process.env.CF_ACCESS_CLIENT_SECRET || '',
        },
        body: JSON.stringify({
          st_job_id: jobNumber,
          channel_id: channelId,
          channel_name: channelName,
          vendor_name: body.vendor_name,
          purchase_description: body.purchase_description,
          amount: amt,
          requested_by_name: body.requested_by_name,
          requested_by_slack_id: body.requested_by_slack_id || '',
          request_id: (newRequest as any).id,
        }),
      }).catch(err => console.error('n8n webhook error:', err));
    }

    return NextResponse.json({
      success: true,
      request: newRequest,
      channel_id: channelId,
    });
  } catch (err) {
    console.error('Card request error:', err);
    return NextResponse.json(
      { error: 'Failed to create card request', detail: String(err) },
      { status: 500 }
    );
  }
}