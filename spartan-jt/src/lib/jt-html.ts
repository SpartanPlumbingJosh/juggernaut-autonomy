// JT HTML template — loads static JS from /jt-app.js
// All 12 tab renderers live in public/jt-app.js

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
--bg:#050609;--s1:#0a0c13;--s2:#0e1019;--s3:#131620;--s4:#181c28;--s5:#1e2233;
--b1:rgba(255,255,255,.03);--b2:rgba(255,255,255,.06);--b3:rgba(255,255,255,.1);
--t1:#f0f2f8;--t2:#7e85a0;--t3:#4a5068;--t4:#2d3248;
--fire:#ff2d46;--fire2:#ff5c70;--firebg:rgba(255,45,70,.07);--firebd:rgba(255,45,70,.18);--fireg:rgba(255,45,70,.4);
--volt:#2d7aff;--volt2:#5c9aff;--voltbg:rgba(45,122,255,.07);--voltbd:rgba(45,122,255,.18);--voltg:rgba(45,122,255,.35);
--mint:#00e87b;--mint2:#44ffaa;--mintbg:rgba(0,232,123,.06);--mintbd:rgba(0,232,123,.16);--mintg:rgba(0,232,123,.3);
--grape:#9945ff;--grapebg:rgba(153,69,255,.07);--grapebd:rgba(153,69,255,.16);--grapeg:rgba(153,69,255,.3);
--amber:#ffa726;--amberbg:rgba(255,167,38,.06);--amberbd:rgba(255,167,38,.16);
--ice:#00d4ff;--icebg:rgba(0,212,255,.05);--icebd:rgba(0,212,255,.14);
--hot:#ff4ecd;--hotbg:rgba(255,78,205,.06);--hotbd:rgba(255,78,205,.16);
--sans:'Outfit',system-ui,sans-serif;--mono:'JetBrains Mono',monospace;--disp:'Space Grotesk',sans-serif;
}
html{font-size:14px;scroll-behavior:smooth}
body{background:var(--bg);color:var(--t1);font-family:var(--sans);-webkit-font-smoothing:antialiased;overflow-x:hidden}
body::before{content:'';position:fixed;inset:0;background:radial-gradient(ellipse 55% 30% at 10% -8%,rgba(255,45,70,.07),transparent 50%),radial-gradient(ellipse 40% 25% at 90% 0%,rgba(45,122,255,.06),transparent 45%),radial-gradient(ellipse 35% 20% at 50% -5%,rgba(153,69,255,.04),transparent 40%),radial-gradient(ellipse 50% 50% at 50% 100%,rgba(0,232,123,.02),transparent 40%);pointer-events:none;z-index:0}
::selection{background:var(--fire);color:#fff}
.shell{display:grid;grid-template-columns:56px 1fr 330px;min-height:100vh}
.rail{background:var(--s1);border-right:1px solid var(--b1);position:fixed;top:0;left:0;bottom:0;width:56px;z-index:20;display:flex;flex-direction:column;align-items:center;padding:12px 0;overflow-y:auto;scrollbar-width:none}.rail::-webkit-scrollbar{display:none}
.rail-logo{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-family:var(--disp);font-weight:900;font-size:17px;color:#fff;margin-bottom:16px;background:var(--fire);position:relative;box-shadow:0 0 24px var(--fireg),0 0 48px rgba(255,45,70,.12);flex-shrink:0}
.rail-logo::before{content:'';position:absolute;inset:-3px;border-radius:13px;background:conic-gradient(from 180deg,var(--fire),var(--grape),var(--volt),var(--fire));opacity:.3;filter:blur(6px);z-index:-1;animation:logospin 8s linear infinite}
@keyframes logospin{to{transform:rotate(360deg)}}
.ri{width:36px;height:36px;border-radius:9px;display:flex;align-items:center;justify-content:center;cursor:pointer;transition:all .15s;color:var(--t3);margin-bottom:2px;flex-shrink:0;position:relative}.ri:hover{background:rgba(255,255,255,.03);color:var(--t2)}.ri.on{background:var(--firebg);color:var(--fire);box-shadow:inset 0 0 0 1px var(--firebd)}.ri svg{width:17px;height:17px}
.ri .tip{position:absolute;left:48px;background:var(--s4);color:var(--t1);padding:5px 10px;border-radius:6px;font-size:10px;font-weight:600;letter-spacing:.5px;white-space:nowrap;pointer-events:none;opacity:0;transition:opacity .15s;z-index:30;border:1px solid var(--b2)}.ri:hover .tip{opacity:1}
.rsep{width:20px;height:1px;background:var(--b1);margin:4px 0;flex-shrink:0}
.main{grid-column:2;padding:18px 22px 80px;position:relative;z-index:1;margin-left:56px}
.tab-hdr{display:flex;align-items:center;gap:12px;margin-bottom:18px;padding-bottom:14px;border-bottom:1px solid var(--b1)}.tab-hdr .tab-icon{width:40px;height:40px;border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0}.tab-hdr .tab-icon svg{width:20px;height:20px}.tab-hdr .tab-info{flex:1}.tab-hdr .tab-title{font-family:var(--disp);font-size:18px;font-weight:700;letter-spacing:-.3px}.tab-hdr .tab-desc{font-size:11px;color:var(--t2);margin-top:2px}.tab-hdr .tab-badge{font-family:var(--mono);font-size:10px;font-weight:600;padding:4px 10px;border-radius:7px}
.hero{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px}
.st{border-radius:12px;padding:16px;position:relative;overflow:hidden}.st::before{content:'';position:absolute;top:0;left:0;right:0;height:2px}.st .num{font-family:var(--mono);font-size:26px;font-weight:700;letter-spacing:-1px;line-height:1;margin-bottom:4px}.st .lbl{font-size:10px;font-weight:600;letter-spacing:1px;text-transform:uppercase}.st .ai{position:absolute;top:10px;right:10px;width:8px;height:8px;border-radius:50%}
.ai-ok{background:var(--mint);box-shadow:0 0 6px var(--mintg)}.ai-warn{background:var(--amber);box-shadow:0 0 6px rgba(255,167,38,.4)}.ai-fail{background:var(--fire);box-shadow:0 0 6px var(--fireg)}.ai-wait{background:var(--t3)}
.sf{background:linear-gradient(150deg,rgba(255,45,70,.14),rgba(255,45,70,.02) 70%);border:1px solid var(--firebd)}.sf::before{background:linear-gradient(90deg,var(--fire),transparent)}.sf .num{color:var(--fire)}.sf .lbl{color:var(--fire2)}
.sv{background:linear-gradient(150deg,rgba(45,122,255,.14),rgba(45,122,255,.02) 70%);border:1px solid var(--voltbd)}.sv::before{background:linear-gradient(90deg,var(--volt),transparent)}.sv .num{color:var(--volt)}.sv .lbl{color:var(--volt2)}
.sm{background:linear-gradient(150deg,rgba(0,232,123,.12),rgba(0,232,123,.02) 70%);border:1px solid var(--mintbd)}.sm::before{background:linear-gradient(90deg,var(--mint),transparent)}.sm .num{color:var(--mint)}.sm .lbl{color:var(--mint2)}
.sg{background:linear-gradient(150deg,rgba(153,69,255,.14),rgba(153,69,255,.02) 70%);border:1px solid var(--grapebd)}.sg::before{background:linear-gradient(90deg,var(--grape),transparent)}.sg .num{color:var(--grape)}.sg .lbl{color:var(--grape)}
.pipe-wrap{background:var(--s2);border:1px solid var(--b1);border-radius:12px;padding:16px 18px;margin-bottom:16px}.pipe-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}.pipe-top h2{font-family:var(--disp);font-size:12px;font-weight:700;letter-spacing:1.8px;text-transform:uppercase;color:var(--t2)}.pipe-top .step{font-family:var(--mono);font-size:11px;font-weight:600;color:var(--volt)}.pipe{display:grid;grid-template-columns:repeat(6,1fr);gap:5px}.pn{text-align:center}.pb{height:7px;border-radius:4px;margin-bottom:6px;overflow:hidden;position:relative}.pb.done{background:var(--mint);box-shadow:0 0 8px var(--mintg)}.pb.now{background:linear-gradient(90deg,var(--volt),var(--ice));box-shadow:0 0 12px var(--voltg);animation:ppulse 2s ease-in-out infinite}@keyframes ppulse{0%,100%{box-shadow:0 0 8px var(--voltg)}50%{box-shadow:0 0 20px var(--voltg)}}.pb.now::after{content:'';position:absolute;top:0;left:0;height:100%;width:35%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.25),transparent);animation:shim 2s infinite}@keyframes shim{0%{transform:translateX(-100%)}100%{transform:translateX(400%)}}.pb.w{background:var(--t4)}.pt{font-size:9px;font-weight:700;letter-spacing:.6px;text-transform:uppercase}.pn.done .pt{color:var(--mint)}.pn.now .pt{color:var(--volt)}.pn.w .pt{color:var(--t4)}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:12px}.full{margin-bottom:12px}
.c{background:var(--s2);border:1px solid var(--b1);border-radius:12px;overflow:hidden}.ch{padding:12px 16px;border-bottom:1px solid var(--b1);display:flex;justify-content:space-between;align-items:center}.ch h3{font-family:var(--disp);font-size:10.5px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--t2)}.ch .tg{font-family:var(--mono);font-size:10px;font-weight:600;padding:2px 8px;border-radius:6px}.cb{padding:14px 16px}
.vr{display:flex;align-items:center;padding:7px 0;border-bottom:1px solid var(--b1);font-size:12px;gap:8px}.vr:last-child{border-bottom:none}.vr .ai-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}.vr .k{flex:1;color:var(--t2)}.vr .v{font-weight:600;text-align:right}
.chip{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:7px;font-size:10px;font-weight:700;letter-spacing:.3px}.c-ok{background:var(--mintbg);border:1px solid var(--mintbd);color:var(--mint)}.c-fail{background:var(--firebg);border:1px solid var(--firebd);color:var(--fire)}.c-warn{background:var(--amberbg);border:1px solid var(--amberbd);color:var(--amber)}.c-info{background:var(--voltbg);border:1px solid var(--voltbd);color:var(--volt)}
.intel{background:var(--s2);border:1px solid var(--b1);border-radius:12px;padding:16px;margin-bottom:12px}.intel-h{display:flex;align-items:center;gap:8px;margin-bottom:10px}.intel-h .intel-icon{width:28px;height:28px;border-radius:7px;display:flex;align-items:center;justify-content:center}.intel-h .intel-icon svg{width:14px;height:14px}.intel-h .intel-title{font-family:var(--disp);font-size:12px;font-weight:700;letter-spacing:.5px}.intel-body{font-size:12px;line-height:1.65;color:var(--t2)}.intel-body strong{color:var(--t1)}
.mt{width:100%;border-collapse:collapse}.mt th{text-align:left;font-size:9px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--t3);padding:7px 8px;border-bottom:1px solid var(--b2)}.mt td{padding:7px 8px;font-size:11.5px;border-bottom:1px solid var(--b1)}.mt tr:hover td{background:rgba(255,255,255,.015)}
.bpct{display:flex;align-items:center;justify-content:space-between;background:var(--s3);border-radius:10px;padding:14px 18px;margin-bottom:14px;border:1px solid var(--b1)}.bpct-left{display:flex;align-items:center;gap:12px}.bpct-num{font-family:var(--mono);font-size:42px;font-weight:700;letter-spacing:-2px;line-height:1}.bpct-info{font-size:11px;color:var(--t2);line-height:1.5}.bpct-info strong{color:var(--t1)}.bpct-bar{width:120px}.bpct-track{height:6px;border-radius:3px;background:rgba(255,255,255,.04);margin-bottom:4px}.bpct-fill{height:100%;border-radius:3px}.bpct-sub{font-family:var(--mono);font-size:9px;color:var(--t3);text-align:right}
.panel{grid-column:3;background:var(--s1);border-left:1px solid var(--b1);position:fixed;top:0;right:0;bottom:0;width:330px;display:flex;flex-direction:column;z-index:10}.panel-h{padding:16px 18px;border-bottom:1px solid var(--b1);display:flex;justify-content:space-between;align-items:center}.panel-h h2{font-family:var(--disp);font-size:12px;font-weight:700;letter-spacing:1.8px;text-transform:uppercase;color:var(--t1)}
.live{display:flex;align-items:center;gap:5px;font-size:10px;font-weight:700;color:var(--mint);text-transform:uppercase;letter-spacing:1px}.live::before{content:'';width:6px;height:6px;border-radius:50%;background:var(--mint);box-shadow:0 0 8px var(--mintg);animation:blink 1.5s infinite}@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
.panel-f{flex:1;overflow-y:auto;padding:10px 14px}
.act{display:flex;gap:10px;padding:10px 0;border-bottom:1px solid var(--b1)}.act:last-child{border-bottom:none}.act-d{width:9px;height:9px;border-radius:50%;margin-top:4px;flex-shrink:0;position:relative}.act-d::after{content:'';position:absolute;top:13px;left:3.5px;width:2px;bottom:-14px;background:var(--b1)}.act:last-child .act-d::after{display:none}
.act-d.fire{background:var(--fire);box-shadow:0 0 7px var(--fireg)}.act-d.volt{background:var(--volt);box-shadow:0 0 7px var(--voltg)}.act-d.mint{background:var(--mint);box-shadow:0 0 7px var(--mintg)}.act-d.grape{background:var(--grape);box-shadow:0 0 7px var(--grapeg)}.act-d.amber{background:var(--amber);box-shadow:0 0 5px rgba(255,167,38,.3)}.act-d.ice{background:var(--ice);box-shadow:0 0 5px rgba(0,212,255,.3)}
.act-b{flex:1;min-width:0}.act-t{font-size:12px;font-weight:600;line-height:1.3}.act-m{font-family:var(--mono);font-size:9.5px;color:var(--t3);margin-top:2px;display:flex;gap:8px}.act-box{margin-top:5px;background:var(--s2);border:1px solid var(--b1);border-radius:6px;padding:7px 9px;font-size:11px;color:var(--t2);line-height:1.45}
.empty{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:40px 20px;text-align:center}.empty-icon{width:48px;height:48px;border-radius:14px;display:flex;align-items:center;justify-content:center;margin-bottom:12px}.empty-icon svg{width:24px;height:24px}.empty-title{font-family:var(--disp);font-size:16px;font-weight:700;margin-bottom:6px}.empty-desc{font-size:12px;color:var(--t3);max-width:320px;line-height:1.5}
.ck-item{display:flex;align-items:flex-start;gap:10px;padding:10px 16px;border-bottom:1px solid var(--b1);transition:background .1s}.ck-item:hover{background:rgba(255,255,255,.01)}.ck-item:last-child{border-bottom:none}.ck-num{font-family:var(--mono);font-size:10px;font-weight:700;color:var(--t3);width:22px;text-align:center;margin-top:2px;flex-shrink:0}.ck-body{flex:1;min-width:0}.ck-title{font-size:12px;font-weight:600;line-height:1.3}.ck-meta{font-family:var(--mono);font-size:9px;color:var(--t3);margin-top:2px;display:flex;gap:8px}
.sec{margin-bottom:20px}.sec-h{font-family:var(--disp);font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--t3);margin-bottom:10px;display:flex;align-items:center;gap:8px}.sec-h::after{content:'';flex:1;height:1px;background:var(--b1)}
.kpi{display:flex;align-items:center;gap:10px;background:var(--s3);border:1px solid var(--b1);border-radius:10px;padding:12px 14px}.kpi-val{font-family:var(--mono);font-size:24px;font-weight:700;line-height:1}.kpi-info{font-size:10px;color:var(--t2)}.kpi-info strong{display:block;font-size:11px;color:var(--t1);font-weight:600}
.loading{display:flex;align-items:center;justify-content:center;height:60vh;color:var(--t3);font-size:14px;font-family:var(--mono)}.hidden{display:none}
@media(max-width:1100px){.shell{grid-template-columns:56px 1fr}.panel{display:none}}
@media(max-width:700px){.shell{grid-template-columns:1fr}.rail{display:none}.main{margin-left:0;padding:12px}.hero{grid-template-columns:1fr 1fr}.g2,.g3{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="shell">
<nav class="rail" id="rail"></nav>
<div class="main"><div id="loading" class="loading">Loading job data...</div><div id="content" class="hidden"></div></div>
<aside class="panel"><div class="panel-h"><h2>Activity</h2><div class="live">Live</div></div><div class="panel-f" id="activityFeed"></div></aside>
</div>
<script>const D = ${jsonData};</script>
<script src="/jt-app.js"></script>
</body>
</html>`;
}