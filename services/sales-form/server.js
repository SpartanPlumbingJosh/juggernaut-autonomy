const express = require('express');
const cors = require('cors');
const path = require('path');
const https = require('https');

const app = express();
app.use(cors());
app.use(express.json({ limit: '5mb' }));

const PORT = process.env.PORT || 3000;

const SUPABASE_URL = process.env.SUPABASE_URL || 'https://kong.thejuggernaut.org/rest/v1';
const SUPABASE_KEY = process.env.SUPABASE_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU';
const CF_ID = process.env.CF_ACCESS_CLIENT_ID || 'd9d91ed78bf6b41408577f15d0bc629f.access';
const CF_SECRET = process.env.CF_ACCESS_CLIENT_SECRET || '8cadf12c93312ab44cdf084065f26eee1bc502b73b4de66a4d0b5f9981517272';

function supabaseQuery(sql) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({ query: sql });
    const url = new URL(SUPABASE_URL + '/rpc/exec_sql');
    const opts = {
      hostname: url.hostname, path: url.pathname, method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'apikey': SUPABASE_KEY,
        'Authorization': `Bearer ${SUPABASE_KEY}`,
        'Content-Profile': 'knowledge_lake',
        'Accept-Profile': 'knowledge_lake',
        'CF-Access-Client-Id': CF_ID,
        'CF-Access-Client-Secret': CF_SECRET,
        'Content-Length': Buffer.byteLength(body)
      }
    };
    const req = https.request(opts, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (parsed.code) reject(new Error(`DB: ${parsed.message}`));
          else resolve(parsed);
        } catch (e) { reject(new Error('Parse error')); }
      });
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

app.use('/form', express.static(path.join(__dirname, 'public', 'form')));
app.use('/materials', express.static(path.join(__dirname, 'public', 'materials')));

app.get('/health', (req, res) => res.json({ status: 'ok', service: 'spartan-sales-form' }));

app.get('/', (req, res) => {
  if (req.query.id) return res.redirect(`/form?id=${req.query.id}`);
  res.json({ service: 'Spartan Sales & Materials', routes: ['/form?id=N', '/materials?id=N'] });
});

app.get('/api/prefill/:id', async (req, res) => {
  try {
    const id = parseInt(req.params.id);
    if (isNaN(id)) return res.status(400).json({ error: 'Invalid ID' });
    const rows = await supabaseQuery(
      `SELECT id, st_job_id, st_estimate_id, customer_name, job_number, sold_amount,
              sold_by, business_unit, track_type, slack_channel_id,
              sales_form_text, material_list_json, form_data, form_confirmed,
              confirmed_data, ai_model, generated_at
       FROM spartan_ops.auto_sales_forms WHERE id = ${id}`
    );
    if (!rows || !rows.length) return res.status(404).json({ error: 'Not found' });
    const row = rows[0];
    let formFields = row.form_data || null;
    if (!formFields && row.sales_form_text) {
      try { formFields = JSON.parse(row.sales_form_text); } catch (e) {}
    }
    res.json({ ...row, form_fields: formFields });
  } catch (err) { console.error('Prefill error:', err); res.status(500).json({ error: 'Server error' }); }
});

app.post('/api/submit', async (req, res) => {
  try {
    const { id, confirmed_data, confirmed_by } = req.body;
    if (!id || !confirmed_data) return res.status(400).json({ error: 'Missing id or confirmed_data' });
    const jsonStr = JSON.stringify(confirmed_data).replace(/'/g, "''");
    const byStr = (confirmed_by || 'production').replace(/'/g, "''");
    await supabaseQuery(
      `UPDATE spartan_ops.auto_sales_forms SET confirmed_data = '${jsonStr}'::jsonb, form_confirmed = true, confirmed_at = now(), confirmed_by = '${byStr}' WHERE id = ${parseInt(id)}`
    );
    res.json({ success: true });
  } catch (err) { console.error('Submit error:', err); res.status(500).json({ error: 'Server error' }); }
});

app.get('/api/materials/:id', async (req, res) => {
  try {
    const id = parseInt(req.params.id);
    if (isNaN(id)) return res.status(400).json({ error: 'Invalid ID' });
    const rows = await supabaseQuery(
      `SELECT id, customer_name, job_number, sold_amount, business_unit, material_list_json, form_confirmed FROM spartan_ops.auto_sales_forms WHERE id = ${id}`
    );
    if (!rows || !rows.length) return res.status(404).json({ error: 'Not found' });
    res.json(rows[0]);
  } catch (err) { console.error('Materials error:', err); res.status(500).json({ error: 'Server error' }); }
});

app.get('/api/catalog/search', async (req, res) => {
  try {
    const q = (req.query.q || '').replace(/'/g, "''").trim();
    if (!q) return res.json([]);
    const rows = await supabaseQuery(
      `SELECT item_code, description, spartan_price, lee_number, category, is_active FROM spartan_ops.lee_supply_catalog WHERE is_active = true AND (description ILIKE '%${q}%' OR item_code ILIKE '%${q}%' OR lee_number ILIKE '%${q}%') ORDER BY description LIMIT 20`
    );
    res.json(rows || []);
  } catch (err) { console.error('Search error:', err); res.status(500).json({ error: 'Server error' }); }
});

app.get('/form', (req, res) => res.sendFile(path.join(__dirname, 'public', 'form', 'index.html')));
app.get('/materials', (req, res) => res.sendFile(path.join(__dirname, 'public', 'materials', 'index.html')));

app.listen(PORT, '0.0.0.0', () => console.log(`Spartan Sales + Materials on port ${PORT}`));
