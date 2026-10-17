"""Build every published form of the article from one source.

    python scripts/build_article.py            # everything
    python scripts/build_article.py --no-pdf   # skip the PDF (needs Playwright + Chromium)

Reads   article/article.md     prose with [[fact]] and {{fig:id}} / {{figs:a,b}} markers
        solar_analytics.story  every number, computed from data/
        solar_analytics.figures the charts, defined once in Plotly

Writes  site/index.html                 interactive article (GitHub Pages root)
        article/blog.md                 blog-ready markdown with PNG figures
        article/figures/*.png           static charts (kaleido)
        article/rooftop-solar-article.pdf
        FINDINGS.md                     the same text, with repo-relative image paths

Static images need kaleido and a Chrome/Chromium; set BROWSER_PATH if it is
not found automatically.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import markdown  # noqa: E402
import plotly.utils  # noqa: E402

from solar_analytics.figures import FIGURES, PALETTE, build_all  # noqa: E402
from solar_analytics.story import compute  # noqa: E402

ART = ROOT / "article"
FIG_DIR = ART / "figures"
REPO_URL = "https://github.com/piyushdash94/rooftop-solar-analytics"
PLOTLY_JS = "https://cdnjs.cloudflare.com/ajax/libs/plotly.js/4.1.1/plotly-cartesian.min.js"
FIG_RE = re.compile(r"^\{\{(figs?):([a-z_,]+)\}\}\s*$", re.M)


# --------------------------------------------------------------------------- text

def fill(text: str, facts: dict) -> str:
    missing = sorted({k for k in re.findall(r"\[\[(\w+)\]\]", text) if k not in facts})
    if missing:
        raise SystemExit(f"article uses facts that story.compute() does not provide: {missing}")
    return re.sub(r"\[\[(\w+)\]\]", lambda m: str(facts[m.group(1)]), text)


REF_RE = re.compile(r"\{\{ref:([a-z0-9_,]+)\}\}")


def cite(body: str, mode: str) -> str:
    """Number citations by first appearance and append a Sources section.

    mode "md": plain [n] markers and a markdown list (blog, FINDINGS.md)
    mode "html": linked markers and an anchored list (site, PDF)
    """
    refs = json.loads((ART / "references.json").read_text(encoding="utf-8"))
    order: list[str] = []
    for m in REF_RE.finditer(body):
        for k in m.group(1).split(","):
            if k not in refs:
                raise SystemExit(f"unknown reference key in article: {k}")
            if k not in order:
                order.append(k)
    num = {k: i + 1 for i, k in enumerate(order)}

    def rep(m):
        ks = m.group(1).split(",")
        if mode == "md":
            return "[" + ", ".join(str(num[k]) for k in ks) + "]"
        return "".join(f'<a class="ref" href="#ref-{num[k]}">[{num[k]}]</a>' for k in ks)
    out = REF_RE.sub(rep, body).rstrip() + "\n\n## Sources\n\n"
    if mode == "md":
        out += "\n".join(f"{num[k]}. {refs[k]['text']} {refs[k]['url']}" for k in order) + "\n"
    else:
        items = "".join(f'<li id="ref-{num[k]}">{html.escape(refs[k]["text"])} '
                        f'<a href="{html.escape(refs[k]["url"])}">{html.escape(refs[k]["url"])}</a></li>' for k in order)
        out += f'<ol class="refs">{items}</ol>\n'
    return out


def split_header(text: str):
    """Title, deck and byline come off the top; the rest is the body."""
    lines = text.splitlines()
    title = lines[0].lstrip("# ").strip()
    deck = lines[2].strip().strip("*")
    byline = lines[4].strip()
    return title, deck, byline, "\n".join(lines[5:]).lstrip()


def fig_ids(token: str) -> list[str]:
    ids = token.split(",")
    for i in ids:
        if i not in FIGURES:
            raise SystemExit(f"unknown figure id in article: {i}")
    return ids


def caption(fid: str) -> str:
    return FIGURES[fid][1]


# --------------------------------------------------------------------------- static figures

def write_pngs(figs) -> None:
    if not os.environ.get("BROWSER_PATH"):
        for cand in sorted(Path("/opt/pw-browsers").glob("chromium-*/chrome-linux*/chrome")):
            os.environ["BROWSER_PATH"] = str(cand)
            break
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for old in FIG_DIR.glob("*.png"):          # drop images of charts that no longer exist
        if old.stem not in figs:
            old.unlink()
    for fid, fig in figs.items():
        f = fig.full_figure_for_development(warn=False) if False else fig
        g = type(f)(f)
        g.update_layout(paper_bgcolor="#FFFFFF", margin=dict(l=12, r=12, t=12, b=12))
        g.write_image(FIG_DIR / f"{fid}.png", width=960, height=int(fig.layout.height or 320), scale=2)


# --------------------------------------------------------------------------- markdown outputs

def to_markdown(body: str, img_prefix: str) -> str:
    body = re.sub(r'^<div class="glance" markdown="1">\s*$|^</div>\s*$', "", body, flags=re.M)

    def rep(m):
        out = []
        for fid in fig_ids(m.group(2)):
            out.append(f"![{caption(fid)}]({img_prefix}{fid}.png)\n\n*{caption(fid)}*\n")
        return "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", FIG_RE.sub(rep, body))


# --------------------------------------------------------------------------- html outputs

def md_to_html(body: str) -> str:
    md = markdown.Markdown(extensions=["tables", "md_in_html", "toc"],
                           extension_configs={"toc": {"permalink": False}})
    out = md.convert(body)
    return out.replace("<table>", '<div class="tbl"><table>').replace("</table>", "</table></div>")


def replace_fig_markers(htm: str, render) -> str:
    def rep(m):
        ids = fig_ids(m.group(2))
        inner = "".join(render(i) for i in ids)
        return f'<div class="pair">{inner}</div>' if len(ids) > 1 else inner
    return re.sub(r"<p>\{\{(figs?):([a-z_,]+)\}\}</p>", rep, htm)


def tokenised_json(fig) -> dict:
    """Swap palette colours for @token strings that the page resolves per theme."""
    s = json.dumps(fig.to_plotly_json(), cls=plotly.utils.PlotlyJSONEncoder)
    rgb = {}
    for name, hx in PALETTE.items():
        h = hx.lstrip("#")
        rgb[tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))] = name
        s = re.sub(re.escape(hx), "@" + name, s, flags=re.I)
    s = re.sub(r"rgba\((\d+),(\d+),(\d+),([\d.]+)\)",
               lambda m: (f"@{rgb[(int(m[1]), int(m[2]), int(m[3]))]}/{m[4]}"
                          if (int(m[1]), int(m[2]), int(m[3])) in rgb else m[0]), s)
    d = json.loads(s)
    d["layout"].pop("template", None)
    d["layout"].pop("width", None)
    d["layout"]["autosize"] = True
    return d


def toc_from(htm: str) -> str:
    items = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', htm)
    return "\n".join(f'<li><a href="#{i}">{t}</a></li>' for i, t in items)


SITE_CSS = """
/* Light theme only, by choice: white page whatever the device's dark-mode setting. */
/* Layout: wide reading column with a sticky contents rail on large screens; charts run
   the full column width and pair up side by side where two belong together. */
