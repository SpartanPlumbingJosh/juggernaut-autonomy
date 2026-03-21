'use client';

import { useEffect, useState, useMemo, useCallback } from 'react';
import Link from 'next/link';

interface JobDetail { st_job_id: string; job_number: string; customer_name: string; bu_name: string; revenue: number; status: string; scope: string; }
interface Summary { total_crew_days: number; actual_revenue: number; target_revenue: number; total_gap: number; avg_per_day: number; efficiency_pct: number; at_target: number; near_target: number; under_target: number; zero_days: number; }
interface TechRow { technician_name: string; crew_days: number; avg_daily: number; min_day: number; max_day: number; total_rev: number; at_target: number; near_target: number; critical: number; zero_days: number; hit_pct: number; gap_to_target: number; }
interface DailyRow { technician_name: string; work_date: string; jobs: number; day_revenue: number; job_details: JobDetail[]; }
interface ViolationRow { st_job_id: string; status: string; business_unit_name: string; work_date: string; technician_name: string; project_id: string | null; summary: string; customer_name: string; }
interface MonthlyRow { month: string; crew_days: number; avg_daily: number; total_rev: number; at_target: number; zero_days: number; efficiency_pct: number; zero_rev_potential: number; }
interface UtilRow { tech: string; weekdays_available: number; install_days: number; idle_weekdays: number; utilization_pct: number; }
interface Data { dailyRevenue: DailyRow[]; techSummary: TechRow[]; chunkingViolations: ViolationRow[]; summary: Summary; monthlyTrend: MonthlyRow[]; utilization: UtilRow[]; }

const T=8824;
function fmt(n:number|null|undefined):string{if(n==null||isNaN(Number(n)))return'$0';return'$'+Number(n).toLocaleString('en-US',{maximumFractionDigits:0})}
function fmtK(n:number):string{if(n>=1e6)return'$'+(n/1e6).toFixed(1)+'M';if(n>=1e3)return'$'+Math.round(n/1e3)+'K';return fmt(n)}
function pct(n:number|null|undefined):string{if(n==null||isNaN(Number(n)))return'0%';return Number(n).toFixed(1)+'%'}
function dC(r:number):string{if(r>=T)return'var(--mint)';if(r>=5000)return'var(--amber)';if(r>0)return'var(--fire)';return'var(--t4)'}
function dB(r:number):'at'|'near'|'critical'|'zero'{if(r>=T)return'at';if(r>=5000)return'near';if(r>0)return'critical';return'zero'}
function dCl(r:number):string{if(r>=T)return'sm';if(r>=5000)return'sv';if(r>0)return'sf';return''}
function mL(d:string):string{return new Date(d+'-01T00:00:00').toLocaleDateString('en-US',{month:'short',year:'2-digit'})}
function dL(d:string):string{return new Date(d+'T00:00:00').toLocaleDateString('en-US',{weekday:'short',month:'short',day:'numeric'})}
function sB(name:string):string{return(name||'').replace(/Dayton - (Plumbing|Drain) - /g,'').replace('Replacement ','').replace('Drain ','')}

