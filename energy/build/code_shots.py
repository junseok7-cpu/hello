"""분석 코드 스크린샷 생성: 실제 소스 줄을 편집기 화면처럼 렌더링하고 번호 표식(①②…)을 붙인다.
실행: python build/code_shots.py (Playwright/Chromium 필요)  → figures/code/*.png"""
import html, pathlib, subprocess, re
from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter

E = pathlib.Path(__file__).resolve().parents[1]
OUT = E / 'figures/code'; OUT.mkdir(parents=True, exist_ok=True)
NUM = '①②③④⑤⑥⑦⑧'

# (파일, 줄 범위들, {줄: 표식 번호}, 제목)
SHOTS = [
 ('s1_audit', 'audit.py', [(6, 15), (22, 23)], {8: 1, 9: 2, 13: 3, 15: 4, 22: 5}, '1단계 · 데이터 점검'),
 ('s2_preprocess', 'analyze.py', [(24, 26), (30, 44)], {26: 1, 33: 2, 35: 3, 39: 4, 42: 5, 44: 6}, '2단계 · 전처리와 피처'),
 ('s3_train', 'analyze.py', [(47, 61)], {49: 1, 50: 2, 54: 3, 59: 4, 60: 5}, '3단계 · 모델 학습'),
 ('s4_eval', 'analyze.py', [(63, 81)], {65: 1, 69: 2, 73: 3, 75: 4, 78: 5}, '4단계 · 평가와 비교'),
 ('s5_anomaly', 'analyze.py', [(159, 162), (170, 178)], {160: 1, 161: 2, 174: 3, 175: 4, 178: 5}, '5단계 · 이상탐지'),
]
CSS = HtmlFormatter(style='one-dark' if 'one-dark' in __import__('pygments.styles').styles.STYLE_MAP else 'monokai').get_style_defs('.hl')
BASE = """<html><head><meta charset='utf-8'><style>
body{margin:0;background:#e9efe6;font-family:'WenQuanYi Zen Hei',sans-serif}
.win{position:absolute;left:24px;top:24px;right:24px;bottom:24px;background:#22272e;border-radius:14px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,.25)}
.bar{height:52px;background:#1b1f24;display:flex;align-items:center;padding:0 18px;gap:10px}
.dot{width:14px;height:14px;border-radius:7px}.tab{margin-left:22px;background:#22272e;color:#e6edf3;padding:14px 22px;font-size:20px;border-radius:8px 8px 0 0;font-family:'DejaVu Sans Mono','WenQuanYi Zen Hei Mono',monospace}
.ttl{margin-left:auto;color:#7ee787;font-size:22px;font-weight:bold}
.code{padding:18px 0;font-family:'DejaVu Sans Mono','WenQuanYi Zen Hei Mono',monospace;font-size:25px;line-height:1.5;color:#e6edf3}
.ln{display:flex;align-items:flex-start;min-height:37px}
.no{width:64px;text-align:right;color:#6e7681;padding-right:14px;flex:none}
.mk{width:44px;flex:none;text-align:center}
.mk span{display:inline-block;width:30px;height:30px;border-radius:15px;background:#3fb950;color:#0d1117;font-weight:bold;font-size:20px;line-height:30px;font-family:'WenQuanYi Zen Hei',sans-serif}
.tx{white-space:pre-wrap;word-break:break-all;padding-right:24px;flex:1}
.on{background:rgba(63,185,80,.16)}
.gap{color:#6e7681;padding-left:122px}
.hl{background:transparent}
%s
.hl .c1,.hl .c{color:#8b949e;font-style:normal}
</style></head><body>%s</body></html>"""

def code_html(file, ranges, marks, title):
    src = (E / file).read_text(encoding='utf-8').splitlines()
    rows = []
    for i, (a, b) in enumerate(ranges):
        if i: rows.append("<div class='ln gap'>⋮</div>")
        for n in range(a, b + 1):
            line = src[n - 1]
            h = highlight(line, PythonLexer(), HtmlFormatter(nowrap=True, cssclass='hl'))
            m = f"<span>{NUM[marks[n]-1]}</span>" if n in marks else ''
            rows.append(f"<div class='ln {'on' if n in marks else ''}'><div class='no'>{n}</div><div class='mk'>{m}</div><div class='tx hl'>{h.rstrip()}</div></div>")
    bar = ("<div class='bar'><div class='dot' style='background:#ff5f56'></div><div class='dot' style='background:#ffbd2e'></div>"
           f"<div class='dot' style='background:#27c93f'></div><div class='tab'>energy/{file}</div><div class='ttl'>{title}</div></div>")
    return BASE % (CSS, f"<div class='win'>{bar}<div class='code'>{''.join(rows)}</div></div>")

def term_html():
    log = (E / 'results/run.log').read_text(encoding='utf-8').splitlines()
    keep = [l for l in log if l.startswith('[') ]
    def short(l):
        l = re.sub(r"'bias': [-\d.]+, ", '', l)
        return l if len(l) < 100 else l[:98] + ' …'
    body = ["<span style='color:#7ee787'>team@energy</span>:<span style='color:#79c0ff'>~/hello/energy</span>$ python analyze.py"]
    tm = {'solar rows': 1, 'seed 0': 2, '] A ': 3, 'interval': 4, 'done': 5}
    def mark(l):
        for k, v in tm.items():
            if k in l and not (k == 'done' and 'supply' in l):
                return f"<span style='display:inline-block;width:28px;height:28px;border-radius:14px;background:#3fb950;color:#0d1117;text-align:center;line-height:28px;font-weight:bold;margin-right:8px'>{NUM[v-1]}</span>"
        return "<span style='display:inline-block;width:36px'></span>"
    body += [mark(l) + html.escape(short(l)) for l in keep]
    body += ["<span style='color:#7ee787'>team@energy</span>:<span style='color:#79c0ff'>~/hello/energy</span>$ ls figures results",
             "figures:  f1_models.png  f2_weather_info.png  f3_days.png  f4_normalize.png  f5_region.png ...",
             "results:  data_audit.json  results.json  run.log"]
    txt = '<br>'.join(body)
    inner = (f"<div class='win'><div class='bar'><div class='dot' style='background:#ff5f56'></div><div class='dot' style='background:#ffbd2e'></div>"
             f"<div class='dot' style='background:#27c93f'></div><div class='tab'>터미널 — python analyze.py</div><div class='ttl'>6단계 · 실행 결과</div></div>"
             f"<div class='code' style='padding:22px 28px;font-size:21px;line-height:1.6;white-space:pre-wrap;word-break:break-all'>{txt}</div></div>")
    return BASE % ('', inner)

H = OUT / 'html'; H.mkdir(exist_ok=True)
for name, file, ranges, marks, title in SHOTS:
    (H / f'{name}.html').write_text(code_html(file, ranges, marks, title), encoding='utf-8')
(H / 's6_run.html').write_text(term_html(), encoding='utf-8')
# 캡처: node build/shoot.js (Playwright)
subprocess.run(['node', str(E / 'build/shoot.js'), str(H), str(OUT)], check=True,
               env={**__import__('os').environ, 'NODE_PATH': '/opt/node22/lib/node_modules'})
