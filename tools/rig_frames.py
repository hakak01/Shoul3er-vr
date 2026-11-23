"""Phase D1: bony landmarks, joint centres and ISB segment frames (Wu 2005, J Biomech) from the bone meshes.
glTF frame of the model: -x = right/lateral, y = up, z = anterior. ISB frames use X anterior, Y up, Z right.
Each frame is a 3x3 matrix whose COLUMNS are the X, Y, Z axes in glTF coordinates."""
import numpy as np
from gapgeom import MM, unit


def sphere_fit(V):
    A = np.c_[2 * V, np.ones(len(V))]; b = (V ** 2).sum(1)
    s = np.linalg.lstsq(A, b, rcond=None)[0]; c = s[:3]; r = np.sqrt(s[3] + c @ c)
    return c, r, np.abs(np.linalg.norm(V - c, axis=1) - r).mean()


def frame(x, y):
    """Right-handed frame from an approximate X and an exact Y (columns X, Y, Z)."""
    y = unit(y); z = unit(np.cross(x, y)); x = np.cross(y, z)
    return np.c_[x, y, z]


def euler_yxz(R):
    """R = Ry(a) Rx(b) Rz(c) -> (a, b, c) degrees (ISB order for clavicle and scapula)."""
    b = np.arcsin(-np.clip(R[1, 2], -1, 1))
    a = np.arctan2(R[0, 2], R[2, 2]); c = np.arctan2(R[1, 0], R[1, 1])
    return np.degrees([a, b, c])


def swing_twist(R):
    """Humerothoracic R = Ry(p) Rx(-e) Ry(-p) Ry(-rot) -> plane p, elevation e, rotation rot (ER +), degrees."""
    d = -R[:, 1]                                          # arm direction (humerus -Y) in thorax axes
    e = np.degrees(np.arccos(np.clip(-d[1], -1, 1)))
    p = np.degrees(np.arctan2(d[0], d[2])) if e > 1e-3 else 0.0
    def ry(a):
        a = np.radians(a); return np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    def rx(a):
        a = np.radians(a); return np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
    S = ry(p) @ rx(-e) @ ry(-p); T = S.T @ R
    return p, e, -np.degrees(np.arctan2(T[0, 2], T[0, 0]))


