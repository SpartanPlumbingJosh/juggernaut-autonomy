const express = require('express');
const crypto = require('crypto');

const app = express();
const PORT = process.env.PORT || 3000;

// --- Config ---
const SB_URL = process.env.SUPABASE_URL || 'https://kong.thejuggernaut.org';
const SB_KEY = process.env.SUPABASE_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU';
const CF_ID = process.env.CF_ACCESS_CLIENT_ID || 'd9d91ed78bf6b41408577f15d0bc629f.access';
const CF_SECRET = process.env.CF_ACCESS_CLIENT_SECRET || '8cadf12c93312ab44cdf084065f26eee1bc502b73b4de66a4d0b5f9981517272';
const SLACK_SIGNING_SECRET = process.env.SLACK_SIGNING_SECRET || '';
const SCHEMA = 'knowledge_lake';

const sbHeaders = {
  'apikey': SB_KEY,
  'Authorization': `Bearer ${SB_KEY}`,
  'CF-Access-Client-Id': CF_ID,
  'CF-Access-Client-Secret': CF_SECRET,
  'Content-Type': 'application/json',
  'Content-Profile': SCHEMA,
  'Prefer': 'resolution=merge-duplicates'
};

// --- Channel name cache (in-memory, refreshes on restart) ---
const channelCache = new Map();

async function getChannelName(channelId) {
  if (channelCache.has(channelId)) return channelCache.get(channelId);

  // Try bookmark_tracked_channels first
  try {
    const url = `${SB_URL}/rest/v1/bookmark_tracked_channels?channel_id=eq.${channelId}&select=channel_name&limit=1`;
    const resp = await fetch(url, {
      headers: {
        'apikey': SB_KEY,
        'Authorization': `Bearer ${SB_KEY}`,
        'CF-Access-Client-Id': CF_ID,
        'CF-Access-Client-Secret': CF_SECRET,
        'Accept-Profile': 'spartan_ops'
      }
    });
    const rows = await resp.json();
    if (rows && rows.length > 0 && rows[0].channel_name) {
      channelCache.set(channelId, rows[0].channel_name);
      return rows[0].channel_name;
    }
  } catch (e) { /* continue */ }

  // Try slack_channel_sweep
  try {
    const url = `${SB_URL}/rest/v1/slack_channel_sweep?channel_id=eq.${channelId}&select=channel_name&limit=1`;
    const resp = await fetch(url, {
      headers: {
        'apikey': SB_KEY,
        'Authorization': `Bearer ${SB_KEY}`,
        'CF-Access-Client-Id': CF_ID,
        'CF-Access-Client-Secret': CF_SECRET,
        'Accept-Profile': SCHEMA
      }
    });
    const rows = await resp.json();
    if (rows && rows.length > 0 && rows[0].channel_name) {
      channelCache.set(channelId, rows[0].channel_name);
      return rows[0].channel_name;
    }
  } catch (e) { /* continue */ }

  // Fallback: use channel_id as name
  channelCache.set(channelId, channelId);
  return channelId;
}

// --- PCI redaction ---
function redactPCI(text) {
  if (!text) return text;
  text = text.replace(/(card.?number[:\s]+)\d{13,16}/gi, '$1[REDACTED]');
  text = text.replace(/((?:cvc|cvv|security.?code)[:\s]+)\d{3,4}/gi, '$1[REDACTED]');
  text = text.replace(/(exp.?date[:\s]+)\d{1,2}\/\d{2,4}/gi, '$1[REDACTED]');
  text = text.replace(/\b3[47]\d{2}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{3,4}\b/g, '[CC-REDACTED]');
  text = text.replace(/\b[4-6]\d{3}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b/g, '[CC-REDACTED]');
  return text;
}

// --- Slack signature verification ---
function verifySlackSignature(req) {
  if (!SLACK_SIGNING_SECRET) return true; // Skip if not configured
  const timestamp = req.headers['x-slack-request-timestamp'];
  const sig = req.headers['x-slack-signature'];
  if (!timestamp || !sig) return false;

  // Reject requests older than 5 minutes
  if (Math.abs(Date.now() / 1000 - parseInt(timestamp)) > 300) return false;

  const baseString = `v0:${timestamp}:${req.rawBody}`;
  const hmac = crypto.createHmac('sha256', SLACK_SIGNING_SECRET).update(baseString).digest('hex');
  const computed = `v0=${hmac}`;
  return crypto.timingSafeEqual(Buffer.from(computed), Buffer.from(sig));
}

// --- Store raw body for signature verification ---
app.use(express.json({
  verify: (req, res, buf) => { req.rawBody = buf.toString(); }
}));

// --- Health check ---
app.get('/', (req, res) => {
  res.json({ status: 'ok', service: 'slack-realtime-ingest', channels_cached: channelCache.size });
});

app.get('/health', (req, res) => {
  res.json({ status: 'ok', uptime: process.uptime(), channels_cached: channelCache.size });
});

// --- Slack Events endpoint ---
app.post('/slack/events', async (req, res) => {
  const body = req.body;

  // 1. URL verification challenge
  if (body.type === 'url_verification') {
    return res.json({ challenge: body.challenge });
  }

  // 2. Verify signature
  if (!verifySlackSignature(req)) {
    console.warn('Invalid Slack signature');
    return res.status(401).send('Invalid signature');
  }

  // 3. Respond 200 immediately — Slack retries after 3 seconds if we don't
  res.status(200).send('ok');

  // 4. Skip retries (Slack resends if it thinks we failed)
  if (req.headers['x-slack-retry-num']) return;

  // 5. Process the event async
  try {
    if (body.type !== 'event_callback') return;
    const event = body.event;
    if (!event) return;

    // Only process message events
    if (event.type !== 'message') return;

    // Skip message_changed, message_deleted, etc. — only new messages and file_shares
    if (event.subtype && !['file_share', 'bot_message', 'thread_broadcast'].includes(event.subtype)) return;

    const channelId = event.channel;
    const ts = event.ts || event.event_ts;
    if (!channelId || !ts) return;

    const channelName = await getChannelName(channelId);
    const isBot = !!(event.bot_id || event.subtype === 'bot_message');

    const row = {
      channel_id: channelId,
      channel_name: channelName,
      message_ts: ts,
      thread_ts: event.thread_ts || null,
      user_id: event.user || '',
      message_text: redactPCI(event.text || ''),
      reactions: null,
      file_count: (event.files || []).length,
      has_attachments: !!(event.files?.length || event.attachments?.length),
      is_bot: isBot,
      message_subtype: event.subtype || null,
      message_date: new Date(parseFloat(ts) * 1000).toISOString()
    };

    // Upsert to Supabase
    const resp = await fetch(`${SB_URL}/rest/v1/slack_raw_messages?on_conflict=channel_id,message_ts`, {
      method: 'POST',
      headers: sbHeaders,
      body: JSON.stringify(row)
    });

    if (!resp.ok) {
      const err = await resp.text();
      console.error(`Supabase upsert failed: ${resp.status} ${err}`);
    }

    // Also update sweep table latest_message_ts
    try {
      await fetch(`${SB_URL}/rest/v1/slack_channel_sweep?channel_id=eq.${channelId}`, {
        method: 'PATCH',
        headers: { ...sbHeaders, 'Prefer': 'return=minimal' },
        body: JSON.stringify({
          latest_message_ts: ts,
          swept_at: new Date().toISOString()
        })
      });
    } catch (e) { /* non-critical */ }

  } catch (err) {
    console.error('Event processing error:', err.message || err);
  }
});

app.listen(PORT, () => {
  console.log(`slack-realtime-ingest listening on port ${PORT}`);
});
