import { NextResponse } from 'next/server';
import { query } from '@/lib/supabase';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const requests = await query(`
      SELECT cr.id, cr.st_job_id, cr.channel_id, cr.requested_by, cr.requested_by_name,
             cr.requested_at, cr.vendor_name, cr.purchase_description, cr.amount,
             cr.responded_by, cr.responded_at, cr.response_time_seconds,
             cr.card_issued, cr.receipt_posted, cr.receipt_url, cr.receipt_message_ts,
             cr.receipt_ai_pass, cr.receipt_ai_notes, cr.reconciled, cr.mismatch_flagged,
             cr.created_at,
             j.job_number, c.name as customer_name,
             COALESCE(j.business_unit_name, bu.name) as business_unit_name,
             btc.channel_name
      FROM spartan_ops.job_card_requests cr
      LEFT JOIN spartan_ops.st_jobs_v2 j ON j.st_job_id = cr.st_job_id
      LEFT JOIN spartan_ops.st_customers_v2 c ON c.st_customer_id = j.st_customer_id
      LEFT JOIN spartan_ops.st_business_units bu ON bu.st_bu_id = j.st_business_unit_id
      LEFT JOIN spartan_ops.bookmark_tracked_channels btc ON btc.channel_id = cr.channel_id
      ORDER BY cr.requested_at DESC
      LIMIT 200
    `);

    // Compute stats
    const total = requests.length;
    const withReceipt = requests.filter((r: any) => r.receipt_posted).length;
    const missing = total - withReceipt;
    const totalSpend = requests.reduce((s: number, r: any) => s + (parseFloat(r.amount) || 0), 0);
    const mismatches = requests.filter((r: any) => r.mismatch_flagged).length;

    // Compute average receipt time (only for those with receipts)
    const receiptTimes: number[] = [];
    for (const r of requests as any[]) {
      if (r.receipt_posted && r.receipt_message_ts && r.requested_at) {
        const reqTime = new Date(r.requested_at).getTime() / 1000;
        const receiptTs = parseFloat(r.receipt_message_ts);
        if (receiptTs > reqTime) {
          receiptTimes.push(receiptTs - reqTime);
        }
      }
    }
    const avgReceiptSeconds = receiptTimes.length > 0
      ? Math.round(receiptTimes.reduce((a, b) => a + b, 0) / receiptTimes.length)
      : null;

    // Per-person breakdown
    const byPerson: Record<string, { total: number; receipts: number; spend: number; missing: number }> = {};
    for (const r of requests as any[]) {
      const name = r.requested_by_name || r.requested_by || 'Unknown';
      if (!byPerson[name]) byPerson[name] = { total: 0, receipts: 0, spend: 0, missing: 0 };
      byPerson[name].total++;
      byPerson[name].spend += parseFloat(r.amount) || 0;
      if (r.receipt_posted) byPerson[name].receipts++;
      else byPerson[name].missing++;
    }

    return NextResponse.json({
      requests,
      stats: { total, withReceipt, missing, totalSpend, mismatches, avgReceiptSeconds },
      byPerson,
    });
  } catch (err) {
    console.error('Cards API error:', err);
    return NextResponse.json(
      { error: 'Failed to fetch card requests', detail: String(err) },
      { status: 500 }
    );
  }
}