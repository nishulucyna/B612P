"""Turns deliverables/npu_proof_data.json (measured on the board by scripts/npu_proof.py) into one self-contained HTML page.
No external libraries or fonts: it opens offline.   python scripts/npu_proof_report.py"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
data = json.loads((ROOT / "deliverables" / "npu_proof_data.json").read_text())

# ---- derive the numbers shown (all from the recorded samples) ----------------------------------------------------------
tl = data["timeline"]
zones = tl["zones"]
rows = tl["rows"]            # t, cdsp_irq, adsp_irq, app_cpu_ticks, sys_busy, sys_idle, temps...
t0 = rows[0][0]
series = dict(t=[], cdsp=[], adsp=[], cores=[], hvx=[], hmx=[])
hvx_i = [i for i, z in enumerate(zones) if "hvx" in z]
hmx_i = [i for i, z in enumerate(zones) if "hmx" in z]
prev = rows[0]
for r in rows[1:]:
    dt = r[0] - prev[0]
    if dt <= 0.05:
        continue
    series["t"].append(round(r[0] - t0, 2))
    series["cdsp"].append(round((r[1] - prev[1]) / dt, 1))
    series["adsp"].append(round((r[2] - prev[2]) / dt, 1))
    series["cores"].append(round(max(0.0, (r[3] - prev[3]) / 100.0 / dt), 2))
    series["hvx"].append(round(max(r[6 + i] for i in hvx_i) / 1000.0, 1))
    series["hmx"].append(round(max(r[6 + i] for i in hmx_i) / 1000.0, 1))
    prev = r
phases = [dict(name=p["name"], a=round(p["t0"] - t0, 2), b=round(p["t1"] - t0, 2)) for p in tl["phases"]]


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def in_phase(name_part, key):
    vals = []
    for p in phases:
        if name_part in p["name"]:
            vals += [v for t, v in zip(series["t"], series[key]) if p["a"] <= t <= p["b"]]
    return vals


stats = {}
for label, part in (("idle", "idle"), ("stt", "speech"), ("llm", "language")):
    stats[label] = dict(cdsp=mean(in_phase(part, "cdsp")), adsp=mean(in_phase(part, "adsp")), cores=mean(in_phase(part, "cores")),
                        hmx_max=max(in_phase(part, "hmx") or [0]), hvx_max=max(in_phase(part, "hvx") or [0]))

payload = dict(series=series, phases=phases, stats=stats, receipts=data["receipts"], encoder_ab=data.get("encoder_ab"),
               llm_ab=data.get("llm_ab"), created=data["created"], transcripts=tl.get("transcripts"))

HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NPU Proof</title>
<style>
:root{--bg:#050914;--card:#0c1426;--line:#1b2c4d;--txt:#e6eefc;--mut:#8aa0c8;--cy:#22d3ee;--vi:#a78bfa;--gr:#34d399;--am:#fbbf24;--rd:#f87171;--bl:#60a5fa}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(1200px 600px at 70% -10%,#13244a 0,transparent 60%),var(--bg);color:var(--txt);font:15px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:28px 16px 80px}
h1{font-size:clamp(26px,5vw,44px);margin:0;letter-spacing:-.02em}h1 b{background:linear-gradient(90deg,var(--cy),var(--vi));-webkit-background-clip:text;color:transparent}
.sub{color:var(--mut);margin:6px 0 22px}h2{margin:34px 0 10px;font-size:20px}h2 small{color:var(--mut);font-weight:400;font-size:13px;margin-left:8px}
.grid{display:grid;gap:12px}.g4{grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}.g2{grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}
.card{background:linear-gradient(180deg,#0e1a33,var(--card));border:1px solid var(--line);border-radius:14px;padding:14px 16px}
.k{color:var(--mut);font-size:12px;letter-spacing:.08em;text-transform:uppercase}.v{font-size:26px;font-weight:700;margin-top:2px}.v small{font-size:13px;color:var(--mut);font-weight:500}
.ok{color:var(--gr)}.cy{color:var(--cy)}.am{color:var(--am)}
.pill{display:inline-block;padding:2px 10px;border-radius:99px;font-size:12px;font-weight:600;border:1px solid}
.npu{color:var(--cy);border-color:#0e7490;background:#06303a}.cpu{color:var(--am);border-color:#92400e;background:#33200a}
.pipe{display:flex;flex-wrap:wrap;gap:8px;align-items:stretch}.node{flex:1 1 150px;border:1px solid var(--line);border-radius:12px;padding:10px 12px;background:#0b1325;position:relative}
.node.npuN{border-color:#0e7490;box-shadow:0 0 22px #22d3ee22 inset,0 0 18px #22d3ee22;animation:glow 2.4s ease-in-out infinite}
@keyframes glow{50%{box-shadow:0 0 30px #22d3ee44 inset,0 0 26px #22d3ee44}}
.node h4{margin:0 0 4px;font-size:14px}.node p{margin:4px 0 0;color:var(--mut);font-size:12.5px}.arrow{align-self:center;color:var(--mut)}
canvas{width:100%;display:block;background:#08101f;border:1px solid var(--line);border-radius:12px}
.legend{display:flex;gap:14px;flex-wrap:wrap;color:var(--mut);font-size:12.5px;margin:6px 2px 14px}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
.bar{min-width:74px;height:26px;border-radius:7px;display:flex;align-items:center;padding:0 10px;font-weight:600;font-size:13px;color:#06101f;white-space:nowrap}
.row{display:grid;grid-template-columns:90px 1fr;gap:10px;align-items:center;margin:6px 0}
details{background:#0b1325;border:1px solid var(--line);border-radius:10px;margin:8px 0;padding:8px 12px}summary{cursor:pointer;color:var(--cy);font-weight:600}
pre{white-space:pre-wrap;word-break:break-word;color:#b6c7e8;font-size:12.5px;margin:8px 0 0}
.note{border-left:3px solid var(--am);background:#1a1405;padding:10px 14px;border-radius:0 10px 10px 0;color:#f3deaa;font-size:13.5px}
button{background:#0e7490;color:#fff;border:0;border-radius:9px;padding:7px 14px;font-weight:600;cursor:pointer}
table{width:100%;border-collapse:collapse;font-size:13.5px}td,th{padding:7px 8px;border-bottom:1px solid var(--line);text-align:left}th{color:var(--mut);font-weight:600}
</style></head><body><div class="wrap">
<h1><b>NPU Proof</b> &mdash; measured on the board, not claimed</h1>
<div class="sub" id="sub"></div>

<div class="grid g4" id="hero"></div>

<h2>Where every step runs <small>honest map: the NPU does the AI, the CPU does glue code</small></h2>
<div class="pipe" id="pipe"></div>

<h2>Live hardware trace <small>recorded on the board while it transcribed speech and extracted incident data</small></h2>
<div style="display:flex;gap:10px;align-items:center;margin-bottom:8px"><button id="replay">&#9654; Replay</button><span class="legend" style="margin:0" id="phaseLegend"></span></div>
<canvas id="c1" height="210"></canvas>
<div class="legend"><span><i style="background:var(--cy)"></i>cDSP / NPU message channel (interrupts per second)</span><span><i style="background:var(--rd)"></i>audio DSP channel (control, must stay flat)</span></div>
<canvas id="c2" height="170"></canvas>
<div class="legend"><span><i style="background:var(--vi)"></i>NPU matrix units HMX (&deg;C)</span><span><i style="background:var(--gr)"></i>NPU vector units HVX (&deg;C)</span></div>
<canvas id="c3" height="150"></canvas>
<div class="legend"><span><i style="background:var(--am)"></i>CPU cores used by the app</span></div>
<div class="grid g4" id="phaseStats"></div>

<h2>Same model, NPU vs CPU <small>A/B on the same board</small></h2>
<div class="grid g2" id="ab"></div>

<h2>Receipts <small>raw output from the board</small></h2>
<div id="rec"></div>

<h2>What this does and does not show</h2>
<div class="note" id="caveats"></div>
</div>
<script>
const D=__DATA__;
const $=s=>document.querySelector(s);
const f=(x,d=1)=>Number(x).toFixed(d);
const R=D.receipts, H=R.health, S=D.stats;
$('#sub').textContent=`Qualcomm HDK8650 (${R.soc||'SM8650'}), Hexagon v75 NPU  ·  captured ${D.created}  ·  ${R.wifi||''}`;

// ---- hero cards
const cd=R.remoteproc.find(r=>/cdsp/.test(r.name))||{};
const w=/weights: (\d+) MiB on HTP0, (\d+) MiB on CPU/.exec(H.llm)||[];
const hero=[
 ['NPU subsystem (cDSP)',`<span class="ok">${(cd.state||'?').toUpperCase()}</span>`,cd.name||''],
 ['Speech recognition',`<span class="cy">encoder + decoder on DSP</span>`,H.stt],
 ['Language model',`<span class="cy">${w[1]||'?'} MiB on the NPU</span>`,w[2]?`${w[2]} MiB (embedding tables) stay in CPU memory`:''],
 ['NPU activity while working',`<span class="cy">${f((S.stt.cdsp+S.llm.cdsp)/2,0)}/s</span> <small>vs ${f(S.idle.cdsp,1)}/s idle</small>`,'cDSP interrupt rate, audio-DSP control: '+f(Math.max(S.stt.adsp,S.llm.adsp),1)+'/s'],
 ['Cloud / network',`<span class="ok">none</span>`,R.wifi+' · no outbound-network code in the app'],
 ['Hexagon libraries in the app',`<span class="cy">${R.mapped_libs.length} loaded</span>`,R.mapped_libs.slice(0,4).join(', ')],
];
$('#hero').innerHTML=hero.map(([k,v,s])=>`<div class="card"><div class="k">${k}</div><div class="v">${v}</div><div style="color:var(--mut);font-size:12px;margin-top:4px;word-break:break-word">${s}</div></div>`).join('');

// ---- pipeline
const P=[
 ['Microphone','Android AudioRecord, 16 kHz','CPU','cpu'],
 ['Mel spectrogram','80×3000 log-mel features','CPU','cpu'],
 ['Whisper encoder','small, w8a16, HTP graph','NPU · Hexagon DSP','npu'],
 ['Whisper decoder','small, fp16, HTP graph, greedy','NPU · Hexagon DSP','npu'],
 ['Information extraction','LLM, grammar-constrained JSON','NPU · HTP (Gemma)','npu'],
 ['Diamond gate + form','plain deterministic code','CPU','cpu'],
 ['Screen','native touch UI','CPU / GPU','cpu']];
$('#pipe').innerHTML=P.map((p,i)=>`${i?'<span class="arrow">➜</span>':''}<div class="node ${p[3]=='npu'?'npuN':''}"><h4>${p[0]}</h4><span class="pill ${p[3]}">${p[2]}</span><p>${p[1]}</p></div>`).join('');

// ---- charts
const s=D.series, T=s.t[s.t.length-1];
const phaseColor=n=>/speech/.test(n)?'#22d3ee':/language/.test(n)?'#a78bfa':'#ffffff';
$('#phaseLegend').innerHTML=D.phases.filter(p=>!/idle/.test(p.name)).map(p=>`<span><i style="background:${phaseColor(p.name)};display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px"></i>${p.name}</span>`).join('');
function chart(id,lines,ymin,ymax,unit,upto){
 const c=$(id),dpr=devicePixelRatio||1,W=c.clientWidth,Hh=+c.getAttribute('height');c.width=W*dpr;c.height=Hh*dpr;
 const x=c.getContext('2d');x.scale(dpr,dpr);x.clearRect(0,0,W,Hh);
 const L=48,Rr=10,Tp=10,B=22,pw=W-L-Rr,ph=Hh-Tp-B,X=t=>L+pw*t/T,Y=v=>Tp+ph*(1-(v-ymin)/(ymax-ymin));
 D.phases.forEach(p=>{if(/idle/.test(p.name))return;x.fillStyle=phaseColor(p.name)+'18';x.fillRect(X(p.a),Tp,X(p.b)-X(p.a),ph);});
 x.strokeStyle='#1b2c4d';x.fillStyle='#8aa0c8';x.font='11px system-ui';x.lineWidth=1;
 for(let i=0;i<=4;i++){const v=ymin+(ymax-ymin)*i/4,yy=Y(v);x.beginPath();x.moveTo(L,yy);x.lineTo(W-Rr,yy);x.stroke();x.fillText(f(v,ymax-ymin<20?1:0)+unit,4,yy+4);}
 for(let t=0;t<=T;t+=10){x.fillText(t+'s',X(t)-8,Hh-6);}
 lines.forEach(([key,col])=>{x.strokeStyle=col;x.lineWidth=2;x.shadowColor=col;x.shadowBlur=8;x.beginPath();let first=true;
  for(let i=0;i<s.t.length;i++){if(s.t[i]>upto)break;const px=X(s.t[i]),py=Y(s[key][i]);first?x.moveTo(px,py):x.lineTo(px,py);first=false;}x.stroke();x.shadowBlur=0;});
}
function draw(upto){
 const cm=Math.max(10,Math.ceil(Math.max(...s.cdsp)/10)*10);
 chart('#c1',[['adsp','#f87171'],['cdsp','#22d3ee']],0,cm,'/s',upto);
 const allT=s.hmx.concat(s.hvx);chart('#c2',[['hvx','#34d399'],['hmx','#a78bfa']],Math.floor(Math.min(...allT)-2),Math.ceil(Math.max(...allT)+2),'°',upto);
 chart('#c3',[['cores','#fbbf24']],0,Math.max(2,Math.ceil(Math.max(...s.cores))),' cores',upto);
}
let raf;function replay(){cancelAnimationFrame(raf);const t0=performance.now(),dur=9000;(function step(now){const u=Math.min(1,(now-t0)/dur);draw(T*u);if(u<1)raf=requestAnimationFrame(step);})(t0);}
$('#replay').onclick=replay;addEventListener('resize',()=>draw(T));if(location.search.includes('static'))draw(T);else replay();

// ---- phase stats
const ps=[['Idle',S.idle],['Speech recognition',S.stt],['Language model',S.llm]];
$('#phaseStats').innerHTML=ps.map(([n,v])=>`<div class="card"><div class="k">${n}</div>
 <div style="margin-top:6px">NPU channel <b class="cy">${f(v.cdsp,1)}/s</b></div><div>audio-DSP channel <b>${f(v.adsp,1)}/s</b></div>
 <div>NPU matrix temp peak <b>${f(v.hmx_max,1)}&deg;C</b></div><div>CPU used <b class="am">${f(v.cores,1)} cores</b></div></div>`).join('');

// ---- A/B
let ab='';
if(D.encoder_ab){const e=D.encoder_ab,m=Math.max(e.cpu.per_inference,e.gpu.per_inference,e.npu.per_inference);
 const row=(n,x,c)=>`<div class="row"><span>${n}</span><div class="bar" style="width:${Math.max(9,100*x.per_inference/m)}%;background:${c}">${f(x.per_inference*1000,0)} ms</div></div>`;
 ab+=`<div class="card"><div class="k">Whisper-small encoder, one 30 s clip</div>${row('NPU (w8a16)',e.npu,'var(--cy)')}${row('GPU (Adreno)',e.gpu,'var(--vi)')}${row('CPU (fp32)',e.cpu,'var(--am)')}
 <div class="v ok" style="margin-top:8px">${f(e.speedup,1)}× faster than the CPU, ${f(e.speedup_vs_gpu,1)}× faster than the GPU</div>
 <div style="color:var(--mut);font-size:12px">wall time of snpe-net-run, 7 inferences minus 1 (start-up excluded); the CPU and GPU run the fp32 graph, the NPU the w8a16 graph</div></div>`;}
if(D.llm_ab&&D.llm_ab.npu&&D.llm_ab.cpu){const a=D.llm_ab,g=(x,k)=>{const m=new RegExp(k+' ([0-9.]+) tok/s').exec((x.log||[''])[0]||'');return m?+m[1]:null};
 const rowf=(n,v,mx,c,extra)=>`<div class="row"><span>${n}</span><div class="bar" style="width:${Math.max(9,100*v/mx)}%;background:${c}">${extra}</div></div>`;
 const pn=g(a.npu,'prefill'),pc=g(a.cpu,'prefill'),dn=g(a.npu,'decode'),dc=g(a.cpu,'decode');
 ab+=`<div class="card"><div class="k">Same LLM file, compute_unit NPU vs CPU</div>
 <div style="margin-top:6px;color:var(--mut);font-size:12.5px">Prompt processing (prefill, tokens/s)</div>
 ${rowf('NPU',pn,Math.max(pn,pc),'var(--cy)',f(pn,0)+' tok/s')}${rowf('CPU',pc,Math.max(pn,pc),'var(--am)',f(pc,0)+' tok/s')}
 <div style="margin-top:6px;color:var(--mut);font-size:12.5px">Answer generation (decode, tokens/s)</div>
 ${rowf('NPU',dn,Math.max(dn,dc),'var(--cy)',f(dn,1)+' tok/s')}${rowf('CPU',dc,Math.max(dn,dc),'var(--am)',f(dc,1)+' tok/s')}
 <div class="v ok" style="margin-top:8px">${f(a.cpu.seconds/a.npu.seconds,1)}× faster per extraction <small>(${f(a.npu.seconds,1)} s vs ${f(a.cpu.seconds,1)} s)</small></div>
 <div style="color:var(--mut);font-size:12px">prefill is ${f(pn/pc,1)}× faster on the NPU; decode only ${f(dn/dc,1)}× because part of the weights stay in CPU memory. Placement on the CPU run: ${/(\d+) MiB on HTP0/.exec(a.cpu.llm_status)?.[1]} MiB on the NPU; on the NPU run: ${w[1]} MiB.</div></div>`;}
$('#ab').innerHTML=ab||'<div class="card">A/B data not collected.</div>';

// ---- receipts
const rc=[['Remote processors (remoteproc)',R.remoteproc.map(r=>`${r.name}: ${r.state}`).join('\n')],
 ['Hexagon libraries mapped into the app process',R.mapped_libs.join('\n')],
 ['Interrupt channel names used as counters',(R.cdsp_irq||[]).join('\n')],
 ['Engine status reported by the app',JSON.stringify(H,null,1)],
 ['Model files on the board',[].concat(R.models.whisper,R.models.llm).join('\n')],
 ['Permissions of the app',(R.app_permissions||[]).join('\n')],
 ['Transcripts produced during the trace',(D.transcripts||[]).join('\n')]];
$('#rec').innerHTML=rc.map(([k,v])=>`<details><summary>${k}</summary><pre>${String(v).replace(/</g,'&lt;')}</pre></details>`).join('');

$('#caveats').innerHTML=`<b>Be precise:</b> the AI steps (speech recognition and extraction) run on the Hexagon NPU/DSP. The mel-spectrogram, the token-embedding lookup, the tokenizer, the form logic and the screen are ordinary CPU code, as in Qualcomm's own reference apps. `+
 `${w[2]?`The language model keeps ${w[2]} MiB of its weights (large embedding tables, memory lookups rather than matrix maths) in CPU memory and puts ${w[1]} MiB on the NPU. `:''}`+
 `The CPU-core figures above include threads that wait on the NPU. The interrupt counter is the evidence of NPU work; the A/B runs show what the same work costs on the CPU.`;
</script></body></html>"""

out = ROOT / "deliverables" / "npu_proof.html"
out.write_text(HTML.replace("__DATA__", json.dumps(payload)), encoding="utf-8")
print("wrote", out, f"({out.stat().st_size // 1024} KB)")
