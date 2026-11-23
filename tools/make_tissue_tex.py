"""Procedural, tileable 1K tissue detail maps -> data/raw/tex/<name>.rgba (raw 1024x1024 RGBA).
R,G = tangent-space normal (x,y); B = cavity / colour variation (0 = groove, 1 = crest); A = 255.
Fibres always run along V (rows). Then run: node tools/encode_ktx2.mjs  (-> assets/tex/*.ktx2)
"""
import os, sys
import numpy as np

N = 1024
OUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw', 'tex')
rng = np.random.default_rng(7)
fx = np.fft.fftfreq(N)[None, :] * N      # cycles per tile, across fibres (u)
fy = np.fft.fftfreq(N)[:, None] * N      # cycles per tile, along fibres (v)
yy, xx = np.mgrid[0:N, 0:N] / N


def norm(h):
    h = h - h.mean()
    return h / (np.abs(h).max() + 1e-9)


def spec(filt):
    """Periodic noise: white noise filtered in frequency space (always tiles)."""
    return norm(np.real(np.fft.ifft2(np.fft.fft2(rng.normal(size=(N, N))) * filt)))


def band(f, lo, hi):
    a = np.abs(f)
    return np.clip((a - lo * 0.5) / (lo * 0.5 + 1e-9), 0, 1) * np.exp(-(a / hi) ** 2)


def fibres(lo, hi, along, angle=0.0):
    """Noise stretched along v. lo/hi = cycles across, along = spread of cycles along."""
    c, s = np.cos(angle), np.sin(angle)
    u, v = c * fx - s * fy, s * fx + c * fy
    return spec(band(u, lo, hi) * np.exp(-(v / along) ** 2))


def iso(lo, hi):
    r = np.sqrt(fx ** 2 + fy ** 2)
    return spec(band(r, lo, hi))


def ridged(n):            # grooves between bundles
    return norm(1.0 - np.abs(n) * 2.0)


def low(n=3):             # very low-frequency field 0..1 for patchiness
    return iso(1, n) * 0.5 + 0.5


def cells(count, seed):
    """Periodic Voronoi: returns (F2-F1) edge distance and F1, in tile units."""
    r = np.random.default_rng(seed); pts = r.random((count, 2))
    f1 = np.full((N, N), 9.0); f2 = np.full((N, N), 9.0)
    for px, py in pts:
        dx = np.abs(xx - px); dx = np.minimum(dx, 1 - dx)
        dy = np.abs(yy - py); dy = np.minimum(dy, 1 - dy)
        d = np.sqrt(dx * dx + dy * dy)
        f2 = np.where(d < f1, f1, np.minimum(f2, d)); f1 = np.minimum(f1, d)
    return f2 - f1, f1


def crimp(k, wobble):
    """Bands across the fibres (tendon crimp / nerve bands of Fontana). k = cycles per tile (integer)."""
    return np.sin(2 * np.pi * (k * yy + wobble * fibres(1, 4, 2)))


def tex_muscle():
    fasc = ridged(fibres(6, 30, 1.2))                    # fascicles ~0.4-2 mm on a 12 mm tile
    fine = fibres(60, 220, 3.0)                          # muscle fibres
    h = fasc * 1.0 + fine * 0.35 + iso(2, 6) * 0.25
    return h, 18, fasc * 0.7 + fine * 0.3


def tex_tendon():
    fine = fibres(40, 260, 2.0)
    cr = crimp(24, 0.6) * (0.4 + 0.6 * low())            # glistening crimp bands
    h = fine * 0.9 + cr * 0.22 + fibres(4, 12, 1.0) * 0.3
    return h, 12, fine * 0.5 + cr * 0.5


def tex_ligament():
    f = fibres(30, 200, 2.5, 0.18) + fibres(30, 200, 2.5, -0.18) + fibres(10, 40, 1.5) * 0.8
    h = norm(f) + crimp(18, 1.0) * 0.2 * low() + iso(2, 8) * 0.25
    return h, 13, norm(f)


def tex_nerve():
    fasc = ridged(fibres(3, 10, 0.8))                    # fascicle bundles ~1-2.5 mm on an 8 mm tile
    fine = fibres(50, 160, 2.5)
    bands = crimp(40, 0.8) * (0.3 + 0.7 * low())         # spiral bands of Fontana
    h = fasc * 1.0 + fine * 0.25 + bands * 0.25
    return h, 15, fasc * 0.8 + bands * 0.2


def tex_vessel():
    h = fibres(15, 80, 2.0) * 0.5 + iso(2, 10) * 0.6 + fibres(1, 3, 30, np.pi / 2) * 0.2
    return h, 6, iso(3, 12)


def tex_bone():
    p = iso(30, 90)
    pores = -np.clip((p - 0.35) / 0.4, 0, 1) ** 1.5      # small pits
    h = iso(2, 10) * 0.6 + pores * 1.0 + iso(120, 300) * 0.2
    return h, 14, h


def tex_cartilage():
    h = iso(2, 8) * 1.0 + iso(20, 60) * 0.15
    return h, 4, iso(3, 10)


def tex_fat():
    edge, f1 = cells(70, 3)                              # lobules ~2-3 mm on a 20 mm tile
    dome = np.sqrt(np.clip(edge / 0.06, 0, 1))
    h = dome * 1.0 + iso(40, 120) * 0.12
    return h, 18, dome


def tex_skin():
    pores = -np.clip((iso(70, 160) - 0.45) / 0.35, 0, 1) ** 2
    lines = ridged(fibres(14, 40, 1.0, 0.7)) * 0.5 + ridged(fibres(14, 40, 1.0, -0.7)) * 0.5
    h = lines * 0.6 + pores * 0.7 + iso(2, 8) * 0.3
    return h, 11, h


def pack(h, tilt, cav):
    """tilt = wanted RMS tilt of the normals in degrees (the shader can scale it further)."""
    h = norm(h); cav = norm(cav) * 0.5 + 0.5
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    k = np.tan(np.radians(tilt)) / np.sqrt((dx ** 2 + dy ** 2).mean())
    dx *= k; dy *= k
    n = np.stack([-dx, -dy, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    rgba = np.empty((N, N, 4), np.uint8)
    rgba[..., 0:2] = np.round((n[..., 0:2] * 0.5 + 0.5) * 255)
    rgba[..., 2] = np.round(cav * 255); rgba[..., 3] = 255
    return rgba, float(np.degrees(np.arccos(n[..., 2])).mean())


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    names = sys.argv[1:] or [k[4:] for k in globals() if k.startswith('tex_')]
    for k in names:
        rng = np.random.default_rng(sum(map(ord, k)))      # own seed per map -> same result when run alone
        rgba, tilt = pack(*globals()['tex_' + k]())
        rgba.tofile(os.path.join(OUT, k + '.rgba'))
        print(f'{k:10s} mean normal tilt {tilt:5.1f} deg')
