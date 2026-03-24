const express = require('express');
const crypto = require('crypto');

const app = express();
const PORT = process.env.PORT || 3000;

// --- Config ---
const SB_URL = process.env.SUPABASE_URL || 'https://kong.thejuggernaut.org';
const SB_KEY = process.env.SUPABASE_KEY;
const CF_ID = process.env.CF_ACCESS_CLIENT_ID;
const CF_SECRET = process.env.CF_ACCESS_CLIENT_SECRET;
const BOT_TOKEN = process.env.SLACK_BOT_TOKEN;
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

// --- Stats ---
let stats = { messagesIngested: 0, channelsJoined: 0, errors: 0, startedAt: new Date().toISOString() };

// --- Channel name cache ---
const channelCache = new Map();

async function getChannelName(channelId) {
  if (channelCache.has(channelId)) return channelCache.get(channelId);
  try {
    const resp = await fetch(`${SB_URL}/rest/v1/bookmark_tracked_channels?channel_id=eq.${channelId}&select=channel_name&limit=1`, {
      headers: { 'apikey': SB_KEY, 'Authorization': `Bearer ${SB_KEY}`, 'CF-Access-Client-Id': CF_ID, 'CF-Access-Client-Secret': CF_SECRET, 'Accept-Profile': 'spartan_ops' }
    });
    const rows = await resp.json();
    if (rows?.[0]?.channel_name) { channelCache.set(channelId, rows[0].channel_name); return rows[0].channel_name; }
  } catch (e) {}
  try {
    const resp = await fetch(`${SB_URL}/rest/v1/slack_channel_sweep?channel_id=eq.${channelId}&select=channel_name&limit=1`, {
      headers: { 'apikey': SB_KEY, 'Authorization': `Bearer ${SB_KEY}`, 'CF-Access-Client-Id': CF_ID, 'CF-Access-Client-Secret': CF_SECRET, 'Accept-Profile': SCHEMA }
    });
    const rows = await resp.json();
    if (rows?.[0]?.channel_name) { channelCache.set(channelId, rows[0].channel_name); return rows[0].channel_name; }
  } catch (e) {}
  // Fallback: ask Slack
  try {
    const resp = await fetch(`https://slack.com/api/conversations.info?channel=${channelId}`, {
      headers: { 'Authorization': `Bearer ${BOT_TOKEN}` }
    });
    const data = await resp.json();
    if (data.ok && data.channel?.name) { channelCache.set(channelId, data.channel.name); return data.channel.name; }
  } catch (e) {}
  channelCache.set(channelId, channelId);
  return channelId;
}

// --- Join a channel ---
async function joinChannel(channelId) {
  try {
    const resp = await fetch('https://slack.com/api/conversations.join', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${BOT_TOKEN}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ channel: channelId })
    });
    const data = await resp.json();
    if (data.ok || data.error === 'already_in_channel') {
      stats.channelsJoined++;
      return true;
    }
    if (data.error === 'method_not_supported_for_channel_type') return false; // Can't join DMs etc
    console.warn(`Failed to join ${channelId}: ${data.error}`);
    return false;
  } catch (e) {
    console.error(`Join error ${channelId}:`, e.message);
    return false;
  }
}

// --- Bulk join all tracked channels on startup ---
async function bulkJoinChannels() {
  console.log('Starting bulk channel join...');
  let offset = 0;
  let totalJoined = 0;
  while (true) {
    try {
      const resp = await fetch(
        `${SB_URL}/rest/v1/bookmark_tracked_channels?select=channel_id&order=created_at.desc&limit=200&offset=${offset}`,
        { headers: { 'apikey': SB_KEY, 'Authorization': `Bearer ${SB_KEY}`, 'CF-Access-Client-Id': CF_ID, 'CF-Access-Client-Secret': CF_SECRET, 'Accept-Profile': 'spartan_ops' } }
      );
      const rows = await resp.json();
      if (!rows || rows.length === 0) break;

      for (const row of rows) {
        await joinChannel(row.channel_id);
        await new Promise(r => setTimeout(r, 1100)); // Tier 3 rate limit
      }
      totalJoined += rows.length;
      offset += 200;
      console.log(`Joined batch: ${totalJoined} channels processed so far`);
      if (rows.length < 200) break;
    } catch (e) {
      console.error('Bulk join error:', e.message);
      break;
    }
  }
  console.log(`Bulk join complete: ${totalJoined} channels processed`);
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
  if (!SLACK_SIGNING_SECRET) return true;
  const timestamp = req.headers['x-slack-request-timestamp'];
  const sig = req.headers['x-slack-signature'];
  if (!timestamp || !sig) return false;
  if (Math.abs(Date.now() / 1000 - parseInt(timestamp)) > 300) return false;
  const baseString = `v0:${timestamp}:${req.rawBody}`;
  const hmac = crypto.createHmac('sha256', SLACK_SIGNING_SECRET).update(baseString).digest('hex');
  const computed = `v0=${hmac}`;
  return crypto.timingSafeEqual(Buffer.from(computed), Buffer.from(sig));
}

// --- Raw body for signature verification ---
app.use(express.json({ verify: (req, res, buf) => { req.rawBody = buf.toString(); } }));

// --- Health ---
app.get('/', (req, res) => res.json({ status: 'ok', service: 'slack-realtime-ingest', ...stats, channels_cached: channelCache.size }));
app.get('/health', (req, res) => res.json({ status: 'ok', uptime: process.uptime(), ...stats, channels_cached: channelCache.size }));

// --- Slack Events endpoint ---
app.post('/slack/events', async (req, res) => {
  const body = req.body;

  // URL verification challenge
  if (body.type === 'url_verification') return res.json({ challenge: body.challenge });

  // Verify signature
  if (!verifySlackSignature(req)) return res.status(401).send('Invalid signature');

  // Respond immediately
  res.status(200).send('ok');

  // Skip retries
  if (req.headers['x-slack-retry-num']) return;

  try {
    if (body.type !== 'event_callback') return;
    const event = body.event;
    if (!event) return;

    // --- Auto-join new public channels ---
    if (event.type === 'channel_created' && event.channel?.id) {
      console.log(`New channel created: ${event.channel.name || event.channel.id} — joining...`);
      await joinChannel(event.channel.id);
      return;
    }

    // --- Process messages ---
    if (event.type !== 'message') return;
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

    const resp = await fetch(`${SB_URL}/rest/v1/slack_raw_messages?on_conflict=channel_id,message_ts`, {
      method: 'POST', headers: sbHeaders, body: JSON.stringify(row)
    });

    if (resp.ok) {
      stats.messagesIngested++;
    } else {
      stats.errors++;
      console.error(`Supabase upsert failed: ${resp.status} ${await resp.text()}`);
    }

    // Update sweep table
    try {
      await fetch(`${SB_URL}/rest/v1/slack_channel_sweep?channel_id=eq.${channelId}`, {
        method: 'PATCH',
        headers: { ...sbHeaders, 'Prefer': 'return=minimal' },
        body: JSON.stringify({ latest_message_ts: ts, swept_at: new Date().toISOString() })
      });
    } catch (e) {}

  } catch (err) {
    stats.errors++;
    console.error('Event processing error:', err.message || err);
  }
});

// --- Start server, then bulk join ---
app.listen(PORT, () => {
  console.log(`slack-realtime-ingest listening on port ${PORT}`);
  // Start bulk join in background after 5 seconds
  setTimeout(() => bulkJoinChannels(), 5000);
});
