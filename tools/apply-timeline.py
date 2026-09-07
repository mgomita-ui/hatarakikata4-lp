# -*- coding: utf-8 -*-
"""
tools/narration.json から index.html の CLIP / S / TOTAL を生成して差し替える。

  python tools/apply-timeline.py            # 生成結果を確認するだけ
  python tools/apply-timeline.py --write    # index.html を書き換える

手で S[] を編集するとナレーション音声とズレる。必ずここを通すこと。
音声側の tools/build-audio.py も同じ narration.json を読むので、両者は常に一致する。
"""
import json, re, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 演出フラグ。narration.json は「絵と尺」だけを持ち、演出はここで並び順に対応させる。
FX = [
    {"tr": None},                                       # 0  暗転・水平線
    {"tr": "fold",  "bl": True},                        # 1  old1
    {"tr": "zoom"},                                     # 2  new1
    {"tr": "fold",  "bl": True},                        # 3  old2
    {"tr": "sweep"},                                    # 4  new2
    {"tr": "fold",  "bl": True},                        # 5  old3
    {"tr": "zoom"},                                     # 6  new3
    {"tr": "fold",  "trip": True},                      # 7  トリプティク
    {"tr": "fold",  "phone": True},                     # 8  スマホ
    {"tr": "sweep", "wf": True},                        # 9  commute
    {"tr": "fold",  "roger": True},                     # 10 口上の入り（水平線が面に開く）
    {"tr": "fold"},                                     # 11 rooftop
    {"tr": "sweep"},                                    # 12 montage（畳みかけ）
    {"tr": "fold"},                                     # 13 strideA（前進）
    {"tr": None,    "title": True},                     # 14 cutin（ハードカット＋タイトル）
    {"tr": "fold",  "endfade": True},                   # 15 finale（結び）
]
INP = {"old1": .5, "new1": .5, "old2": .5, "new2": .5, "old3": .5, "new3": .5,
       "old4": .5, "new4": .5,
       "commute": 1.0, "rooftop": .5, "climax": 1.0,
       "intro": .15, "tripbg": .15, "phonebg": .15, "legacy": .15, "finale": .05,
       "montage": 0.0, "strideA": .15, "cutin": 0.0}
FOCUS = {"old1": ("60% 50%", .7), "new1": ("45% 45%", None), "old2": ("45% 50%", .7),
         "new2": ("50% 50%", None), "old3": ("50% 55%", .7), "new3": ("50% 45%", None),
         "old4": ("50% 55%", .7), "new4": ("55% 50%", None),
         "commute": ("50% 55%", None), "rooftop": ("55% 45%", None), "climax": ("50% 55%", None),
         "legacy": ("50% 50%", None), "finale": ("50% 55%", None),
         # トリプティク/スマホの背面。図版が主役なので彩度を落として沈める
         "intro": ("50% 55%", .8), "tripbg": ("50% 50%", .55), "phonebg": ("50% 50%", .55),
         "montage": ("50% 50%", None), "strideA": ("50% 45%", None), "cutin": ("50% 50%", None)}
FLAGS = ("bl", "trip", "phone", "wf", "roger", "title", "endfade")


def build():
    d = json.load(open(os.path.join(ROOT, "tools", "narration.json"), encoding="utf-8"))
    SC, L, TOTAL = d["scenes"], d["lines"], d["total"]
    if len(SC) != len(FX):
        sys.exit("シーン数 %d と演出定義 %d が一致しません" % (len(SC), len(FX)))

    rows = []
    for name, inp in INP.items():
        focus, sat = FOCUS[name]
        r = "    %s:{src:'%s.mp4',inp:%s,focus:'%s'" % (name, name, inp, focus)
        if sat:
            r += ",sat:%s" % sat
        rows.append(r + "}")
    clip = "  var CLIP={\n" + ",\n".join(rows) + "\n  };\n"

    body = []
    for i, s in enumerate(SC):
        fx = FX[i]
        mine = [l for l in L if s["t0"] <= l["cue"] < s["t1"]]
        parts = ["t0:%s" % s["t0"], "t1:%s" % s["t1"],
                 "clip:%s" % ("'%s'" % s["clip"] if s["clip"] else "null"),
                 "tr:%s" % ("'%s'" % fx["tr"] if fx["tr"] else "null")]
        parts += ["%s:true" % k for k in FLAGS if fx.get(k)]
        ln = ",".join("[%.2f,'%s','%s']" % (round(l["cue"] - s["t0"], 2),
                                            l["text"].replace("'", "\\'"), l["cls"])
                      for l in mine)
        parts.append("lines:[%s]" % ln)
        body.append("    {" + ", ".join(parts) + "}")
    scenes = "  var S=[\n" + ",\n".join(body) + "\n  ];\n"

    roger = SC[[i for i, f in enumerate(FX) if f.get("roger")][0]]["t0"]
    title = [l for l in L if l["cls"] == "huge"][0]["cue"]
    return clip, scenes, TOTAL, roger, title


def main(write=False):
    clip, scenes, total, roger, title = build()
    p = os.path.join(ROOT, "index.html")
    src = open(p, encoding="utf-8").read()

    new = re.sub(r"  var CLIP=\{.*?\n  \};\n", lambda m: clip, src, count=1, flags=re.S)
    new = re.sub(r"  var S=\[.*?\n  \];\n", lambda m: scenes, new, count=1, flags=re.S)
    new = re.sub(r"var TOTAL=[\d.]+,", "var TOTAL=%s," % total, new, count=1)

    const = "var CINE_ROGER=%s, CINE_TITLE=%s;" % (roger, title)
    if "CINE_ROGER" in new:
        new = re.sub(r"var CINE_ROGER=[\d.]+, CINE_TITLE=[\d.]+;", lambda m: const, new, count=1)
    else:
        new = new.replace("var TOTAL=%s," % total, const + "\n  var TOTAL=%s," % total, 1)

    for label, frag in (("CLIP", clip), ("S", scenes)):
        if frag not in new:
            sys.exit("!! %s の差し替えに失敗しました" % label)

    print("TOTAL=%s  口上の入り=%ss  タイトル=%ss" % (total, roger, title))
    print("index.html: %d -> %d bytes" % (len(src), len(new)))
    if write:
        open(p, "w", encoding="utf-8").write(new)
        print("書き換えました。")
    else:
        print(scenes)
        print("(--write で反映)")


if __name__ == "__main__":
    main("--write" in sys.argv)
