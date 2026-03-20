import { query } from '@/lib/supabase';
import { Metadata } from 'next';

interface FormData {
  customerName: string;
  address: string;
  phone: string;
  stJob: string;
  slackChannel: string;
  dateSold: string;
  soldBy: string;
  hoursBid: string;
  starPkg: string;
  pkgAmt: string;
  payMethod: string;
  financingCo: string;
  rightToCancel: string;
  depositCollected: string;
  workType: string;
  equipment: string;
  dustContain: string;
  promises: string;
  specialTools: string;
  crewMsg: string;
  picsTaken: string;
  videoTaken: string;
  returnVisit: string;
  returnWhen: string;
  excavating: string;
  excavLocation: string;
  excavMarked: string;
  calledOUPS: string;
  oupsTicket: string;
  subcontractor: string;
  subName: string;
  subAgreement: string;
  formFinished: string;
  jobTypes: { name: string; avgTime: string; permit: string }[];
  pricingCheck: { sale: number; hours: number; rate: number } | null;
}

function formatMoney(num: number): string {
  return num.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

function has(v: string | undefined | null): boolean {
  return v !== undefined && v !== null && v.toString().trim() !== '' && v.toString().trim() !== '0';
}

function stars(s: string): string {
  if (!s) return '';
  const t = s.toLowerCase();
  if (t.includes('5')) return '⭐⭐⭐⭐⭐';
  if (t.includes('4')) return '⭐⭐⭐⭐';
  if (t.includes('3')) return '⭐⭐⭐';
  if (t.includes('2')) return '⭐⭐';
  if (t.includes('1')) return '⭐';
  return s;
}

function tierInfo(rate: number): { label: string; color: string; emoji: string } {
  if (rate >= 1250) return { label: 'Excellent', color: '#4caf50', emoji: '🟢' };
  if (rate >= 937.5) return { label: 'Good', color: '#4fc3f7', emoji: '🔵' };
  if (rate > 750) return { label: 'Tight', color: '#ffeb3b', emoji: '🟡' };
  return { label: 'Critical', color: '#ff4444', emoji: '🔴' };
}

export async function generateMetadata({ params }: { params: Promise<{ jobId: string }> }): Promise<Metadata> {
  const { jobId } = await params;
  return { title: `Checklist — Job ${jobId}` };
}

export default async function ChecklistPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;

  if (!/^\d+$/.test(jobId)) {
    return <ErrorPage message="Invalid job ID" />;
  }

  const rows = await query<{ form_data: FormData; created_at: string }>(
    `SELECT form_data, created_at FROM spartan_ops.sales_form_checklists WHERE st_job_id = '${jobId}' LIMIT 1`
  );

  if (rows.length === 0) {
    return <ErrorPage message={`No checklist found for Job ${jobId}`} />;
  }

  const d = typeof rows[0].form_data === 'string' ? JSON.parse(rows[0].form_data) : rows[0].form_data;
  const createdAt = rows[0].created_at;

  return (
    <html lang="en">
      <head>
        <meta charSet="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <style dangerouslySetInnerHTML={{ __html: CSS }} />
      </head>
      <body>
        <h1>💪 SALES TO INSTALL CHECKLIST 💪</h1>

        {/* Job Summary */}
        <div className="section">
          <h2>😊 Job Summary</h2>
          <div className="grid">
            <GridItem label="Customer" value={d.customerName} />
            <GridItem label="Address" value={d.address} />
            <GridItem label="Phone" value={d.phone} />
            <GridItem label="ST Job #" value={d.stJob} />
            <GridItem label="Sold By" value={d.soldBy} />
            <GridItem label="Date Sold" value={d.dateSold} />
            <GridItem label="Hours Bid" value={d.hoursBid} />
            <GridItem label="Star Package" value={stars(d.starPkg)} />
            <GridItem label="Amount" value={has(d.pkgAmt) ? `$${formatMoney(parseFloat((d.pkgAmt || '0').replace(/[^0-9.]/g, '')))}` : ''} />
            <GridItem label="Payment" value={d.payMethod} />
            {has(d.financingCo) && <GridItem label="Financing" value={d.financingCo} />}
            <GridItem label="Right to Cancel" value={d.rightToCancel} />
            <GridItem label="40% Deposit" value={d.depositCollected} />
          </div>
        </div>

        {/* Work Details */}
        {(has(d.workType) || has(d.equipment) || has(d.dustContain) || has(d.promises) || has(d.specialTools)) && (
          <div className="section">
            <h2>🔧 Work Details</h2>
            <div className="grid">
              {has(d.workType) && <GridItem label="Type of Work" value={d.workType} />}
              {has(d.equipment) && <GridItem label="Equipment/Material" value={d.equipment} />}
              {has(d.dustContain) && <GridItem label="Dust Containment" value={d.dustContain} />}
              {has(d.promises) && <GridItem label="Promises/Expectations" value={d.promises} />}
              {has(d.specialTools) && <GridItem label="Special Tools" value={d.specialTools} />}
              {has(d.picsTaken) && <GridItem label="Pictures Taken" value={d.picsTaken} />}
              {has(d.videoTaken) && <GridItem label="Video Taken" value={d.videoTaken} />}
            </div>
          </div>
        )}

        {/* Additional Details */}
        {(has(d.returnVisit) || has(d.excavating) || has(d.subcontractor)) && (
          <div className="section">
            <h2>📋 Additional Details</h2>
            <div className="grid">
              {has(d.returnVisit) && <GridItem label="Return Visit" value={d.returnVisit} />}
              {d.returnVisit?.toLowerCase() === 'yes' && has(d.returnWhen) && <GridItem label="When/What Part" value={d.returnWhen} />}
              {has(d.excavating) && <GridItem label="Excavating" value={d.excavating} />}
              {d.excavating?.toLowerCase() === 'yes' && (
                <>
                  {has(d.excavLocation) && <GridItem label="Location" value={d.excavLocation} />}
                  {has(d.excavMarked) && <GridItem label="Area Marked" value={d.excavMarked} />}
                  {has(d.calledOUPS) && <GridItem label="Called OUPS" value={d.calledOUPS} />}
                  {has(d.oupsTicket) && <GridItem label="OUPS Ticket #" value={d.oupsTicket} />}
                </>
              )}
              {has(d.subcontractor) && <GridItem label="Subcontractor Needed" value={d.subcontractor} />}
              {d.subcontractor?.toLowerCase() === 'yes' && (
                <>
                  {has(d.subName) && <GridItem label="Subcontractor" value={d.subName} />}
                  {has(d.subAgreement) && <GridItem label="Agreement Signed" value={d.subAgreement} />}
                </>
              )}
            </div>
          </div>
        )}

        {/* Crew Message */}
        {has(d.crewMsg) && (
          <div className="crew-msg">💪 <em>{d.crewMsg}</em></div>
        )}

        {/* Job Types */}
        {d.jobTypes && d.jobTypes.length > 0 && (
          <>
            {d.jobTypes.map((jt: { name: string; avgTime: string; permit: string }, i: number) => (
              <div key={i} className="job-header">
                <div className="name">{jt.name}</div>
                <div className="meta">⏱️ {jt.avgTime} | 📝 Permit: {jt.permit}</div>
              </div>
            ))}
          </>
        )}

        {/* Pricing Check */}
        {d.pricingCheck && d.pricingCheck.sale > 0 && d.pricingCheck.hours > 0 && (
          <div className="pricing">
            <h2 style={{ marginTop: 0 }}>📊 Pricing Check</h2>
            <div className="row">
              <span className="lb">Sale</span>
              <span className="vl">${formatMoney(d.pricingCheck.sale)}</span>
            </div>
            <div className="row">
              <span className="lb">Hours Bid</span>
              <span className="vl">{d.pricingCheck.hours}</span>
            </div>
            <div className="row">
              <span className="lb">Rate</span>
              <span className="vl">${formatMoney(d.pricingCheck.rate)}/hr</span>
            </div>
            <div className="row">
              <span className="lb">Tier</span>
              <span className="vl" style={{ color: tierInfo(d.pricingCheck.rate).color }}>
                {tierInfo(d.pricingCheck.rate).emoji} {tierInfo(d.pricingCheck.rate).label}
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