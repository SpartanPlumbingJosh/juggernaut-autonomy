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
        'Content-Type': 'application/json', 'apikey': SUPABASE_KEY,
        'Authorization': `Bearer ${SUPABASE_KEY}`,
        'Content-Profile': 'knowledge_lake', 'Accept-Profile': 'knowledge_lake',
        'CF-Access-Client-Id': CF_ID, 'CF-Access-Client-Secret': CF_SECRET,
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

function sqlEsc(s) { return (s || '').replace(/'/g, "''"); }

app.use('/form', express.static(path.join(__dirname, 'public', 'form')));
app.use('/materials', express.static(path.join(__dirname, 'public', 'materials')));
app.get('/health', (req, res) => res.json({ status: 'ok', service: 'spartan-sales-form' }));
app.get('/', (req, res) => {
  if (req.query.id) return res.redirect(`/form?id=${req.query.id}`);
  res.json({ service: 'Spartan Job Tracker', routes: ['/form?id=N', '/materials?id=N'] });
});

// === ORIGINAL: Prefill ===
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
    if (!formFields && row.sales_form_text) { try { formFields = JSON.parse(row.sales_form_text); } catch(e){} }
    res.json({ ...row, form_fields: formFields });
  } catch (err) { console.error('Prefill error:', err); res.status(500).json({ error: 'Server error' }); }
});

// === ORIGINAL: Submit ===
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

// === ORIGINAL: Materials + Catalog ===
app.get('/api/materials/:id', async (req, res) => {
  try {
    const id = parseInt(req.params.id);
    if (isNaN(id)) return res.status(400).json({ error: 'Invalid ID' });
    const rows = await supabaseQuery(
      `SELECT id, customer_name, job_number, sold_amount, business_unit, material_list_json, form_confirmed FROM spartan_ops.auto_sales_forms WHERE id = ${id}`
    );
    if (!rows || !rows.length) return res.status(404).json({ error: 'Not found' });
    res.json(rows[0]);
  } catch (err) { res.status(500).json({ error: 'Server error' }); }
});

