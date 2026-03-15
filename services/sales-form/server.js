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

// Safe string escape for SQL
function esc(s) { return (s || '').replace(/'/g, "''"); }

app.use('/form', express.static(path.join(__dirname, 'public', 'form')));
app.use('/materials', express.static(path.join(__dirname, 'public', 'materials')));

app.get('/health', (req, res) => res.json({ status: 'ok', service: 'spartan-sales-form' }));

app.get('/', (req, res) => {
  if (req.query.id) return res.redirect(`/form?id=${req.query.id}`);
  res.json({ service: 'Spartan Job Tracker', routes: ['/form?id=N', '/materials?id=N'] });
});

// ═══════════════════════════════════════
// ORIGINAL ENDPOINTS (preserved)
// ═══════════════════════════════════════

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

// ═══════════════════════════════════════
// NEW: CUSTOMER INTEL API
// ═══════════════════════════════════════

app.get('/api/intel/:id', async (req, res) => {
  try {
    const id = parseInt(req.params.id);
    if (isNaN(id)) return res.status(400).json({ error: 'Invalid ID' });

    // Get the form record to find customer name and st_job_id
    const form = await supabaseQuery(
      `SELECT st_job_id, customer_name, job_number, sold_amount, business_unit, slack_channel_id
       FROM spartan_ops.auto_sales_forms WHERE id = ${id}`
    );
    if (!form || !form.length) return res.status(404).json({ error: 'Form not found' });
    const f = form[0];
    const custName = esc(f.customer_name || '');

    // Parallel queries for customer data
    const [priorJobs, estimates, invoiceTotals, customerInfo] = await Promise.all([
      // All jobs for this customer
      supabaseQuery(
        `SELECT st_job_id, st_job_number, customer_address, status, sold_amount, track_type,
                job_type, scope_summary, selling_tech_name, service_tech_name,
                created_at::text, closed_at::text, is_recall
         FROM spartan_ops.jobs
         WHERE customer_name ILIKE '%${custName}%'
         ORDER BY created_at DESC LIMIT 25`
      ).catch(() => []),

      // Open estimates for this customer
      supabaseQuery(
        `SELECT e.st_estimate_id, e.status, e.total, e.created_on::text, e.name
         FROM spartan_ops.st_estimates e
         WHERE e.customer_name ILIKE '%${custName}%'
         AND e.status NOT IN ('Sold', 'Dismissed')
         ORDER BY e.created_on DESC LIMIT 15`
      ).catch(() => []),

      // Total invoiced amount for this customer
      supabaseQuery(
        `SELECT count(*) as invoice_count, coalesce(sum(i.total), 0) as total_invoiced
         FROM spartan_ops.st_invoices i
         WHERE i.customer_name ILIKE '%${custName}%'`
      ).catch(() => [{ invoice_count: 0, total_invoiced: 0 }]),

      // Customer record from st_customers
      supabaseQuery(
        `SELECT st_customer_id, name, address_street, address_city, address_state, address_zip,
                email, phone, created_on::text
         FROM spartan_ops.st_customers
         WHERE name ILIKE '%${custName}%'
         LIMIT 1`
      ).catch(() => [])
    ]);

    // Compute stats
    const jobCount = (priorJobs || []).length;
    const installCount = (priorJobs || []).filter(j => j.track_type === 'install').length;
    const serviceCount = (priorJobs || []).filter(j => j.track_type === 'service').length;
    const recallCount = (priorJobs || []).filter(j => j.is_recall === true).length;
    const totalSold = (priorJobs || []).reduce((sum, j) => sum + (parseFloat(j.sold_amount) || 0), 0);
    const inv = (invoiceTotals && invoiceTotals[0]) || { invoice_count: 0, total_invoiced: 0 };
    const cust = (customerInfo && customerInfo[0]) || null;
    const openEstCount = (estimates || []).length;
    const openEstTotal = (estimates || []).reduce((sum, e) => sum + (parseFloat(e.total) || 0), 0);

    res.json({
      customer: cust,
      stats: {
        total_jobs: jobCount,
        install_jobs: installCount,
        service_jobs: serviceCount,
        recall_count: recallCount,
        total_sold: totalSold,
        total_invoiced: parseFloat(inv.total_invoiced) || 0,
        invoice_count: parseInt(inv.invoice_count) || 0,
        open_estimates: openEstCount,
        open_estimate_total: openEstTotal,
        customer_since: cust ? cust.created_on : null
      },
      prior_jobs: priorJobs || [],
      open_estimates: estimates || []
    });
  } catch (err) { console.error('Intel error:', err); res.status(500).json({ error: 'Server error' }); }
});

// ═══════════════════════════════════════
// NEW: VERIFICATIONS API
// ═══════════════════════════════════════

app.get('/api/verifications/:stJobId', async (req, res) => {
  try {
    const stJobId = esc(req.params.stJobId);

    const rows = await supabaseQuery(
      `SELECT jv.verification_code, jv.verification_name, jv.phase, jv.stage, jv.result,
              jv.is_hard_gate, jv.ai_confidence, jv.ai_reasoning, jv.completed_at::text
       FROM spartan_ops.job_verifications jv
       JOIN spartan_ops.jobs j ON j.id = jv.job_id
       WHERE j.st_job_id = '${stJobId}'
       ORDER BY jv.verification_code`
    );

    // Compute score
    const checks = rows || [];
    const passed = checks.filter(c => c.result === 'pass').length;
    const failed = checks.filter(c => c.result === 'fail').length;
    const skipped = checks.filter(c => c.result === 'skip').length;
    const pending = checks.filter(c => c.result === 'pending' || !c.result).length;
    const total = checks.length;
    const scored = total - pending - skipped;
    const score = scored > 0 ? Math.round(passed / scored * 100) : 0;

    res.json({
      checks,
      score: { passed, failed, skipped, pending, total, score }
    });
  } catch (err) { console.error('Verifications error:', err); res.status(500).json({ error: 'Server error' }); }
});

// ═══════════════════════════════════════
// NEW: FINANCIALS API
// ═══════════════════════════════════════

app.get('/api/financials/:stJobId', async (req, res) => {
  try {
    const stJobId = esc(req.params.stJobId);

    const [invoices, payments] = await Promise.all([
      supabaseQuery(
        `SELECT st_invoice_id, number, status, subtotal, tax, total, created_on::text
         FROM spartan_ops.st_invoices
         WHERE st_job_id = '${stJobId}'::bigint
         ORDER BY created_on DESC`
      ).catch(() => []),

      supabaseQuery(
        `SELECT id, total, type_name, memo, created_on::text
         FROM spartan_ops.st_payments
         WHERE st_job_id = '${stJobId}'
         ORDER BY created_on DESC`
      ).catch(() => [])
    ]);

    const invoiceTotal = (invoices || []).reduce((sum, i) => sum + (parseFloat(i.total) || 0), 0);
    const paymentTotal = (payments || []).reduce((sum, p) => sum + (parseFloat(p.total) || 0), 0);

    res.json({
      invoices: invoices || [],
      payments: payments || [],
      totals: {
        invoiced: invoiceTotal,
        paid: paymentTotal,
        outstanding: invoiceTotal - paymentTotal
      }
    });
  } catch (err) { console.error('Financials error:', err); res.status(500).json({ error: 'Server error' }); }
});

// ═══════════════════════════════════════
// NEW: JOB TYPE LOOKUP API
// ═══════════════════════════════════════

app.get('/api/jobtypes', async (req, res) => {
  try {
    const rows = await supabaseQuery(
      `SELECT st_job_type_id::text, name FROM spartan_ops.st_job_types ORDER BY name`
    );
    res.json(rows || []);
  } catch (err) { console.error('JobTypes error:', err); res.status(500).json({ error: 'Server error' }); }
});

// ═══════════════════════════════════════
// STATIC FILE ROUTES (must be last)
// ═══════════════════════════════════════

app.get('/form', (req, res) => res.sendFile(path.join(__dirname, 'public', 'form', 'index.html')));
app.get('/materials', (req, res) => res.sendFile(path.join(__dirname, 'public', 'materials', 'index.html')));

app.listen(PORT, '0.0.0.0', () => console.log(`Spartan Job Tracker on port ${PORT}`));
