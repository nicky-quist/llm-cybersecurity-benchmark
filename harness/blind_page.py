"""
The blind comparison pages, and the index that ties them together.

Separated from judge.py because these are large HTML templates and mixing them
into the judging logic made both hard to read. Templates use %%TOKEN%%
placeholders rather than f-strings, so the embedded CSS and JavaScript braces do
not have to be doubled.

The page never learns which model wrote which response. It records a verdict of
"a" or "b" against a pairing id; judge.py maps that back to model names using the
same seed that decided the presentation order. That separation is what makes the
blinding real rather than cosmetic — there is nothing in the delivered HTML that
a determined judge could inspect to work out the answer.

Verdicts live in the browser's localStorage until exported, so judging can be
done across several sittings without a server round trip.
"""
import html
import json
import os

STORAGE_KEY = "llmsec-verdicts-v1"

# Shared by the comparison pages and the index.
BASE_CSS = """
:root{--bg:#0a1120;--panel:#0f1729;--line:#223052;--text:#e9eefa;--muted:#93a4c2;
      --faint:#66789a;--accent:#59b6ff;--ok:#34d399;--warn:#f5b544}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
     font:15px/1.7 Inter,Segoe UI,system-ui,sans-serif}
a{color:var(--accent)}
header{padding:18px 24px;border-bottom:1px solid var(--line);background:var(--bg)}
h1{margin:0 0 8px;font-size:.82rem;letter-spacing:.7px;text-transform:uppercase;color:var(--faint)}
.q{margin:0;max-width:100ch;color:#cfdaf0}
.btn{border:1px solid var(--line);background:var(--panel);color:var(--text);
     border-radius:9px;padding:9px 14px;font:inherit;font-size:.85rem;cursor:pointer}
.btn:hover{border-color:var(--faint)}
.btn.primary{background:var(--accent);border-color:var(--accent);color:#04121f;font-weight:600}
.btn.on{background:var(--ok);border-color:var(--ok);color:#04121f;font-weight:700}
.btn:disabled{opacity:.45;cursor:not-allowed}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
"""

MD_CSS = """
.md h3{font-size:1rem;margin:22px 0 8px;color:#eaf0fb}
.md h4{font-size:.92rem;margin:18px 0 6px;color:#cfdaf0}
.md p{margin:0 0 12px}
.md ul,.md ol{margin:0 0 12px;padding-left:22px}
.md li{margin-bottom:6px}
.md code{background:#16223c;padding:1px 6px;border-radius:5px;
         font:12.5px ui-monospace,Consolas,monospace}
.md pre{background:#080e1b;border:1px solid var(--line);border-radius:8px;padding:12px;
        overflow-x:auto;margin:0 0 14px}
.md pre code{background:none;padding:0;font-size:12.5px;line-height:1.6}
.md table{border-collapse:collapse;margin:0 0 14px;width:100%;font-size:.88rem}
.md th,.md td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
.md th{background:#16223c}
.md strong{color:#fff}
"""

# Minimal Markdown renderer. Both responses go through it unchanged — rendering
# one side differently would hand it a presentation advantage unrelated to
# content, which is the opposite of what a blind comparison is for.
MD_JS = r"""
function md(src){
  const esc=s=>s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  const blocks=[];
  src=src.replace(/```(\w*)\n([\s\S]*?)```/g,(m,lang,code)=>{
    blocks.push('<pre><code>'+esc(code.replace(/\s+$/,''))+'</code></pre>');
    return '\u0000'+(blocks.length-1)+'\u0000';
  });
  const inline=s=>esc(s)
    .replace(/`([^`]+)`/g,'<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g,'$1<em>$2</em>');
  const out=[]; let list=null,table=null,para=[];
  const closeList=()=>{if(list){out.push('</'+list+'>');list=null;}};
  const closeTable=()=>{if(table){out.push('</tbody></table>');table=null;}};
  const closePara=()=>{if(para.length){out.push('<p>'+inline(para.join(' '))+'</p>');para=[];}};
  const closeAll=()=>{closePara();closeList();closeTable();};
  for(const raw of src.split('\n')){
    const line=raw.replace(/\s+$/,'');
    const ph=line.match(/^\u0000(\d+)\u0000$/);
    if(ph){closeAll();out.push(blocks[+ph[1]]);continue;}
    if(!line.trim()){closeAll();continue;}
    const h=line.match(/^(#{1,6})\s+(.*)$/);
    if(h){closeAll();const l=Math.min(h[1].length+2,5);
      out.push('<h'+l+'>'+inline(h[2])+'</h'+l+'>');continue;}
    if(/^\|/.test(line)){
      if(/^[\s|:-]+$/.test(line))continue;
      const cells=line.split('|').slice(1,-1).map(c=>c.trim());
      if(!table){closePara();closeList();
        out.push('<table><thead><tr>'+cells.map(c=>'<th>'+inline(c)+'</th>').join('')+'</tr></thead><tbody>');
        table=true;continue;}
      out.push('<tr>'+cells.map(c=>'<td>'+inline(c)+'</td>').join('')+'</tr>');continue;
    }
    closeTable();
    const ul=line.match(/^\s*[-*]\s+(.*)$/), ol=line.match(/^\s*\d+[.)]\s+(.*)$/);
    if(ul||ol){closePara();const want=ul?'ul':'ol';
      if(list!==want){closeList();out.push('<'+want+'>');list=want;}
      out.push('<li>'+inline((ul||ol)[1])+'</li>');continue;}
    closeList(); para.push(line);
  }
  closeAll(); return out.join('\n');
}
// Python's html.escape also encodes apostrophes as &#x27;. Reverse everything it
// emits, &amp; last so a literal "&amp;lt;" is not double-decoded.
const un=s=>s.replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"')
             .replace(/&#x27;/g,"'").replace(/&#39;/g,"'").replace(/&amp;/g,'&');
"""