app.get('/api/catalog/search', async (req, res) => {
  try {
    const q = (req.query.q || '').replace(/'/g, "''").trim();
    if (!q) return res.json([]);
    const rows = await supabaseQuery(
      `SELECT item_code, description, spartan_price, lee_number, category, is_active FROM spartan_ops.lee_supply_catalog WHERE is_active = true AND (description ILIKE '%${q}%' OR item_code ILIKE '%${q}%' OR lee_number ILIKE '%${q}%') ORDER BY description LIMIT 20`
    );
    res.json(rows || []);
  } catch (err) { res.status(500).json({ error: 'Server error' }); }
});

// ═══════════════════════════════════════
// NEW: Customer Intel
// jobs: st_job_id, st_job_number, customer_name, customer_address, status, sold_amount, track_type, job_type, scope_summary, selling_tech_name, service_tech_name, is_recall, created_at, closed_at
// st_customers: st_customer_id, name, address_street/city/state/zip, created_at
// st_estimates: st_estimate_id, estimate_name, status_name, subtotal, tax, created_on, summary, st_job_id
// st_invoices: st_invoice_id, st_job_id(BIGINT), customer_name, total, sub_total, sales_tax, invoice_date, balance
// ═══════════════════════════════════════

app.get('/api/intel/:id', async (req, res) => {
  try {
    const id = parseInt(req.params.id);
    if (isNaN(id)) return res.status(400).json({ error: 'Invalid ID' });

    const form = await supabaseQuery(
      `SELECT st_job_id, customer_name, job_number FROM spartan_ops.auto_sales_forms WHERE id = ${id}`
    );
    if (!form || !form.length) return res.status(404).json({ error: 'Not found' });
    const custName = sqlEsc((form[0].customer_name || '').trim());

    const [priorJobs, estimates, invoiceTotals, customerInfo] = await Promise.all([
      supabaseQuery(
        `SELECT st_job_id, st_job_number, customer_address, status, sold_amount, track_type,
                job_type, scope_summary, selling_tech_name, service_tech_name,
                created_at::text, closed_at::text, is_recall
         FROM spartan_ops.jobs WHERE customer_name ILIKE '%${custName}%'
         ORDER BY created_at DESC LIMIT 25`
      ).catch(() => []),

      supabaseQuery(
        `SELECT e.st_estimate_id, e.status_name, e.subtotal, e.tax,
                (coalesce(e.subtotal,0) + coalesce(e.tax,0)) as total,
                e.created_on::text, e.estimate_name, e.summary
         FROM spartan_ops.st_estimates e
         JOIN spartan_ops.jobs j ON j.st_job_id = e.st_job_id::text
         WHERE j.customer_name ILIKE '%${custName}%'
           AND e.status_name NOT IN ('Sold', 'Dismissed')
         ORDER BY e.created_on DESC LIMIT 15`
      ).catch(() => []),

      supabaseQuery(
        `SELECT count(*) as cnt, coalesce(sum(total), 0) as amt
         FROM spartan_ops.st_invoices WHERE customer_name ILIKE '%${custName}%'`
      ).catch(() => [{ cnt: 0, amt: 0 }]),

      supabaseQuery(
        `SELECT st_customer_id, name, address_street, address_city, address_state, address_zip, created_at::text as customer_since
         FROM spartan_ops.st_customers WHERE name ILIKE '%${custName}%' LIMIT 1`
      ).catch(() => [])
    ]);

    const jobs = priorJobs || [];
    const inv = (invoiceTotals && invoiceTotals[0]) || { cnt: 0, amt: 0 };
    const cust = (customerInfo && customerInfo[0]) || null;
    const ests = estimates || [];

    res.json({
      customer: cust,
      stats: {
        total_jobs: jobs.length,
        install_jobs: jobs.filter(j => j.track_type === 'install').length,
        service_jobs: jobs.filter(j => j.track_type === 'service').length,
        recall_count: jobs.filter(j => j.is_recall).length,
        total_sold: jobs.reduce((s, j) => s + (parseFloat(j.sold_amount) || 0), 0),
        total_invoiced: parseFloat(inv.amt) || 0,
        invoice_count: parseInt(inv.cnt) || 0,
        open_estimates: ests.length,
        open_estimate_total: ests.reduce((s, e) => s + (parseFloat(e.total) || 0), 0),
        customer_since: cust ? cust.customer_since : null
      },
      prior_jobs: jobs,
      open_estimates: ests
    });
  } catch (err) { console.error('Intel error:', err); res.status(500).json({ error: 'Server error' }); }
});

// === NEW: Verifications ===
app.get('/api/verifications/:stJobId', async (req, res) => {
  try {
    const stJobId = sqlEsc(req.params.stJobId);
    const rows = await supabaseQuery(
      `SELECT jv.verification_code, jv.verification_name, jv.phase, jv.stage, jv.result,
              jv.is_hard_gate, jv.ai_confidence, jv.ai_reasoning, jv.completed_at::text
       FROM spartan_ops.job_verifications jv
       JOIN spartan_ops.jobs j ON j.id = jv.job_id
       WHERE j.st_job_id = '${stJobId}'
       ORDER BY jv.verification_code`
    );
    const checks = rows || [];
    const passed = checks.filter(c => c.result === 'pass').length;
    const failed = checks.filter(c => c.result === 'fail').length;
    const skipped = checks.filter(c => c.result === 'skip').length;
    const pending = checks.filter(c => !c.result || c.result === 'pending').length;
    const scored = checks.length - pending - skipped;
    res.json({
      checks,
      score: { passed, failed, skipped, pending, total: checks.length, score: scored > 0 ? Math.round(passed / scored * 100) : 0 }
    });
  } catch (err) { console.error('Verifications error:', err); res.status(500).json({ error: 'Server error' }); }
});

// === NEW: Financials ===
app.get('/api/financials/:stJobId', async (req, res) => {
  try {
    const stJobId = sqlEsc(req.params.stJobId);
    const [invoices, payments] = await Promise.all([
      supabaseQuery(
        `SELECT st_invoice_id, summary, invoice_date::text, sub_total, sales_tax, total, balance
         FROM spartan_ops.st_invoices WHERE st_job_id = '${stJobId}'::bigint
         ORDER BY invoice_date DESC`
      ).catch(() => []),
      supabaseQuery(
        `SELECT p.st_payment_id, p.total, p.payment_type, p.memo, p.payment_date::text
         FROM spartan_ops.st_payments p
         JOIN spartan_ops.st_invoices i ON p.applied_to::text LIKE '%' || i.st_invoice_id::text || '%'
         WHERE i.st_job_id = '${stJobId}'::bigint
         ORDER BY p.payment_date DESC LIMIT 20`
      ).catch(() => [])
    ]);
    const invTotal = (invoices || []).reduce((s, i) => s + (parseFloat(i.total) || 0), 0);
    const payTotal = (payments || []).reduce((s, p) => s + (parseFloat(p.total) || 0), 0);
    res.json({
      invoices: invoices || [], payments: payments || [],
      totals: { invoiced: invTotal, paid: payTotal, outstanding: invTotal - payTotal }
    });
  } catch (err) { console.error('Financials error:', err); res.status(500).json({ error: 'Server error' }); }
});

// === Job Types Lookup ===
app.get('/api/jobtypes', async (req, res) => {
  try {
    const rows = await supabaseQuery(`SELECT st_job_type_id::text, name FROM spartan_ops.st_job_types ORDER BY name`);
    res.json(rows || []);
  } catch (err) { res.status(500).json({ error: 'Server error' }); }
});

// Static file routes (last)
app.get('/form', (req, res) => res.sendFile(path.join(__dirname, 'public', 'form', 'index.html')));
app.get('/materials', (req, res) => res.sendFile(path.join(__dirname, 'public', 'materials', 'index.html')));
app.listen(PORT, '0.0.0.0', () => console.log(`Spartan Job Tracker on port ${PORT}`));
