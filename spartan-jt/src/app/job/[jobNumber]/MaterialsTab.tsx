'use client';

interface EstimateItem {
  id: number;
  qty: number;
  total: number;
  unitCost: number;
  unitRate: number;
  totalCost: number;
  description: string;
  sku?: { name: string; type: string; displayName: string };
}

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
  return v > 0 ? '$' + v.toFixed(2) : '\u2014';
}

export default function MaterialsTab({ job, data, amt }: { job: any; data: any; amt: number }) {
  const estimates = (data.estimates || []) as any[];
  const budget18 = amt * 0.18;

  const allItems: EstimateItem[] = [];
  estimates.forEach((est: any) => {
    const items = Array.isArray(est.items) ? est.items : [];
    items.forEach((item: any) => allItems.push(item));
  });

  const materials = allItems.filter(i => i.sku?.type === 'Material');
  const services = allItems.filter(i => i.sku?.type === 'Service');
  const totalMaterialCost = materials.reduce((s, i) => s + (i.totalCost || 0), 0);
  const totalServiceRevenue = services.reduce((s, i) => s + (i.total || 0), 0);
  const materialPct = amt > 0 ? ((totalMaterialCost / amt) * 100) : 0;
  const budgetOk = materialPct <= 18;

  return <>
    <div className="tab-hdr">
      <div className="tab-icon" style={{ background: 'var(--mintbg)', border: '1px solid var(--mintbd)', color: 'var(--mint)' }}>
        <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/>
          <polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>
        </svg>
      </div>
      <div className="tab-info">
        <div className="tab-title">Materials</div>
        <div className="tab-desc">Estimate line items, material costs, and 18% budget tracking</div>
      </div>
      <div className="tab-badge" style={{ background: budgetOk ? 'var(--mintbg)' : 'var(--firebg)', border: `1px solid ${budgetOk ? 'var(--mintbd)' : 'var(--firebd)'}`, color: budgetOk ? 'var(--mint)' : 'var(--fire)' }}>
        {materialPct.toFixed(1)}% MATERIAL
      </div>
    </div>

    <div className="hero" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
      <div className="st sf"><div className="num">{money(amt)}</div><div className="lbl">Sale Amount</div></div>
      <div className="st sv"><div className="num">{money(budget18)}</div><div className="lbl">18% Budget</div></div>
      <div className="st sm"><div className="num" style={{ color: budgetOk ? 'var(--mint)' : 'var(--fire)' }}>{moneyExact(totalMaterialCost)}</div><div className="lbl">Material Cost</div></div>
      <div className="st sg"><div className="num">{money(totalServiceRevenue)}</div><div className="lbl">Service Revenue</div></div>
    </div>

    <div className="c full">
      <div className="ch"><h3>18% Material Budget</h3></div>
      <div className="cb">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          <div style={{ flex: 1, height: 8, borderRadius: 4, background: 'var(--s3)', overflow: 'hidden' }}>
            <div style={{ width: `${Math.min(materialPct / 18 * 100, 100)}%`, height: '100%', borderRadius: 4, background: budgetOk ? 'var(--mint)' : 'var(--fire)', transition: 'width 0.3s' }} />
          </div>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 700, color: budgetOk ? 'var(--mint)' : 'var(--fire)' }}>
            {materialPct.toFixed(1)}%
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--t3)' }}>
          <span>$0</span>
          <span style={{ color: budgetOk ? 'var(--mint)' : 'var(--fire)', fontWeight: 600 }}>
            {moneyExact(totalMaterialCost)} of {moneyExact(budget18)} used
          </span>
          <span>{moneyExact(budget18)}</span>
        </div>
      </div>
    </div>

    {estimates.length > 0 && <div className="c full">
      <div className="ch"><h3>Estimates</h3><div className="tg" style={{ background: 'var(--mintbg)', border: '1px solid var(--mintbd)', color: 'var(--mint)' }}>{estimates.length}</div></div>
      <div className="cb" style={{ padding: 0 }}>
        <table className="mt"><thead><tr><th>Estimate</th><th>Status</th><th>Sold By</th><th>Sold On</th><th>Subtotal</th></tr></thead><tbody>
          {estimates.map((est: any, i: number) => (
            <tr key={i}>
              <td style={{ fontFamily: 'var(--mono)', color: 'var(--ice)' }}>{est.estimate_name || est.st_estimate_id}</td>
              <td><span className={`chip ${est.status_name === 'Sold' ? 'c-ok' : est.status_name === 'Open' ? 'c-info' : 'c-fail'}`}>{est.status_name}</span></td>
              <td>{est.sold_by_name || '\u2014'}</td>
              <td>{fmt(est.sold_on)}</td>
              <td style={{ color: 'var(--t1)' }}>{moneyExact(est.subtotal)}</td>
            </tr>
          ))}
        </tbody></table>
      </div>
    </div>}

    <div className="c full">
      <div className="ch"><h3>Materials</h3><div className="tg" style={{ background: 'var(--voltbg)', border: '1px solid var(--voltbd)', color: 'var(--volt)' }}>{materials.length}</div></div>
      {materials.length > 0 ? <div className="cb" style={{ padding: 0 }}>
        <table className="mt"><thead><tr><th>Item</th><th>SKU</th><th style={{ textAlign: 'right' }}>Qty</th><th style={{ textAlign: 'right' }}>Unit Cost</th><th style={{ textAlign: 'right' }}>Total Cost</th></tr></thead><tbody>
          {materials.map((item, i) => (
            <tr key={i}>
              <td style={{ maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.sku?.displayName || item.description}</td>
              <td style={{ fontFamily: 'var(--mono)', color: 'var(--ice)', fontSize: 11 }}>{item.sku?.name || '\u2014'}</td>
              <td style={{ textAlign: 'right' }}>{item.qty}</td>
              <td style={{ textAlign: 'right' }}>{moneyExact(item.unitCost)}</td>
              <td style={{ textAlign: 'right', color: 'var(--fire)', fontWeight: 600 }}>{moneyExact(item.totalCost)}</td>
            </tr>
          ))}
          <tr style={{ borderTop: '2px solid var(--b2)', fontWeight: 700 }}>
            <td colSpan={4} style={{ textAlign: 'right', color: 'var(--t2)' }}>Total Material Cost</td>
            <td style={{ textAlign: 'right', color: budgetOk ? 'var(--mint)' : 'var(--fire)' }}>{moneyExact(totalMaterialCost)}</td>
          </tr>
        </tbody></table>
      </div> : <div className="cb" style={{ color: 'var(--t3)', fontSize: 12 }}>No material line items found on estimates.</div>}
    </div>

    <div className="c full">
      <div className="ch"><h3>Service Line Items</h3><div className="tg" style={{ background: 'var(--grapebg)', border: '1px solid var(--grapebd)', color: 'var(--grape)' }}>{services.length}</div></div>
      {services.length > 0 ? <div className="cb" style={{ padding: 0 }}>
        <table className="mt"><thead><tr><th>Service</th><th>SKU</th><th style={{ textAlign: 'right' }}>Qty</th><th style={{ textAlign: 'right' }}>Rate</th><th style={{ textAlign: 'right' }}>Total</th></tr></thead><tbody>
          {services.map((item, i) => (
            <tr key={i}>
              <td style={{ maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.sku?.displayName || item.description}</td>
              <td style={{ fontFamily: 'var(--mono)', color: 'var(--ice)', fontSize: 11 }}>{item.sku?.name || '\u2014'}</td>
              <td style={{ textAlign: 'right' }}>{item.qty}</td>
              <td style={{ textAlign: 'right' }}>{moneyExact(item.unitRate)}</td>
              <td style={{ textAlign: 'right', color: 'var(--mint)', fontWeight: 600 }}>{moneyExact(item.total)}</td>
            </tr>
          ))}
          <tr style={{ borderTop: '2px solid var(--b2)', fontWeight: 700 }}>
            <td colSpan={4} style={{ textAlign: 'right', color: 'var(--t2)' }}>Total Service Revenue</td>
            <td style={{ textAlign: 'right', color: 'var(--mint)' }}>{moneyExact(totalServiceRevenue)}</td>
          </tr>
        </tbody></table>
      </div> : <div className="cb" style={{ color: 'var(--t3)', fontSize: 12 }}>No service line items found on estimates.</div>}
    </div>

    {estimates.length === 0 && <div style={{ color: 'var(--t3)', fontSize: 12, padding: 20, textAlign: 'center' }}>No estimates found for this job.</div>}
  </>;
}