PAGE = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Blind comparison %%PID%%</title>
<style>%%BASE_CSS%%%%MD_CSS%%
header{position:sticky;top:0;z-index:6}
.topline{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);align-items:start}
section{background:var(--bg);padding:22px 24px;min-width:0}
h2{margin:0 0 16px;font-size:.9rem;color:var(--accent);letter-spacing:.6px;
   position:sticky;top:96px;background:var(--bg);padding:8px 0;z-index:4}
.verdict{position:sticky;bottom:0;background:var(--panel);border-top:1px solid var(--line);
         padding:16px 24px;z-index:8}
.vrow{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
.vrow .lbl{color:var(--faint);font-size:.75rem;text-transform:uppercase;letter-spacing:.7px;
           font-weight:700;min-width:78px}
.rubrics{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:14px}
.rub{border:1px solid var(--line);border-radius:10px;padding:12px 14px;background:var(--bg)}
.rub h3{margin:0 0 10px;font-size:.8rem;color:var(--accent);letter-spacing:.5px}
.dim{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:center;margin-bottom:7px}
.dim label{font-size:.8rem;color:var(--muted)}
.dim .scale{display:flex;gap:3px}
.dim .scale button{width:26px;height:26px;border-radius:6px;border:1px solid var(--line);
  background:var(--panel);color:var(--muted);cursor:pointer;font-size:.75rem;padding:0}
.dim .scale button.sel{background:var(--accent);border-color:var(--accent);color:#04121f;font-weight:700}
textarea{width:100%;background:var(--bg);border:1px solid var(--line);border-radius:9px;
         color:var(--text);padding:10px 12px;font:inherit;font-size:.85rem;resize:vertical}
.saved{color:var(--ok);font-size:.82rem}
.nav{display:flex;gap:8px;align-items:center}
@media(max-width:900px){.cols,.rubrics{grid-template-columns:1fr}h2{position:static}}
</style></head><body>
<header>
  <div class="topline">
    <h1>Blind comparison %%PID%% &middot; %%CATEGORY%%</h1>
    <div class="nav">
      <a class="btn" href="index.html">All comparisons</a>
      %%PREV%%%%NEXT%%
    </div>
  </div>
  <p class="q">%%PROMPT%%</p>
</header>
<div class="cols">
  <section><h2>Response A</h2><div class="md" id="a"></div></section>
  <section><h2>Response B</h2><div class="md" id="b"></div></section>
</div>
<div class="verdict">
  <div class="vrow">
    <span class="lbl">Verdict</span>
    <button class="btn" id="pickA" type="button">A is better</button>
    <button class="btn" id="pickB" type="button">B is better</button>
    <button class="btn" id="pickSkip" type="button">Skip</button>
    <span class="saved" id="savedMsg"></span>
  </div>
  <div class="rubrics">
    <div class="rub"><h3>Response A</h3><div id="rubA"></div></div>
    <div class="rub"><h3>Response B</h3><div id="rubB"></div></div>
  </div>
  <div class="vrow" style="align-items:flex-start">
    <span class="lbl" style="padding-top:10px">Why</span>
    <textarea id="rationale" rows="2" placeholder="One line — what decided it?"></textarea>
  </div>
</div>
<script id="src-a" type="text/plain">%%A_TEXT%%</script>
<script id="src-b" type="text/plain">%%B_TEXT%%</script>
<script>
%%MD_JS%%
document.getElementById('a').innerHTML = md(un(document.getElementById('src-a').textContent));
document.getElementById('b').innerHTML = md(un(document.getElementById('src-b').textContent));

const PID = "%%PID%%";
const KEY = "%%STORAGE_KEY%%";
const DIMS = %%DIMS%%;

function loadAll(){ try { return JSON.parse(localStorage.getItem(KEY) || "{}"); }
                    catch(e){ return {}; } }
function saveAll(v){ try { localStorage.setItem(KEY, JSON.stringify(v)); return true; }
                     catch(e){ return false; } }

let state = loadAll()[PID] || {choice:null, a:{}, b:{}, rationale:""};

function buildRubric(side, host){
  host.innerHTML = DIMS.map(d =>
    '<div class="dim"><label title="'+d[1]+'">'+d[0]+'</label><span class="scale">'
    + [1,2,3,4,5].map(n => '<button type="button" data-side="'+side+'" data-dim="'+d[0]
        +'" data-n="'+n+'">'+n+'</button>').join('') + '</span></div>').join('');
}
buildRubric('a', document.getElementById('rubA'));
buildRubric('b', document.getElementById('rubB'));

function paint(){
  document.getElementById('pickA').classList.toggle('on', state.choice==='a');
  document.getElementById('pickB').classList.toggle('on', state.choice==='b');
  document.getElementById('pickSkip').classList.toggle('on', state.choice==='skip');
  document.querySelectorAll('.scale button').forEach(b => {
    const v = state[b.dataset.side][b.dataset.dim];
    b.classList.toggle('sel', String(v) === b.dataset.n);
  });
  document.getElementById('rationale').value = state.rationale || "";
}

function persist(){
  const all = loadAll();
  all[PID] = state;
  const ok = saveAll(all);
  const msg = document.getElementById('savedMsg');
  msg.textContent = ok
    ? "saved locally" + (state.choice ? "" : " — no verdict yet")
    : "could not save (private browsing?) — export before closing";
  paint();
}

document.querySelectorAll('.scale button').forEach(b =>
  b.addEventListener('click', () => {
    state[b.dataset.side][b.dataset.dim] =
      state[b.dataset.side][b.dataset.dim] === +b.dataset.n ? undefined : +b.dataset.n;
    persist();
  }));
for (const [id, val] of [['pickA','a'],['pickB','b'],['pickSkip','skip']]) {
  document.getElementById(id).addEventListener('click', () => {
    state.choice = state.choice === val ? null : val;
    persist();
  });
}
document.getElementById('rationale').addEventListener('input', e => {
  state.rationale = e.target.value; persist();
});
paint();
</script>
</body></html>"""

INDEX = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Blind judging</title>
<style>%%BASE_CSS%%
.wrap{max-width:1000px;margin:0 auto;padding:26px 24px 60px}
h2{margin:0 0 6px;font-size:1.5rem;letter-spacing:-.5px}
.lede{color:var(--muted);margin:0 0 22px;max-width:80ch}
table{width:100%;border-collapse:collapse;margin-bottom:22px}
th,td{text-align:left;padding:11px 13px;border-bottom:1px solid var(--line);font-size:.88rem}
th{color:var(--faint);font-size:.72rem;text-transform:uppercase;letter-spacing:.7px}
tr:hover{background:var(--panel)}
.pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:.75rem;font-weight:600;
      border:1px solid var(--line);color:var(--faint)}
.pill.done{color:var(--ok);border-color:var(--ok)}
.pill.part{color:var(--warn);border-color:var(--warn)}
.bar{height:8px;border-radius:5px;background:var(--panel);overflow:hidden;margin:0 0 22px}
.bar>span{display:block;height:100%;background:var(--ok)}
.exportbox{width:100%;height:190px;background:var(--panel);border:1px solid var(--line);
  border-radius:10px;color:var(--text);padding:12px;font:12px ui-monospace,Consolas,monospace;
  margin-top:12px}
.note{color:var(--faint);font-size:.84rem;line-height:1.65;margin:10px 0 0}
code{background:var(--panel);padding:1px 6px;border-radius:5px;font-size:.85em}
</style></head><body><div class="wrap">
<h2>Blind judging</h2>
<p class="lede">Model identities are withheld. Pick a winner, score the rubric, then export
and hand the file to <code>harness/judge.py --import</code>. Progress is stored in this
browser only — export before clearing site data.</p>
<div class="bar"><span id="bar" style="width:0%"></span></div>
<table><thead><tr><th>#</th><th>Category</th><th>Prompt</th><th>Status</th></tr></thead>
<tbody id="rows"></tbody></table>
<button class="btn primary" id="exportBtn" type="button">Export verdicts</button>
<button class="btn" id="clearBtn" type="button">Clear all</button>
<textarea class="exportbox" id="out" readonly placeholder="Export output appears here — copy it into a file."></textarea>
<p class="note">Save it as <code>harness/verdicts.json</code>, then run:<br>
<code>python harness/judge.py --import harness/verdicts.json --append</code></p>
</div>
<script>
const KEY = "%%STORAGE_KEY%%";
const PAIRINGS = %%PAIRINGS%%;
function loadAll(){ try { return JSON.parse(localStorage.getItem(KEY) || "{}"); }
                    catch(e){ return {}; } }

function render(){
  const all = loadAll();
  let done = 0;
  document.getElementById('rows').innerHTML = PAIRINGS.map(p => {
    const v = all[String(p.pairing_id)];
    let cls = "", label = "not started";
    if (v && v.choice === 'skip') { cls = "part"; label = "skipped"; }
    else if (v && v.choice) { cls = "done"; label = "judged"; done++; }
    else if (v) { cls = "part"; label = "in progress"; }
    return '<tr><td><a href="pairing-' + String(p.pairing_id).padStart(3,'0') + '.html">'
      + p.pairing_id + '</a></td><td>' + p.category + '</td><td>' + p.prompt_id
      + '</td><td><span class="pill ' + cls + '">' + label + '</span></td></tr>';
  }).join('');
  document.getElementById('bar').style.width =
    (PAIRINGS.length ? (done / PAIRINGS.length) * 100 : 0) + '%';
}

document.getElementById('exportBtn').addEventListener('click', () => {
  const all = loadAll();
  const out = PAIRINGS.filter(p => all[String(p.pairing_id)] &&
                                   all[String(p.pairing_id)].choice &&
                                   all[String(p.pairing_id)].choice !== 'skip')
    .map(p => Object.assign({pairing_id: p.pairing_id}, all[String(p.pairing_id)]));
  document.getElementById('out').value = JSON.stringify(out, null, 2);
  document.getElementById('out').select();
});
document.getElementById('clearBtn').addEventListener('click', () => {
  if (confirm('Delete every verdict stored in this browser?')) {
    try { localStorage.removeItem(KEY); } catch(e) {}
    document.getElementById('out').value = ''; render();
  }
});
render();
</script></body></html>"""


def _fill(template, mapping):
    for token, value in mapping.items():
        template = template.replace(f"%%{token}%%", value)
    return template


def render_comparison(path, pairing, prompt, a_text, b_text, rubric, prev_id, next_id):
    prev_link = (f'<a class="btn" href="pairing-{prev_id:03d}.html">&larr; prev</a>'
                 if prev_id is not None else "")
    next_link = (f'<a class="btn" href="pairing-{next_id:03d}.html">next &rarr;</a>'
                 if next_id is not None else "")

    page = _fill(PAGE, {
        "BASE_CSS": BASE_CSS,
        "MD_CSS": MD_CSS,
        "MD_JS": MD_JS,
        "PID": str(pairing["pairing_id"]),
        "CATEGORY": html.escape(pairing["category"]),
        "PROMPT": html.escape(prompt["prompt_text"]),
        "A_TEXT": html.escape(a_text),
        "B_TEXT": html.escape(b_text),
        "DIMS": json.dumps([[k, d] for k, d in rubric]),
        "STORAGE_KEY": STORAGE_KEY,
        "PREV": prev_link,
        "NEXT": next_link,
    })
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    return path


def render_index(path, pairings):
    rows = [{"pairing_id": p["pairing_id"], "prompt_id": p["prompt_id"],
             "category": p["category"]} for p in pairings]
    page = _fill(INDEX, {
        "BASE_CSS": BASE_CSS,
        "STORAGE_KEY": STORAGE_KEY,
        "PAIRINGS": json.dumps(rows),
    })
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    return path
