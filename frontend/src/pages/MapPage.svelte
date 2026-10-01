<script lang="ts">
  import { onMount, onDestroy, untrack } from 'svelte';
  import { MediaQuery } from 'svelte/reactivity';
  import { MapView, glideFrom, GLIDE_MS, type MapObj, type FactoryBox } from '../lib/mapview';
  import { live, stations, factory, geo, nodes, powerlines, pins, trails, loadPins, flow, collectibles, loadDetail } from '../lib/api';
  import { route, replaceQuery } from '../lib/router';
  import { LAYERS, stationsObjs, liveObjs, factoryObjs, nodeObjs, pinObjs, applyGeo, collectibleObjs, factoryBoxes, stationVisible,
           type StationFilter } from '../lib/scene';
  import { C, MOBILE_QUERY, factoryStatusColor } from '../lib/fmt';
  import { KEYS, loadJson, saveJson } from '../lib/storage';
  import type { Factory, Frame, Stations } from '../lib/types';
  import Detail from '../lib/Detail.svelte';
  import PinEditor from '../lib/PinEditor.svelte';
  import StationList from '../lib/map/StationList.svelte';
  import HeightPanel from '../lib/map/HeightPanel.svelte';
  import TimeTravel from '../lib/map/TimeTravel.svelte';
  import LayerMenu from '../lib/map/LayerMenu.svelte';
  import Legend from '../lib/map/Legend.svelte';
  import DrawBar from '../lib/map/DrawBar.svelte';
  import MeasurePanel from '../lib/map/MeasurePanel.svelte';
  import FlowPanel from '../lib/map/FlowPanel.svelte';
  import MapBar from '../lib/map/MapBar.svelte';
  import { heatOverlay, measureOverlay, trailsOverlay, pinsOverlay } from '../lib/map/overlays';
  import { computeFlow, flowItemList } from '../lib/map/flow';
  import { tipTitle, tipText } from '../lib/map/tooltip';
  import { attachGestures, type Pt } from '../lib/map/gestures';
  import { minPoints, type Draft } from '../lib/map/draw';
  import { matches } from '../lib/fuzzy';
  import { prefs, rememberView } from '../lib/prefs';
  import { tn, both } from '../lib/names';
  import { t, locale } from '../lib/i18n';

  let { kiosk = false, followKey = '' }: { kiosk?: boolean; followKey?: string } = $props();

  const DETAIL_W = 380;          // desktop: the detail card covers this much of the right edge
  const SHEET_H = 280;           // phone: follow mode keeps the target above the bottom sheet

  let cv: HTMLCanvasElement;
  let view: MapView | null = null;
  let stationList = $state<StationList>();       // absent in kiosk mode
  let sel = $state<MapObj | null>(null);
  // followKey (kiosk) is only the initial target; afterwards the user decides
  let follow = $state<string>(untrack(() => followKey) || ($prefs.followMe && $prefs.me ? 'player:' + $prefs.me : ''));
  let q = $state('');
  let filters = $state<StationFilter>({ truck: true, train: true, load: true, unload: true });
  const savedLayers = loadJson<Record<string, boolean>>(KEYS.layers, {});
  let layers = $state<Record<string, boolean>>(Object.fromEntries(LAYERS.map(([k, , on]) => [k, savedLayers[k] ?? on])));
  let showLayers = $state(false), showList = $state(false), showLegend = $state(false);
  let tip = $state<{ x: number; y: number; o: MapObj } | null>(null);
  let draw = $state<Draft | null>(null);
  let editPin = $state<any>(null);
  let flowItem = $state<string>('');            // item flow: selected item, '' = off
  let showFlow = $state(false);
  // Height filter: floors derived from machine heights (clusters), range [from, to] in metres
  let showZ = $state(false);
  let zRange = $state<[number, number] | null>(null);
  // Time travel: the selected minute frame replaces the live objects until the bar is closed
  let showTT = $state(false);
  let ttFrame: Frame | null = null;
  // Measuring: points in world coordinates
  let measure = $state<number[][] | null>(null);
  // Pick mode: #/map?pick=site — one tap sets the planner's build site and jumps back
  let pickMode = $state<string | null>($route.q.get('pick'));
  let scaleTxt = $state(''), scaleW = $state(80);
  const mobile = new MediaQuery(MOBILE_QUERY);
  const isMobile = $derived(mobile.current);

  // Map objects per data source; rebuild() merges them in drawing order
  const objs = { stations: [] as MapObj[], live: [] as MapObj[], factory: [] as MapObj[], nodes: [] as MapObj[], pins: [] as MapObj[], collectibles: [] as MapObj[] };
  // Factory outlines: coloured by the live state, or by the time travel frame while one is shown
  let boxes: FactoryBox[] = [];
  function rebuild() {
    if (!view) return;
    view.objs = [...objs.collectibles, ...objs.factory, ...objs.nodes, ...objs.stations, ...objs.pins, ...objs.live];
    // move the current selection over to the new object
    if (sel) { const n = view.objs.find(o => o.key === sel!.key); if (n) { sel = n; view.sel = n; } }
    view.boxes = boxes;
    applyFilter(); view.invalidate();
  }

  // --- Data → objects. When switching back to the map the stores are already filled and the effects
  // run before onMount — the view doesn't exist yet then; ingestAll() catches up after setup.
  function ingestStations(s: Stations) { objs.stations = stationsObjs(s); applyGeo(view!, $geo, $powerlines, s); }
  function ingestFactory(f: Factory) { objs.factory = factoryObjs(f); if (!ttFrame) boxes = factoryBoxes(f.factories); }
  function ingestAll() {
    if (!view) return;
    if ($stations) ingestStations($stations);
    if ($factory) ingestFactory($factory);
    if ($nodes) objs.nodes = nodeObjs($nodes);
    if ($collectibles) objs.collectibles = collectibleObjs($collectibles);
    objs.pins = pinObjs($pins);
    if ($live) objs.live = liveObjs($live);
    applyGeo(view, $geo, $powerlines, $stations);
    rebuild();
  }
  $effect(() => { const s = $stations; if (s) untrack(() => { if (view) { ingestStations(s); rebuild(); } }); });
  $effect(() => { const f = $factory; if (f) untrack(() => { if (view) { ingestFactory(f); rebuild(); } }); });
  $effect(() => { const n = $nodes; if (n) untrack(() => { if (view) { objs.nodes = nodeObjs(n); rebuild(); } }); });
  $effect(() => { const c = $collectibles; if (c) untrack(() => { if (view) { objs.collectibles = collectibleObjs(c); rebuild(); } }); });
  $effect(() => { const p = $pins; untrack(() => { if (view) { objs.pins = pinObjs(p); rebuild(); } }); });
  $effect(() => { const g = $geo, pl = $powerlines; untrack(() => { if (view) { applyGeo(view, g, pl, $stations); view.invalidate(); } }); });
  $effect(() => {
    const lv = $live; if (!lv) return;
    untrack(() => {
      if (!view || ttFrame) return;
      const nw = liveObjs(lv);
      glideFrom(nw, objs.live);                     // glide smoothly to the new position
      objs.live = nw; rebuild();
    });
  });
  // Players who are not online are not followed (their character just stands around in the game).
  // The target is remembered: when the player comes online, following resumes by itself.
  const followState = $derived.by(() => {
    if (!follow) return 'off';
    if (!follow.startsWith('player:')) return 'active';
    const p = ($live?.players || []).find(x => 'player:' + x.name === follow);
    return !p ? 'gone' : p.online === true ? 'active' : 'offline';
  });
  $effect(() => {                      // Follow mode: MapView moves the camera along in the render loop (same interpolation as the dot)
    const f = followState === 'active' ? follow : '', s = sel, mob = isMobile;
    untrack(() => {
      if (!view) return;
      view.followKey = f || null;
      view.followOff = { x: !mob && s ? DETAIL_W : 0, y: mob && s ? SHEET_H : 0 };
      if (f) {                            // zoom in once when enabled, afterwards just track
        const o = view.objs.find(x => x.key === f);
        if (o && view.k < 1) { view.k = 1; view.invalidate(); }
        view.redraw();
      }
    });
  });
  $effect(() => { void $trails; untrack(() => view?.redraw()); });

  // --- Item flow: producers, consumers, stations, nodes and belts/pipes of one item
  const flowInfo = $derived(computeFlow(flowItem, $factory, $stations, $nodes, $flow));
  const flowItems = $derived(flowItemList($flow, $factory, locale()));
  $effect(() => {
    const fi = flowInfo;
    untrack(() => {
      if (!view) return;
      view.flowFocus = fi ? { keys: fi.keys, paths: fi.paths, color: C.light } : null;
      // make machine and node layers visible while item flow is active
      if (fi) { view.layers = { ...layers, machines: true, nodes: true, generators: true }; }
      else view.layers = { ...layers };
      view.invalidate(); writeHash();
    });
  });
  function flowFit() {
    if (!view || !flowInfo) return;
    const pts = [...view.objs.filter(o => flowInfo!.keys.has(o.key) && o.kind !== 'node').map(o => [o.x, o.y]), ...flowInfo.paths.flat()];
    if (!pts.length) return;
    const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
    view.fit(Math.min(...xs) - 100, Math.min(...ys) - 100, Math.max(...xs) + 100, Math.max(...ys) + 100);
  }
  function closeFlow() { flowItem = ''; showFlow = false; }

  // Collectibles: "62 of 106 left" in the layer menu
  const collectCount = $derived.by(() => {
    const c = $collectibles; if (!c) return {} as Record<string, string>;
    const o = c.open || {}, tot = c.total || {};
    return {
      c_somersloop: `${(tot.somersloop ?? 0) - (o.somersloop?.length ?? 0)} / ${tot.somersloop}`,
      c_mercer: `${(tot.mercer ?? 0) - (o.mercer?.length ?? 0)} / ${tot.mercer}`,
      c_slug: $t('{n} left', { n: (o.slug1?.length ?? 0) + (o.slug2?.length ?? 0) + (o.slug3?.length ?? 0) }),
      c_droppod: `${c.looted_pods} / ${tot.droppod}`,
    } as Record<string, string>;
  });

  $effect(() => { const r = zRange; untrack(() => { if (view) { view.zRange = r ? [r[0] - 3, r[1] + 3] : null; view.invalidate(); } }); });

  function setMeasure(m: number[][] | null) { measure = m; view?.redraw(); }

  // --- Time travel: frame → map objects (players/trains/trucks) + factory outline by the state at that time
  function applyFrame(_t: number | null, f: Frame | null) {
    ttFrame = f;
    if (!view) return;
    if (!f) {                                      // back to live
      if ($live) objs.live = liveObjs($live);
      boxes = factoryBoxes($factory?.factories || []);
      rebuild(); return;
    }
    const at = (x: number, y: number) => [x * 100, y * 100, 0];      // frame metres → live centimetres
    const players = f.p.map(([name, x, y, on]) => ({ name, pos: at(x, y), online: !!on }));
    const trains = f.tr.map(([name, x, y, speed, docked]) => ({ name, pos: at(x, y), speed, docked: !!docked, derailed: false }));
    const liveTk = new Map(($live?.trucks || []).map(v => [v.id || v.name, v]));
    const trucks = f.tk.map(([id, x, y, speed]) => ({ ...(liveTk.get(id) || { name: id, type: 'Truck' }), id, pos: at(x, y), speed }));
    const nw = liveObjs({ ...($live as any), players, trains, trucks, source: 'frm' });
    glideFrom(nw, objs.live, performance.now() - (GLIDE_MS - 800));   // frames: only the last 800 ms of the glide
    objs.live = nw;
    const st = new Map(f.f.map(x => [x[0], x]));
    boxes = factoryBoxes($factory?.factories || [], c => {
      const s = st.get(c.key);
      return s ? factoryStatusColor(s[2] / 100, s[1] / 100) : C.none;
    });
    rebuild();
  }

  // --- Filter (search, chips) → view.hidden
  function applyFilter() {
    if (!view) return;
    const qq = q.trim().toLowerCase();
    const h = new Set<string>();
    for (const o of view.objs) {
      if (o.kind === 'station') {
        const s = o.data;
        let vis = stationVisible(s, filters);
        if (vis && qq) vis = matches(qq, s.name, ...s.items.map((i: { item: string }) => both(i.item)));
        if (!vis) h.add(o.key);
      } else if (qq && o.kind !== 'player') {
        if (!matches(qq, o.label, o.data?.recipe, o.data?.item, ...(o.data?.out || []).map((x: { item: string }) => x.item))) h.add(o.key);
      }
    }
    view.hidden = h; view.invalidate();
  }
  $effect(() => { void q; void filters.truck; void filters.train; void filters.load; void filters.unload; untrack(applyFilter); });
  $effect(() => {
    const L = { ...layers };
    saveJson(KEYS.layers, L);
    untrack(() => { if (view) { view.layers = L; view.labels = L.labels !== false; view.invalidate(); } });
  });

  // --- Selection
  function select(o: MapObj | null, center = true) {
    sel = o; if (!view) return;
    view.sel = o; view.links = [];
    if (o && o.kind === 'station' && o.data.kind === 'truck') {
      const mine = new Set((o.data.vehicles || []).map((v: { id: string }) => v.id));
      view.links = objs.stations.filter(x => x !== o && x.data.kind === 'truck' && (x.data.vehicles || []).some((v: { id: string }) => mine.has(v.id))).map(x => [o, x]);
    } else if (o && o.kind === 'truck') {
      view.links = objs.stations.filter(x => x.data.kind === 'truck' && (x.data.vehicles || []).some((v: { id: string }) => v.id === o.data.id)).map(x => [o, x]);
    }
    if (o && center) view.focus(o.x, o.y, o.kind === 'machine' ? 3 : 1.2, isMobile ? Math.min(420, view.h * .5) : 0, !isMobile ? DETAIL_W : 0);
    view.redraw(); writeHash();
  }
  const pick = (key: string) => { const o = view?.objs.find(x => x.key === key); if (o) select(o); };

  // --- Address bar
  let hashT = 0;
  function writeHash() {
    if (kiosk || !view) return;
    clearTimeout(hashT);
    hashT = window.setTimeout(() => {
      if (!view) return;
      const c = view.center();
      rememberView(c.x, c.y, view.k);
      // Switched to another page meanwhile? Then don't bend the address back to the map.
      // location.hash instead of $route: the router only learns of the switch via the hashchange event, which would be too late
      if (!/^#\/(map|karte)(\?|$)/.test(location.hash)) return;
      replaceQuery('map', { x: String(Math.round(c.x)), y: String(Math.round(c.y)), z: view.k.toFixed(3), ...(sel ? { sel: sel.key } : {}),
        ...(flowItem ? { item: flowItem } : {}), ...(pickMode ? { pick: pickMode } : {}) });
    }, 300);
  }
  function fromRoute() {
    const r = $route;
    if (!view || r.page !== 'map') return;
    if (r.q.has('x')) {
      view.k = parseFloat(r.q.get('z') || '1');
      view.dx = view.w / 2 - view.k * +r.q.get('x')!; view.dy = view.h / 2 - view.k * +r.q.get('y')!; view.invalidate();
    }
    const s = r.q.get('sel');
    if (s) { const o = view.objs.find(x => x.key === s); if (o) select(o, !r.q.has('x')); }
    pickMode = r.q.get('pick');
    const w = r.q.get('item');
    if (w !== null && w !== flowItem) { flowItem = w; showFlow = true; if (!r.q.has('x')) setTimeout(flowFit, 300); }
  }
  let routeReady = false;
  $effect(() => { void $route; untrack(() => { if (routeReady) fromRoute(); }); });

  function fitFactory() {
    if (!view) return;
    const xs = objs.stations.map(o => o.x).concat(objs.factory.map(o => o.x)), ys = objs.stations.map(o => o.y).concat(objs.factory.map(o => o.y));
    if (!xs.length) return;
    const lo = (a: number[]) => a.slice().sort((p, q) => p - q)[Math.floor(a.length * .01)];
    const hi = (a: number[]) => a.slice().sort((p, q) => p - q)[Math.floor(a.length * .99)];
    view.fit(lo(xs) - 150, lo(ys) - 150, hi(xs) + 150, hi(ys) + 150);
  }
  function fitMap() { if (view && $stations) { const m = $stations.map; view.fit(m.west / 100, m.north / 100, m.east / 100, m.south / 100, .98); } }
  function setMapImage(s: Stations) {
    const m = s.map;
    view!.setImage('/map.jpg', { x: m.west / 100, y: m.north / 100, w: (m.east - m.west) / 100, h: (m.south - m.north) / 100 });
  }

  function scalebar() {
    if (!view) return;
    const want = 110 / view.k, steps = [5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000];
    const d = steps.find(s => s >= want) || 5000;
    scaleW = d * view.k; scaleTxt = d >= 1000 ? d / 1000 + ' km' : d + ' m';
  }

  // --- Pointer input: what hover and tap mean depends on the mode (measure, pick, draw, select)
  function onTap(p: Pt) {
    const v = view!;
    if (measure) {                                       // measuring: append point (snap to nearest object)
      const o = v.hit(p.x, p.y, 12);
      setMeasure([...measure, o ? [o.x, o.y] : [v.wx(p.x), v.wy(p.y)]]);
    } else if (pickMode) {                               // pick the build site for the planner
      saveJson(KEYS.site, { x: Math.round(v.wx(p.x)), y: Math.round(v.wy(p.y)) });
      pickMode = null; location.hash = '#/planner';
    } else if (draw) {                                   // drawing mode: place points
      draw.pts = [...draw.pts, [Math.round(v.wx(p.x)), Math.round(v.wy(p.y))]];
      if (draw.shape === 'point') finishDraw();
      v.redraw();
    } else return false;
    return true;
  }
  function onHover(p: Pt) {
    const v = view!;
    if (draw) return;
    const o = v.hit(p.x, p.y);
    if (o !== v.hover) { v.hover = o; v.redraw(); }
    tip = o ? { x: p.x, y: p.y, o } : null;
    cv.style.cursor = pickMode || measure ? 'crosshair' : o ? 'pointer' : 'grab';
  }

  let initT = 0, detachGestures = () => {};
  onMount(() => {
    const v = view = new MapView(cv);
    (window as any).__fgmap = v;          // for smoke tests (read camera/objects), otherwise unused
    v.layers = { ...layers };
    v.labels = layers.labels !== false;
    v.onchange = () => { scalebar(); writeHash(); };
    v.overlays.push(heatOverlay(() => $factory), measureOverlay(() => measure), trailsOverlay(() => $trails), pinsOverlay(() => $pins, () => draw));
    if ($stations) setMapImage($stations);
    detachGestures = attachGestures(cv, v, {
      hover: onHover,
      leave: () => { tip = null; if (v.hover) { v.hover = null; v.redraw(); } },
      pan: () => { if (follow) follow = ''; tip = null; },
      tap: onTap,
      select: (p, touch) => select(v.hit(p.x, p.y, touch ? 18 : 10), false),
      dblclick: () => { if (draw && draw.shape !== 'point') finishDraw(); },
    });

    // the detail layer (foundations/walls) is only drawn from zoom 0.8 — load it once in the background
    loadDetail().then(d => { if (d && view) { view.detail = d; view.invalidate(); } }).catch(() => {});
    const init = () => {
      if (!view) return;
      if (!$stations) { initT = window.setTimeout(init, 200); return; }
      ingestAll();
      if (!view.img) setMapImage($stations);
      if (!kiosk && ($route.q.has('x') || $route.q.has('item') || $route.q.has('sel') || $route.q.has('pick'))) { if (!$route.q.has('x')) fitFactory(); fromRoute(); }
      else if ($prefs.lastView && !kiosk) {           // own start view: continue where you left off
        const lv = $prefs.lastView; view.k = lv.z; view.dx = view.w / 2 - lv.z * lv.x; view.dy = view.h / 2 - lv.z * lv.y; view.invalidate();
      } else fitFactory();
      routeReady = true; scalebar();
    };
    init();
    addEventListener('keydown', key);
  });
  onDestroy(() => {
    clearTimeout(hashT); clearTimeout(initT); detachGestures();
    view?.destroy(); view = null;
    removeEventListener('keydown', key);
  });

  function key(e: KeyboardEvent) {
    if (kiosk || !view) return;
    const inField = (e.target as HTMLElement)?.matches?.('input, textarea');
    if (inField) { if (e.key === 'Escape') { q = ''; (e.target as HTMLElement).blur(); } return; }
    const r = { w: view.w / 2, h: view.h / 2 };
    if (e.key === '/') { e.preventDefault(); stationList?.focus(); }
    else if (e.key === 'Escape') { if (draw) draw = null; else if (q) q = ''; else select(null); }
    else if (e.key === '+' || e.key === '=') view.zoomAt(r.w, r.h, 1.4);
    else if (e.key === '-') view.zoomAt(r.w, r.h, 1 / 1.4);
    else if (e.key === 'f') fitFactory();
    else if (e.key === 'g') fitMap();
    else if (e.key === 'l') layers.labels = layers.labels === false;
    else if (e.key === 'm') layers.mapimg = !layers.mapimg;
    else if (e.key.startsWith('Arrow')) {
      const s = 80; view.pan(e.key === 'ArrowLeft' ? s : e.key === 'ArrowRight' ? -s : 0, e.key === 'ArrowUp' ? s : e.key === 'ArrowDown' ? -s : 0);
    }
  }

  // --- Drawing / pins
  function startDraw(shape: Draft['shape']) { draw = { shape, pts: [] }; select(null); }
  function finishDraw() {
    if (!draw) return;
    if (draw.pts.length >= minPoints(draw.shape)) editPin = { author: '', cat: 'planned', color: C.accent, text: '', shape: draw.shape, geom: draw.pts };
    draw = null; view?.redraw();
  }
  function editObj(o: MapObj) {
    if (o.kind === 'pin') editPin = { ...o.data };
    else if (o.kind === 'factory') editPin = { factory: o.data };
  }
  const followName = $derived(follow.split(':').slice(1).join(':'));
</script>

<div class="wrap" class:kiosk>
  {#if !kiosk}
  <StationList bind:this={stationList} bind:q bind:filters bind:open={showList} selKey={sel?.key || ''} onpick={pick} onfit={(a, b, c, d) => view?.fit(a, b, c, d)} />
  {#if showList}<button class="backdrop" aria-label={$t('Close list')} onclick={() => (showList = false)}></button>{/if}
  {/if}

  <section class="map">
    <canvas bind:this={cv} aria-label={$t('Factory map')}></canvas>
    {#if tip && !isMobile}
      <div class="tip" style="left:{tip.x + 14}px;top:{tip.y + 14}px"><b>{tipTitle(tip.o, $tn)}</b><span>{tipText(tip.o, $tn)}</span></div>
    {/if}

    {#if !kiosk}
    <div class="ctl">
      <button class="cb m-only" onclick={() => (showList = !showList)} aria-label={$t('Station list')}>☰</button>
      <div class="grp"><button class="cb" onclick={() => view?.zoomAt(view.w / 2, view.h / 2, 1.5)} aria-label={$t('Zoom in')}>+</button>
        <button class="cb" onclick={() => view?.zoomAt(view.w / 2, view.h / 2, 1 / 1.5)} aria-label={$t('Zoom out')}>−</button></div>
      <button class="cb wide" onclick={fitFactory} title={$t('Zoom to the factory area (f)')}><span class="i">⌂</span><span class="t">{$t('Factory')}</span></button>
      <button class="cb wide" onclick={fitMap} title={$t('Whole map (g)')}><span class="i">⤢</span><span class="t">{$t('Whole map')}</span></button>
      <button class="cb wide" class:on={showLayers} onclick={() => (showLayers = !showLayers)}><span class="i">◫</span><span class="t">{$t('Layers')}</span></button>
      <button class="cb wide" class:on={!!draw} onclick={() => (draw ? (draw = null) : startDraw('point'))} title={$t('Put a note on the map')}><span class="i">✎</span><span class="t">{$t('Note')}</span></button>
      <button class="cb wide" class:on={showZ || !!zRange} onclick={() => { showZ = !showZ; if (!showZ) zRange = null; }} title={$t('Filter by height/floor')}><span class="i">☰</span><span class="t">{$t('Height')}</span></button>
      <button class="cb wide" class:on={!!measure} onclick={() => { setMeasure(measure ? null : []); select(null); }} title={$t('Measure distance and area')}><span class="i">⟷</span><span class="t">{$t('Measure')}</span></button>
      <button class="cb wide" class:on={showTT} onclick={() => (showTT = !showTT)} title={$t('Play back the last few hours')}><span class="i">◷</span><span class="t">{$t('Time travel')}</span></button>
      <button class="cb wide" class:on={showFlow || !!flowItem} onclick={() => { showFlow = !showFlow; if (!showFlow) flowItem = ''; }} title={$t('Trace an item through the factory')}><span class="i">⇶</span><span class="t">{$t('Item flow')}</span></button>
      {#if showLayers}<LayerMenu bind:layers bind:showLegend counts={collectCount} />{/if}
      {#if draw}<DrawBar bind:draw onfinish={finishDraw} />{/if}
    </div>
    {#if showLegend}<Legend />{/if}
    <div class="scale"><span style="width:{scaleW}px"></span>{scaleTxt}</div>
    {/if}

    {#if sel && !kiosk}
      <div class="detail panel">
        <button class="close" onclick={() => select(null)} aria-label={$t('Close')}>✕</button>
        <Detail o={sel} onpick={pick} following={follow === sel.key}
          onfollow={['player', 'train', 'truck'].includes(sel.kind) ? () => (follow = follow === sel!.key ? '' : sel!.key) : undefined}
          onpin={editObj} />
      </div>
    {/if}
    {#if showTT && !kiosk}<TimeTravel onframe={applyFrame} onclose={() => (showTT = false)} />{/if}
    {#if showZ && !kiosk}<HeightPanel bind:zRange onclose={() => (showZ = false)} />{/if}
    {#if measure && !kiosk}<MeasurePanel pts={measure} onchange={setMeasure} />{/if}
    {#if pickMode && !kiosk}
      <MapBar variant="pick">{$t('Tap the spot where you want to build.')}
        <a class="lk" href="#/planner">{$t('Cancel')}</a></MapBar>
    {/if}
    {#if (showFlow || flowItem) && !kiosk}<FlowPanel bind:item={flowItem} items={flowItems} info={flowInfo} onfit={flowFit} onclose={closeFlow} />{/if}
    {#if follow && !kiosk}
      <div class="following" class:paused={followState !== 'active'}>
        {#if followState === 'active'}{$t('Follow {name}', { name: followName })}
        {:else}{$t('{name} is offline — following resumes automatically at their next login', { name: followName })}{/if}
        <button onclick={() => (follow = '')}>{$t('stop')}</button></div>
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
  .scale { position: absolute; left: 12px; bottom: 12px; font-size: 12px; color: var(--text2); display: flex; align-items: center; gap: 8px;
           text-shadow: 0 1px 2px #000; pointer-events: none; }
  .scale span { height: 6px; border: 2px solid var(--text2); border-top: none; }
  .detail { position: absolute; top: 12px; right: 12px; bottom: 12px; width: 360px; overflow: auto; z-index: 15; box-shadow: 0 10px 30px #0008; height: fit-content; max-height: calc(100% - 24px); }
  .close { position: absolute; top: 10px; right: 14px; background: none; border: none; color: var(--dim); font-size: 16px; z-index: 1; }
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
    .detail { top: auto; left: 0; right: 0; bottom: 0; width: auto; max-height: 55%; height: auto; }
  }
</style>
