# -*- coding: utf-8 -*-
"""「時間がもったいない」の効果音を合成して media/cine/koby/sfx/*.wav に書き出す。

素材ライブラリを使わず numpy で作る（権利の心配がなく、尺と音色を直せる）。
  explosion  「もう、やめましょうよ！」の爆発
  clang      赤髪の男が営業の腕を掴んだ瞬間の「カキン！」（剣と剣がぶつかる鈍い音）
  whoosh     赤髪の男が画面右から入ってくる
  don        「この研修を、終わらせに来た」の重い一撃
  kiran      「三時間で、終わります」のキラーン
  deflate    「……一旦、保留で」のヒュ〜ン（しぼむ）
  sting      「実施は十一月一日」のガーン
"""
import os
import numpy as np
from scipy.signal import butter, lfilter, fftconvolve
from scipy.io import wavfile

SR = 44100
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'media', 'cine', 'koby', 'sfx')
rng = np.random.default_rng(7)


def t_(sec):
    return np.arange(int(sec * SR)) / SR


def lp(x, hz, order=2):
    b, a = butter(order, hz / (SR / 2), 'low')
    return lfilter(b, a, x)


def hp(x, hz, order=2):
    b, a = butter(order, hz / (SR / 2), 'high')
    return lfilter(b, a, x)


def bp(x, lo, hi, order=2):
    b, a = butter(order, [lo / (SR / 2), hi / (SR / 2)], 'band')
    return lfilter(b, a, x)


def reverb(x, sec=1.2, wet=0.25):
    n = int(sec * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / (SR * sec / 5))
    ir = lp(ir, 6000)
    ir /= np.abs(ir).sum() ** 0.5 * 30
    y = fftconvolve(x, ir)[:len(x) + n]
    out = np.zeros(len(y))
    out[:len(x)] = x
    return out + wet * y


def env_exp(n, tau):
    return np.exp(-np.arange(n) / (SR * tau))


def stereo(x, pan=0.0):
    l = x * np.cos((pan + 1) * np.pi / 4)
    r = x * np.sin((pan + 1) * np.pi / 4)
    return np.stack([l, r], axis=1)


def save(name, st, peak=0.95):
    st = np.tanh(st / (np.abs(st).max() + 1e-9) * 1.4)
    st = st / np.abs(st).max() * peak
    os.makedirs(OUT, exist_ok=True)
    wavfile.write(os.path.join(OUT, name + '.wav'), SR, (st * 32767).astype(np.int16))
    print('  ', name, '%.2fs' % (len(st) / SR))


def explosion():
    n = int(2.8 * SR)
    t = np.arange(n) / SR
    crack = hp(rng.standard_normal(n), 1500) * env_exp(n, 0.03)
    body = lp(rng.standard_normal(n), 900, 4) * env_exp(n, 0.55)
    rumble = lp(rng.standard_normal(n), 120, 4) * env_exp(n, 1.0) * 6
    f = 90 * np.exp(-t * 1.6) + 32
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, 0.45) * 1.6
    x = crack * 0.6 + body * 2.2 + rumble + boom
    x[:int(0.004 * SR)] *= np.linspace(0, 1, int(0.004 * SR))
    x = reverb(x, 1.6, 0.35)
    L = x + lp(rng.standard_normal(len(x)), 300) * 0.02
    R = np.roll(x, 90)
    save('explosion', np.stack([L, R], axis=1))


