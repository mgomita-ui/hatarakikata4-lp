# -*- coding: utf-8 -*-
"""両ページの GAS_URL をまとめて差し替える。

  python tools/gas/set-url.py https://script.google.com/macros/s/…/exec
  python tools/gas/set-url.py ""        # 空に戻す（mailto に戻る）
"""
import re, sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAGES = ['index.html', 'bootcamp/index.html']

def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    url = sys.argv[1].strip()
    if url and not re.match(r'^https://script\.google\.com/macros/s/[\w-]+/exec$', url):
        sys.exit('GAS のウェブアプリ URL（…/exec）ではありません: ' + url)
    for rel in PAGES:
        p = os.path.join(ROOT, rel)
        s = open(p, encoding='utf-8', newline='').read()
        t, n = re.subn(r"var GAS_URL='[^']*';", "var GAS_URL='%s';" % url, s)
        if n != 1:
            sys.exit(f'{rel}: GAS_URL の定義が {n} 箇所（1 箇所のはず）')
        open(p, 'w', encoding='utf-8', newline='').write(t)
        print(f'{rel}: GAS_URL = {url or "(空)"}')

if __name__ == '__main__':
    main()
