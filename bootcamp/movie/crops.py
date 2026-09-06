# -*- coding: utf-8 -*-
"""漫画のページから、動画に使う窓を切り出す。

  python bootcamp/movie/crops.py

anim/ に入るのは Higgsfield に渡す 16:9 の開始画像。**フキダシを外した領域**を選んである。
フキダシごと動かすと中の日本語が崩れるため、セリフは build.py 側でテロップとして焼き直す。
src/ に入るのは Ken Burns 用の帯コマ（現在はラストの s12 のみ使用）。

座標は manga2/pages/<page>.jpg（1024x1536）上のピクセル。
コマ割りを変えたら、ここだけ直せば作り直せる。
"""
import os, sys, io
from PIL import Image

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = os.path.join(HERE, '..', '..', 'manga2', 'pages')

# key: (page, x0, y0, x1, y1) — フキダシを含まない窓
ANIM = {
    'a_desk': ('p01', 330, 470, 1024, 861),    # 社長がデスクで窓の外を見る
    'a_trio': ('p05', 200, 758, 824, 1102),    # 社員2人／奥を社長が通る
    'c03':    ('p05', 400, 1108, 1017, 1455),  # PCの前で手が止まる
    'c04':    ('p09', 0, 0, 768, 432),         # 会議室のドアが開く
    'c05':    ('p09', 30, 437, 675, 800),      # ホワイトボード 10:00-15:00
    'c06':    ('p09', 378, 808, 968, 1140),    # 講師が三本指（Klingは指を描き替えるので静止で使う）
    'c08':    ('p13', 400, 380, 1024, 731),    # 見積3案を見る
    'a_face': ('p17', 505, 880, 1024, 1172),   # 涙
    'c10':    ('p21', 240, 1148, 923, 1532),   # 決めるんは、ワシらや
}

# key: (page, y0, y1) — 全幅の帯コマ
STRIP = {
    's12': ('p24', 949, 1524),                 # ラスト「いつAIやるの、今でしょ。」
}


def main():
    for d in ('anim', 'src'):
        os.makedirs(os.path.join(HERE, d), exist_ok=True)

    for k, (page, x0, y0, x1, y1) in ANIM.items():
        im = Image.open(os.path.join(PAGES, page + '.jpg')).crop((x0, y0, x1, y1))
        im = im.resize((1280, int(1280 * im.height / im.width)), Image.LANCZOS)
        h = 720
        if im.height > h:                      # 縦が余るぶんは中央を残す
            t = (im.height - h) // 2
            im = im.crop((0, t, 1280, t + h))
        elif im.height < h:
            pad = Image.new('RGB', (1280, h), (255, 255, 255))
            pad.paste(im, (0, (h - im.height) // 2))
            im = pad
        im.save(os.path.join(HERE, 'anim', k + '.png'))
        print(f'anim/{k}.png  {page} {x0},{y0}-{x1},{y1}')

    for k, (page, y0, y1) in STRIP.items():
        im = Image.open(os.path.join(PAGES, page + '.jpg')).crop((0, y0, 1024, y1))
        im.save(os.path.join(HERE, 'src', k + '.png'))
        print(f'src/{k}.png   {page} y{y0}-{y1}')


if __name__ == '__main__':
    main()