def clang():
    """剣と剣がぶつかる鈍い音。高い鈴のような響きではなく、重い刃がかち合う短い衝撃と、刃がこすれる音。"""
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    parts = [(410, 0.22, 1.0), (733, 0.18, 0.9), (1187, 0.14, 0.7), (1846, 0.10, 0.5), (2690, 0.07, 0.35)]
    ring = np.zeros(n)
    for f, tau, a in parts:
        ring += a * np.sin(2 * np.pi * f * t * (1 - 0.004 * np.exp(-t * 25))) * env_exp(n, tau)
    ring = lp(ring, 3000, 2)
    impact = bp(rng.standard_normal(n), 300, 2500) * env_exp(n, 0.018) * 4
    thud = np.sin(2 * np.pi * np.cumsum(140 * np.exp(-t * 20) + 60) / SR) * env_exp(n, 0.06) * 1.5
    scrape = bp(rng.standard_normal(n), 2000, 6000) * np.exp(-np.maximum(t - 0.02, 0) / 0.09) * np.minimum(t / 0.02, 1) * 0.35
    x = ring + impact + thud + scrape
    x[:int(0.001 * SR)] *= np.linspace(0, 1, int(0.001 * SR))
    x = reverb(x, 0.9, 0.25)
    save('clang', stereo(x, 0.1))


def whoosh():
    n = int(0.75 * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    # 低い帯と高い帯を、時間とともに入れ替える（区間をつなぐとプチッと鳴るので、連続した2本を混ぜる）
    low = bp(noise, 250, 1200)
    high = bp(noise, 1500, 7000)
    k = np.sin(np.pi * t / t[-1]) ** 1.5
    y = low * (1 - k) + high * k * 1.6
    y *= np.sin(np.pi * t / t[-1]) ** 2
    L = y * np.linspace(0.3, 1.0, n)  # 右から入って中央へ
    R = y * np.linspace(1.0, 0.8, n)
    save('whoosh', np.stack([L, R], axis=1), peak=0.8)


def don():
    n = int(2.2 * SR)
    t = np.arange(n) / SR
    f = 75 * np.exp(-t * 3) + 44
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, 0.4)
    skin = lp(rng.standard_normal(n), 700) * env_exp(n, 0.05) * 2.5
    x = body * 2 + skin
    x[:int(0.003 * SR)] *= np.linspace(0, 1, int(0.003 * SR))
    x = reverb(x, 1.8, 0.45)
    save('don', stereo(x))


def kiran():
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    rise = np.minimum(t / 0.14, 1)
    f = 1900 + 2300 * rise
    main = np.sin(2 * np.pi * np.cumsum(f) / SR)
    shimmer = sum(np.sin(2 * np.pi * h * t + p) for h, p in ((6300, 0.3), (8400, 1.1), (10500, 2.0))) / 3
    trem = 0.6 + 0.4 * np.sin(2 * np.pi * 14 * t)
    e = np.minimum(t / 0.02, 1) * np.exp(-np.maximum(t - 0.14, 0) / 0.45)
    x = (main * 0.8 + shimmer * 0.5 * trem) * e
    x = reverb(x, 1.2, 0.35)
    L = x
    R = np.roll(x, 140)
    save('kiran', np.stack([L, R], axis=1), peak=0.7)


def deflate():
    n = int(1.3 * SR)
    t = np.arange(n) / SR
    f = 1250 * np.exp(-t * 1.5) + 180
    f = f * (1 + 0.03 * np.sin(2 * np.pi * 7 * t))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR)
    x = x + 0.3 * np.sin(2 * np.pi * np.cumsum(2 * f) / SR)
    e = np.minimum(t / 0.05, 1) * np.minimum((t[-1] - t) / 0.2, 1)
    x *= e
    x = reverb(x, 0.8, 0.2)
    save('deflate', stereo(x), peak=0.75)


def sting():
    n = int(2.6 * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for f0, a in ((55, 1.0), (58.3, 0.8), (110, 0.6), (116.5, 0.5), (164.8, 0.35)):
        for h in range(1, 9):
            x += a / h * np.sin(2 * np.pi * f0 * h * t)
    x = lp(x, 1400, 4)
    e = np.minimum(t / 0.015, 1) * env_exp(n, 0.9)
    hit = lp(rng.standard_normal(n), 400) * env_exp(n, 0.08) * 4
    x = x * e + hit
    x = reverb(x, 1.8, 0.4)
    save('sting', stereo(x))


if __name__ == '__main__':
    import sys
    names = sys.argv[1:]
    for fn in (explosion, clang, whoosh, don, kiran, deflate, sting):
        if not names or fn.__name__ in names:
            fn()
