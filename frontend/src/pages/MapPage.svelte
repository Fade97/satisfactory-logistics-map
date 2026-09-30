<script lang="ts">
  import { onMount, onDestroy, untrack } from 'svelte';
  import { MapView, type MapObj } from '../lib/mapview';
  import { live, stations, factory, geo, nodes, powerlines, pins, trails, loadPins, flow, collectibles } from '../lib/api';
  import { route, replaceQuery } from '../lib/router';
  import { LAYERS, stationsObjs, liveObjs, factoryObjs, nodeObjs, pinObjs, applyGeo, factoryColor, collectibleObjs } from '../lib/scene';
  import { C, MODE_DE, fmtNum } from '../lib/fmt';
  import Detail from '../lib/Detail.svelte';
  import PinEditor from '../lib/PinEditor.svelte';
  import StationList from '../lib/map/StationList.svelte';
  import HeightPanel from '../lib/map/HeightPanel.svelte';
  import TimeTravel from '../lib/map/TimeTravel.svelte';
  import { matches, fuzzy } from '../lib/fuzzy';
  import ItemPicker from '../lib/ItemPicker.svelte';
  import { prefs, rememberView } from '../lib/prefs';
  import { tn, both } from '../lib/names';

  let { kiosk = false, followKey = '' }: { kiosk?: boolean; followKey?: string } = $props();

  let cv: HTMLCanvasElement;
  let V: MapView | null = null;
  let sel = $state<MapObj | null>(null);
  let follow = $state<string>(followKey || ($prefs.followMe && $prefs.me ? 'player:' + $prefs.me : ''));
  let q = $state('');
  let F = $state({ truck: true, train: true, load: true, unload: true });
  let layers = $state<Record<string, boolean>>(Object.fromEntries(
    LAYERS.map(([k, , on]) => [k, JSON.parse(localStorage.getItem('fgmap.layers') || '{}')[k] ?? on])));
  let showLayers = $state(false), showList = $state(false), showLegend = $state(false);
  let tip = $state<{ x: number; y: number; o: MapObj } | null>(null);
  let draw = $state<null | { shape: 'point' | 'line' | 'area'; pts: number[][] }>(null);
  let editPin = $state<any>(null);
  let flowItem = $state<string>('');            // Warenfluss: gewählte Ware, '' = aus
  let showFlow = $state(false);
  // Höhenfilter: Stockwerke aus den Maschinenhöhen (Häufungen), Bereich [von, bis] in Metern
  let showZ = $state(false);
  // Zeitreise: gewähltes Minutenbild ersetzt die Live-Objekte, bis die Leiste geschlossen wird
  let showTT = $state(false);
  let ttFrame: any = null;
  let zRange = $state<[number, number] | null>(null);
  // Messen: Punkte in Weltkoordinaten
  let measure = $state<number[][] | null>(null);
  // Auswahlmodus: #/map?pick=site — ein Tippen setzt den Bauplatz des Rechners und springt zurück
  let pickMode = $state<string | null>($route.q.get('pick'));
  let scaleTxt = $state(''), scaleW = $state(80);
  let isMobile = $state(matchMedia('(max-width: 760px)').matches);
  matchMedia('(max-width: 760px)').addEventListener('change', e => (isMobile = e.matches));

  let objs = { st: [] as MapObj[], lv: [] as MapObj[], fac: [] as MapObj[], nd: [] as MapObj[], pn: [] as MapObj[], co: [] as MapObj[] };
  function rebuild() {
    if (!V) return;
    const byKey = new Map(V.objs.map(o => [o.key, o]));
    V.objs = [...objs.co, ...objs.fac, ...objs.nd, ...objs.st, ...objs.pn, ...objs.lv];
    // laufende Auswahl auf das neue Objekt umhängen
    if (sel) { const n = V.objs.find(o => o.key === sel!.key); if (n) { sel = n; V.sel = n; } }
    V.boxes = ($factory?.factories || []).map(f => ({ box: f.box, color: factoryColor(f), layer: 'factories' }));
    applyFilter(); V.invalidate();
    void byKey;
  }

  // --- Daten → Objekte. Beim Zurückwechseln auf die Karte sind die Stores schon gefüllt und die Effekte
  // laufen vor onMount — dann fehlt V noch; ingestAll() holt das nach dem Aufbau nach.
  function ingestStations(s: any) { objs.st = stationsObjs(s); applyGeo(V!, $geo, $powerlines, s); }
  function ingestAll() {
    if (!V) return;
    if ($stations) ingestStations($stations);
    if ($factory) objs.fac = factoryObjs($factory);
    if ($nodes) objs.nd = nodeObjs($nodes);
    if ($collectibles) objs.co = collectibleObjs($collectibles);
    objs.pn = pinObjs($pins);
    if ($live) objs.lv = liveObjs($live);
    applyGeo(V, $geo, $powerlines, $stations);
    rebuild();
  }
  $effect(() => { const s = $stations; if (s) untrack(() => { if (V) { ingestStations(s); rebuild(); } }); });
  $effect(() => { const f = $factory; if (f) untrack(() => { if (V) { objs.fac = factoryObjs(f); rebuild(); } }); });
  $effect(() => { const n = $nodes; if (n) untrack(() => { if (V) { objs.nd = nodeObjs(n); rebuild(); } }); });
  $effect(() => { const c = $collectibles; if (c) untrack(() => { if (V) { objs.co = collectibleObjs(c); rebuild(); } }); });
  $effect(() => { const p = $pins; untrack(() => { if (V) { objs.pn = pinObjs(p); rebuild(); } }); });
  $effect(() => { const g = $geo, pl = $powerlines; untrack(() => { if (V) { applyGeo(V, g, pl, $stations); V.invalidate(); } }); });
  $effect(() => {
    const lv = $live; if (!lv) return;
    untrack(() => {
      if (!V || ttFrame) return;
      const old = new Map(objs.lv.map(o => [o.key, o]));
      const nw = liveObjs(lv);
      for (const o of nw) {            // weich zur neuen Position gleiten
        const p = old.get(o.key);
        if (p) { o.sx = p.x; o.sy = p.y; o.tx = o.x; o.ty = o.y; o.x = p.x; o.y = p.y; o.t0 = performance.now(); }
      }
      objs.lv = nw; rebuild();
    });
  });
  // Spieler, die nicht online sind, werden nicht verfolgt (ihre Figur steht nur im Spiel herum).
  // Das Ziel bleibt gemerkt: Kommt der Spieler online, geht das Folgen von selbst weiter.
  const followState = $derived.by(() => {
    if (!follow) return 'aus';
    if (!follow.startsWith('player:')) return 'aktiv';
    const p = ($live?.players || []).find(x => 'player:' + x.name === follow);
    return !p ? 'weg' : p.online === true ? 'aktiv' : 'offline';
  });
  $effect(() => {                      // Folge-Modus: die Kamera führt die MapView im Render-Loop nach (gleiche Interpolation wie der Punkt)
    const f = followState === 'aktiv' ? follow : '', s = sel, mob = isMobile;
    untrack(() => {
      if (!V) return;
      V.followKey = f || null;
      V.followOff = { x: !mob && s ? 380 : 0, y: mob && s ? 280 : 0 };
      if (f) {                            // beim Einschalten einmal hinzoomen, danach nur noch mitführen
        const o = V.objs.find(x => x.key === f);
        if (o && V.k < 1) { V.k = 1; V.invalidate(); }
        V.redraw();
      }
    });
  });
  $effect(() => { const t = $trails; untrack(() => { if (V) V.redraw(); void t; }); });

  // --- Warenfluss: Erzeuger, Verbraucher, Stationen, Knoten und Bänder/Rohre einer Ware
  const flowInfo = $derived.by(() => {
    const it = flowItem;
    if (!it) return null;
    const keys = new Set<string>();
    let prod = 0, cons = 0, np = 0, nc = 0, ns = 0;
    for (const m of $factory?.machines || []) {
      const o = m.out.find(x => x.item === it), i = m.inp.find(x => x.item === it);
      if (o) { keys.add('machine:' + m.id); prod += o.rate; np++; }
      if (i) { keys.add('machine:' + m.id); cons += i.rate; nc++; }
    }
    for (const g of $factory?.generators || []) if (g.fuel === it) { keys.add('generator:' + g.id); nc++; }
    for (const s of [...($stations?.trucks || []), ...($stations?.trains || [])])
      if (s.items.some(x => x.item === it)) { keys.add('station:' + s.id.split('.').pop()); ns++; }
    for (const n of $nodes || []) if (n.item === it) keys.add('node:' + n.id);
    for (const f of $factory?.factories || []) if (f.out.some(o => o.item === it) || f.inp.some(o => o.item === it)) keys.add('factory:' + f.key);
    return { keys, paths: ($flow || {})[it] || [], prod, cons, np, nc, ns };
  });
  const flowItems = $derived([...new Set([...Object.keys($flow || {}), ...($factory?.balance || []).map(b => b.item)])].sort((a, b) => a.localeCompare(b, 'de')));
  $effect(() => {
    const fi = flowInfo;
    untrack(() => {
      if (!V) return;
      V.flowFocus = fi ? { keys: fi.keys, paths: fi.paths, color: '#f5f2ea' } : null;
      // Maschinen- und Knoten-Ebene für die Dauer des Warenflusses sichtbar machen
      if (fi) { V.layers = { ...layers, machines: true, nodes: true, generators: true }; }
      else V.layers = { ...layers };
      V.invalidate(); writeHash();
    });
  });
  function flowFit() {
    if (!V || !flowInfo) return;
    const pts = [...V.objs.filter(o => flowInfo!.keys.has(o.key) && o.kind !== 'node').map(o => [o.x, o.y]), ...flowInfo.paths.flat()];
    if (!pts.length) return;
    const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
    V.fit(Math.min(...xs) - 100, Math.min(...ys) - 100, Math.max(...xs) + 100, Math.max(...ys) + 100);
  }

  // Sammelobjekte: „noch 62 von 106“ im Ebenenmenü
  const collectCount = $derived.by(() => {
    const c = $collectibles; if (!c) return {} as Record<string, string>;
    const o = c.open || {}, t = c.total || {};
    return {
      c_somersloop: `${(t.somersloop ?? 0) - (o.somersloop?.length ?? 0)} / ${t.somersloop}`,
      c_mercer: `${(t.mercer ?? 0) - (o.mercer?.length ?? 0)} / ${t.mercer}`,
      c_slug: `${(o.slug1?.length ?? 0) + (o.slug2?.length ?? 0) + (o.slug3?.length ?? 0)} offen`,
      c_droppod: `${c.looted_pods} / ${t.droppod}`,
    } as Record<string, string>;
  });

  $effect(() => { const r = zRange; untrack(() => { if (V) { V.zRange = r ? [r[0] - 3, r[1] + 3] : null; V.invalidate(); } }); });

  // --- Messen: Strecke, Fläche, Höhe
  const measureInfo = $derived.by(() => {
    const m = measure;
    if (!m || m.length < 2) return null;
    let len = 0;
    for (let i = 1; i < m.length; i++) len += Math.hypot(m[i][0] - m[i - 1][0], m[i][1] - m[i - 1][1]);
    let area = 0;
    if (m.length >= 3) { for (let i = 0; i < m.length; i++) { const a = m[i], b = m[(i + 1) % m.length]; area += a[0] * b[1] - b[0] * a[1]; } area = Math.abs(area) / 2; }
    return { len, area, direct: Math.hypot(m[m.length - 1][0] - m[0][0], m[m.length - 1][1] - m[0][1]) };
  });

  // --- Zeitreise: Bild → Kartenobjekte (Spieler/Züge/LKW) + Fabrik-Umriss nach damaligem Zustand
  function applyFrame(t: number | null, f: any) {
    ttFrame = f;
    if (!V) return;
    if (!f) {                                      // zurück zu live
      if ($live) objs.lv = liveObjs($live);
      V.boxes = ($factory?.factories || []).map(x => ({ box: x.box, color: factoryColor(x), layer: 'factories' }));
      rebuild(); return;
    }
    const pl = f.p.map((x: any) => ({ name: x[0], pos: [x[1] * 100, x[2] * 100, 0], online: !!x[3] }));
    const tr = f.tr.map((x: any) => ({ name: x[0], pos: [x[1] * 100, x[2] * 100, 0], speed: x[3], docked: !!x[4], derailed: false }));
    const liveTk = new Map(($live?.trucks || []).map(v => [v.id || v.name, v]));
    const tk = f.tk.map((x: any) => ({ ...(liveTk.get(x[0]) || { name: x[0], type: 'LKW' }), id: x[0], pos: [x[1] * 100, x[2] * 100, 0], speed: x[3] }));
    const old = new Map(objs.lv.map(o => [o.key, o]));
    const nw = liveObjs({ ...($live as any), players: pl, trains: tr, trucks: tk, source: 'frm' });
    for (const o of nw) { const p = old.get(o.key); if (p) { o.sx = p.x; o.sy = p.y; o.tx = o.x; o.ty = o.y; o.x = p.x; o.y = p.y; o.t0 = performance.now() - 4000; } }
    objs.lv = nw;
    const st = new Map(f.f.map((x: any) => [x[0], x]));
    V.boxes = ($factory?.factories || []).map(x => {
      const s: any = st.get(x.key);
      const col = !s ? '#6f6b64' : s[2] > 30 ? '#e5484d' : s[2] > 8 ? '#e2b93b' : s[1] > 20 ? '#4cc38a' : '#8a857c';
      return { box: x.box, color: col, layer: 'factories' };
    });
    rebuild();
  }

  // --- Filter (Suche, Chips) → V.hidden
  function applyFilter() {
    if (!V) return;
    const qq = q.trim().toLowerCase();
    const h = new Set<string>();
    for (const o of V.objs) {
      if (o.kind === 'station') {
        const s = o.data;
        let vis = F[s.kind as 'truck' | 'train'] && (s.mode === 'mixed' || s.mode === 'none' ? F.load || F.unload : F[s.mode as 'load' | 'unload']);
        if (vis && qq) vis = matches(qq, s.name, ...s.items.map((i: any) => both(i.item)));
        if (!vis) h.add(o.key);
      } else if (qq && o.kind !== 'player') {
        if (!matches(qq, o.label, o.data?.recipe, o.data?.item, ...(o.data?.out || []).map((x: any) => x.item))) h.add(o.key);
      }
    }
    V.hidden = h; V.invalidate();
  }
  $effect(() => { void q; void F.truck; void F.train; void F.load; void F.unload; untrack(applyFilter); });
  $effect(() => {
    const L = { ...layers };
    localStorage.setItem('fgmap.layers', JSON.stringify(L));
    untrack(() => { if (V) { V.layers = L; V.labels = L.labels !== false; V.invalidate(); } });
  });

  // --- Auswahl
  function select(o: MapObj | null, center = true) {
    sel = o; if (!V) return;
    V.sel = o; V.links = [];
    if (o && o.kind === 'station' && o.data.kind === 'truck') {
      const mine = new Set((o.data.vehicles || []).map((v: any) => v.id));
      V.links = objs.st.filter(x => x !== o && x.data.kind === 'truck' && (x.data.vehicles || []).some((v: any) => mine.has(v.id))).map(x => [o, x]);
    } else if (o && o.kind === 'truck') {
      V.links = objs.st.filter(x => x.data.kind === 'truck' && (x.data.vehicles || []).some((v: any) => v.id === o.data.id)).map(x => [o, x]);
    }
    if (o && center) V.focus(o.x, o.y, o.kind === 'machine' ? 3 : 1.2, isMobile ? Math.min(420, V.h * .5) : 0, !isMobile ? 380 : 0);
    V.redraw(); writeHash();
  }
  const pick = (key: string) => { const o = V?.objs.find(x => x.key === key); if (o) select(o); };

  // --- Adresszeile
  let hashT = 0;
  function writeHash() {
    if (kiosk || !V) return;
    clearTimeout(hashT);
    hashT = window.setTimeout(() => {
      if (!V) return;
      const c = V.center();
      rememberView(c.x, c.y, V.k);
      // Inzwischen auf eine andere Seite gewechselt? Dann die Adresse nicht zurück auf die Karte biegen.
      // location.hash statt $route: der Router erfährt vom Wechsel erst mit dem hashchange-Ereignis, danach wäre es zu spät
      if (!/^#\/(map|karte)(\?|$)/.test(location.hash)) return;
      replaceQuery('map', { x: String(Math.round(c.x)), y: String(Math.round(c.y)), z: V!.k.toFixed(3), ...(sel ? { sel: sel.key } : {}),
        ...(flowItem ? { item: flowItem } : {}), ...(pickMode ? { pick: pickMode } : {}) });
    }, 300);
  }
  function fromRoute() {
    const r = $route;
    if (!V || r.page !== 'map') return;
    if (r.q.has('x')) {
      V.k = parseFloat(r.q.get('z') || '1');
      V.dx = V.w / 2 - V.k * +r.q.get('x')!; V.dy = V.h / 2 - V.k * +r.q.get('y')!; V.invalidate();
    }
    const s = r.q.get('sel');
    if (s) { const o = V.objs.find(x => x.key === s); if (o) select(o, !r.q.has('x')); }
    pickMode = r.q.get('pick');
    const w = r.q.get('item');
    if (w !== null && w !== flowItem) { flowItem = w; showFlow = true; if (!r.q.has('x')) setTimeout(flowFit, 300); }
  }
  let routeReady = false;
  $effect(() => { void $route; untrack(() => { if (routeReady) fromRoute(); }); });

  function fitFactory() {
    if (!V) return;
    const xs = objs.st.map(o => o.x).concat(objs.fac.map(o => o.x)), ys = objs.st.map(o => o.y).concat(objs.fac.map(o => o.y));
    if (!xs.length) return;
    const lo = (a: number[]) => a.slice().sort((p, q) => p - q)[Math.floor(a.length * .01)];
    const hi = (a: number[]) => a.slice().sort((p, q) => p - q)[Math.floor(a.length * .99)];
    V.fit(lo(xs) - 150, lo(ys) - 150, hi(xs) + 150, hi(ys) + 150);
  }
  function fitMap() { if (V && $stations) { const m = $stations.map; V.fit(m.west / 100, m.north / 100, m.east / 100, m.south / 100, .98); } }

  function scalebar() {
    if (!V) return;
    const want = 110 / V.k, steps = [5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000];
    const d = steps.find(s => s >= want) || 5000;
    scaleW = d * V.k; scaleTxt = d >= 1000 ? d / 1000 + ' km' : d + ' m';
  }

  // --- Gesten
  onMount(() => {
    V = new MapView(cv);
    (window as any).__fgmap = V;          // für Rauchtests (Kamera/Objekte lesen), sonst ungenutzt
    V.layers = { ...layers };
    V.labels = layers.labels !== false;
    V.onchange = () => { scalebar(); writeHash(); };
    let heatKey = '', heatCv: HTMLCanvasElement | null = null, heatBox = { x: 0, y: 0, k: 1 };
    V.overlays.push({ key: 'heat', layer: 'heat', draw: (c, v) => {
      const ms = ($factory?.machines || []).filter(m => m.state === 'steht' && m.block !== 'voll');
      if (!ms.length) return;
      // Wärmebild in Weltkoordinaten einmal je Datenstand rendern (4 m/px), dann nur skaliert zeichnen
      const key = ($factory?.at || 0) + ':' + ms.length;
      if (key !== heatKey) {
        heatKey = key;
        const xs = ms.map(m => m.pos[0]), ys = ms.map(m => m.pos[1]), pad = 120, res = 4;
        const x0 = Math.min(...xs) - pad, y0 = Math.min(...ys) - pad;
        const w = Math.ceil((Math.max(...xs) + pad - x0) / res), h = Math.ceil((Math.max(...ys) + pad - y0) / res);
        heatCv = document.createElement('canvas'); heatCv.width = w; heatCv.height = h;
        const hc = heatCv.getContext('2d')!;
        for (const m of ms) {
          const px = (m.pos[0] - x0) / res, py = (m.pos[1] - y0) / res, r = 40 / res;
          const g = hc.createRadialGradient(px, py, 0, px, py, r);
          g.addColorStop(0, 'rgba(0,0,0,.22)'); g.addColorStop(1, 'rgba(0,0,0,0)');
          hc.fillStyle = g; hc.fillRect(px - r, py - r, 2 * r, 2 * r);
        }
        // Dichte (Alpha) → Farbe: gelb bei wenig, rot bei viel
        const img = hc.getImageData(0, 0, w, h), d = img.data;
        for (let i = 0; i < d.length; i += 4) {
          const a = d[i + 3] / 255; if (!a) continue;
          const t = Math.min(1, a * 1.6);
          d[i] = 229; d[i + 1] = Math.round(185 - 113 * t); d[i + 2] = Math.round(59 + 18 * t); d[i + 3] = Math.round(Math.min(.75, a * 1.4) * 255);
        }
        hc.putImageData(img, 0, 0);
        heatBox = { x: x0, y: y0, k: res };
      }
      if (heatCv) c.drawImage(heatCv, v.sx(heatBox.x), v.sy(heatBox.y), heatCv.width * heatBox.k * v.k, heatCv.height * heatBox.k * v.k);
    } });
    V.overlays.push({ key: 'measure', layer: 'measure', draw: (c, v) => {
      const m = measure; if (!m || !m.length) return;
      c.strokeStyle = '#f59a23'; c.lineWidth = 2; c.setLineDash([8, 5]); c.beginPath();
      m.forEach((q, i) => (i ? c.lineTo : c.moveTo).call(c, v.sx(q[0]), v.sy(q[1])));
      c.stroke(); c.setLineDash([]);
      c.font = '600 12px "Barlow Condensed", sans-serif'; c.textAlign = 'center';
      for (let i = 0; i < m.length; i++) {
        const x = v.sx(m[i][0]), y = v.sy(m[i][1]);
        c.fillStyle = '#f59a23'; c.beginPath(); c.arc(x, y, 4, 0, Math.PI * 2); c.fill();
        if (i) {                                         // Teilstrecke an die Mitte schreiben
          const d = Math.hypot(m[i][0] - m[i - 1][0], m[i][1] - m[i - 1][1]);
          const mx = (x + v.sx(m[i - 1][0])) / 2, my = (y + v.sy(m[i - 1][1])) / 2;
          c.strokeStyle = 'rgba(12,13,14,.9)'; c.lineWidth = 3.5; const t = d >= 1000 ? (d / 1000).toFixed(2) + ' km' : Math.round(d) + ' m';
          c.strokeText(t, mx, my - 6); c.fillStyle = '#f5f2ea'; c.fillText(t, mx, my - 6);
        }
      }
    } });
    V.overlays.push({ key: 'trails', layer: 'trails', draw: (c, v) => {
      const T = $trails; c.lineWidth = 2; c.lineJoin = 'round';
      for (const n in T) {
        const pts = T[n]; if (pts.length < 2) continue;
        const now = Date.now() / 1000;
        for (let i = 1; i < pts.length; i++) {       // ältere Abschnitte blasser
          c.globalAlpha = Math.max(.12, 1 - (now - pts[i][0]) / 7200) * .8;
          c.strokeStyle = '#f59a23'; c.beginPath();
          c.moveTo(v.sx(pts[i - 1][1]), v.sy(pts[i - 1][2])); c.lineTo(v.sx(pts[i][1]), v.sy(pts[i][2])); c.stroke();
        }
      }
      c.globalAlpha = 1;
    } });
    V.overlays.push({ key: 'pins', layer: 'pins', draw: (c, v) => {
      for (const p of $pins) {
        if (p.shape === 'point') continue;
        c.strokeStyle = p.color; c.fillStyle = p.color; c.lineWidth = 2.5; c.beginPath();
        p.geom.forEach((q, i) => (i ? c.lineTo : c.moveTo).call(c, v.sx(q[0]), v.sy(q[1])));
        if (p.shape === 'area') { c.closePath(); c.globalAlpha = .15; c.fill(); c.globalAlpha = 1; c.setLineDash([6, 4]); }
        c.stroke(); c.setLineDash([]);
      }
      if (draw && draw.pts.length) {
        c.strokeStyle = '#f5f2ea'; c.lineWidth = 2; c.setLineDash([4, 4]); c.beginPath();
        draw.pts.forEach((q, i) => (i ? c.lineTo : c.moveTo).call(c, v.sx(q[0]), v.sy(q[1])));
        if (draw.shape === 'area' && draw.pts.length > 2) c.closePath();
        c.stroke(); c.setLineDash([]);
        for (const q of draw.pts) { c.fillStyle = '#f5f2ea'; c.fillRect(v.sx(q[0]) - 3, v.sy(q[1]) - 3, 6, 6); }
      }
    } });
    if ($stations) {
      const m = $stations.map;
      V.setImage('/map.jpg', { x: m.west / 100, y: m.north / 100, w: (m.east - m.west) / 100, h: (m.south - m.north) / 100 });
    }
    const ptrs = new Map<number, { x: number; y: number }>();
    let g: any = null, lastTap: any = null;
    const loc = (e: PointerEvent | MouseEvent) => { const r = cv.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
    cv.addEventListener('pointerdown', e => {
      const p = loc(e); ptrs.set(e.pointerId, p);
      if (ptrs.size === 1) g = { t: 'pan', x0: p.x, y0: p.y, dx: V!.dx, dy: V!.dy, moved: 0, type: e.pointerType };
      else if (ptrs.size === 2) {
        const [a, b] = [...ptrs.values()];
        g = { t: 'pinch', d0: Math.hypot(a.x - b.x, a.y - b.y), k0: V!.k, wx: V!.wx((a.x + b.x) / 2), wy: V!.wy((a.y + b.y) / 2) };
      }
      cv.setPointerCapture(e.pointerId);
    });
    cv.addEventListener('pointermove', e => {
      const p = loc(e);
      if (!ptrs.has(e.pointerId)) {                        // Hover (Maus)
        if (e.pointerType === 'mouse' && !draw) {
          const o = V!.hit(p.x, p.y);
          if (o !== V!.hover) { V!.hover = o; V!.redraw(); }
          tip = o ? { x: p.x, y: p.y, o } : null;
          cv.style.cursor = pickMode || measure ? 'crosshair' : o ? 'pointer' : draw ? 'crosshair' : 'grab';
        }
        return;
      }
      ptrs.set(e.pointerId, p);
      if (g?.t === 'pan') {
        g.moved = Math.max(g.moved, Math.hypot(p.x - g.x0, p.y - g.y0));
        if (g.moved < (g.type === 'touch' ? 9 : 4)) return;
        if (follow) follow = '';
        V!.dx = g.dx + p.x - g.x0; V!.dy = g.dy + p.y - g.y0; V!.redraw(); V!.onchange(); tip = null;
      } else if (g?.t === 'pinch' && ptrs.size === 2) {
        const [a, b] = [...ptrs.values()];
        const k = Math.max(.02, Math.min(30, g.k0 * Math.hypot(a.x - b.x, a.y - b.y) / g.d0));
        const m = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
        V!.k = k; V!.dx = m.x - g.wx * k; V!.dy = m.y - g.wy * k; V!.redraw(); V!.onchange();
      }
    });
    const up = (e: PointerEvent) => {
      if (!ptrs.has(e.pointerId)) return;
      ptrs.delete(e.pointerId);
      if (g?.t === 'pinch') { g = ptrs.size === 1 ? { t: 'pan', ...(() => { const p = [...ptrs.values()][0]; return { x0: p.x, y0: p.y }; })(), dx: V!.dx, dy: V!.dy, moved: 99 } : null; return; }
      if (g?.t === 'pan' && g.moved < (g.type === 'touch' ? 9 : 4) && e.type === 'pointerup') {
        const p = loc(e);
        if (measure) {                                       // Messen: Punkt anhängen (nächstes Objekt einrasten)
          const o = V!.hit(p.x, p.y, 12);
          measure = [...measure, o ? [o.x, o.y] : [V!.wx(p.x), V!.wy(p.y)]];
          V!.redraw();
        } else if (pickMode) {                               // Bauplatz für den Rechner wählen
          const site = { x: Math.round(V!.wx(p.x)), y: Math.round(V!.wy(p.y)) };
          localStorage.setItem('fgmap.site', JSON.stringify(site));
          pickMode = null; location.hash = '#/planner';
        } else if (draw) {                                   // Zeichenmodus: Punkte setzen
          draw.pts = [...draw.pts, [Math.round(V!.wx(p.x)), Math.round(V!.wy(p.y))]];
          if (draw.shape === 'point') finishDraw();
          V!.redraw();
        } else {
          const now = performance.now();
          if (g.type === 'touch' && lastTap && now - lastTap.t < 320 && Math.hypot(p.x - lastTap.x, p.y - lastTap.y) < 30) {
            V!.zoomAt(p.x, p.y, 2); lastTap = null;
          } else {
            lastTap = { t: now, ...p };
            select(V!.hit(p.x, p.y, g.type === 'touch' ? 18 : 10), false);
          }
        }
      }
      g = null;
    };
    cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
    cv.addEventListener('pointerleave', () => { tip = null; if (V!.hover) { V!.hover = null; V!.redraw(); } });
    cv.addEventListener('wheel', e => { e.preventDefault(); const p = loc(e); V!.zoomAt(p.x, p.y, Math.exp(-e.deltaY * .0016)); }, { passive: false });
    cv.addEventListener('dblclick', e => { if (draw && draw.shape !== 'point') { finishDraw(); } });

    // Detailebene einmal laden (Binärpaket, ~180 KB gzip); erst nötig ab Zoom 0,8
    fetch('/api/detail').then(r => r.ok ? r.arrayBuffer() : null).then(buf => {
      if (!buf || !V) return;
      const h = new Int32Array(buf, 0, 2), nt = h[0], nw = h[1];
      const tiles = new Int16Array(buf, 8, 3 * nt), tmeta = new Uint8Array(buf, 8 + 6 * nt, nt);
      const wOff = 8 + 6 * nt + nt + ((nt % 2) ? 1 : 0);
      V.detail = { tiles, tmeta, walls: new Int16Array(buf, wOff, 5 * nw) }; V.invalidate();
    }).catch(() => {});
    const init = () => {
      if (!$stations) return setTimeout(init, 200);
      ingestAll();
      const m = $stations.map;
      if (!V!.img) V!.setImage('/map.jpg', { x: m.west / 100, y: m.north / 100, w: (m.east - m.west) / 100, h: (m.south - m.north) / 100 });
      if (!kiosk && ($route.q.has('x') || $route.q.has('item') || $route.q.has('sel') || $route.q.has('pick'))) { if (!$route.q.has('x')) fitFactory(); fromRoute(); }
      else if ($prefs.lastView && !kiosk) {           // eigene Startansicht: dort weiter, wo man war
        const lv = $prefs.lastView; V!.k = lv.z; V!.dx = V!.w / 2 - lv.z * lv.x; V!.dy = V!.h / 2 - lv.z * lv.y; V!.invalidate();
      } else fitFactory();
      routeReady = true; scalebar();
    };
    init();
    addEventListener('keydown', key);
  });
  onDestroy(() => { clearTimeout(hashT); V?.destroy(); removeEventListener('keydown', key); });

  function key(e: KeyboardEvent) {
    if (kiosk || !V) return;
    const inField = (e.target as HTMLElement)?.matches?.('input, textarea');
    if (inField) { if (e.key === 'Escape') { q = ''; (e.target as HTMLElement).blur(); } return; }
    const r = { w: V.w / 2, h: V.h / 2 };
    if (e.key === '/') { e.preventDefault(); (document.querySelector('#q') as HTMLInputElement)?.focus(); }
    else if (e.key === 'Escape') { if (draw) draw = null; else if (q) q = ''; else select(null); }
    else if (e.key === '+' || e.key === '=') V.zoomAt(r.w, r.h, 1.4);
    else if (e.key === '-') V.zoomAt(r.w, r.h, 1 / 1.4);
    else if (e.key === 'f') fitFactory();
    else if (e.key === 'g') fitMap();
    else if (e.key === 'l') layers.labels = layers.labels === false;
    else if (e.key === 'm') layers.mapimg = !layers.mapimg;
    else if (e.key.startsWith('Arrow')) {
      const s = 80; V.pan(e.key === 'ArrowLeft' ? s : e.key === 'ArrowRight' ? -s : 0, e.key === 'ArrowUp' ? s : e.key === 'ArrowDown' ? -s : 0);
    }
  }

  // --- Zeichnen / Pins
  function startDraw(shape: 'point' | 'line' | 'area') { draw = { shape, pts: [] }; select(null); }
  function finishDraw() {
    if (!draw) return;
    const need = draw.shape === 'point' ? 1 : draw.shape === 'line' ? 2 : 3;
    if (draw.pts.length >= need) editPin = { author: '', cat: 'geplant', color: '#f59a23', text: '', shape: draw.shape, geom: draw.pts };
    draw = null; V?.redraw();
  }
  function editObj(o: MapObj) {
    if (o.kind === 'pin') editPin = { ...o.data };
    else if (o.kind === 'factory') editPin = { factory: o.data };
  }

  function tipText(o: MapObj) {
    const d = o.data;
    if (o.kind === 'station') return (d.kind === 'train' ? 'Zugbahnhof' : 'Truckstation') + ' · ' + MODE_DE[d.mode] + (d.items[0] ? ' · ' + d.items.map((i: any) => $tn(i.item)).join(', ') : '');
    if (o.kind === 'machine') return $tn(d.name) + ' · ' + d.state + ' ' + d.pct + ' %' + (d.why ? ' · ' + d.why : '');
    if (o.kind === 'node') return (d.used ? 'belegt' : 'frei') + (d.rate ? ' · ' + d.rate + '/min' : '');
    if (o.kind === 'player') return d.online === null ? 'Stand des Saves' : d.online ? 'online' : 'offline';
    if (o.kind === 'truck' || o.kind === 'train') return (d.cargo ? d.cargo.item + ' · ' : '') + (d.speed != null ? Math.round(d.speed) + ' km/h' : 'Position aus dem Save');
    if (o.kind === 'factory') return d.n + ' Maschinen · ' + (d.states['steht'] || 0) + ' stehen';
    if (o.kind === 'pin') return d.author;
    if (o.kind === 'generator') return d.producing ? 'erzeugt ' + d.cap + ' MW' : 'steht';
    if (o.kind === 'collectible') return 'noch nicht eingesammelt · Höhe ' + d.pos[2] + ' m';
    return '';
  }
</script>

<div class="wrap" class:kiosk>
  {#if !kiosk}
  <StationList bind:q bind:F bind:open={showList} selKey={sel?.key || ''} onpick={pick} onfit={(a, b, c, d) => V?.fit(a, b, c, d)} />
  {#if showList}<button class="backdrop" aria-label="Liste schließen" onclick={() => (showList = false)}></button>{/if}
  {/if}

  <section class="map">
    <canvas bind:this={cv} aria-label="Fabrikkarte"></canvas>
    {#if tip && !isMobile}
      <div class="tip" style="left:{tip.x + 14}px;top:{tip.y + 14}px"><b>{tip.o.kind === 'machine' || tip.o.kind === 'node' || tip.o.kind === 'generator' ? $tn(tip.o.kind === 'machine' ? (tip.o.data.recipe || tip.o.data.name) : tip.o.kind === 'node' ? tip.o.data.item : tip.o.data.name) : tip.o.label}</b><span>{tipText(tip.o)}</span></div>
    {/if}

    {#if !kiosk}
    <div class="ctl">
      <button class="cb m-only" onclick={() => (showList = !showList)} aria-label="Stationsliste">☰</button>
      <div class="grp"><button class="cb" onclick={() => V?.zoomAt(V.w / 2, V.h / 2, 1.5)} aria-label="Hineinzoomen">+</button>
        <button class="cb" onclick={() => V?.zoomAt(V.w / 2, V.h / 2, 1 / 1.5)} aria-label="Herauszoomen">−</button></div>
      <button class="cb wide" onclick={fitFactory} title="Auf das Fabrikgebiet (f)"><span class="i">⌂</span><span class="t">Fabrik</span></button>
      <button class="cb wide" onclick={fitMap} title="Ganze Karte (g)"><span class="i">⤢</span><span class="t">Ganze Karte</span></button>
      <button class="cb wide" class:on={showLayers} onclick={() => (showLayers = !showLayers)}><span class="i">◫</span><span class="t">Ebenen</span></button>
      <button class="cb wide" class:on={!!draw} onclick={() => (draw ? (draw = null) : startDraw('point'))} title="Notiz auf die Karte setzen"><span class="i">✎</span><span class="t">Notiz</span></button>
      <button class="cb wide" class:on={showZ || !!zRange} onclick={() => { showZ = !showZ; if (!showZ) zRange = null; }} title="Nach Höhe/Stockwerk filtern"><span class="i">☰</span><span class="t">Höhe</span></button>
      <button class="cb wide" class:on={!!measure} onclick={() => { measure = measure ? null : []; select(null); V?.redraw(); }} title="Strecke und Fläche messen"><span class="i">⟷</span><span class="t">Messen</span></button>
      <button class="cb wide" class:on={showTT} onclick={() => (showTT = !showTT)} title="Die letzten Stunden abspielen"><span class="i">◷</span><span class="t">Zeitreise</span></button>
      <button class="cb wide" class:on={showFlow || !!flowItem} onclick={() => { showFlow = !showFlow; if (!showFlow) flowItem = ''; }} title="Eine Ware durch die Fabrik verfolgen"><span class="i">⇶</span><span class="t">Warenfluss</span></button>
      {#if showLayers}
        <div class="layers panel">
          {#each LAYERS as [k, l]}
            <label><input type="checkbox" bind:checked={layers[k]} /> {l}{#if collectCount[k]}<span class="cnt">{collectCount[k]}</span>{/if}</label>
          {/each}
          <label><input type="checkbox" checked={layers.labels !== false} onchange={e => (layers.labels = (e.target as HTMLInputElement).checked)} /> Beschriftungen</label>
          <button class="lg" onclick={() => (showLegend = !showLegend)}>Legende {showLegend ? 'ausblenden' : 'zeigen'}</button>
        </div>
      {/if}
      {#if draw}
        <div class="drawbar panel">
          <div class="seg">
            {#each [['point', 'Punkt'], ['line', 'Linie'], ['area', 'Fläche']] as [s, l]}
              <button class:on={draw.shape === s} onclick={() => (draw = { shape: s as any, pts: [] })}>{l}</button>
            {/each}
          </div>
          <p>{draw.shape === 'point' ? 'Tippe auf die Stelle der Notiz.' : 'Setze Punkte, dann „Fertig“.'}</p>
          {#if draw.shape !== 'point'}<button class="btn primary" onclick={finishDraw} disabled={draw.pts.length < (draw.shape === 'line' ? 2 : 3)}>Fertig</button>{/if}
          <button class="btn" onclick={() => (draw = null)}>Abbrechen</button>
        </div>
      {/if}
    </div>
    {#if showLegend}
      <div class="legend panel">
        <div><span class="dot" style="background:{C.load}"></span> Beladen <span class="dot" style="background:{C.unload}"></span> Entladen <span class="dot" style="background:{C.mixed}"></span> gemischt</div>
        <div><span class="sq"></span> Zugbahnhof · <span class="dot" style="background:#c3bfb7"></span> Truckstation · Balken = Füllstand</div>
        <div><span class="dot" style="background:#f59a23;box-shadow:0 0 0 2px #f5f2ea"></span> Spieler · <span class="sq" style="background:{C.train}"></span> Zug · <span class="dia"></span> Fahrzeug</div>
        <div><span class="sq sm" style="background:{C.ok}"></span> läuft <span class="sq sm" style="background:{C.warn}"></span> teilweise <span class="sq sm" style="background:{C.bad}"></span> Materialmangel <span class="sq sm" style="background:#8a857c"></span> Ausgang voll</div>
        <div>Fabrik-Umriss: grün läuft · gelb etwas Mangel · rot viel Mangel</div>
        <div class="muted">Kartengrafik: satisfactory.wiki.gg · CC BY-NC-SA</div>
      </div>
    {/if}
    <div class="scale"><span style="width:{scaleW}px"></span>{scaleTxt}</div>
    {/if}

    {#if sel && !kiosk}
      <div class="detail panel">
        <button class="close" onclick={() => select(null)} aria-label="Schließen">✕</button>
        <Detail o={sel} onpick={pick} following={follow === sel.key}
          onfollow={['player', 'train', 'truck'].includes(sel.kind) ? () => (follow = follow === sel!.key ? '' : sel!.key) : undefined}
          onpin={editObj} />
      </div>
    {/if}
    {#if showTT && !kiosk}<TimeTravel onframe={applyFrame} onclose={() => (showTT = false)} />{/if}
    {#if showZ && !kiosk}<HeightPanel bind:zRange onclose={() => (showZ = false)} />{/if}
    {#if measure && !kiosk}
      <div class="flowbar panel meas">
        <div class="zh"><b>Messen</b><button class="x" onclick={() => { measure = null; V?.redraw(); }} aria-label="Messen beenden">✕</button></div>
        {#if measureInfo}
          <div class="fs"><span>Strecke <b class="num">{measureInfo.len >= 1000 ? (measureInfo.len / 1000).toFixed(2) + ' km' : Math.round(measureInfo.len) + ' m'}</b></span>
            {#if measure.length > 2}<span>Luftlinie Anfang–Ende <b class="num">{Math.round(measureInfo.direct)} m</b></span>
              <span>Fläche <b class="num">{measureInfo.area >= 1e6 ? (measureInfo.area / 1e6).toFixed(2) + ' km²' : fmtNum(Math.round(measureInfo.area)) + ' m²'}</b> ≈ {fmtNum(Math.floor(measureInfo.area / 64))} Fundamente 8×8</span>{/if}
            <span>≈ {fmtNum(Math.ceil(measureInfo.len / 12))} Gleisstücke · {fmtNum(Math.ceil(measureInfo.len / 56))} Bänder (max. 56 m)</span></div>
          <button class="lk" onclick={() => { measure = measure!.slice(0, -1); V?.redraw(); }}>letzten Punkt entfernen</button>
        {:else}<p class="muted">Tippe Punkte auf die Karte. Auf Stationen und Maschinen rastet der Punkt ein.</p>{/if}
      </div>
    {/if}
    {#if pickMode && !kiosk}
      <div class="flowbar panel pick">Tippe auf die Stelle, an der gebaut werden soll.
        <a class="lk" href="#/planner">Abbrechen</a></div>
    {/if}
    {#if (showFlow || flowItem) && !kiosk}
      <div class="flowbar panel">
        <div class="fr"><ItemPicker bind:value={flowItem} items={flowItems} placeholder="Ware verfolgen, z. B. Stahlträger" onpick={() => setTimeout(flowFit, 30)} />
          <button class="x" onclick={() => { flowItem = ''; showFlow = false; }} aria-label="Warenfluss beenden">✕</button></div>
        {#if flowInfo}
          <div class="fs"><span><b class="num">{fmtNum(flowInfo.prod)}</b>/min erzeugt · {flowInfo.np} Maschinen</span>
            <span><b class="num">{fmtNum(flowInfo.cons)}</b>/min verbraucht · {flowInfo.nc}</span>
            <span>{flowInfo.ns} Stationen · {flowInfo.paths.length} Bänder/Rohre</span></div>
          {#if !flowInfo.paths.length}<p class="muted">Im letzten Save lag diese Ware auf keinem Band.</p>{/if}
          <button class="lk" onclick={flowFit}>Auf alle Stellen zoomen</button>
        {/if}
      </div>
    {/if}
    {#if follow && !kiosk}
      <div class="following" class:paused={followState !== 'aktiv'}>
        {#if followState === 'aktiv'}Karte folgt {follow.split(':').slice(1).join(':')}
        {:else}{follow.split(':').slice(1).join(':')} ist offline — Folgen startet automatisch beim nächsten Login{/if}
        <button onclick={() => (follow = '')}>beenden</button></div>
    {/if}
  </section>
</div>

{#if editPin}
  <PinEditor pin={editPin} onclose={(saved: boolean) => { editPin = null; if (saved) loadPins(); }} />
{/if}

<style>
  .wrap { display: flex; height: 100%; position: relative; }
  .map { flex: 1; position: relative; overflow: hidden; background: #16171a; touch-action: none; }
  canvas { position: absolute; inset: 0; display: block; cursor: grab; }
  .tip { position: absolute; pointer-events: none; background: var(--plate); border: 1px solid var(--seam); padding: 6px 9px; font-size: 12.5px;
         display: flex; flex-direction: column; max-width: 300px; z-index: 5; }
  .tip span { color: var(--dim); }
  .ctl { position: absolute; top: 12px; left: 12px; display: flex; flex-direction: column; gap: 6px; z-index: 10; align-items: flex-start; }
  .grp { display: flex; flex-direction: column; }
  .cb { background: var(--plate); border: 1px solid var(--seam); color: var(--text); min-width: 36px; height: 36px; font-size: 18px;
        display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 0 10px; }
  .cb.wide { font-family: var(--cond); font-weight: 600; font-size: 15px; justify-content: flex-start; }
  .cb .i { width: 16px; text-align: center; font-size: 15px; }
  .cb:hover { border-color: var(--dim); }
  .cb.on { border-color: var(--ficsit); color: var(--ficsit); }
  .grp .cb + .cb { border-top: none; }
  .m-only { display: none; }
  .layers { position: absolute; left: calc(100% + 8px); top: 90px; padding: 10px 14px; display: flex; flex-direction: column; gap: 3px; width: 230px;
            box-shadow: 0 8px 24px #0007; }
  .layers label { display: flex; gap: 8px; align-items: center; font-size: 13.5px; cursor: pointer; }
  .layers input { accent-color: var(--ficsit); }
  .layers .cnt { margin-left: auto; color: var(--dim); font-size: 12px; font-variant-numeric: tabular-nums; }
  .lg { margin-top: 6px; background: none; border: none; color: var(--ficsit); text-align: left; padding: 0; font-size: 13px; }
  .drawbar { position: absolute; left: calc(100% + 8px); top: 130px; padding: 12px; width: 240px; box-shadow: 0 8px 24px #0007; }
  .drawbar p { font-size: 13px; color: var(--text2); margin: 8px 0; }
  .drawbar .btn { margin-right: 6px; }
  .seg { display: flex; }
  .seg button { flex: 1; background: var(--steel); border: 1px solid var(--seam); padding: 5px; font-size: 13px; color: var(--text2); }
  .seg button.on { border-color: var(--ficsit); color: var(--ficsit); }
  .legend { position: absolute; left: 12px; bottom: 44px; padding: 10px 14px; font-size: 12.5px; display: flex; flex-direction: column; gap: 4px; z-index: 9; }
  .legend .dot { margin: 0 3px 0 6px; }
  .sq { display: inline-block; width: 10px; height: 10px; background: #c3bfb7; border-radius: 2px; vertical-align: -1px; }
  .sq.sm { width: 8px; height: 8px; margin-left: 6px; }
  .dia { display: inline-block; width: 8px; height: 8px; background: var(--ficsit); transform: rotate(45deg); margin: 0 3px; }
  .scale { position: absolute; left: 12px; bottom: 12px; font-size: 12px; color: var(--text2); display: flex; align-items: center; gap: 8px;
           text-shadow: 0 1px 2px #000; pointer-events: none; }
  .scale span { height: 6px; border: 2px solid var(--text2); border-top: none; }
  .detail { position: absolute; top: 12px; right: 12px; bottom: 12px; width: 360px; overflow: auto; z-index: 15; box-shadow: 0 10px 30px #0008; height: fit-content; max-height: calc(100% - 24px); }
  .close { position: absolute; top: 10px; right: 14px; background: none; border: none; color: var(--dim); font-size: 16px; z-index: 1; }
  .flowbar { position: absolute; top: 12px; left: 50%; transform: translateX(-50%); width: min(460px, calc(100% - 120px)); padding: 10px 12px; z-index: 14;
             box-shadow: 0 8px 24px #0007; display: flex; flex-direction: column; gap: 6px; }
  .flowbar .fr { display: flex; gap: 6px; align-items: center; }
  .flowbar .x { background: none; border: none; color: var(--dim); font-size: 15px; }
  .flowbar .fs { display: flex; flex-wrap: wrap; gap: 2px 14px; font-size: 12.5px; color: var(--text2); }
  .flowbar p { margin: 0; font-size: 12.5px; }
  .flowbar .lk { background: none; border: none; color: var(--ficsit); padding: 0; text-align: left; font-size: 12.5px; }
  .flowbar.meas { top: auto; bottom: 40px; }
  .meas .x { background: none; border: none; color: var(--dim); margin-left: auto; }
  .meas .zh { display: flex; align-items: center; gap: 10px; }
  .flowbar.pick { flex-direction: row; justify-content: space-between; align-items: center; border-left: 3px solid var(--ficsit); }
  .following { position: absolute; top: 12px; left: 50%; transform: translateX(-50%); background: var(--ficsit); color: #1b1c1e; padding: 5px 12px;
               font-family: var(--cond); font-weight: 600; font-size: 15px; z-index: 12; }
  .following.paused { background: var(--plate2); color: var(--text2); border: 1px solid var(--seam); font-family: var(--body); font-weight: 400; font-size: 13px; }
  .following button { background: none; border: none; text-decoration: underline; color: inherit; font: inherit; }
  .backdrop { display: none; }
  .kiosk .map { background: #16171a; }
  @media (max-width: 760px) {
    .backdrop { display: block; position: absolute; inset: 0; background: #0007; border: none; z-index: 19; }
    .m-only { display: inline-flex; }
    .cb.wide .t { display: none; }
    .cb.wide { justify-content: center; padding: 0; width: 40px; }
    .cb { height: 40px; min-width: 40px; }
    .layers, .drawbar { left: 48px; top: 0; }
    .flowbar { left: 56px; right: 8px; width: auto; transform: none; top: 8px; }
    .flowbar.meas { bottom: 12px; top: auto; }
    .detail { top: auto; left: 0; right: 0; bottom: 0; width: auto; max-height: 55%; height: auto; }
    .legend { bottom: 40px; right: 12px; }
  }

</style>
