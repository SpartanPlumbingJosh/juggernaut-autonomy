'use client';

function moneyExact(n: number | string | null | undefined): string {
  const v = parseFloat(String(n || 0));
  return v > 0 ? '$' + v.toFixed(2) : '\u2014';
}
function money(n: number | string | null | undefined): string {
  const v = parseFloat(String(n || 0));
  return v > 0 ? '$' + v.toLocaleString(undefined, { maximumFractionDigits: 0 }) : '\u2014';
}
function fmt(d: string | null | undefined): string {
  if (!d) return '\u2014';
  try { return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); } catch { return d; }
}

export default function MaterialsTab({ job, data, amt }: { job: any; data: any; amt: number }) {
  const ml = data.materialList;
  const hasList = ml && ml.material_list_json;
  const list = hasList ? ml.material_list_json : { parts: [], tools: [], consumables: [] };
  const parts = list.parts || [];
  const tools = list.tools || [];
  const consumables = list.consumables || [];
  const totalItems = parts.length + tools.length + consumables.length;

  const matCost = parts.reduce((s: number, i: any) => s + (parseFloat(i.est_cost) || 0), 0)
    + tools.reduce((s: number, i: any) => s + (parseFloat(i.est_cost) || 0), 0)
    + consumables.reduce((s: number, i: any) => s + (parseFloat(i.est_cost) || 0), 0);
  const soldAmt = hasList ? parseFloat(ml.sold_amount) || amt : amt;
  const budget18 = soldAmt * 0.18;
  const materialPct = soldAmt > 0 ? (matCost / soldAmt) * 100 : 0;
  const budgetOk = materialPct <= 18;

  if (!hasList) {
    return <>
      <div className="tab-hdr">
        <div className="tab-icon" style={{ background: 'var(--mintbg)', border: '1px solid var(--mintbd)', color: 'var(--mint)' }}>
          <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/>
            <polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>
          </svg>
        </div>
        <div className="tab-info">
          <div className="tab-title">Materials &mdash; Lee Supply</div>
          <div className="tab-desc">AI-generated material list from Lee Supply catalog</div>
        </div>
      </div>
      <div className="empty">
        <div className="empty-icon" style={{ background: 'var(--mintbg)', color: 'var(--mint)' }}>
          <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/>
            <polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>
          </svg>
        </div>
        <div className="empty-title">No materials generated yet</div>
        <div className="empty-desc">AI will generate a material list from the Lee Supply catalog once the job scope is finalized and the sales-to-install pipeline processes this job.</div>
        <div style={{ marginTop: 16, padding: '4px 12px', borderRadius: 20, background: 'var(--s3)', border: '1px solid var(--b2)', fontSize: 10, color: 'var(--t3)', fontWeight: 600 }}>Awaiting AI Generation</div>
      </div>
    </>;
  }

  return <>
    <div className="tab-hdr">
      <div className="tab-icon" style={{ background: 'var(--mintbg)', border: '1px solid var(--mintbd)', color: 'var(--mint)' }}>
        <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/>
          <polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>
        </svg>
      </div>
      <div className="tab-info">
        <div className="tab-title">Materials &mdash; Lee Supply</div>
        <div className="tab-desc">AI-generated material list &middot; {totalItems} items &middot; Generated {fmt(ml.generated_at)}</div>
      </div>
      <div className="tab-badge" style={{ background: budgetOk ? 'var(--mintbg)' : 'var(--firebg)', border: `1px solid ${budgetOk ? 'var(--mintbd)' : 'var(--firebd)'}`, color: budgetOk ? 'var(--mint)' : 'var(--fire)' }}>
        {materialPct.toFixed(1)}% OF REVENUE
      </div>
    </div>

    <div className="hero" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
      <div className="st sf"><div className="num">{money(soldAmt)}</div><div className="lbl">Sale Amount</div></div>
      <div className="st sv"><div className="num">{money(budget18)}</div><div className="lbl">18% Budget</div></div>
      <div className="st sm"><div className="num" style={{ color: budgetOk ? 'var(--mint)' : 'var(--fire)' }}>{moneyExact(matCost)}</div><div className="lbl">Material Cost</div></div>
      <div className="st sg"><div className="num">{totalItems}</div><div className="lbl">Lee Items</div></div>
    </div>

    {/* 18% Budget Gauge */}
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
            {moneyExact(matCost)} of {moneyExact(budget18)} budget
          </span>
          <span>{moneyExact(budget18)}</span>
        </div>
      </div>
    </div>

    {/* Status Row */}
    <div className="g3" style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12, margin: '0 0 16px 0' }}>
      <div className="c"><div className="cb" style={{ textAlign: 'center', padding: '12px' }}>
        <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--volt)' }}>&mdash;</div>
        <div style={{ fontSize: 11, color: 'var(--t3)', marginTop: 2 }}><strong>Ordered</strong> &middot; Sent to Lee</div>
      </div></div>
      <div className="c"><div className="cb" style={{ textAlign: 'center', padding: '12px' }}>
        <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--amber)' }}>&mdash;</div>
        <div style={{ fontSize: 11, color: 'var(--t3)', marginTop: 2 }}><strong>Staged</strong> &middot; In truck</div>
      </div></div>
      <div className="c"><div className="cb" style={{ textAlign: 'center', padding: '12px' }}>
        <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--mint)' }}>&mdash;</div>
        <div style={{ fontSize: 11, color: 'var(--t3)', marginTop: 2 }}><strong>Verified</strong> &middot; Photo confirmed</div>
      </div></div>
    </div>

    {/* Parts */}
    {parts.length > 0 && <div className="c full">
      <div className="ch"><h3>Parts</h3><div className="tg" style={{ background: 'var(--mintbg)', border: '1px solid var(--mintbd)', color: 'var(--mint)' }}>{parts.length}</div></div>
      <div className="cb" style={{ padding: 0 }}>
        <table className="mt"><thead><tr><th style={{ textAlign: 'right' }}>Qty</th><th>Item</th><th>Lee #</th><th style={{ textAlign: 'right' }}>Cost</th></tr></thead><tbody>
          {parts.map((p: any, i: number) => (
            <tr key={i}>
              <td style={{ textAlign: 'right', fontWeight: 600 }}>{p.qty}</td>
              <td style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.item}</td>
              <td style={{ fontFamily: 'var(--mono)', color: 'var(--ice)', fontSize: 11 }}>{p.lee_number || '\u2014'}</td>
              <td style={{ textAlign: 'right', color: 'var(--fire)', fontWeight: 600 }}>{moneyExact(p.est_cost)}</td>
            </tr>
          ))}
          <tr style={{ borderTop: '2px solid var(--b2)', fontWeight: 700 }}>
            <td colSpan={3} style={{ textAlign: 'right', color: 'var(--t2)' }}>Parts Total</td>
            <td style={{ textAlign: 'right', color: budgetOk ? 'var(--mint)' : 'var(--fire)' }}>{moneyExact(parts.reduce((s: number, p: any) => s + (parseFloat(p.est_cost) || 0), 0))}</td>
          </tr>
        </tbody></table>
      </div>
    </div>}

    {/* Tools */}
    {tools.length > 0 && <div className="c full">
      <div className="ch"><h3>Tools</h3><div className="tg" style={{ background: 'var(--voltbg)', border: '1px solid var(--voltbd)', color: 'var(--volt)' }}>{tools.length}</div></div>
      <div className="cb" style={{ padding: 0 }}>
        <table className="mt"><thead><tr><th style={{ textAlign: 'right' }}>Qty</th><th>Item</th><th>Lee #</th><th style={{ textAlign: 'right' }}>Cost</th></tr></thead><tbody>
          {tools.map((t: any, i: number) => (
            <tr key={i}>
              <td style={{ textAlign: 'right', fontWeight: 600 }}>{t.qty}</td>
              <td>{t.item}</td>
              <td style={{ fontFamily: 'var(--mono)', color: 'var(--ice)', fontSize: 11 }}>{t.lee_number || '\u2014'}</td>
              <td style={{ textAlign: 'right' }}>{moneyExact(t.est_cost)}</td>
            </tr>
          ))}
        </tbody></table>
      </div>
    </div>}

    {/* Consumables */}
    {consumables.length > 0 && <div className="c full">
      <div className="ch"><h3>Consumables</h3><div className="tg" style={{ background: 'var(--grapebg)', border: '1px solid var(--grapebd)', color: 'var(--grape)' }}>{consumables.length}</div></div>
      <div className="cb" style={{ padding: 0 }}>
        <table className="mt"><thead><tr><th style={{ textAlign: 'right' }}>Qty</th><th>Item</th><th>Lee #</th><th style={{ textAlign: 'right' }}>Cost</th></tr></thead><tbody>
          {consumables.map((c: any, i: number) => (
            <tr key={i}>
              <td style={{ textAlign: 'right', fontWeight: 600 }}>{c.qty}</td>
              <td>{c.item}</td>
              <td style={{ fontFamily: 'var(--mono)', color: 'var(--ice)', fontSize: 11 }}>{c.lee_number || '\u2014'}</td>
              <td style={{ textAlign: 'right' }}>{moneyExact(c.est_cost)}</td>
            </tr>
          ))}
        </tbody></table>
      </div>
    </div>}

    {/* Generation info */}
    <div style={{ fontSize: 11, color: 'var(--t3)', textAlign: 'center', padding: '8px 0' }}>
      AI-generated from Lee Supply catalog &middot; {ml.ai_model || 'Gemini Flash'} &middot; {fmt(ml.generated_at)}
      {ml.form_confirmed && <span style={{ color: 'var(--mint)', fontWeight: 600 }}> &middot; Confirmed {fmt(ml.confirmed_at)}</span>}
      {!ml.form_confirmed && <span style={{ color: 'var(--amber)', fontWeight: 600 }}> &middot; Awaiting confirmation</span>}
    </div>
  </>;
}