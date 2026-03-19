'use client';

function fmt(d: string | null | undefined): string {
  if (!d) return '\u2014';
  try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); } catch { return d; }
}
function money(n: number | string | null | undefined): string {
  const v = parseFloat(String(n || 0));
  return v > 0 ? '$' + v.toLocaleString(undefined, { maximumFractionDigits: 0 }) : '\u2014';
}
function moneyExact(n: number | string | null | undefined): string {
  const v = parseFloat(String(n || 0));
  return '$' + v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function Icon({ name }: { name: string }) {
  const paths: Record<string, string> = {
    chart: '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
    truck: '<rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>',
    check: '<polyline points="20 6 9 17 4 12"/>',
    dollar: '<line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/>',
  };
  return <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round" dangerouslySetInnerHTML={{ __html: paths[name] || '' }} />;
}

function VR({ dot, k, v, style }: { dot?: string; k: string; v: string; style?: React.CSSProperties }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0', borderBottom: '1px solid var(--b1)' }}>
      {dot && <div className={dot} style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0 }} />}
      <div style={{ flex: 1, fontSize: 12, color: 'var(--t2)' }}>{k}</div>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 600, ...style }}>{v}</div>
    </div>
  );
}

function BudgetGauge({ label, spent, budget }: { label: string; spent: number; budget: number }) {
  const pct = budget > 0 ? Math.min((spent / budget) * 100, 100) : 0;
  const over = spent > budget;
  const color = over ? 'var(--fire)' : pct > 80 ? 'var(--amber)' : 'var(--mint)';
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--t3)', marginBottom: 4 }}>
        <span>{label}</span>
        <span style={{ color, fontWeight: 600 }}>{pct.toFixed(0)}% used</span>
      </div>
      <div style={{ height: 8, borderRadius: 4, background: 'var(--s3)', overflow: 'hidden' }}>
        <div style={{ width: `${Math.min(pct, 100)}%`, height: '100%', borderRadius: 4, background: color, transition: 'width 0.5s' }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--t3)', marginTop: 3 }}>
        <span>Spent: {moneyExact(spent)}</span>
        <span>Budget: {moneyExact(budget)}</span>
      </div>
    </div>
  );
}

interface TimelineEvent { date: string; type: 'invoice' | 'payment' | 'po'; title: string; amount: number; detail?: string; }

