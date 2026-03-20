import { query } from '@/lib/supabase';
import { Metadata } from 'next';

function formatMoney(num: number): string {
  if (isNaN(num)) return '0.00';
  return num.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

function has(v: unknown): boolean {
  if (v === undefined || v === null) return false;
  const s = String(v).trim();
  return s !== '' && s !== '0';
}

function str(v: unknown): string {
  if (v === undefined || v === null) return '';
  return String(v);
}

function stars(s: unknown): string {
  if (!s) return '';
  const t = String(s).toLowerCase();
  if (t.includes('5')) return '⭐⭐⭐⭐⭐';
  if (t.includes('4')) return '⭐⭐⭐⭐';
  if (t.includes('3')) return '⭐⭐⭐';
  if (t.includes('2')) return '⭐⭐';
  if (t.includes('1')) return '⭐';
  return String(s);
}

function parseMoney(v: unknown): number {
  if (typeof v === 'number') return v;
  return parseFloat(String(v || '0').replace(/[^0-9.]/g, '')) || 0;
}

function tierInfo(rate: number): { label: string; color: string; emoji: string } {
  if (rate >= 1250) return { label: 'Excellent', color: '#4caf50', emoji: '🟢' };
  if (rate >= 937.5) return { label: 'Good', color: '#4fc3f7', emoji: '🔵' };
  if (rate > 750) return { label: 'Tight', color: '#ffeb3b', emoji: '🟡' };
  return { label: 'Critical', color: '#ff4444', emoji: '🔴' };
}

interface JobType { name: string; avgTime: string; permit: string }
interface PricingCheck { sale: number; hours: number; rate: number }
interface FormRecord { form_data: Record<string, unknown>; created_at: string }

export async function generateMetadata({ params }: { params: Promise<{ jobId: string }> }): Promise<Metadata> {
  const { jobId } = await params;
  return { title: `Checklist — Job ${jobId}` };
}

export default async function ChecklistPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;

  if (!/^\d+$/.test(jobId)) {
    return <ErrorPage message="Invalid job ID" />;
  }

  let d: Record<string, unknown>;
  let createdAt: string;

  try {
    const rows = await query<FormRecord>(
      `SELECT form_data, created_at FROM spartan_ops.sales_form_checklists WHERE st_job_id = '${jobId}' LIMIT 1`
    );

    if (rows.length === 0) {
      return <ErrorPage message={`No checklist found for Job ${jobId}`} />;
    }

    d = typeof rows[0].form_data === 'string' ? JSON.parse(rows[0].form_data as string) : rows[0].form_data;
    createdAt = rows[0].created_at;
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Unknown error';
    return <ErrorPage message={`Error loading checklist: ${msg}`} />;
  }

  const amt = parseMoney(d.pkgAmt);
  const jobTypes = (d.jobTypes || []) as JobType[];
  const pricing = d.pricingCheck as PricingCheck | null;

  return (
    <html lang="en">
      <head>
        <meta charSet="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <style dangerouslySetInnerHTML={{ __html: CSS }} />
      </head>
      <body>
        <h1>💪 SALES TO INSTALL CHECKLIST 💪</h1>

        <div className="section">
          <h2>😊 Job Summary</h2>
          <div className="grid">
            <GridItem label="Customer" value={str(d.customerName)} />
            <GridItem label="Address" value={str(d.address)} />
            <GridItem label="Phone" value={str(d.phone)} />
            <GridItem label="ST Job #" value={str(d.stJob)} />
            <GridItem label="Sold By" value={str(d.soldBy)} />
            <GridItem label="Date Sold" value={str(d.dateSold)} />
            <GridItem label="Hours Bid" value={str(d.hoursBid)} />
            <GridItem label="Star Package" value={stars(d.starPkg)} />
            <GridItem label="Amount" value={amt > 0 ? `$${formatMoney(amt)}` : ''} />
            <GridItem label="Payment" value={str(d.payMethod)} />
            {has(d.financingCo) && <GridItem label="Financing" value={str(d.financingCo)} />}
            <GridItem label="Right to Cancel" value={str(d.rightToCancel)} />
            <GridItem label="40% Deposit" value={str(d.depositCollected)} />
          </div>
        </div>

        {(has(d.workType) || has(d.equipment) || has(d.dustContain) || has(d.promises) || has(d.specialTools)) && (
          <div className="section">
            <h2>🔧 Work Details</h2>
            <div className="grid">
              {has(d.workType) && <GridItem label="Type of Work" value={str(d.workType)} />}
              {has(d.equipment) && <GridItem label="Equipment/Material" value={str(d.equipment)} />}
              {has(d.dustContain) && <GridItem label="Dust Containment" value={str(d.dustContain)} />}
              {has(d.promises) && <GridItem label="Promises/Expectations" value={str(d.promises)} />}
              {has(d.specialTools) && <GridItem label="Special Tools" value={str(d.specialTools)} />}
              {has(d.picsTaken) && <GridItem label="Pictures Taken" value={str(d.picsTaken)} />}
              {has(d.videoTaken) && <GridItem label="Video Taken" value={str(d.videoTaken)} />}
            </div>
          </div>
        )}

        {(has(d.returnVisit) || has(d.excavating) || has(d.subcontractor)) && (
          <div className="section">
            <h2>📋 Additional Details</h2>
            <div className="grid">
              {has(d.returnVisit) && <GridItem label="Return Visit" value={str(d.returnVisit)} />}
              {str(d.returnVisit).toLowerCase() === 'yes' && has(d.returnWhen) && <GridItem label="When/What Part" value={str(d.returnWhen)} />}
              {has(d.excavating) && <GridItem label="Excavating" value={str(d.excavating)} />}
              {str(d.excavating).toLowerCase() === 'yes' && (
                <>
                  {has(d.excavLocation) && <GridItem label="Location" value={str(d.excavLocation)} />}
                  {has(d.excavMarked) && <GridItem label="Area Marked" value={str(d.excavMarked)} />}
                  {has(d.calledOUPS) && <GridItem label="Called OUPS" value={str(d.calledOUPS)} />}
                  {has(d.oupsTicket) && <GridItem label="OUPS Ticket #" value={str(d.oupsTicket)} />}
                </>
              )}
              {has(d.subcontractor) && <GridItem label="Subcontractor Needed" value={str(d.subcontractor)} />}
              {str(d.subcontractor).toLowerCase() === 'yes' && (
                <>
                  {has(d.subName) && <GridItem label="Subcontractor" value={str(d.subName)} />}
                  {has(d.subAgreement) && <GridItem label="Agreement Signed" value={str(d.subAgreement)} />}
                </>
              )}
            </div>
          </div>
        )}

        {has(d.crewMsg) && (
          <div className="crew-msg">💪 <em>{str(d.crewMsg)}</em></div>
        )}

        {jobTypes.length > 0 && (
          <>
            {jobTypes.map((jt: JobType, i: number) => (
              <div key={i} className="job-header">
                <div className="name">{jt.name}</div>
                <div className="meta">⏱️ {jt.avgTime} | 📝 Permit: {jt.permit}</div>
              </div>
            ))}
          </>
        )}

        {pricing && pricing.sale > 0 && pricing.hours > 0 && (
          <div className="pricing">
            <h2 style={{ marginTop: 0 }}>📊 Pricing Check</h2>
            <div className="row"><span className="lb">Sale</span><span className="vl">${formatMoney(pricing.sale)}</span></div>
            <div className="row"><span className="lb">Hours Bid</span><span className="vl">{pricing.hours}</span></div>
            <div className="row"><span className="lb">Rate</span><span className="vl">${formatMoney(pricing.rate)}/hr</span></div>
            <div className="row">
              <span className="lb">Tier</span>
              <span className="vl" style={{ color: tierInfo(pricing.rate).color }}>
                {tierInfo(pricing.rate).emoji} {tierInfo(pricing.rate).label}
              </span>
            </div>
          </div>
        )}

        <div className="timestamp">
          Generated: {new Date(createdAt).toLocaleString('en-US', { timeZone: 'America/New_York' })} ET
        </div>
      </body>
    </html>
  );
}