:root{
  color-scheme:light;
  --bg:#FFFFFF; --surface:#FFFFFF; --ink:#1E252A; --mut:#5E696F; --rule:#E2DED4; --soft:#EFECE5;
  --sun:#C2851E; --rain:#3C6A89; --pv:#2B6350; --dim:#9A5B3D;
  --c-ink:#1E252A; --c-mut:#6B767D; --c-grid:#E4E0D6; --c-card:#FFFFFF; --c-sun:#C2851E; --c-rain:#3C6A89;
  --c-pv:#2B6350; --c-dim:#9A5B3D; --c-hi:#7C4E08; --c-ramp0:#F1ECDD; --c-ramp1:#E3C06C;
  --font:"Source Sans 3","Source Sans Pro",system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);font-size:17.5px;line-height:1.65;
  -webkit-font-smoothing:antialiased;padding-inline:20px}
a{color:var(--pv);text-underline-offset:3px}
a:focus-visible{outline:2px solid var(--sun);outline-offset:2px}
header.top{max-width:1180px;margin:0 auto;padding-block:48px 28px;border-bottom:1px solid var(--rule)}
header.top h1{font-size:clamp(2rem,4.6vw,3.1rem);line-height:1.08;letter-spacing:-.022em;font-weight:700;
  margin:0;max-width:18ch;text-wrap:balance}
header.top .deck{font-size:1.22rem;color:var(--mut);margin:14px 0 0;max-width:46ch;line-height:1.45;text-wrap:balance}
header.top .byline{font-size:.92rem;color:var(--mut);margin:18px 0 0}
header.top .byline b{color:var(--ink);font-weight:600}
.page{max-width:1180px;margin:0 auto;padding-block:32px 72px;display:grid;grid-template-columns:minmax(0,1fr);gap:40px}
@media (min-width:1080px){.page{grid-template-columns:200px minmax(0,1fr);gap:56px}}
nav.toc{display:none}
@media (min-width:1080px){nav.toc{display:block;position:sticky;top:calc(env(safe-area-inset-top,0px) + 24px);
  align-self:start;font-size:.86rem;line-height:1.4}}
