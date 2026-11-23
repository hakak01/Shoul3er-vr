// WebXR: Enter VR / MR, controllers, wrist menu, ray selection, grab / two-hand zoom.
import * as THREE from 'three';
import { XRControllerModelFactory } from 'three/addons/webxr/XRControllerModelFactory.js';

const MIN_S = 0.5, MAX_S = 20;

export class XR {
  constructor(app) {
    this.app = app; const r = app.renderer;
    this.hands = {}; this.grabbing = new Set(); this.grab = null; this.mode = null;
    this.ray = new THREE.Raycaster();
    r.xr.enabled = true; r.xr.setReferenceSpaceType('local-floor');
    const factory = new XRControllerModelFactory();
    for (let i = 0; i < 2; i++) {
      const ctrl = r.xr.getController(i), grip = r.xr.getControllerGrip(i);
      grip.add(factory.createControllerModel(grip));
      app.scene.add(ctrl, grip);
      const h = { ctrl, grip, hand: null, source: null };
      ctrl.addEventListener('connected', (e) => this.connect(h, e.data));
      ctrl.addEventListener('disconnected', () => { h.hand = null; h.source = null; });
      ctrl.addEventListener('selectstart', () => this.trigger(h, true));
      ctrl.addEventListener('selectend', () => this.trigger(h, false));
      ctrl.addEventListener('squeezestart', () => { this.grabbing.add(h); this.grab = null; });
      ctrl.addEventListener('squeezeend', () => { this.grabbing.delete(h); this.grab = null; });
    }
    // pointer line + cursor for the right hand
    this.line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3(0, 0, -1)]),
      new THREE.LineBasicMaterial({ color: 0xffffff }));
    this.cursor = new THREE.Mesh(new THREE.SphereGeometry(0.004), new THREE.MeshBasicMaterial({ color: 0xffc233 }));
    app.scene.add(this.cursor); this.cursor.visible = false;
    // wrist menu group (attached to left grip when known)
    this.wrist = new THREE.Group();
    this.wrist.position.set(0.14, 0.03, 0.0); this.wrist.rotation.x = -0.6;
    this.wrist.add(app.menus.menu.mesh);
    app.menus.info.mesh.position.set(0, 0.14 + 0.065, 0); this.wrist.add(app.menus.info.mesh);
    this.panels = [app.menus.menu, app.menus.info];
    this.setupButtons();
  }

  async setupButtons() {
    const vr = document.getElementById('vrBtn'), ar = document.getElementById('arBtn');
    if (!navigator.xr) { vr.textContent = 'VR not available'; ar.style.display = 'none'; return; }
    if (await navigator.xr.isSessionSupported('immersive-vr').catch(() => false)) {
      vr.disabled = false; vr.onclick = () => this.start('immersive-vr');
    } else vr.textContent = 'VR not available';
    if (await navigator.xr.isSessionSupported('immersive-ar').catch(() => false)) {
      ar.disabled = false; ar.onclick = () => this.start('immersive-ar');
    } else ar.style.display = 'none';
  }

  async start(type) {
    const s = await navigator.xr.requestSession(type, { optionalFeatures: ['local-floor', 'bounded-floor'] });
    this.mode = type; const app = this.app;
    app.scene.background = type === 'immersive-ar' ? null : app.bg;
    app.renderer.xr.setFoveation(1);
    await app.renderer.xr.setSession(s);
    this.needPlace = true;
    s.addEventListener('end', () => { this.mode = null; app.scene.background = app.bg; app.onXREnd(); app.menus.refresh(); });
    app.menus.refresh();
  }
  end() { const s = this.app.renderer.xr.getSession(); if (s) s.end(); }

  connect(h, source) {
    h.source = source; h.hand = source.handedness; this.hands[h.hand] = h;
    if (h.hand === 'left') h.grip.add(this.wrist);
    if (h.hand === 'right') h.ctrl.add(this.line);
  }

  // Place the model 55 cm in front of the head, palm towards the user.
  place() {
    const cam = this.app.renderer.xr.getCamera(), head = new THREE.Vector3(), q = new THREE.Quaternion();
    cam.getWorldPosition(head); cam.getWorldQuaternion(q);
    if (head.lengthSq() < 1e-4) return false;            // headset pose not known yet
    const f = new THREE.Vector3(0, 0, -1).applyQuaternion(q); f.y = 0;
    if (f.lengthSq() < 1e-6) f.set(0, 0, -1); f.normalize();
    const root = this.app.root;
    root.scale.setScalar(1);
    root.position.copy(head).addScaledVector(f, 0.55).add(new THREE.Vector3(0, -0.3, 0));
    root.quaternion.setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.atan2(-f.x, -f.z));
    return true;
  }

  // Focus: bring a structure 35 cm in front of the head; enlarge small ones.
  focus(s) {
    const A = this.app.anatomy, root = this.app.root, cam = this.app.renderer.xr.getCamera();
    root.updateMatrixWorld(true);
    const { center, size } = A.bounds(s);
    const local = root.worldToLocal(center.clone());
    const sc = THREE.MathUtils.clamp(root.scale.x * Math.max(1, 0.12 / Math.max(size, 1e-4)), MIN_S, MAX_S);
    root.scale.setScalar(sc);
    const head = new THREE.Vector3(), q = new THREE.Quaternion();
    cam.getWorldPosition(head); cam.getWorldQuaternion(q);
    const target = head.addScaledVector(new THREE.Vector3(0, 0, -1).applyQuaternion(q), 0.35);
    root.position.copy(target).sub(local.multiplyScalar(sc).applyQuaternion(root.quaternion));
  }

  panelHit() {
    const hits = this.ray.intersectObjects(this.panels.map((p) => p.mesh), false);
    return hits[0] || null;
  }

  trigger(h, down) {
    if (h.hand !== 'right') return;
    this.ray.setFromXRController(h.ctrl);
    if (!down) { this.panels.forEach((p) => p.up()); return; }
    const ph = this.panelHit();
    if (ph) { const p = ph.object.userData.panel; p.down(...p.uvToPx(ph.uv)); return; }
    const hit = this.app.anatomy.pick(this.ray);
    this.app.anatomy.select(hit ? hit.struct : null);
    this.app.menus.refresh();
  }

  update(dt) {
    if (!this.mode) return;
    if (this.needPlace && this.place()) this.needPlace = false;
    const R = this.hands.right;
    // right-hand ray: panels hover/drag + cursor
    if (R && R.source) {
      this.ray.setFromXRController(R.ctrl);
      const ph = this.panelHit();
      this.panels.forEach((p) => { if (!ph || ph.object !== p.mesh) p.leave(); });
      if (ph) {
        const p = ph.object.userData.panel; p.move(...p.uvToPx(ph.uv));
        this.cursor.position.copy(ph.point); this.cursor.visible = true;
        this.line.scale.z = ph.distance;
      } else { this.cursor.visible = false; this.line.scale.z = 1.5; }
      // thumbstick moves the clipping plane
      const gp = R.source.gamepad, A = this.app.anatomy;
      if (gp && gp.axes.length >= 4 && A.clip.mode !== 'off' && Math.abs(gp.axes[3]) > 0.15) {
        A.clip.pos = THREE.MathUtils.clamp(A.clip.pos - gp.axes[3] * dt * 0.25, 0, 1);
        this.stickMoved = true;
      } else if (this.stickMoved) { this.stickMoved = false; this.app.menus.refresh(); }
    }
    this.updateGrab();
  }

  updateGrab() {
    const root = this.app.root, hs = [...this.grabbing];
    if (!hs.length) return;
    if (!this.grab) {   // (re)start a grab
      const g = { n: hs.length, pos: root.position.clone(), quat: root.quaternion.clone(), scale: root.scale.x };
      if (hs.length === 1) {
        g.inv = hs[0].ctrl.matrixWorld.clone().invert();
        g.model = root.matrixWorld.clone();
      } else {
        const a = hs[0].ctrl.getWorldPosition(new THREE.Vector3()), b = hs[1].ctrl.getWorldPosition(new THREE.Vector3());
        g.mid = a.clone().add(b).multiplyScalar(0.5); g.dist = a.distanceTo(b); g.dir = b.clone().sub(a).normalize();
      }
      this.grab = g; return;
    }
    const g = this.grab;
    if (g.n === 1) {
      const m = new THREE.Matrix4().multiplyMatrices(hs[0].ctrl.matrixWorld, g.inv).multiply(g.model);
      const s = new THREE.Vector3(); m.decompose(root.position, root.quaternion, s);
    } else {
      const a = hs[0].ctrl.getWorldPosition(new THREE.Vector3()), b = hs[1].ctrl.getWorldPosition(new THREE.Vector3());
      const mid = a.clone().add(b).multiplyScalar(0.5), dir = b.clone().sub(a).normalize();
      const sc = THREE.MathUtils.clamp(g.scale * a.distanceTo(b) / Math.max(g.dist, 1e-3), MIN_S, MAX_S);
      const q = new THREE.Quaternion().setFromUnitVectors(g.dir, dir);
      root.scale.setScalar(sc);
      root.quaternion.copy(q).multiply(g.quat);
      root.position.copy(g.pos).sub(g.mid).multiplyScalar(sc / g.scale).applyQuaternion(q).add(mid);
    }
  }
}
