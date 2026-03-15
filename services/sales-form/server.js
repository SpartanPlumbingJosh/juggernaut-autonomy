const express = require('express');
const cors = require('cors');
const path = require('path');
const https = require('https');

const app = express();
app.use(cors());
app.use(express.json({ limit: '5mb' }));
app.use(express.static(path.join(__dirname, 'public')));

const PORT = process.env.PORT || 3000;

const NEON_URL = 'https://ep-crimson-bar-aetz67os.c-2.us-east-2.aws.neon.tech/sql';
const NEON_CONN = process.env.NEON_CONNECTION_STRING ||
  'postgresql://neondb_owner:npg_OYkCRU4aze2l@ep-crimson-bar-aetz67os.c-2.us-east-2.aws.neon.tech/neondb';

// --- Neon query helper ---
function neonQuery(sql, params = []) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({ query: sql, params });
    const url = new URL(NEON_URL);
    const opts = {
      hostname: url.hostname, path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Neon-Connection-String': NEON_CONN,
        'Content-Length': Buffer.byteLength(body)
      }
    };
    const req = https.request(opts, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(new Error('Neon parse error: ' + data.substring(0, 200))); }
      });
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

// --- Health check ---
app.get('/health', (req, res) => res.json({ status: 'ok', service: 'spartan-sales-form' }));

// --- Prefill data ---
app.get('/api/prefill/:id', async (req, res) => {
  try {
    const id = parseInt(req.params.id);
    if (isNaN(id)) return res.status(400).json({ error: 'Invalid ID' });

    const result = await neonQuery(
      `SELECT id, st_job_id, st_estimate_id, customer_name, job_number, sold_amount,
              sold_by, business_unit, track_type, slack_channel_id,
              sales_form_text, material_list_json, form_data, form_confirmed,
              confirmed_data, ai_model, generated_at
       FROM spartan_ops.auto_sales_forms WHERE id = ${id}`
    );

    if (!result.rows || result.rows.length === 0) {
      return res.status(404).json({ error: 'Form not found' });
    }

    const row = result.rows[0];
    let formFields = row.form_data || null;
    if (!formFields && row.sales_form_text) {
      try { formFields = JSON.parse(row.sales_form_text); } catch (e) {}
    }

    res.json({
      id: row.id,
      st_job_id: row.st_job_id,
      customer_name: row.customer_name,
      job_number: row.job_number,
      sold_amount: row.sold_amount,
      sold_by: row.sold_by,
      business_unit: row.business_unit,
      track_type: row.track_type,
      slack_channel_id: row.slack_channel_id,
      form_fields: formFields,
      material_list: row.material_list_json,
      form_confirmed: row.form_confirmed,
      confirmed_data: row.confirmed_data,
      ai_model: row.ai_model,
      generated_at: row.generated_at
    });
  } catch (err) {
    console.error('Prefill error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

// --- Submit confirmed form ---
app.post('/api/submit', async (req, res) => {
  try {
    const { id, confirmed_data, confirmed_by } = req.body;
    if (!id || !confirmed_data) {
      return res.status(400).json({ error: 'Missing id or confirmed_data' });
    }

    const jsonStr = JSON.stringify(confirmed_data).replace(/'/g, "''");
    const byStr = (confirmed_by || 'production').replace(/'/g, "''");

    await neonQuery(
      `UPDATE spartan_ops.auto_sales_forms
       SET confirmed_data = '${jsonStr}'::jsonb,
           form_confirmed = true,
           confirmed_at = now(),
           confirmed_by = '${byStr}'
       WHERE id = ${parseInt(id)}`
    );

    res.json({ success: true, message: 'Form confirmed' });
  } catch (err) {
    console.error('Submit error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

// --- SPA fallback ---
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Spartan Sales Form running on port ${PORT}`);
});