export default function EfficiencyClient(){
  const[data,setData]=useState<Data|null>(null);const[err,setErr]=useState('');const[tab,setTab]=useState(0);const[loading,setLoading]=useState(true);
  const y=new Date().getFullYear();const[fr,sFr]=useState(`${y}-01-01`);const[to,sTo]=useState(`${y}-12-31`);const[tf,sTf]=useState<string>('all');
  const fetchData=useCallback(()=>{setLoading(true);setErr('');fetch(`/api/analytics/efficiency?from=${fr}&to=${to}`).then(r=>r.json()).then(d=>{if(d.error)setErr(d.error);else setData(d)}).catch(e=>setErr(String(e))).finally(()=>setLoading(false))},[fr,to]);
  useEffect(()=>{fetchData()},[fetchData]);
  if(err)return<div className="loading-screen"style={{color:'var(--fire)'}}>Error: {err}</div>;
  if(!data||loading)return<div className="loading-screen">Loading install efficiency data...</div>;
  const{summary:s,techSummary,chunkingViolations,dailyRevenue,monthlyTrend,utilization}=data;
  const fd=tf==='all'?dailyRevenue:dailyRevenue.filter(d=>d.technician_name===tf);
  const at=[...new Set(dailyRevenue.map(d=>d.technician_name))].sort();
  const tabs=[{l:'Overview',i:'◎'},{l:'By Installer',i:'⬡'},{l:'Violations',i:'⚠',c:chunkingViolations.length},{l:'Daily',i:'▦'}];
  return(<div style={{maxWidth:1100,margin:'0 auto',padding:'24px 20px 80px'}}>
    <div style={{marginBottom:20}}>
      <div style={{fontFamily:'var(--mono)',fontSize:10,color:'var(--t4)',marginBottom:5,letterSpacing:'.3px'}}><Link href="/"style={{color:'var(--t3)',textDecoration:'none'}}>JOB TRACKER</Link> / ANALYTICS</div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',flexWrap:'wrap',gap:12}}>
        <div><h1 style={{fontFamily:'var(--disp)',fontSize:26,fontWeight:800,letterSpacing:'-.5px',lineHeight:1.1}}>Install Crew Efficiency</h1>
          <div style={{fontSize:11.5,color:'var(--t2)',marginTop:4}}>Target: <span style={{fontFamily:'var(--mono)',color:'var(--mint)'}}>{fmt(T)}</span>/crew/day &middot; SOP: Daily Production Tasks Step 13</div></div>
        <div style={{fontFamily:'var(--mono)',fontSize:36,fontWeight:800,color:s.efficiency_pct>=80?'var(--mint)':s.efficiency_pct>=60?'var(--amber)':'var(--fire)',lineHeight:1}}>{pct(s.efficiency_pct)}</div>
      </div>
    </div>
    <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:16,flexWrap:'wrap'}}>
      <label style={{fontSize:10,fontWeight:700,letterSpacing:'1px',textTransform:'uppercase'as const,color:'var(--t3)'}}>Range</label>
      <input type="date"value={fr}onChange={e=>sFr(e.target.value)}style={{background:'var(--s3)',border:'1px solid var(--b1)',borderRadius:7,padding:'5px 8px',color:'var(--t1)',fontFamily:'var(--mono)',fontSize:11,outline:'none'}}/>
      <span style={{color:'var(--t4)',fontSize:11}}>→</span>
      <input type="date"value={to}onChange={e=>sTo(e.target.value)}style={{background:'var(--s3)',border:'1px solid var(--b1)',borderRadius:7,padding:'5px 8px',color:'var(--t1)',fontFamily:'var(--mono)',fontSize:11,outline:'none'}}/>
      <button onClick={fetchData}style={{background:'var(--firebg)',border:'1px solid var(--firebd)',borderRadius:7,padding:'5px 12px',color:'var(--fire)',fontFamily:'var(--mono)',fontSize:10,fontWeight:700,cursor:'pointer',letterSpacing:'.5px'}}>REFRESH</button>
      <div style={{marginLeft:'auto',display:'flex',gap:4}}>
        {[{l:'Q1',f:`${y}-01-01`,t:`${y}-04-01`},{l:'Q2',f:`${y}-04-01`,t:`${y}-07-01`},{l:'YTD',f:`${y}-01-01`,t:`${y}-12-31`}].map(p=>(<button key={p.l}onClick={()=>{sFr(p.f);sTo(p.t)}}style={{background:fr===p.f&&to===p.t?'var(--voltbg)':'transparent',border:fr===p.f&&to===p.t?'1px solid var(--voltbd)':'1px solid var(--b1)',borderRadius:6,padding:'4px 10px',color:fr===p.f&&to===p.t?'var(--volt)':'var(--t3)',fontFamily:'var(--mono)',fontSize:10,fontWeight:700,cursor:'pointer'}}>{p.l}</button>))}
      </div>
    </div>
    <div className="hero"style={{gridTemplateColumns:'repeat(4,1fr)'}}>
      <HC l="ACTUAL REVENUE"v={fmtK(s.actual_revenue)}c="sv"/><HC l="TARGET REVENUE"v={fmtK(s.target_revenue)}c=""/><HC l="REVENUE GAP"v={`-${fmtK(s.total_gap)}`}c="sf"/><HC l="AVG / CREW DAY"v={fmt(s.avg_per_day)}c={s.avg_per_day>=T?'sm':s.avg_per_day>=5000?'sv':'sf'}/>
    </div>
    <div className="hero"style={{gridTemplateColumns:'repeat(4,1fr)'}}>
      <HC l={`AT TARGET (${fmt(T)}+)`}v={String(s.at_target)}s={`of ${s.total_crew_days} crew-days`}c="sm"/><HC l="NEAR ($5K-$8.8K)"v={String(s.near_target)}c="sv"/><HC l="CRITICAL (<$5K)"v={String(s.under_target)}c="sf"/><HC l="$0 VIOLATIONS"v={String(s.zero_days)}s={s.zero_days>0?`= ${fmtK(s.zero_days*T)} burned`:undefined}c={s.zero_days>0?'sf':''}/>
    </div>
    <div style={{display:'flex',gap:2,marginBottom:18,background:'var(--s2)',padding:3,borderRadius:10,border:'1px solid var(--b1)'}}>
      {tabs.map((t,i)=>(<button key={t.l}onClick={()=>setTab(i)}style={{flex:1,padding:'8px 0',border:'none',borderRadius:8,cursor:'pointer',fontFamily:'var(--sans)',fontSize:11,fontWeight:700,letterSpacing:'.5px',textTransform:'uppercase'as const,background:tab===i?'var(--firebg)':'transparent',color:tab===i?'var(--fire)':'var(--t3)',boxShadow:tab===i?'inset 0 0 0 1px var(--firebd)':'none',transition:'all .15s'}}><span style={{marginRight:4}}>{t.i}</span>{t.l}{t.c?` (${t.c})`:''}</button>))}
    </div>
    {tab===0&&<OvTab m={monthlyTrend}u={utilization}/>}{tab===1&&<InTab ts={techSummary}dr={dailyRevenue}/>}{tab===2&&<ViTab v={chunkingViolations}/>}{tab===3&&<DaTab dr={fd}at={at}tf={tf}sTf={sTf}/>}
  </div>);
}