export default function FinancialsTab({ job, data, amt, invTotal, paidTotal }: { job: any; data: any; amt: number; invTotal: number; paidTotal: number; }) {
  const invoices = data.invoices || [];
  const payments = data.payments || [];
  const purchaseOrders = data.purchaseOrders || [];
  const outstanding = invTotal - paidTotal;
  const deposit40 = amt * 0.4;
  const materialCost = purchaseOrders.reduce((s: number, po: any) => s + (parseFloat(po.total) || 0), 0);
  const materialBudget = amt * 0.18;
  const materialPct = amt > 0 ? ((materialCost / amt) * 100) : 0;
  const revenue = invoices.reduce((s: number, i: any) => s + (parseFloat(i.sub_total) || 0), 0);
  const profit = revenue - materialCost;
  const margin = revenue > 0 ? ((profit / revenue) * 100) : 0;

  const timeline: TimelineEvent[] = [
    ...invoices.map((inv: any) => ({ date: inv.invoice_date || inv.created_on || '', type: 'invoice' as const, title: `Invoice ${inv.reference_number || inv.st_invoice_id}`, amount: parseFloat(inv.total) || 0, detail: `Subtotal: ${moneyExact(inv.sub_total)} + Tax: ${moneyExact(inv.sales_tax)}` })),
    ...payments.map((p: any) => ({ date: p.payment_date || '', type: 'payment' as const, title: `Payment \u2014 ${p.payment_type || 'Unknown'}`, amount: parseFloat(p.total) || 0, detail: p.memo || undefined })),
    ...purchaseOrders.map((po: any) => ({ date: po.po_date || po.created_on || '', type: 'po' as const, title: `PO ${po.po_number || po.st_po_id}`, amount: parseFloat(po.total) || 0, detail: `Status: ${po.status || 'Unknown'}${po.items?.length ? ` \u2022 ${po.items.length} item${po.items.length > 1 ? 's' : ''}` : ''}` })),
  ].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

  const typeColor: Record<string, { bg: string; bd: string; fg: string; icon: string }> = {
    invoice: { bg: 'var(--firebg)', bd: 'var(--firebd)', fg: 'var(--fire)', icon: 'dollar' },
    payment: { bg: 'var(--mintbg)', bd: 'var(--mintbd)', fg: 'var(--mint)', icon: 'check' },
    po: { bg: 'var(--icebg)', bd: 'var(--icebd)', fg: 'var(--ice)', icon: 'truck' },
  };

  const mmChecks = [
    { label: 'All invoices created', pass: invoices.length > 0 },
    { label: '40% deposit collected', pass: paidTotal >= deposit40 },
    { label: 'Payment collected in full', pass: outstanding <= 0 && invTotal > 0 },
    { label: 'Material cost under 18%', pass: materialCost > 0 ? materialCost <= materialBudget : null },
    { label: 'PO documented', pass: purchaseOrders.length > 0 ? true : null },
    { label: 'Profit margin positive', pass: revenue > 0 ? profit > 0 : null },
  ];

  return <>
    <div className="tab-hdr">
      <div className="tab-icon" style={{ background: 'var(--firebg)', border: '1px solid var(--firebd)', color: 'var(--fire)' }}><Icon name="chart" /></div>
      <div className="tab-info"><div className="tab-title">Financials</div><div className="tab-desc">Deposits &middot; PO Costs &middot; Profitability &middot; Money Manager</div></div>
    </div>
    <div className="hero" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
      <div className="st sf"><div className="ai ai-ok" /><div className="num">{money(amt)}</div><div className="lbl">Total Sale</div></div>
      <div className="st sv"><div className="ai ai-ok" /><div className="num">{money(invTotal)}</div><div className="lbl">Invoiced</div></div>
      <div className="st sm"><div className="ai ai-ok" /><div className="num" style={{ color: paidTotal >= deposit40 ? 'var(--mint)' : 'var(--fire)' }}>{money(paidTotal)}</div><div className="lbl">Paid</div></div>
    </div>
    <div className="hero" style={{ gridTemplateColumns: 'repeat(3,1fr)', marginTop: 0 }}>
      <div className="st sg"><div className="num" style={{ color: outstanding <= 0 ? 'var(--mint)' : 'var(--fire)' }}>{money(outstanding > 0 ? outstanding : 0)}</div><div className="lbl">Outstanding</div></div>
      <div className="st" style={{ background: 'var(--icebg)', border: '1px solid var(--icebd)' }}><div className="num" style={{ color: materialCost <= materialBudget ? 'var(--ice)' : 'var(--fire)' }}>{money(materialCost)}</div><div className="lbl" style={{ color: 'var(--ice)' }}>Material Cost</div></div>
      <div className="st" style={{ background: profit > 0 ? 'var(--mintbg)' : 'var(--firebg)', border: `1px solid ${profit > 0 ? 'var(--mintbd)' : 'var(--firebd)'}` }}><div className="num" style={{ color: profit > 0 ? 'var(--mint)' : 'var(--fire)' }}>{money(Math.abs(profit))}</div><div className="lbl" style={{ color: profit > 0 ? 'var(--mint)' : 'var(--fire)' }}>{profit >= 0 ? 'Est. Profit' : 'Est. Loss'}</div></div>
    </div>
    <div className="c full"><div className="ch"><h3>Invoices</h3><div className="tg" style={{ background: 'var(--firebg)', border: '1px solid var(--firebd)', color: 'var(--fire)' }}>{invoices.length}</div></div>
      {invoices.length > 0 ? <div className="cb" style={{ padding: 0 }}><table className="mt"><thead><tr><th>Invoice</th><th>Date</th><th>Subtotal</th><th>Tax</th><th>Total</th><th>Balance</th></tr></thead><tbody>
        {invoices.map((inv: any, i: number) => <tr key={i}><td style={{ fontFamily: 'var(--mono)', color: 'var(--ice)' }}>{inv.reference_number || inv.st_invoice_id}</td><td>{fmt(inv.invoice_date)}</td><td>{moneyExact(inv.sub_total)}</td><td>{moneyExact(inv.sales_tax)}</td><td style={{ color: 'var(--t1)' }}>{moneyExact(inv.total)}</td><td style={{ color: parseFloat(inv.balance) > 0 ? 'var(--fire)' : 'var(--mint)' }}>{moneyExact(inv.balance)}</td></tr>)}
      </tbody></table></div> : <div className="cb" style={{ color: 'var(--t3)', fontSize: 12 }}>No invoices found.</div>}
    </div>
    <div className="c full"><div className="ch"><h3>Payments</h3><div className="tg" style={{ background: 'var(--mintbg)', border: '1px solid var(--mintbd)', color: 'var(--mint)' }}>{payments.length}</div></div>
      {payments.length > 0 ? <div className="cb" style={{ padding: 0 }}><table className="mt"><thead><tr><th>Payment</th><th>Type</th><th>Amount</th><th>Date</th><th>Memo</th></tr></thead><tbody>
        {payments.map((p: any, i: number) => <tr key={i}><td style={{ fontFamily: 'var(--mono)', color: 'var(--ice)' }}>{p.st_payment_id}</td><td>{p.payment_type || '\u2014'}</td><td style={{ color: 'var(--mint)' }}>{moneyExact(p.total)}</td><td>{fmt(p.payment_date)}</td><td>{p.memo || '\u2014'}</td></tr>)}
      </tbody></table></div> : <div className="cb" style={{ color: 'var(--t3)', fontSize: 12 }}>No payments linked.</div>}
    </div>
    <div className="c full"><div className="ch"><h3>Purchase Orders</h3><div className="tg" style={{ background: 'var(--icebg)', border: '1px solid var(--icebd)', color: 'var(--ice)' }}>{purchaseOrders.length}</div></div>
      {purchaseOrders.length > 0 ? <div className="cb" style={{ padding: 0 }}><table className="mt"><thead><tr><th>PO #</th><th>Date</th><th>Status</th><th>Items</th><th>Total</th></tr></thead><tbody>
        {purchaseOrders.map((po: any, i: number) => { const itemCount = po.items?.length || 0; const statusColor = po.status === 'Received' ? 'var(--mint)' : po.status === 'Pending' ? 'var(--amber)' : 'var(--t2)'; return <tr key={i}><td style={{ fontFamily: 'var(--mono)', color: 'var(--ice)' }}>{po.po_number || po.st_po_id}</td><td>{fmt(po.po_date)}</td><td><span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 10, fontWeight: 600, background: `${statusColor}15`, color: statusColor }}>{po.status || '\u2014'}</span></td><td style={{ textAlign: 'center' }}>{itemCount}</td><td style={{ fontFamily: 'var(--mono)', fontWeight: 600, color: 'var(--t1)' }}>{moneyExact(po.total)}</td></tr>; })}
      </tbody></table></div> : <div className="cb" style={{ color: 'var(--t3)', fontSize: 12 }}>No purchase orders for this job.</div>}
    </div>
    <div className="g2">
      <div className="c"><div className="ch"><h3>Deposit Tracking</h3></div><div className="cb">
        <VR dot={paidTotal >= deposit40 ? 'ai-ok' : 'ai-fail'} k="40% Required" v={moneyExact(deposit40)} />
        <VR dot={paidTotal >= deposit40 ? 'ai-ok' : 'ai-fail'} k="Collected" v={moneyExact(paidTotal)} style={{ color: paidTotal >= deposit40 ? 'var(--mint)' : 'var(--fire)' }} />
        <div style={{ marginTop: 8 }}><BudgetGauge label="Deposit Progress" spent={paidTotal} budget={deposit40} /></div>
      </div></div>
      <div className="c"><div className="ch"><h3>18% Material Budget</h3></div><div className="cb">
        <VR dot={materialCost > 0 && materialCost <= materialBudget ? 'ai-ok' : materialCost > materialBudget ? 'ai-fail' : 'ai-wait'} k="Budget Cap (18%)" v={moneyExact(materialBudget)} />
        <VR dot={materialCost > 0 ? (materialCost <= materialBudget ? 'ai-ok' : 'ai-fail') : 'ai-wait'} k="PO Material Spend" v={materialCost > 0 ? moneyExact(materialCost) : 'No POs'} style={{ color: materialCost > materialBudget ? 'var(--fire)' : materialCost > 0 ? 'var(--mint)' : 'var(--t3)' }} />
        <VR k="Material %" v={materialCost > 0 && amt > 0 ? `${materialPct.toFixed(1)}%` : '\u2014'} style={{ color: materialPct > 18 ? 'var(--fire)' : materialPct > 14 ? 'var(--amber)' : 'var(--mint)' }} />
        {materialCost > 0 && <div style={{ marginTop: 8 }}><BudgetGauge label="Material Budget" spent={materialCost} budget={materialBudget} /></div>}
      </div></div>
    </div>
    <div className="c full"><div className="ch"><h3>Profitability</h3></div><div className="cb">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 12 }}>
        <div style={{ textAlign: 'center' }}><div style={{ fontSize: 10, color: 'var(--t3)', fontWeight: 600, textTransform: 'uppercase' as const, letterSpacing: 1 }}>Revenue</div><div style={{ fontFamily: 'var(--mono)', fontSize: 18, fontWeight: 700, color: 'var(--t1)', marginTop: 4 }}>{moneyExact(revenue)}</div></div>
        <div style={{ textAlign: 'center' }}><div style={{ fontSize: 10, color: 'var(--t3)', fontWeight: 600, textTransform: 'uppercase' as const, letterSpacing: 1 }}>Material</div><div style={{ fontFamily: 'var(--mono)', fontSize: 18, fontWeight: 700, color: 'var(--ice)', marginTop: 4 }}>{moneyExact(materialCost)}</div></div>
        <div style={{ textAlign: 'center' }}><div style={{ fontSize: 10, color: 'var(--t3)', fontWeight: 600, textTransform: 'uppercase' as const, letterSpacing: 1 }}>Est. Profit</div><div style={{ fontFamily: 'var(--mono)', fontSize: 18, fontWeight: 700, color: profit >= 0 ? 'var(--mint)' : 'var(--fire)', marginTop: 4 }}>{moneyExact(profit)}</div></div>
        <div style={{ textAlign: 'center' }}><div style={{ fontSize: 10, color: 'var(--t3)', fontWeight: 600, textTransform: 'uppercase' as const, letterSpacing: 1 }}>Margin</div><div style={{ fontFamily: 'var(--mono)', fontSize: 18, fontWeight: 700, color: margin >= 82 ? 'var(--mint)' : margin >= 70 ? 'var(--amber)' : 'var(--fire)', marginTop: 4 }}>{revenue > 0 ? `${margin.toFixed(1)}%` : '\u2014'}</div></div>
      </div>
      {revenue > 0 && <div style={{ fontSize: 10, color: 'var(--t3)', textAlign: 'center', fontStyle: 'italic' }}>Based on invoice subtotals minus PO costs. Does not include labor.</div>}
    </div></div>
    <div className="c full"><div className="ch"><h3>Money Manager Review</h3><span style={{ fontSize: 10, color: 'var(--t3)', fontWeight: 500 }}>Post-close checklist</span></div><div className="cb">
      {mmChecks.map((item, i) => { const dotClass = item.pass === true ? 'ai-ok' : item.pass === false ? 'ai-fail' : 'ai-wait'; return (<div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', borderBottom: i < mmChecks.length - 1 ? '1px solid var(--b1)' : 'none' }}><div className={dotClass} style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0 }} /><div style={{ flex: 1, fontSize: 12, color: 'var(--t2)' }}>{item.label}</div><div style={{ fontSize: 11, fontWeight: 600, color: item.pass === true ? 'var(--mint)' : item.pass === false ? 'var(--fire)' : 'var(--t3)' }}>{item.pass === true ? 'PASS' : item.pass === false ? 'FAIL' : 'N/A'}</div></div>); })}
    </div></div>
    {timeline.length > 0 && <div className="c full"><div className="ch"><h3>Financial Timeline</h3></div><div className="cb" style={{ padding: '8px 12px' }}>
      {timeline.map((evt, i) => { const tc = typeColor[evt.type]; return (<div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: '8px 0', borderBottom: i < timeline.length - 1 ? '1px solid var(--b1)' : 'none' }}><div style={{ width: 28, height: 28, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', background: tc.bg, border: `1px solid ${tc.bd}`, color: tc.fg, flexShrink: 0 }}><Icon name={tc.icon} /></div><div style={{ flex: 1, minWidth: 0 }}><div style={{ fontSize: 12, fontWeight: 600, color: 'var(--t1)' }}>{evt.title}</div>{evt.detail && <div style={{ fontSize: 10, color: 'var(--t3)', marginTop: 2 }}>{evt.detail}</div>}</div><div style={{ textAlign: 'right', flexShrink: 0 }}><div style={{ fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 600, color: tc.fg }}>{moneyExact(evt.amount)}</div><div style={{ fontSize: 9, color: 'var(--t3)' }}>{fmt(evt.date)}</div></div></div>); })}
    </div></div>}
  </>;
}
