'use client';
import { useState } from 'react';

function $(n: number | string | null | undefined): string {
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

function ProductImage({ src, alt }: { src?: string; alt: string }) {
  const [err, setErr] = useState(false);
  const [expanded, setExpanded] = useState(false);

  if (!src || err) {
    return <div style={{ width: 64, height: 64, borderRadius: 8, background: 'var(--s3)', border: '1px solid var(--b2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--t3)', flexShrink: 0 }}>
      <svg fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24" width="24" height="24"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/></svg>
    </div>;
  }

  return <>
    <img
      src={src} alt={alt} onError={() => setErr(true)}
      onClick={() => setExpanded(true)}
      style={{ width: 64, height: 64, borderRadius: 8, objectFit: 'contain', background: '#fff', border: '1px solid var(--b2)', flexShrink: 0, cursor: 'pointer', transition: 'transform 0.15s' }}
      onMouseOver={e => (e.currentTarget.style.transform = 'scale(1.1)')}
      onMouseOut={e => (e.currentTarget.style.transform = 'scale(1)')}
    />
    {expanded && <div onClick={() => setExpanded(false)} style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 9999,
      background: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center',
      cursor: 'pointer'
    }}>
      <img src={src} alt={alt} style={{ maxWidth: '80vw', maxHeight: '80vh', borderRadius: 12, background: '#fff', boxShadow: '0 20px 60px rgba(0,0,0,0.5)' }} />
      <div style={{ position: 'absolute', top: 20, right: 20, color: '#fff', fontSize: 24, fontWeight: 700 }}>{'\u2715'}</div>
    </div>}
  </>;
}

function ItemCard({ item, images, num }: { item: any; images: Record<string, string>; num: number }) {
  const imgUrl = item.lee_number ? images[item.lee_number] : undefined;
  const cost = parseFloat(item.est_cost) || 0;

  return (
    <div style={{ display: 'flex', gap: 14, padding: '14px 16px', borderBottom: '1px solid var(--b1)', alignItems: 'flex-start' }}>
      <div style={{ position: 'relative' }}>
        <ProductImage src={imgUrl} alt={item.item || ''} />
        <div style={{
          position: 'absolute', top: -4, left: -4, width: 20, height: 20, borderRadius: 10,
          background: 'var(--s2)', border: '1px solid var(--b2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 9, fontWeight: 700, color: 'var(--t3)'
        }}>{num}</div>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--t1)', lineHeight: 1.3, marginBottom: 3 }}>
          {item.item}
        </div>
        {item.lee_number && <div style={{ fontSize: 11, color: 'var(--ice)', marginBottom: 4 }}>
          Lee Supply #{item.lee_number}
        </div>}
        {item.notes && <div style={{ fontSize: 12, color: 'var(--t3)', lineHeight: 1.4 }}>
          {item.notes}
        </div>}
      </div>
      <div style={{ textAlign: 'right', flexShrink: 0, minWidth: 60 }}>
        <div style={{ fontSize: 11, color: 'var(--t3)', marginBottom: 2 }}>Qty: {item.qty}</div>
        {cost > 0 && <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--t1)' }}>{$(cost)}</div>}
      </div>
    </div>
  );
}