function HC({l,v,s,c}:{l:string;v:string;s?:string;c:string}){return(<div className={`st ${c}`}style={{padding:'14px 16px'}}><div className="num"style={{fontSize:22}}>{v}</div><div className="lbl">{l}</div>{s&&<div style={{fontSize:10,color:'var(--t3)',marginTop:2,fontFamily:'var(--mono)'}}>{s}</div>}</div>)}
function GB({v,m,c}:{v:number;m:number;c:string}){return(<div className="gauge-bar"><div className="gauge-fill"style={{width:`${Math.min((v/m)*100,100)}%`,background:c}}/></div>)}

function OvTab({m,u}:{m:MonthlyRow[];u:UtilRow[]}){
  const mx=useMemo(()=>Math.max(...m.map(x=>Number(x.avg_daily)),T*1.1),[m]);
  return(<>
    <div className="c"style={{marginBottom:16}}>
      <div className="ch"><h3>Monthly Trend</h3><div className="tg"style={{background:'var(--firebg)',color:'var(--fire)',border:'1px solid var(--firebd)'}}>Target: {fmt(T)}/day</div></div>
      <div className="cb">
        <div style={{display:'flex',alignItems:'flex-end',gap:6,height:180,marginBottom:16,position:'relative'}}>
          <div style={{position:'absolute',bottom:`${(T/mx)*160+16}px`,left:0,right:0,height:1,background:'var(--firebd)',zIndex:1}}/>
          <div style={{position:'absolute',bottom:`${(T/mx)*160+20}px`,right:4,fontSize:8,fontFamily:'var(--mono)',color:'var(--fire)',fontWeight:700,letterSpacing:'.5px',zIndex:1}}>TARGET</div>
          {m.map((r,i)=>{const h=Math.max((Number(r.avg_daily)/mx)*160,4);return(<div key={i}style={{flex:1,display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'flex-end',height:'100%'}}>
            <div style={{fontFamily:'var(--mono)',fontSize:9,fontWeight:700,color:dC(Number(r.avg_daily)),marginBottom:4}}>{fmt(Number(r.avg_daily))}</div>
            <div style={{width:'100%',maxWidth:52}}>{(()=>{const tot=r.crew_days||1,aH=(r.at_target/tot)*h,zH=(r.zero_days/tot)*h,rH=h-aH-zH;return(<div style={{height:h,borderRadius:4,overflow:'hidden',display:'flex',flexDirection:'column'}}>{r.at_target>0&&<div style={{height:aH,background:'var(--mint)',minHeight:2}}/>}{rH>0&&<div style={{height:rH,background:Number(r.avg_daily)>=5000?'var(--amber)':'var(--fire)',minHeight:2}}/>}{r.zero_days>0&&<div style={{height:zH,background:'var(--t4)',minHeight:2}}/>}</div>)})()}</div>
            <div style={{fontFamily:'var(--mono)',fontSize:9,color:'var(--t4)',marginTop:6,fontWeight:600}}>{mL(r.month)}</div>
          </div>)})}
        </div>
        <table className="mt"><thead><tr><th>Month</th><th style={{textAlign:'right'}}>Crew Days</th><th style={{textAlign:'right'}}>Revenue</th><th style={{textAlign:'right'}}>Avg/Day</th><th style={{textAlign:'right'}}>At Target</th><th style={{textAlign:'right'}}>$0 Days</th><th style={{textAlign:'right'}}>$0 Potential</th><th style={{textAlign:'right'}}>Eff.</th></tr></thead>
          <tbody>{m.map((r,i)=>(<tr key={i}><td style={{fontWeight:600}}>{mL(r.month)}</td><td style={{fontFamily:'var(--mono)',textAlign:'right'}}>{r.crew_days}</td><td style={{fontFamily:'var(--mono)',textAlign:'right',color:'var(--mint)'}}>{fmtK(r.total_rev)}</td><td style={{fontFamily:'var(--mono)',textAlign:'right',color:dC(Number(r.avg_daily)),fontWeight:700}}>{fmt(Number(r.avg_daily))}</td><td style={{fontFamily:'var(--mono)',textAlign:'right',color:'var(--mint)'}}>{r.at_target}</td><td style={{fontFamily:'var(--mono)',textAlign:'right',color:Number(r.zero_days)>0?'var(--fire)':'var(--t4)'}}>{r.zero_days}</td><td style={{fontFamily:'var(--mono)',textAlign:'right',color:Number(r.zero_rev_potential)>0?'var(--fire)':'var(--t4)',fontSize:10}}>{Number(r.zero_rev_potential)>0?fmtK(r.zero_rev_potential):'—'}</td><td style={{fontFamily:'var(--mono)',textAlign:'right',fontWeight:700,color:Number(r.efficiency_pct)>=80?'var(--mint)':Number(r.efficiency_pct)>=60?'var(--amber)':'var(--fire)'}}>{pct(r.efficiency_pct)}</td></tr>))}</tbody></table>
      </div></div>
    <div className="c"><div className="ch"><h3>Lead Installer Utilization</h3><div className="tg"style={{background:'var(--grapebg)',color:'var(--grape)',border:'1px solid var(--grapebd)'}}>Kade &amp; Isaac</div></div>
      <div className="cb"><div style={{fontSize:10,color:'var(--t3)',marginBottom:12}}>Weekdays with install-BU appointments. Idle = no install work dispatched.</div>
        {u.map((r,i)=>(<div key={i}style={{display:'flex',alignItems:'center',gap:16,padding:'10px 0',borderBottom:i<u.length-1?'1px solid var(--b1)':'none'}}>
          <div style={{fontWeight:700,fontSize:13,minWidth:110}}>{r.tech}</div>
          <div style={{flex:1}}><div style={{display:'flex',justifyContent:'space-between',marginBottom:4}}><span style={{fontSize:10,fontWeight:700,letterSpacing:'1px',textTransform:'uppercase'as const,color:'var(--t3)'}}>{r.install_days} / {r.weekdays_available} weekdays</span><span style={{fontFamily:'var(--mono)',fontSize:12,fontWeight:800,color:Number(r.utilization_pct)>=70?'var(--mint)':Number(r.utilization_pct)>=40?'var(--amber)':'var(--fire)'}}>{pct(r.utilization_pct)}</span></div>
            <GB v={Number(r.utilization_pct)}m={100}c={Number(r.utilization_pct)>=70?'linear-gradient(90deg,var(--mint),var(--mint2))':Number(r.utilization_pct)>=40?'linear-gradient(90deg,var(--amber),#ffd54f)':'linear-gradient(90deg,var(--fire),var(--fire2))'}/></div>
          <div style={{fontFamily:'var(--mono)',fontSize:11,color:Number(r.idle_weekdays)>10?'var(--fire)':'var(--t3)',minWidth:60,textAlign:'right'as const}}>{r.idle_weekdays} idle</div>
        </div>))}</div></div>
    <div style={{display:'flex',gap:16,marginTop:12,fontSize:10,color:'var(--t3)'}}><span><span style={{display:'inline-block',width:10,height:10,borderRadius:2,background:'var(--mint)',verticalAlign:'middle',marginRight:4}}/>At target ({fmt(T)}+)</span><span><span style={{display:'inline-block',width:10,height:10,borderRadius:2,background:'var(--amber)',verticalAlign:'middle',marginRight:4}}/>Near ($5K-{fmtK(T)})</span><span><span style={{display:'inline-block',width:10,height:10,borderRadius:2,background:'var(--fire)',verticalAlign:'middle',marginRight:4}}/>Critical (&lt;$5K / $0)</span></div>
  </>);
}

