<script lang="ts">
  // 3D view of a factory: machines as blocks at real size, height and rotation, coloured by state.
  // The factory's belts/pipes as lines at machine height (from the item flow). Rotate/zoom via OrbitControls.
  import { onMount, onDestroy } from 'svelte';
  import * as THREE from 'three';
  import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
  import type { Machine } from './types';
  import { machineColor, C, MOBILE_QUERY } from './fmt';
  import { t, tr, lx } from './i18n';
  import { tn } from './names';
  import { portal } from './actions';

  let { machines, flow = [], onclose, title = '' }: { machines: Machine[]; flow?: number[][][]; onclose: () => void; title?: string } = $props();

  // Footprint W × D × H in metres (Satisfactory wiki, rounded). Unknown: 8 × 8 × 8.
  const SIZE: Record<string, [number, number, number]> = {
    Build_SmelterMk1_C: [6, 9, 9], Build_ConstructorMk1_C: [8, 10, 8], Build_AssemblerMk1_C: [10, 15, 11],
    Build_ManufacturerMk1_C: [18, 20, 12], Build_FoundryMk1_C: [10, 9, 9], Build_OilRefinery_C: [10, 20, 31],
    Build_Blender_C: [18, 16, 15], Build_Packager_C: [8, 8, 12], Build_MinerMk1_C: [6, 14, 18], Build_MinerMk2_C: [6, 14, 18],
    Build_MinerMk3_C: [6, 14, 18], Build_WaterPump_C: [19.5, 19.5, 26], Build_OilPump_C: [8, 14, 20],
    Build_FrackingExtractor_C: [4, 4, 5], Build_HadronCollider_C: [24, 38, 32], Build_QuantumEncoder_C: [22, 48, 18],
    Build_Converter_C: [16, 16, 16],
  };
  // Attached to <body> (use:portal): the detail card (.panel) has a clip-path — a fixed fullscreen inside it would be clipped.
  let host: HTMLDivElement, tip = $state<{ x: number; y: number; m: Machine } | null>(null);
  let failed = $state('');
  let renderer: THREE.WebGLRenderer, raf = 0, ro: ResizeObserver;
  let scene: THREE.Scene | null = null, ctl: OrbitControls | null = null;

  onMount(() => {
    scene = new THREE.Scene();
    scene.background = new THREE.Color(C.mapBg);
    const cam = new THREE.PerspectiveCamera(45, 1, 1, 20000);
    const mobile = matchMedia(MOBILE_QUERY + ', (pointer: coarse)').matches;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: !mobile, powerPreference: 'low-power' });
    } catch (e) {
      failed = tr('This device does not provide WebGL ({err}).', { err: (e as Error)?.message || e }); return;
    }
    // Phone: reduced pixel density is enough for blocks and saves GPU memory (otherwise Safari loses the context)
    renderer.setPixelRatio(mobile ? Math.min(1.5, devicePixelRatio) : Math.min(2, devicePixelRatio));
    renderer.domElement.addEventListener('webglcontextlost', ev => { ev.preventDefault(); failed = tr('The device reset the graphics (not enough graphics memory).'); cancelAnimationFrame(raf); });
    host.appendChild(renderer.domElement);
    scene.add(new THREE.HemisphereLight('#e8e6e1', '#2a2620', 1.6));
    const sun = new THREE.DirectionalLight('#ffffff', 1.4); sun.position.set(-300, 600, -200); scene.add(sun);

    // Centre and extent; world: x east, y south, z up → three: x, -z (flip south→north), y up
    // Centre = median, not mean: single distant machines (pumps, miners) would otherwise shift the view
    const med = (a: number[]) => { const b = [...a].sort((p, q) => p - q); return b[Math.floor(b.length / 2)]; };
    const cx = med(machines.map(m => m.pos[0])), cy = med(machines.map(m => m.pos[1]));
    const zmin = Math.min(...machines.map(m => m.z ?? 0));
    const P = (x: number, y: number, z: number) => new THREE.Vector3(x - cx, z - zmin, y - cy);

    // Machines: one box geometry per type, instances coloured by state → few draw calls
    const groups = new Map<string, Machine[]>();
    for (const m of machines) { const k = m.cls; if (!groups.has(k)) groups.set(k, []); groups.get(k)!.push(m); }
    const pickables: { mesh: THREE.InstancedMesh; list: Machine[] }[] = [];
    const mtx = new THREE.Matrix4(), q = new THREE.Quaternion(), col = new THREE.Color();
    for (const [cls, list] of groups) {
      const [w, d, h] = SIZE[cls] || [8, 8, 8];
      const geo = new THREE.BoxGeometry(w, h, d); geo.translate(0, h / 2, 0);
      const mat = new THREE.MeshStandardMaterial({ roughness: .75, metalness: .15 });
      const mesh = new THREE.InstancedMesh(geo, mat, list.length);
      list.forEach((m, i) => {
        q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), -(m.yaw || 0) * Math.PI / 180);
        mtx.compose(P(m.pos[0], m.pos[1], m.z ?? 0), q, new THREE.Vector3(1, 1, 1));
        mesh.setMatrixAt(i, mtx);
        mesh.setColorAt(i, col.set(machineColor(m)));
      });
      scene.add(mesh); pickables.push({ mesh, list });
      // Edges for readability: all machines of a type in ONE geometry (one draw call instead of one per machine)
      const eg = new THREE.EdgesGeometry(geo), ep = eg.getAttribute('position') as THREE.BufferAttribute;
      const all = new Float32Array(ep.count * 3 * list.length), v = new THREE.Vector3();
      list.forEach((_, i) => {
        mesh.getMatrixAt(i, mtx);
        for (let j = 0; j < ep.count; j++) { v.fromBufferAttribute(ep, j).applyMatrix4(mtx); all.set([v.x, v.y, v.z], (i * ep.count + j) * 3); }
      });
      eg.dispose();                                   // only needed for the vertex positions
      const eg2 = new THREE.BufferGeometry(); eg2.setAttribute('position', new THREE.BufferAttribute(all, 3));
      scene.add(new THREE.LineSegments(eg2, new THREE.LineBasicMaterial({ color: C.ring, transparent: true, opacity: .5 })));
    }
    // Belts/pipes (2D) at the floor height of the nearest machine
    const nearZ = (x: number, y: number) => {
      let best = 0, bd = 1e9;
      for (const m of machines) { const d = (m.pos[0] - x) ** 2 + (m.pos[1] - y) ** 2; if (d < bd) { bd = d; best = m.z ?? 0; } }
      return best;
    };
    const lineMat = new THREE.LineBasicMaterial({ color: '#8d8a84', transparent: true, opacity: .6 });
    for (const p of flow) {
      const pts = p.map(([x, y]) => P(x, y, nearZ(x, y) + 1));
      scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), lineMat));
    }
    // Ground grid
    const xs = machines.map(m => m.pos[0] - cx).sort((a, b) => a - b), ys = machines.map(m => m.pos[1] - cy).sort((a, b) => a - b);
    const qq = (a: number[], f: number) => a[Math.min(a.length - 1, Math.floor(a.length * f))];
    const span = Math.max(60, qq(xs, .95) - qq(xs, .05), qq(ys, .95) - qq(ys, .05));
    const grid = new THREE.GridHelper(Math.ceil(span * 1.4 / 8) * 8, Math.ceil(span * 1.4 / 8), '#3a3d41', '#26282b');
    scene.add(grid);

    ctl = new OrbitControls(cam, renderer.domElement);
    ctl.target.set((qq(xs, .05) + qq(xs, .95)) / 2, 10, (qq(ys, .05) + qq(ys, .95)) / 2); ctl.enableDamping = true; ctl.maxPolarAngle = Math.PI * .49;
    // Distance from the field of view: the factory (span) must fit the NARROWER view direction — in portrait
    // that is the width, whose angle follows from vFOV × aspect ratio
    const frame = () => {
      const vf = THREE.MathUtils.degToRad(cam.fov), hf = 2 * Math.atan(Math.tan(vf / 2) * cam.aspect);
      const dist = (span * 0.75) / Math.tan(Math.min(vf, hf) / 2);
      const dir = new THREE.Vector3(0.55, 0.6, 0.6).normalize();
      cam.position.copy(dir.multiplyScalar(dist)).add(ctl.target);
      ctl!.update();
    };
    let framed = false;
    const resize = () => {
      const r = host.getBoundingClientRect();
      renderer.setSize(r.width, r.height); cam.aspect = r.width / Math.max(1, r.height); cam.updateProjectionMatrix();
      if (!framed && r.width > 0) { frame(); framed = true; }
    };
    ro = new ResizeObserver(resize); ro.observe(host); resize();

    // Tooltip via raycast
    const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
    renderer.domElement.addEventListener('pointerup', e => pick(e));
    const pick = (e: PointerEvent) => {
      const r = renderer.domElement.getBoundingClientRect();
      ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(ndc, cam);
      let hit: { m: Machine; d: number } | null = null;
      for (const pk of pickables) {
        const h = ray.intersectObject(pk.mesh)[0];
        if (h && h.instanceId !== undefined && (!hit || h.distance < hit.d)) hit = { m: pk.list[h.instanceId], d: h.distance };
      }
      tip = hit ? { x: e.clientX - r.left, y: e.clientY - r.top, m: hit.m } : null;
    };
    renderer.domElement.addEventListener('pointermove', e => { if (e.pointerType === 'mouse') pick(e); });
    const loop = () => { ctl!.update(); renderer.render(scene!, cam); raf = requestAnimationFrame(loop); };
    loop();
    addEventListener('keydown', esc);
  });
  const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onclose(); };
  /** Free GPU memory: geometries and materials of all scene objects (shared ones are disposed once) */
  function disposeScene(s: THREE.Scene) {
    const done = new Set<{ dispose(): void }>();
    s.traverse(o => {
      const m = o as THREE.Mesh;
      if (m.geometry) done.add(m.geometry);
      for (const mat of [m.material ?? []].flat()) done.add(mat);
      if (o instanceof THREE.InstancedMesh) o.dispose();
    });
    done.forEach(x => x.dispose());
  }
  onDestroy(() => {
    cancelAnimationFrame(raf); ro?.disconnect(); ctl?.dispose();
    if (scene) disposeScene(scene);
    renderer?.dispose(); removeEventListener('keydown', esc);
  });