nav.toc p{margin:0 0 10px;color:var(--mut);font-weight:600}
nav.toc ol{list-style:none;margin:0;padding:0;display:grid;gap:7px;border-left:1px solid var(--rule)}
nav.toc a{color:var(--mut);text-decoration:none;display:block;padding-left:12px;margin-left:-1px;border-left:2px solid transparent}
nav.toc a:hover,nav.toc a.on{color:var(--ink);border-left-color:var(--sun)}
main{min-width:0}
main>p,main>ul,main>ol,main>pre,main>h2{max-width:74ch}
main>p:first-child{font-size:1.1rem}
h2{font-size:1.5rem;line-height:1.2;letter-spacing:-.012em;font-weight:650;margin:2.6em 0 .55em;text-wrap:balance;
  scroll-margin-top:20px}
p{margin:0 0 1em}
ul,ol{padding-left:1.25em;margin:0 0 1.1em}
li{margin:.3em 0}
strong{font-weight:650}
pre{background:var(--soft);border:1px solid var(--rule);border-radius:8px;padding:14px 16px;overflow-x:auto;
  font-family:var(--mono);font-size:.86rem;line-height:1.55;margin:0 0 1.2em}
code{font-family:var(--mono);font-size:.9em}
.glance{margin:28px 0 8px;max-width:none}
.glance ul{list-style:none;padding:0;margin:0;display:grid;gap:1px;background:var(--rule);border:1px solid var(--rule);
  border-radius:12px;overflow:hidden;grid-template-columns:minmax(0,1fr)}
