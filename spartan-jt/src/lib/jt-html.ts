// JT HTML template — Spartan branded, expandable sidebar, bigger fonts
export function buildJTHtml(data: Record<string, any>): string {
  const jsonData = JSON.stringify(data);
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Job Tracker \u2014 Spartan Plumbing</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
--bg:#070809;--s1:#0d0e12;--s2:#111318;--s3:#16181f;--s4:#1c1f29;--s5:#222633;
--b1:rgba(255,255,255,.04);--b2:rgba(255,255,255,.07);--b3:rgba(255,255,255,.12);
--t1:#f0f2f8;--t2:#8c93ae;--t3:#555d78;--t4:#353b50;
--fire:#cc2244;--fire2:#e8506e;--firebg:rgba(204,34,68,.08);--firebd:rgba(204,34,68,.22);--fireg:rgba(204,34,68,.4);
--gold:#c9a84c;--gold2:#dfc06a;--goldbg:rgba(201,168,76,.08);--goldbd:rgba(201,168,76,.2);--goldg:rgba(201,168,76,.35);
--volt:#2d7aff;--volt2:#5c9aff;--voltbg:rgba(45,122,255,.07);--voltbd:rgba(45,122,255,.18);--voltg:rgba(45,122,255,.35);
--mint:#00e87b;--mint2:#44ffaa;--mintbg:rgba(0,232,123,.06);--mintbd:rgba(0,232,123,.16);--mintg:rgba(0,232,123,.3);
--grape:#9945ff;--grapebg:rgba(153,69,255,.07);--grapebd:rgba(153,69,255,.16);--grapeg:rgba(153,69,255,.3);
--amber:#ffa726;--amberbg:rgba(255,167,38,.06);--amberbd:rgba(255,167,38,.16);
--ice:#00d4ff;--icebg:rgba(0,212,255,.05);--icebd:rgba(0,212,255,.14);
--sans:'Outfit',system-ui,sans-serif;--mono:'JetBrains Mono',monospace;--disp:'Space Grotesk',sans-serif;
--rail-w:56px;
}
html{font-size:15px;scroll-behavior:smooth}
body{background:var(--bg);color:var(--t1);font-family:var(--sans);-webkit-font-smoothing:antialiased;overflow-x:hidden}
body::before{content:'';position:fixed;inset:0;background:radial-gradient(ellipse 55% 30% at 10% -8%,rgba(204,34,68,.06),transparent 50%),radial-gradient(ellipse 40% 25% at 90% 0%,rgba(201,168,76,.04),transparent 45%);pointer-events:none;z-index:0}
::selection{background:var(--fire);color:#fff}
.shell{display:grid;grid-template-columns:var(--rail-w) 1fr 330px;min-height:100vh;transition:grid-template-columns .25s ease}
.shell.exp{--rail-w:210px}
.rail{background:var(--s1);border-right:1px solid var(--b1);position:fixed;top:0;left:0;bottom:0;width:var(--rail-w);z-index:20;display:flex;flex-direction:column;align-items:center;padding:12px 0;overflow-y:auto;scrollbar-width:none;transition:width .25s ease}.rail::-webkit-scrollbar{display:none}
.rail.exp{width:210px;align-items:flex-start;padding:12px 10px}
.rail-hdr{display:flex;align-items:center;gap:10px;margin-bottom:14px;flex-shrink:0;padding:0 2px;width:100%}
.rail-logo{width:38px;height:38px;border-radius:10px;flex-shrink:0;overflow:hidden;display:flex;align-items:center;justify-content:center}
.rail-logo img{width:100%;height:100%;object-fit:cover}
.rail-brand{display:none;font-family:var(--disp);font-weight:800;font-size:15px;color:var(--gold);letter-spacing:.5px;line-height:1.1}
.rail-brand small{display:block;font-size:9px;font-weight:600;letter-spacing:2px;color:var(--t3);text-transform:uppercase}
.exp .rail-brand{display:block}
.ri{width:38px;height:38px;border-radius:9px;display:flex;align-items:center;justify-content:center;cursor:pointer;transition:all .15s;color:var(--t3);margin-bottom:2px;flex-shrink:0;position:relative;gap:10px}
.ri:hover{background:rgba(255,255,255,.04);color:var(--t2)}.ri.on{background:var(--firebg);color:var(--fire);box-shadow:inset 0 0 0 1px var(--firebd)}
.exp .ri{width:100%;justify-content:flex-start;padding:0 10px;border-radius:8px;height:36px}
.ri .rlbl{display:none;font-size:12px;font-weight:600;white-space:nowrap;letter-spacing:.3px}
.exp .ri .rlbl{display:block}
.ri .tip{position:absolute;left:50px;background:var(--s4);color:var(--t1);padding:5px 10px;border-radius:6px;font-size:10px;font-weight:600;letter-spacing:.5px;white-space:nowrap;pointer-events:none;opacity:0;transition:opacity .15s;z-index:30;border:1px solid var(--b2)}.ri:hover .tip{opacity:1}
.exp .ri .tip{display:none}
.rsep{width:20px;height:1px;background:var(--b1);margin:4px 0;flex-shrink:0}
.exp .rsep{width:100%}
.rtoggle{margin-top:auto;width:38px;height:38px;border-radius:9px;display:flex;align-items:center;justify-content:center;cursor:pointer;color:var(--t3);transition:all .15s;flex-shrink:0;font-size:16px}
.rtoggle:hover{background:rgba(255,255,255,.04);color:var(--t1)}
.exp .rtoggle{width:100%;justify-content:flex-end;padding-right:14px}
.main{grid-column:2;padding:20px 28px 80px;position:relative;z-index:1;margin-left:var(--rail-w);transition:margin-left .25s ease}
.tab-hdr{display:flex;align-items:center;gap:14px;margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid var(--b1)}
.tab-hdr .tab-icon{width:44px;height:44px;border-radius:11px;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:22px}
.tab-hdr .tab-info{flex:1}
.tab-hdr .tab-title{font-family:var(--disp);font-size:22px;font-weight:700;letter-spacing:-.3px}
.tab-hdr .tab-desc{font-size:12px;color:var(--t3);margin-top:2px}
.tab-hdr .tab-badge{font-family:var(--mono);font-size:11px;font-weight:600;padding:5px 12px;border-radius:8px}
.hero{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}
.st{border-radius:14px;padding:18px;position:relative;overflow:hidden}.st::before{content:'';position:absolute;top:0;left:0;right:0;height:2px}
.st .num{font-family:var(--mono);font-size:30px;font-weight:700;letter-spacing:-1px;line-height:1;margin-bottom:5px}
.st .lbl{font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase}
.st .ai{position:absolute;top:12px;right:12px;width:9px;height:9px;border-radius:50%}
.ai-ok{background:var(--mint);box-shadow:0 0 6px var(--mintg)}.ai-warn{background:var(--amber);box-shadow:0 0 6px rgba(255,167,38,.4)}.ai-fail{background:var(--fire);box-shadow:0 0 6px var(--fireg)}.ai-wait{background:var(--t3)}
.sf{background:linear-gradient(150deg,rgba(204,34,68,.14),rgba(204,34,68,.02) 70%);border:1px solid var(--firebd)}.sf::before{background:linear-gradient(90deg,var(--fire),transparent)}.sf .num{color:var(--fire)}.sf .lbl{color:var(--fire2)}
.sv{background:linear-gradient(150deg,rgba(45,122,255,.14),rgba(45,122,255,.02) 70%);border:1px solid var(--voltbd)}.sv::before{background:linear-gradient(90deg,var(--volt),transparent)}.sv .num{color:var(--volt)}.sv .lbl{color:var(--volt2)}
.sm{background:linear-gradient(150deg,rgba(0,232,123,.12),rgba(0,232,123,.02) 70%);border:1px solid var(--mintbd)}.sm::before{background:linear-gradient(90deg,var(--mint),transparent)}.sm .num{color:var(--mint)}.sm .lbl{color:var(--mint2)}
.sg{background:linear-gradient(150deg,rgba(201,168,76,.14),rgba(201,168,76,.02) 70%);border:1px solid var(--goldbd)}.sg::before{background:linear-gradient(90deg,var(--gold),transparent)}.sg .num{color:var(--gold)}.sg .lbl{color:var(--gold2)}
.pipe-wrap{background:var(--s2);border:1px solid var(--b1);border-radius:14px;padding:16px 18px;margin-bottom:18px}.pipe-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}.pipe-top h2{font-family:var(--disp);font-size:13px;font-weight:700;letter-spacing:1.8px;text-transform:uppercase;color:var(--t2)}.pipe-top .step{font-family:var(--mono);font-size:12px;font-weight:600;color:var(--gold)}.pipe{display:grid;grid-template-columns:repeat(6,1fr);gap:5px}.pn{text-align:center}.pb{height:8px;border-radius:4px;margin-bottom:6px;overflow:hidden;position:relative}.pb.done{background:var(--mint);box-shadow:0 0 8px var(--mintg)}.pb.now{background:linear-gradient(90deg,var(--gold),var(--gold2));box-shadow:0 0 12px var(--goldg);animation:ppulse 2s ease-in-out infinite}@keyframes ppulse{0%,100%{box-shadow:0 0 8px var(--goldg)}50%{box-shadow:0 0 20px var(--goldg)}}.pb.now::after{content:'';position:absolute;top:0;left:0;height:100%;width:35%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.25),transparent);animation:shim 2s infinite}@keyframes shim{0%{transform:translateX(-100%)}100%{transform:translateX(400%)}}.pb.w{background:var(--t4)}.pt{font-size:10px;font-weight:700;letter-spacing:.6px;text-transform:uppercase}.pn.done .pt{color:var(--mint)}.pn.now .pt{color:var(--gold)}.pn.w .pt{color:var(--t4)}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:12px}.full{margin-bottom:14px}
.c{background:var(--s2);border:1px solid var(--b1);border-radius:14px;overflow:hidden}.ch{padding:14px 18px;border-bottom:1px solid var(--b1);display:flex;justify-content:space-between;align-items:center}.ch h3{font-family:var(--disp);font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--t2)}.ch .tg{font-family:var(--mono);font-size:11px;font-weight:600;padding:3px 10px;border-radius:6px}.cb{padding:14px 18px}
.vr{display:flex;align-items:center;padding:8px 0;border-bottom:1px solid var(--b1);font-size:13px;gap:10px}.vr:last-child{border-bottom:none}.vr .ai-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}.vr .k{flex:1;color:var(--t2)}.vr .v{font-weight:600;text-align:right}
.chip{display:inline-flex;align-items:center;gap:4px;padding:4px 10px;border-radius:7px;font-size:11px;font-weight:700;letter-spacing:.3px}.c-ok{background:var(--mintbg);border:1px solid var(--mintbd);color:var(--mint)}.c-fail{background:var(--firebg);border:1px solid var(--firebd);color:var(--fire)}.c-warn{background:var(--amberbg);border:1px solid var(--amberbd);color:var(--amber)}.c-info{background:var(--voltbg);border:1px solid var(--voltbd);color:var(--volt)}
.intel{background:var(--s2);border:1px solid var(--b1);border-radius:14px;padding:18px;margin-bottom:14px}.intel-h{display:flex;align-items:center;gap:10px;margin-bottom:10px}.intel-h .intel-icon{width:30px;height:30px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:15px}.intel-h .intel-title{font-family:var(--disp);font-size:14px;font-weight:700;letter-spacing:.3px}.intel-body{font-size:13px;line-height:1.65;color:var(--t2)}.intel-body strong{color:var(--t1)}
.mt{width:100%;border-collapse:collapse}.mt th{text-align:left;font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--t3);padding:8px 10px;border-bottom:1px solid var(--b2)}.mt td{padding:8px 10px;font-size:13px;border-bottom:1px solid var(--b1)}.mt tr:hover td{background:rgba(255,255,255,.015)}
.bpct{display:flex;align-items:center;justify-content:space-between;background:var(--s3);border-radius:12px;padding:16px 20px;margin-bottom:16px;border:1px solid var(--b1)}.bpct-left{display:flex;align-items:center;gap:14px}.bpct-num{font-family:var(--mono);font-size:44px;font-weight:700;letter-spacing:-2px;line-height:1}.bpct-info{font-size:12px;color:var(--t2);line-height:1.5}.bpct-info strong{color:var(--t1)}.bpct-bar{width:130px}.bpct-track{height:7px;border-radius:4px;background:rgba(255,255,255,.04);margin-bottom:4px}.bpct-fill{height:100%;border-radius:4px}.bpct-sub{font-family:var(--mono);font-size:10px;color:var(--t3);text-align:right}
.panel{grid-column:3;background:var(--s1);border-left:1px solid var(--b1);position:fixed;top:0;right:0;bottom:0;width:330px;display:flex;flex-direction:column;z-index:10}.panel-h{padding:18px 20px;border-bottom:1px solid var(--b1);display:flex;justify-content:space-between;align-items:center}.panel-h h2{font-family:var(--disp);font-size:13px;font-weight:700;letter-spacing:1.8px;text-transform:uppercase;color:var(--t1)}
.live{display:flex;align-items:center;gap:5px;font-size:11px;font-weight:700;color:var(--mint);text-transform:uppercase;letter-spacing:1px}.live::before{content:'';width:7px;height:7px;border-radius:50%;background:var(--mint);box-shadow:0 0 8px var(--mintg);animation:blink 1.5s infinite}@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
.panel-f{flex:1;overflow-y:auto;padding:10px 16px}
.act{display:flex;gap:10px;padding:10px 0;border-bottom:1px solid var(--b1)}.act:last-child{border-bottom:none}.act-d{width:9px;height:9px;border-radius:50%;margin-top:4px;flex-shrink:0;position:relative}.act-d::after{content:'';position:absolute;top:13px;left:3.5px;width:2px;bottom:-14px;background:var(--b1)}.act:last-child .act-d::after{display:none}
.act-d.fire{background:var(--fire);box-shadow:0 0 7px var(--fireg)}.act-d.volt{background:var(--volt);box-shadow:0 0 7px var(--voltg)}.act-d.mint{background:var(--mint);box-shadow:0 0 7px var(--mintg)}.act-d.grape{background:var(--grape);box-shadow:0 0 7px var(--grapeg)}.act-d.amber{background:var(--amber);box-shadow:0 0 5px rgba(255,167,38,.3)}.act-d.ice{background:var(--ice);box-shadow:0 0 5px rgba(0,212,255,.3)}
.act-b{flex:1;min-width:0}.act-t{font-size:13px;font-weight:600;line-height:1.3}.act-m{font-family:var(--mono);font-size:10px;color:var(--t3);margin-top:2px;display:flex;gap:8px}.act-box{margin-top:5px;background:var(--s2);border:1px solid var(--b1);border-radius:6px;padding:7px 9px;font-size:12px;color:var(--t2);line-height:1.45}
.empty{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:40px 20px;text-align:center}.empty-icon{width:52px;height:52px;border-radius:14px;display:flex;align-items:center;justify-content:center;margin-bottom:12px;font-size:24px}.empty-title{font-family:var(--disp);font-size:18px;font-weight:700;margin-bottom:6px}.empty-desc{font-size:13px;color:var(--t3);max-width:320px;line-height:1.5}
.ck-item{display:flex;align-items:flex-start;gap:12px;padding:11px 18px;border-bottom:1px solid var(--b1);transition:background .1s}.ck-item:hover{background:rgba(255,255,255,.01)}.ck-item:last-child{border-bottom:none}.ck-num{font-family:var(--mono);font-size:11px;font-weight:700;color:var(--t3);width:24px;text-align:center;margin-top:3px;flex-shrink:0}.ck-body{flex:1;min-width:0}.ck-title{font-size:13px;font-weight:600;line-height:1.3}.ck-meta{font-family:var(--mono);font-size:10px;color:var(--t3);margin-top:3px;display:flex;gap:8px}
.sec{margin-bottom:22px}.sec-h{font-family:var(--disp);font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--t3);margin-bottom:10px;display:flex;align-items:center;gap:8px}.sec-h::after{content:'';flex:1;height:1px;background:var(--b1)}
.kpi{display:flex;align-items:center;gap:12px;background:var(--s3);border:1px solid var(--b1);border-radius:12px;padding:14px 16px}.kpi-val{font-family:var(--mono);font-size:28px;font-weight:700;line-height:1}.kpi-info{font-size:11px;color:var(--t2)}.kpi-info strong{display:block;font-size:12px;color:var(--t1);font-weight:600}
.loading{display:flex;align-items:center;justify-content:center;height:60vh;color:var(--t3);font-size:15px;font-family:var(--mono)}.hidden{display:none}
@media(max-width:1100px){.shell{grid-template-columns:var(--rail-w) 1fr}.panel{display:none}}
@media(max-width:700px){.shell{grid-template-columns:1fr}.rail{display:none}.main{margin-left:0;padding:14px}.hero{grid-template-columns:1fr 1fr}.g2,.g3{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="shell" id="shell">
<nav class="rail" id="rail"></nav>
<div class="main"><div id="loading" class="loading">Loading...</div><div id="content" class="hidden"></div></div>
<aside class="panel"><div class="panel-h"><h2>Activity</h2><div class="live">Live</div></div><div class="panel-f" id="activityFeed"></div></aside>
</div>
<script>const D = ${jsonData};</script>
<script src="/jt-app.js"></script>
</body>
</html>`;
}