def build(get, log):
    """get(name, mat=None) -> (V, F). Returns the rig dict (joints, frames, landmarks, rest angles)."""
    P = lambda n, m=None: get(n, m)[0]
    # --- thorax: IJ, PX, C7, T8 -------------------------------------------------------------------
    x0 = P('Vertebra T1')[:, 0].mean()                                         # midline
    man = P('Manubrium of sternum'); mid = man[np.abs(man[:, 0] - x0) < 4 * MM]
    top = mid[mid[:, 1] > mid[:, 1].max() - 3 * MM]; IJ = top[np.argmax(top[:, 2])]   # notch, front edge
    xp = P('Xiphoid process'); xm = xp[np.abs(xp[:, 0] - x0) < 6 * MM]; PX = xm[np.argmin(xm[:, 1])]
    C7 = P('Vertebra C7'); C7 = C7[np.argmin(C7[:, 2])]                          # spinous tips (most posterior)
    T8 = P('Vertebra T8'); T8 = T8[np.argmin(T8[:, 2])]
    Yt = unit((IJ + C7) / 2 - (PX + T8) / 2)
    Zt = unit(np.cross(IJ - (PX + T8) / 2, C7 - (PX + T8) / 2))
    if Zt[0] > 0: Zt = -Zt                                                       # right = -x
    Ft = frame(np.cross(Yt, Zt), Yt)
    up, lat, ant = Ft[:, 1], Ft[:, 2], Ft[:, 0]
    # --- clavicle ----------------------------------------------------------------------------------
    cl, clc = P('Clavicle'), P('Clavicle', 'Cartilage')
    SCl = cl[np.argmax(-(cl @ lat))]
    s = clc @ lat; mid = (s.min() + s.max()) / 2; med, latc = clc[s < mid], clc[s >= mid]
    SC, AC = med.mean(0), latc.mean(0)                                         # joint centres from joint surfaces
    ACl = latc[np.argmax(-(latc @ ant))]                                       # most dorsal point of the AC joint
    Zc = unit(ACl - SCl); Fc = frame(np.cross(up, Zc), np.cross(Zc, np.cross(up, Zc)))
    # --- humerus: GH sphere fit, epicondyles, elbow axis ------------------------------------------
    hc = P('Humerus', 'Cartilage'); hy = hc @ up; hb = P('Humerus')
    head = hc[hy > hy.max() - 0.06]; GH, r_gh, e_gh = sphere_fit(head)
    hlo = hb[hb @ up < (hb @ up).min() + 40 * MM]
    EL, EM = hlo[np.argmax(hlo @ lat)], hlo[np.argmin(hlo @ lat)]
    Fh = frame(np.cross(GH - (EL + EM) / 2, EL - EM), GH - (EL + EM) / 2)
    dist = hc[hy < hy.min() + 0.05]; q = dist @ unit(EL - EM); qn = (q - q.min()) / np.ptp(q)
    cap, cap_r, _ = sphere_fit(dist[qn > 0.62]); tro, tro_r, _ = sphere_fit(dist[qn < 0.5])
    EC = (cap + tro) / 2; eax = unit(cap - tro)                                # elbow centre + axis (lateral)
    # --- forearm ------------------------------------------------------------------------------------
    ra, ul = P('Radius'), P('Ulna')
    RS, US = ra[np.argmin(ra @ up)], ul[np.argmin(ul @ up)]
    rh = ra[ra @ up > (ra @ up).max() - 8 * MM]; RH = rh.mean(0)               # radial head centre
    uy = ul @ up; UH = ul[(uy > uy.min() + 3 * MM) & (uy < uy.min() + 12 * MM)].mean(0)
    fax = unit(UH - RH)
    Ff = frame(np.cross(US - (EL + EM) / 2, RS - US), (EL + EM) / 2 - US)
    if Ff[:, 0] @ ant < 0: Ff = frame(-np.cross(US - (EL + EM) / 2, RS - US), (EL + EM) / 2 - US)
    # flexion: + moves the wrist forward; supination: + moves the radial styloid backward
    if np.cross(eax, US - EC) @ ant < 0: eax = -eax
    if np.cross(fax, RS - RH) @ ant > 0: fax = -fax
    # --- scapula: AA, TS, AI -------------------------------------------------------------------------
    sc = P('Scapula'); gl = P('Scapula', 'Cartilage'); gl = gl[np.linalg.norm(gl - GH, axis=1) < 40 * MM]
    acr = sc[(sc @ up) > (gl @ up).max()]                                     # above the glenoid
    AA = acr[np.argmax(acr @ unit(lat - ant))]
    AI = sc[np.argmin(sc @ up)]
    c0 = sc.mean(0); pn = np.linalg.eigh(np.cov((sc - c0).T))[1][:, 0]         # scapular plane normal
    pn = pn if pn @ ant < 0 else -pn                                            # -> posterior
    off, sz = (sc - c0) @ pn, sc @ lat
    ridge = sc[(off > 8 * MM) & (sc @ up > GH @ up - 30 * MM) & (sz > sz.min() + 15 * MM) & (sz < AA @ lat - 25 * MM)]
    rc = ridge.mean(0); rd = np.linalg.eigh(np.cov((ridge - rc).T))[1][:, 2]   # spine line
    dl = np.linalg.norm(np.cross(sc - rc, rd), axis=1)
    near = sc[dl < 6 * MM]; TS = near[np.argmin(near @ lat)]                 # root of the spine on the medial border
    n = unit(np.cross(AA - TS, AI - TS)); n = n if n @ ant > 0 else -n
    Fs = frame(n, np.cross(unit(AA - TS), n))
    # --- rest angles ---------------------------------------------------------------------------------
    rel = lambda F: Ft.T @ F
    flex = np.degrees(np.arccos(np.clip(-Fh[:, 1] @ unit((US + RS) / 2 - EC), -1, 1)))
    a = lambda u: unit(u - fax * (u @ fax))
    sup = 90 - np.degrees(np.arccos(np.clip(a(RS - US) @ a(EL - EM), -1, 1)))
    rest = dict(clavicle=euler_yxz(rel(Fc)).tolist(), scapula=euler_yxz(rel(Fs)).tolist(),
                humerus=list(swing_twist(rel(Fh))), elbowFlexion=float(flex), supination=float(sup))
    log('GH sphere r %.1f mm (fit err %.2f); capitellum r %.1f, trochlea r %.1f; elbow axis %.1f deg from Zh'
        % (r_gh / MM, e_gh / MM, cap_r / MM, tro_r / MM, np.degrees(np.arccos(abs(eax @ Fh[:, 2])))))
    log('rest: clavicle YXZ %s, scapula YXZ %s, humerus plane/elev/rot %s, elbow %.0f, supination %.0f' % (
        np.round(rest['clavicle'], 1), np.round(rest['scapula'], 1), np.round(rest['humerus'], 1), flex, sup))
    L = dict(IJ=IJ, PX=PX, C7=C7, T8=T8, SC=SCl, AC=ACl, AA=AA, TS=TS, AI=AI, GH=GH, EL=EL, EM=EM, RS=RS, US=US)
    joints = dict(thorax=IJ, clavicle=SC, scapula=AC, humerus=GH, ulna=EC, radius=RH)
    axes = dict(elbow=eax, forearm=fax)
    fr = dict(thorax=Ft, clavicle=Fc, scapula=Fs, humerus=Fh, forearm=Ff)
    j = lambda d: {k: np.round(np.asarray(v), 5).tolist() for k, v in d.items()}
    return dict(landmarks=j(L), joints=j(joints), axes=j(axes), frames={k: np.round(v, 5).tolist() for k, v in fr.items()},
                rest=rest, ghRadius=round(float(r_gh), 5), forearmAxisEnd=np.round(UH, 5).tolist())