function GridItem({ label, value }: { label: string; value: string }) {
  if (!has(value)) return null;
  return (
    <div className="gi">
      <span className="label">{label}</span>
      <span className="value">{value}</span>
    </div>
  );
}

function ErrorPage({ message }: { message: string }) {
  return (
    <html lang="en">
      <head><style dangerouslySetInnerHTML={{ __html: CSS }} /></head>
      <body>
        <h1>💪 SALES TO INSTALL CHECKLIST 💪</h1>
        <div className="section">
          <h2>⚠️ {message}</h2>
          <p style={{ color: '#a0a0a0' }}>This job may not have a Sales to Install form submitted yet, or the form was processed before the new system was activated.</p>
        </div>
      </body>
    </html>
  );
}

const CSS = `
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;max-width:800px;margin:0 auto;padding:20px;background:#1a1a2e;color:#e0e0e0}
h1{color:#ff6b35;text-align:center;border-bottom:3px solid #ff6b35;padding-bottom:15px;font-size:24px}
h2{color:#ffd700;margin-top:30px;font-size:20px}
p{line-height:1.6}
.section{background:#16213e;border-radius:10px;padding:20px;margin:15px 0;border-left:4px solid #ff6b35}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.gi span{display:block}
.label{color:#a0a0a0;font-size:13px}
.value{color:#fff;font-size:15px;font-weight:500}
.job-header{background:#0f3460;border-radius:10px;padding:15px 20px;margin:20px 0 10px;border-left:4px solid #ffd700}
.job-header .name{font-size:20px;font-weight:bold;color:#ffd700}
.job-header .meta{font-size:14px;color:#a0a0a0;margin-top:5px}
.crew-msg{background:#16213e;border-radius:10px;padding:16px 20px;margin:15px 0;border-left:4px solid #ffd700;font-size:16px;color:#fff;line-height:1.5}
.pricing{background:#16213e;border-radius:10px;padding:20px;margin:20px 0;border-left:4px solid #4fc3f7}
.pricing .row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.08)}
.pricing .row:last-child{border-bottom:none}
.pricing .lb{color:#a0a0a0;font-size:15px}
.pricing .vl{color:#fff;font-size:15px;font-weight:600}
.timestamp{text-align:center;color:#666;font-size:12px;margin-top:30px}
@media(max-width:600px){.grid{grid-template-columns:1fr}body{padding:10px}}
`;