export default function MaterialsTab({ job, data, amt }: { job: any; data: any; amt: number }) {
  const ml = data.materialList;
  const images: Record<string, string> = data.catalogImages || {};
  const hasList = ml && ml.material_list_json;
  const list = hasList ? ml.material_list_json : { parts: [], tools: [] };
  const parts = list.parts || [];
  const tools = list.tools || [];
  const totalItems = parts.length + tools.length;

  const matCost = [...parts, ...tools].reduce((s: number, i: any) => s + (parseFloat(i.est_cost) || 0), 0);
  const soldAmt = hasList ? parseFloat(ml.sold_amount) || amt : amt;
  const materialPct = soldAmt > 0 ? (matCost / soldAmt) * 100 : 0;

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
          <div className="tab-title">Materials</div>
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
        <div className="empty-title">No materials yet</div>
        <div className="empty-desc">The material list will be generated automatically when a sale is processed.</div>
        <div style={{ marginTop: 16, padding: '4px 12px', borderRadius: 20, background: 'var(--s3)', border: '1px solid var(--b2)', fontSize: 10, color: 'var(--t3)', fontWeight: 600 }}>Waiting for sale</div>
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
        <div className="tab-title">Materials</div>
        <div className="tab-desc">{totalItems} items from Lee Supply &middot; Generated {fmt(ml.generated_at)}</div>
      </div>
    </div>

    {/* Summary Bar */}
    <div className="hero" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
      <div className="st" style={{ background: 'var(--s3)', border: '1px solid var(--b2)' }}>
        <div className="num" style={{ fontSize: 28 }}>{totalItems}</div>
        <div className="lbl">Items</div>
      </div>
      <div className="st" style={{ background: 'var(--s3)', border: '1px solid var(--b2)' }}>
        <div className="num" style={{ fontSize: 28, color: 'var(--t1)' }}>{$(matCost)}</div>
        <div className="lbl">Material Cost</div>
      </div>
      <div className="st" style={{ background: 'var(--s3)', border: '1px solid var(--b2)' }}>
        <div className="num" style={{ fontSize: 28, color: materialPct <= 18 ? 'var(--mint)' : 'var(--fire)' }}>
          {materialPct.toFixed(1)}%
        </div>
        <div className="lbl">of {money(soldAmt)} job</div>
      </div>
    </div>

    {/* Material Cost Bar */}
    <div style={{ padding: '0 0 16px 0' }}>
      <div style={{ height: 6, borderRadius: 3, background: 'var(--s3)', overflow: 'hidden' }}>
        <div style={{
          width: `${Math.min(materialPct / 25 * 100, 100)}%`,
          height: '100%', borderRadius: 3,
          background: materialPct <= 18 ? 'var(--mint)' : 'var(--fire)',
          transition: 'width 0.3s'
        }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 10, color: 'var(--t3)' }}>
        <span>{$(matCost)} material cost</span>
        <span>{materialPct.toFixed(1)}% of {money(soldAmt)} job revenue</span>
      </div>
    </div>

    {/* Parts List */}
    {parts.length > 0 && <div className="c full">
      <div className="ch"><h3>Parts</h3><div className="tg" style={{ background: 'var(--mintbg)', border: '1px solid var(--mintbd)', color: 'var(--mint)' }}>{parts.length}</div></div>
      <div className="cb" style={{ padding: 0 }}>
        {parts.map((p: any, i: number) => <ItemCard key={i} item={p} images={images} num={i + 1} />)}
        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '12px 16px', borderTop: '2px solid var(--b2)' }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--t2)' }}>Parts Total ({parts.length} items)</span>
          <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--t1)' }}>
            {$(parts.reduce((s: number, p: any) => s + (parseFloat(p.est_cost) || 0), 0))}
          </span>
        </div>
      </div>
    </div>}

    {/* Tools */}
    {tools.length > 0 && <div className="c full">
      <div className="ch"><h3>Specialty Tools</h3><div className="tg" style={{ background: 'var(--voltbg)', border: '1px solid var(--voltbd)', color: 'var(--volt)' }}>{tools.length}</div></div>
      <div className="cb" style={{ padding: 0 }}>
        {tools.map((t: any, i: number) => <ItemCard key={i} item={t} images={images} num={i + 1} />)}
      </div>
    </div>}

    {/* Footer */}
    <div style={{ fontSize: 11, color: 'var(--t3)', textAlign: 'center', padding: '12px 0' }}>
      Generated by AI ({ml.ai_model || 'Sonnet 4.6'}) from Lee Supply catalog &middot; {fmt(ml.generated_at)}
      {ml.form_confirmed && <span style={{ color: 'var(--mint)', fontWeight: 600 }}> &middot; Confirmed {fmt(ml.confirmed_at)}</span>}
      {!ml.form_confirmed && <span style={{ color: 'var(--amber)', fontWeight: 600 }}> &middot; Awaiting confirmation</span>}
    </div>
  </>;
}