@media (min-width:480px){.glance ul{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (min-width:760px){.glance ul{grid-template-columns:repeat(3,minmax(0,1fr))}}
.glance li{background:var(--surface);margin:0;padding:16px 18px;font-size:.92rem;color:var(--mut);line-height:1.45}
.glance li strong{display:block;color:var(--ink);font-size:1.45rem;letter-spacing:-.015em;margin-bottom:3px;
  font-variant-numeric:tabular-nums}
.tbl{overflow-x:auto;margin:0 0 1.4em}
table{border-collapse:collapse;width:100%;font-size:.92rem;line-height:1.45}
th,td{text-align:left;padding:9px 12px 9px 0;border-bottom:1px solid var(--rule);vertical-align:top}
th{color:var(--mut);font-weight:600;font-size:.84rem}
td:first-child{font-weight:600;white-space:nowrap}
td{font-variant-numeric:tabular-nums}
figure{margin:26px 0 30px;min-width:0}
figure .plot{min-height:200px}
figure .frame{background:var(--surface);border:1px solid var(--rule);border-radius:12px;padding:10px 8px 4px}
figcaption{font-size:.86rem;color:var(--mut);line-height:1.5;margin-top:9px;max-width:80ch}
.pair{display:grid;grid-template-columns:minmax(0,1fr);gap:0 22px;margin:0}
@media (min-width:820px){.pair{grid-template-columns:repeat(2,minmax(0,1fr))}}
a.ref{font-size:.78em;vertical-align:.25em;text-decoration:none;margin-left:1px;color:var(--pv)}
ol.refs{font-size:.86rem;color:var(--mut);line-height:1.5;padding-left:1.4em;max-width:80ch}
ol.refs li{margin:.45em 0;scroll-margin-top:20px;overflow-wrap:anywhere}
ol.refs a{color:var(--pv)}
footer{max-width:1180px;margin:0 auto;border-top:1px solid var(--rule);padding-block:22px 48px;color:var(--mut);font-size:.88rem}
footer p{max-width:80ch}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
"""

SITE_JS = """
const TOK=['ink','mut','grid','card','sun','rain','pv','dim','hi','ramp0','ramp1'];
function tokens(){const cs=getComputedStyle(document.documentElement),o={};TOK.forEach(k=>o[k]=cs.getPropertyValue('--c-'+k).trim());return o}
function rgba(hex,a){const h=hex.replace('#','');return `rgba(${parseInt(h.slice(0,2),16)},${parseInt(h.slice(2,4),16)},${parseInt(h.slice(4,6),16)},${a})`}
function res(v,t){if(typeof v==='string'&&v[0]==='@'){const[n,a]=v.slice(1).split('/');return t[n]?(a?rgba(t[n],a):t[n]):v}
 if(Array.isArray(v))return v.map(x=>res(x,t));if(v&&typeof v==='object'){const o={};for(const k in v)o[k]=res(v[k],t);return o}return v}
const FONT=getComputedStyle(document.documentElement).getPropertyValue('--font');
function draw(){const t=tokens();document.querySelectorAll('.plot').forEach(el=>{const f=res(FIGS[el.dataset.fig],t);
 f.layout.font=Object.assign({},f.layout.font,{family:FONT});
 if(window.innerWidth<560&&f.layout.legend){f.layout.legend.font=Object.assign({},f.layout.legend.font,{size:11})}
 if(window.innerWidth<560&&el.dataset.fig==='calendar'){f.data.forEach(t=>{if(t.marker&&Array.isArray(t.marker.size))t.marker.size=t.marker.size.map(s=>s*0.45)})}
 el.style.height=(f.layout.height||320)+'px';
 Plotly.react(el,f.data,f.layout,{displayModeBar:false,responsive:true,scrollZoom:false})})}
function boot(){if(!window.Plotly){document.querySelectorAll('.plot').forEach(el=>el.textContent='Interactive chart could not load (plotly.js unavailable).');return}
 draw();
 new MutationObserver(draw).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
 const links=[...document.querySelectorAll('nav.toc a')],heads=links.map(a=>document.getElementById(a.hash.slice(1)));
 const spy=()=>{let i=0;heads.forEach((h,j)=>{if(h&&h.getBoundingClientRect().top<140)i=j});links.forEach((a,j)=>a.classList.toggle('on',j===i))};
 addEventListener('scroll',spy,{passive:true});spy()}
boot();
"""


def build_site(title, deck, byline, body, figs, facts) -> str:
    htm = md_to_html(body)
    htm = replace_fig_markers(htm, lambda i: f'<figure><div class="frame"><div class="plot" data-fig="{i}" role="img" '
                                             f'aria-label="{html.escape(caption(i))}"></div></div>'
                                             f'<figcaption>{html.escape(caption(i))}</figcaption></figure>')
    data = {k: tokenised_json(f) for k, f in figs.items()}
    by = byline.replace("By ", "By <b>", 1).replace(" · ", "</b> · ", 1) if " · " in byline else html.escape(byline)
    head = f"""<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(deck)}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Sans+3:ital,wght@0,400;0,600;0,700;1,400&display=swap">
<style>{SITE_CSS}</style>"""
    body_html = f"""<header class="top"><h1>{html.escape(title)}</h1><p class="deck">{html.escape(deck)}</p><p class="byline">{by}</p></header>
<div class="page">
<nav class="toc" aria-label="Contents"><p>Contents</p><ol>{toc_from(htm)}</ol></nav>
<main>{htm}</main>
</div>
<footer><p>Data: TPCODL bills ({facts['first']} to {facts['last']}); NASA POWER satellite weather. Charts are interactive: hover for values.
Code, data and the method behind every number: <a href="{REPO_URL}">{REPO_URL.replace('https://', '')}</a>.</p></footer>
<script src="{PLOTLY_JS}"></script>
<script>const FIGS={json.dumps(data, separators=(',', ':'))};</script>
<script>{SITE_JS}</script>
"""
    return head, body_html


def full_document(head: str, body_html: str) -> str:
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n<meta name="color-scheme" content="light">\n'
            f"{head}\n</head>\n<body>\n{body_html}</body>\n</html>\n")


PDF_CSS = """
@page{size:A4;margin:18mm 17mm 20mm}
*{box-sizing:border-box}
body{font-family:"Source Sans 3","DejaVu Sans",sans-serif;color:#1E252A;font-size:10.6pt;line-height:1.5;margin:0}
h1{font-size:25pt;line-height:1.1;letter-spacing:-.02em;margin:0 0 6pt;font-weight:700}
.deck{font-size:13pt;color:#5E696F;margin:0 0 8pt;line-height:1.35}
.byline{font-size:9.5pt;color:#5E696F;margin:0 0 16pt;padding-bottom:10pt;border-bottom:.6pt solid #D9D4C8}
h2{font-size:14.5pt;margin:18pt 0 5pt;break-after:avoid;font-weight:650}
p{margin:0 0 7pt;orphans:3;widows:3}
ul,ol{margin:0 0 8pt;padding-left:14pt}li{margin:2pt 0}
pre{background:#F2EFE8;border:.6pt solid #E0DBCF;border-radius:4pt;padding:7pt 9pt;font-size:8.6pt;
  font-family:"DejaVu Sans Mono",monospace;white-space:pre-wrap;break-inside:avoid}
.glance ul{list-style:none;padding:0;display:grid;grid-template-columns:repeat(3,1fr);gap:6pt;margin:10pt 0 4pt}
.glance li{border-top:1.2pt solid #C2851E;padding-top:4pt;font-size:9pt;color:#5E696F;margin:0}
.glance li strong{display:block;font-size:13pt;color:#1E252A}
table{border-collapse:collapse;width:100%;font-size:8.8pt;margin:4pt 0 9pt;break-inside:auto}
th,td{text-align:left;padding:3.5pt 6pt 3.5pt 0;border-bottom:.5pt solid #DDD8CC;vertical-align:top}
th{color:#5E696F;font-weight:600}tr{break-inside:avoid}
figure{margin:8pt 0 11pt;break-inside:avoid}
figure img{width:90%;display:block;margin:0 auto;border:.5pt solid #E2DED4;border-radius:3pt}
figcaption{font-size:8.6pt;color:#5E696F;margin:3pt auto 0;width:90%;line-height:1.4}
a{color:#2B6350}
a.ref{font-size:.75em;vertical-align:.25em;text-decoration:none}
ol.refs{font-size:8.4pt;color:#5E696F;padding-left:14pt}ol.refs li{margin:2.5pt 0;overflow-wrap:anywhere}
"""


def build_pdf(title, deck, byline, body, out: Path) -> None:
    htm = md_to_html(body)

    def img(i):
        b64 = base64.b64encode((FIG_DIR / f"{i}.png").read_bytes()).decode()
        return f'<figure><img src="data:image/png;base64,{b64}" alt=""><figcaption>{html.escape(caption(i))}</figcaption></figure>'
    htm = replace_fig_markers(htm, img)
    page = (f'<!doctype html><html><head><meta charset="utf-8"><style>{PDF_CSS}</style></head><body>'
            f'<h1>{html.escape(title)}</h1><p class="deck">{html.escape(deck)}</p>'
            f'<p class="byline">{html.escape(byline)} · interactive version and code: {REPO_URL.replace("https://", "")}</p>'
            f'{htm}'
            f'</body></html>')
    tmp = ART / ".print.html"
    tmp.write_text(page, encoding="utf-8")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(tmp.resolve().as_uri())
        pg.wait_for_timeout(400)
        pg.pdf(path=str(out), format="A4", print_background=True, display_header_footer=True,
               header_template="<span></span>",
               footer_template='<div style="font-size:7.5pt;color:#8A949A;width:100%;text-align:center;'
                               'font-family:sans-serif">Reading a rooftop against the sky · '
                               '<span class="pageNumber"></span> / <span class="totalPages"></span></div>',
               margin=dict(top="18mm", bottom="20mm", left="17mm", right="17mm"))
        b.close()
    tmp.unlink()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--no-png", action="store_true")
    ap.add_argument("--fragment", help="also write the page without <html>/<head>/<body> to this path")
    args = ap.parse_args()

    B = compute()
    facts = B["facts"]
    src = fill((ART / "article.md").read_text(encoding="utf-8"), facts)
    title, deck, byline, body = split_header(src)
    figs = build_all(B)

    if not args.no_png:
        write_pngs(figs)
    head = f"# {title}\n\n*{deck}*\n\n{byline}\n\n"
    body_md, body = cite(body, "md"), cite(body, "html")
    (ART / "blog.md").write_text(head + to_markdown(body_md, "figures/"), encoding="utf-8")
    (ROOT / "FINDINGS.md").write_text(
        "<!-- Generated by scripts/build_article.py from article/article.md. Edit the source, not this file. -->\n\n"
        + head + to_markdown(body_md, "article/figures/"), encoding="utf-8")
    head, body_html = build_site(title, deck, byline, body, figs, facts)
    (ROOT / "site" / "index.html").write_text(full_document(head, body_html), encoding="utf-8")
    if args.fragment:   # same page without the document wrapper, for hosts that add their own
        Path(args.fragment).write_text(head + "\n" + body_html, encoding="utf-8")
    if not args.no_pdf:
        build_pdf(title, deck, byline, body, ART / "rooftop-solar-article.pdf")
    print("built: site/index.html, article/blog.md, FINDINGS.md"
          + ("" if args.no_png else ", article/figures/*.png") + ("" if args.no_pdf else ", article/rooftop-solar-article.pdf"))


if __name__ == "__main__":
    main()