</script>

<div class="wrap f3d" use:portal role="dialog" aria-modal="true" aria-label={$t('3D view')}>
  <div class="bar"><b>{$lx(title)}</b><span class="muted">{$t('{n} machines · drag to rotate, wheel/pinch to zoom, right mouse button to pan', { n: machines.length })}</span>
    <button class="btn" onclick={onclose}>{$t('Close')}</button></div>
  {#if failed}<div class="fail">{failed} {$t('The 2D map still works.')}</div>{/if}
  <div class="host" bind:this={host}>
    {#if tip}<div class="tip" style="left:{tip.x + 12}px;top:{tip.y + 12}px"><b>{$tn(tip.m.recipe || tip.m.name)}</b><span>{$tn(tip.m.name)} · {$t(tip.m.state)} {tip.m.pct} % · {tip.m.z} m</span></div>{/if}
  </div>
</div>

<style>
  :global(.f3d) { position: fixed; inset: 0; z-index: 120; background: #16171a; display: flex; flex-direction: column; }
  :global(.f3d .bar) { display: flex; align-items: center; gap: 14px; padding: 8px 12px; background: var(--plate); border-bottom: 2px solid var(--ficsit); }
  :global(.f3d .bar b) { font-family: var(--cond); font-size: 18px; }
  :global(.f3d .bar .muted) { flex: 1; font-size: 12.5px; }
  :global(.f3d .fail) { padding: 24px 16px; color: var(--warn); }
  :global(.f3d .host) { flex: 1; position: relative; min-height: 0; touch-action: none; }
  :global(.f3d .tip) { position: absolute; pointer-events: none; background: var(--plate); border: 1px solid var(--seam); padding: 6px 9px; font-size: 12.5px;
         display: flex; flex-direction: column; }
  :global(.f3d .tip span) { color: var(--dim); }
  @media (max-width: 760px) { :global(.f3d .bar .muted) { display: none; } }
</style>