function InTab({ts,dr}:{ts:TechRow[];dr:DailyRow[]}){
  const[exp,sExp]=useState<string|null>(null);
  return(<div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(340px,1fr))',gap:12}}>
    {ts.map((t,i)=>{const io=exp===t.technician_name;const td=io?dr.filter(d=>d.technician_name===t.technician_name).sort((a,b)=>b.work_date.localeCompare(a.work_date)):[];
      return(<div key={i}className="c"style={{gridColumn:io?'1 / -1':undefined}}>
        <div className="ch"style={{cursor:'pointer'}}onClick={()=>sExp(io?null:t.technician_name)}><h3>{t.technician_name}</h3>
          <div style={{display:'flex',alignItems:'center',gap:8}}><div className="tg"style={{background:Number(t.hit_pct)>=50?'var(--mintbg)':Number(t.hit_pct)>=25?'var(--amberbg)':'var(--firebg)',color:Number(t.hit_pct)>=50?'var(--mint)':Number(t.hit_pct)>=25?'var(--amber)':'var(--fire)',border:`1px solid ${Number(t.hit_pct)>=50?'var(--mintbd)':Number(t.hit_pct)>=25?'var(--amberbd)':'var(--firebd)'}`}}>{pct(t.hit_pct)} hit rate</div><span style={{color:'var(--t4)',fontSize:11,transition:'transform .15s',display:'inline-block',transform:io?'rotate(180deg)':'none'}}>▼</span></div></div>
        <div className="cb">
          <div style={{marginBottom:12}}><div style={{display:'flex',justifyContent:'space-between',marginBottom:4}}><span style={{fontSize:10,fontWeight:700,letterSpacing:'1px',textTransform:'uppercase'as const,color:'var(--t3)'}}>Avg Daily Revenue</span><span style={{fontFamily:'var(--mono)',fontSize:16,fontWeight:800,color:dC(Number(t.avg_daily))}}>{fmt(Number(t.avg_daily))}</span></div>
            <GB v={Number(t.avg_daily)}m={T}c={Number(t.avg_daily)>=T?'linear-gradient(90deg,var(--mint),var(--mint2))':Number(t.avg_daily)>=5000?'linear-gradient(90deg,var(--amber),#ffd54f)':'linear-gradient(90deg,var(--fire),var(--fire2))'}/></div>
          <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:8,marginBottom:10}}>
            <SB l="Crew Days"v={String(t.crew_days)}c="var(--t1)"/><SB l="Total Rev"v={fmtK(Number(t.total_rev))}c="var(--mint)"/><SB l="Gap"v={fmtK(Number(t.gap_to_target))}c="var(--fire)"/><SB l="Min Day"v={fmt(Number(t.min_day))}c="var(--t2)"/><SB l="Max Day"v={fmt(Number(t.max_day))}c="var(--mint)"/><SB l="$0 Days"v={String(t.zero_days)}c={Number(t.zero_days)>0?'var(--fire)':'var(--t4)'}/>
          </div>
          <div style={{display:'flex',gap:4}}>{Number(t.at_target)>0&&<DP n={Number(t.at_target)}l="AT TARGET"bg="var(--mintbg)"bd="var(--mintbd)"c="var(--mint)"/>}{Number(t.near_target)>0&&<DP n={Number(t.near_target)}l="NEAR"bg="var(--voltbg)"bd="var(--voltbd)"c="var(--volt)"/>}{Number(t.critical)>0&&<DP n={Number(t.critical)}l="CRITICAL"bg="var(--firebg)"bd="var(--firebd)"c="var(--fire)"/>}</div>
          {io&&td.length>0&&(<div style={{marginTop:14,borderTop:'1px solid var(--b1)',paddingTop:12}}><div style={{fontSize:10,fontWeight:700,letterSpacing:'1px',textTransform:'uppercase'as const,color:'var(--t3)',marginBottom:8}}>Day-by-day breakdown</div>{td.map((d,di)=>(<DR key={di}d={d}st={false}/>))}</div>)}
        </div></div>)})}
  </div>);
}

