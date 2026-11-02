"""weekly/YYYY-MM-DD.md と weekly/_template.html から weekly/YYYY-MM-DD.html を作り、
weekly/index.html に一覧のカードを足す。

使い方（リポジトリ直下で）:
    .venv/Scripts/python -I .claude/skills/weekly-report/scripts/build_html.py YYYY-MM-DD
"""
import html
import re
import sys

MARKER = "<!-- 新しい週報はこの下に追加する（新しい順） -->"

date = sys.argv[1]
md = open(f"weekly/{date}.md", encoding="utf-8").read().splitlines()
tpl = open("weekly/_template.html", encoding="utf-8").read()

parts = dict(re.findall(r'<template data-part="(\w+)">\n(.*?)</template>\n', tpl, re.S))
shell = re.sub(r"<!-- 以下は生成用.*", "</body>\n</html>\n", tpl, flags=re.S)


def esc(s):
    s = html.escape(s, quote=False)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", s)


def fill(part, **kv):
    out = parts[part]
    for k, v in kv.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def src_class(src):
    return {"Zenn": "zenn", "Qiita": "qiita"}.get(src, "github")


period = count = None
themes = []
mode = None
for line in md:
    if m := re.match(r"対象期間: (.+?) ／ 記事 (\d+) 件", line):
        period, count = m.group(1), m.group(2)
    elif m := re.match(r"## (.+?)（(\d+)件）", line):
        themes.append(dict(name=m.group(1), n=m.group(2), blurb="", reps=[], others=[]))
        mode = "blurb"
    elif line.startswith("### 代表記事"):
        mode = "rep"
    elif line.startswith("### その他の記事"):
        mode = "other"
    elif m := re.match(r"#### \[(.+?)\]\((\S+?)\)$", line):
        themes[-1]["reps"].append(dict(title=m.group(1), url=m.group(2)))
    elif mode == "blurb" and line.strip() and themes:
        themes[-1]["blurb"] = line.strip()
    elif mode == "rep" and line.strip() and themes[-1]["reps"]:
        src, summary = line.split(" ／ ", 1)
        themes[-1]["reps"][-1].update(src=src, summary=summary)
    elif mode == "other" and (m := re.match(r"- \[(.+?)\]\((\S+?)\) — (.+?)、(.+)$", line)):
        themes[-1]["others"].append(dict(title=m.group(1), url=m.group(2), src=m.group(3), point=m.group(4)))

if not (period and count and themes):
    sys.exit("md の形式が想定と違います（対象期間・テーマ見出しが読み取れない）")

nav, sections = [], []
for i, t in enumerate(themes, 1):
    sid = f"theme-{i}"
    nav.append(fill("nav", ID=sid, NAME=esc(t["name"]), N=t["n"]))
    reps = "".join(
        fill("rep", URL=r["url"], TITLE=esc(r["title"]), SRC=r["src"],
             SRCCLASS=src_class(r["src"]), SUMMARY=esc(r["summary"]))
        for r in t["reps"]
    )
    others = ""
    if t["others"]:
        items = "".join(
            fill("item", URL=o["url"], TITLE=esc(o["title"]), SRC=o["src"],
                 SRCCLASS=src_class(o["src"]), POINT=esc(o["point"]))
            for o in t["others"]
        )
        others = fill("others", N=str(len(t["others"])), ITEMS=items.rstrip("\n"))
    sections.append(fill("section", ID=sid, NAME=esc(t["name"]), N=t["n"],
                         BLURB=esc(t["blurb"]), REPS=reps.rstrip("\n"), OTHERS=others.rstrip("\n")))

out = (shell.replace("{{DATE}}", date).replace("{{PERIOD}}", period).replace("{{COUNT}}", count)
       .replace("{{NAV}}", "".join(nav).rstrip("\n")).replace("{{SECTIONS}}", "\n".join(sections)))
assert "{{" not in out, "穴埋めの残りがあります"
open(f"weekly/{date}.html", "w", encoding="utf-8", newline="\n").write(out)
print(f"weekly/{date}.html: テーマ {len(themes)}、代表 {sum(len(t['reps']) for t in themes)}、"
      f"その他 {sum(len(t['others']) for t in themes)}")

# --- 一覧ページ ---
index = open("weekly/index.html", encoding="utf-8").read()
if MARKER not in index:
    sys.exit("weekly/index.html に追加位置のコメントがありません")
if f'href="{date}.html"' in index:
    print("weekly/index.html: すでにカードがあるので変更しません")
else:
    tags = "\n".join(f"            <li>{esc(t['name'])}</li>" for t in themes)
    card = f"""      <li>
        <a class="report" href="{date}.html">
          <h2>週報 {date}</h2>
          <p class="meta">対象期間 {esc(period)} ／ 記事 {count} 件</p>
          <ul class="themes">
{tags}
          </ul>
        </a>
      </li>"""
    index = index.replace(MARKER, MARKER + "\n" + card)
    open("weekly/index.html", "w", encoding="utf-8", newline="\n").write(index)
    print("weekly/index.html: カードを追加しました")