function ViTab({v}:{v:ViolationRow[]}){
  if(v.length===0)return(<div className="empty"><div className="empty-icon"style={{background:'var(--mintbg)',border:'1px solid var(--mintbd)'}}><svg viewBox="0 0 24 24"fill="none"stroke="var(--mint)"strokeWidth="2"strokeLinecap="round"strokeLinejoin="round"><path d="M20 6L9 17l-5-5"/></svg></div><div className="empty-title"style={{color:'var(--mint)'}}>No Chunking Violations</div><div className="empty-desc">All install jobs have revenue attached.</div></div>);
  return(<div className="c"><div className="ch"><h3>$0 Install Jobs — Chunking Violations</h3><div className="tg"style={{background:'var(--firebg)',color:'var(--fire)',border:'1px solid var(--firebd)'}}>{v.length} violations = {fmtK(v.length*T)} burned</div></div>
    <div className="cb"><div style={{fontSize:11,color:'var(--t2)',marginBottom:12,lineHeight:1.5}}>Chunking SOP: ¼=$2,500 · ½=$5,000 · ¾=$7,500 · full=$10,000+. $0 install-BU jobs = revenue not attached before crew rolled.</div>
      <div style={{overflowX:'auto'as const}}><table className="mt"><thead><tr><th>Date</th><th>Job</th><th>Customer</th><th>Installer</th><th>BU</th><th>Status</th><th>Summary</th></tr></thead>
        <tbody>{v.map((r,i)=>(<tr key={i}><td style={{fontFamily:'var(--mono)',fontSize:10.5,whiteSpace:'nowrap'as const}}>{r.work_date}</td><td><Link href={`/job/${r.st_job_id}`}style={{color:'var(--volt)',textDecoration:'none',fontFamily:'var(--mono)',fontSize:10.5}}>{r.st_job_id}</Link></td><td style={{fontSize:11,maxWidth:140,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'as const}}>{r.customer_name||'—'}</td><td style={{fontWeight:600}}>{r.technician_name}</td><td style={{fontSize:10,color:'var(--t2)',maxWidth:140,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'as const}}>{sB(r.business_unit_name)}</td><td><span className={`chip ${r.status==='Completed'?'c-ok':r.status==='Canceled'?'c-fail':'c-warn'}`}>{r.status}</span></td><td style={{fontSize:10,color:'var(--t2)',maxWidth:200,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'as const}}>{r.summary||'—'}</td></tr>))}</tbody></table></div></div></div>);
}

function DaTab({dr,at,tf,sTf}:{dr:DailyRow[];at:string[];tf:string;sTf:(v:string)=>void}){
  const g=useMemo(()=>{const m:Record<string,DailyRow[]>={};for(const r of dr){if(!m[r.work_date])m[r.work_date]=[];m[r.work_date].push(r)}return Object.entries(m).sort((a,b)=>b[0].localeCompare(a[0]))},[dr]);
  return(<div>
    <div style={{display:'flex',gap:4,marginBottom:14,flexWrap:'wrap'}}>
      <button onClick={()=>sTf('all')}style={{background:tf==='all'?'var(--voltbg)':'transparent',border:tf==='all'?'1px solid var(--voltbd)':'1px solid var(--b1)',borderRadius:6,padding:'4px 10px',color:tf==='all'?'var(--volt)':'var(--t3)',fontFamily:'var(--mono)',fontSize:10,fontWeight:700,cursor:'pointer'}}>ALL</button>
      {at.map(t=>(<button key={t}onClick={()=>sTf(t)}style={{background:tf===t?'var(--voltbg)':'transparent',border:tf===t?'1px solid var(--voltbd)':'1px solid var(--b1)',borderRadius:6,padding:'4px 10px',color:tf===t?'var(--volt)':'var(--t3)',fontFamily:'var(--mono)',fontSize:10,fontWeight:700,cursor:'pointer'}}>{t.split(' ')[1]||t}</button>))}
    </div>
    {g.length===0?(<div className="empty"><div className="empty-title">No Daily Data</div><div className="empty-desc">No install crew-days found for this filter.</div></div>):g.map(([date,rows])=>{const dt=rows.reduce((s,r)=>s+Number(r.day_revenue),0);return(<div key={date}style={{marginBottom:6}}>
      <div className={`st ${dCl(dt)}`}style={{padding:'10px 16px',marginBottom:2}}><div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}><div style={{display:'flex',alignItems:'center',gap:10}}><span style={{fontWeight:700,fontSize:13}}>{dL(date)}</span><span style={{fontSize:10,color:'var(--t3)'}}>{rows.length} crew{rows.length>1?'s':''}</span></div><div style={{fontFamily:'var(--mono)',fontSize:18,fontWeight:800,color:dC(dt)}}>{fmt(dt)}</div></div></div>
      {rows.map((r,j)=>(<DR key={j}d={r}st={true}/>))}
    </div>)})}
  </div>);
}

function DR({d,st}:{d:DailyRow;st:boolean}){
  const[o,sO]=useState(false);const b=dB(d.day_revenue);
  return(<div style={{marginBottom:2}}>
    <div onClick={()=>d.job_details?.length>0&&sO(!o)}style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'8px 16px',background:'var(--s2)',border:'1px solid var(--b1)',borderRadius:o?'8px 8px 0 0':8,cursor:d.job_details?.length>0?'pointer':'default',transition:'all .1s'}}>
      <div style={{display:'flex',alignItems:'center',gap:10}}>
        {st&&<span style={{fontWeight:600,fontSize:12,minWidth:110}}>{d.technician_name}</span>}
        {!st&&<span style={{fontFamily:'var(--mono)',fontSize:10.5,color:'var(--t3)',minWidth:80}}>{dL(d.work_date)}</span>}
        <span style={{fontSize:10,color:'var(--t3)',fontFamily:'var(--mono)'}}>{d.jobs}j</span>
        <span className={`chip ${b==='at'?'c-ok':b==='near'?'c-warn':b==='critical'?'c-fail':''}`}style={b==='zero'?{background:'var(--s3)',border:'1px solid var(--b1)',color:'var(--t4)'}:{}}>{b==='at'?'AT TARGET':b==='near'?'NEAR':b==='critical'?'CRITICAL':'$0'}</span>
      </div>
      <div style={{display:'flex',alignItems:'center',gap:8}}><span style={{fontFamily:'var(--mono)',fontSize:14,fontWeight:800,color:dC(d.day_revenue)}}>{fmt(d.day_revenue)}</span>{d.job_details?.length>0&&<span style={{color:'var(--t4)',fontSize:9,transition:'transform .15s',display:'inline-block',transform:o?'rotate(180deg)':'none'}}>▼</span>}</div>
    </div>
    {o&&d.job_details&&(<div style={{background:'var(--s3)',border:'1px solid var(--b1)',borderTop:'none',borderRadius:'0 0 8px 8px',padding:'8px 12px'}}>
      {d.job_details.map((j,ji)=>(<div key={ji}style={{display:'flex',alignItems:'center',gap:10,padding:'6px 4px',borderBottom:ji<d.job_details.length-1?'1px solid var(--b1)':'none',fontSize:11}}>
        <Link href={`/job/${j.st_job_id}`}style={{color:'var(--volt)',textDecoration:'none',fontFamily:'var(--mono)',fontSize:10,minWidth:70,flexShrink:0}}>#{j.job_number||j.st_job_id}</Link>
        <span style={{flex:1,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'as const,color:'var(--t2)'}}>{j.customer_name||'—'}</span>
        <span style={{fontSize:9,color:'var(--t3)',maxWidth:100,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'as const}}>{sB(j.bu_name)}</span>
        <span className={`chip ${j.status==='Completed'?'c-ok':j.status==='Canceled'?'c-fail':'c-warn'}`}style={{fontSize:8,padding:'2px 6px'}}>{j.status}</span>
        <span style={{fontFamily:'var(--mono)',fontSize:11,fontWeight:700,color:j.revenue>0?'var(--mint)':'var(--fire)',minWidth:60,textAlign:'right'as const}}>{fmt(j.revenue)}</span>
      </div>))}</div>)}
  </div>);
}

function SB({l,v,c}:{l:string;v:string;c:string}){return(<div style={{background:'var(--s3)',borderRadius:8,padding:'8px 10px',textAlign:'center'as const}}><div style={{fontFamily:'var(--mono)',fontSize:14,fontWeight:700,color:c,lineHeight:1,marginBottom:3}}>{v}</div><div style={{fontSize:8,fontWeight:700,letterSpacing:'1px',textTransform:'uppercase'as const,color:'var(--t4)'}}>{l}</div></div>)}
function DP({n,l,bg,bd,c}:{n:number;l:string;bg:string;bd:string;c:string}){return(<div style={{display:'flex',alignItems:'center',gap:4,padding:'3px 8px',borderRadius:6,fontSize:9,fontWeight:700,letterSpacing:'.5px',background:bg,border:`1px solid ${bd}`,color:c}}><span style={{fontFamily:'var(--mono)'}}>{n}</span> {l}</div>)}
