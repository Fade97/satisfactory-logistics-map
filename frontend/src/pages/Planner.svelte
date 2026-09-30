<script lang="ts">
  // Produktionsrechner: Ziele → LP im Backend → Flussdiagramm, Bauliste, freie Knoten, als Notiz speichern.
  import { onMount } from 'svelte';
  import { nodes, factory, status } from '../lib/api';
  import { route, toMap } from '../lib/router';
  import { fmtNum, fmtMW } from '../lib/fmt';
  import PinEditor from '../lib/PinEditor.svelte';
  import ItemPicker from '../lib/ItemPicker.svelte';
  import { layout, edgePath, W, H, LABEL_CHARS, type FNode, type FEdge } from '../lib/flowlayout';
  import { tn } from '../lib/names';

  interface Step { recipe: string; cls: string; alt: boolean; building: string; machines: number; full: number; clock: number | null; power: number;
    out: { item: string; rate: number }[]; inp: { item: string; rate: number }[] }
  let recipes = $state<{ key: string; item: string; fluid: boolean; recipes: { cls: string; name: string; alt: boolean }[] }[]>([]);
  let targets = $state<{ item: string; rate: number }[]>([{ item: '', rate: 10 }]);
  let exclude = $state<string[]>([]);
  const SAVED = JSON.parse(localStorage.getItem('fgmap.planner') || '{}');
  let useSurplus = $state(SAVED.useSurplus ?? true);
  let goal = $state<'raw' | 'machines' | 'power'>(SAVED.goal || 'raw');
  let maxClock = $state<number>(SAVED.maxClock || 100);
  let sloop = $state<boolean>(!!SAVED.sloop);
  let allow = $state<Record<string, string[]>>(SAVED.allow || {});      // Ware → erlaubte Rezeptklassen
  let recipeFor = $state<string | null>(null);                          // offene Rezeptwahl
  let res = $state<any>(null), busy = $state(false), err = $state('');
  let site = $state<{ x: number; y: number } | null>(JSON.parse(localStorage.getItem('fgmap.site') || 'null'));
  $effect(() => localStorage.setItem('fgmap.planner', JSON.stringify({ useSurplus, goal, maxClock, sloop, allow })));
  let savePin = $state<any>(null);

  onMount(async () => {
    recipes = await (await fetch('/api/recipes')).json();
    const q = $route.q;
    const last = JSON.parse(localStorage.getItem('fgmap.plannerTargets') || 'null');
    if (q.get('item')) { targets = [{ item: q.get('item')!, rate: +(q.get('rate') || 10) }]; run(); }
    else if (last?.length) { targets = last; run(); }                 // zurück von der Karte: letzten Plan wieder zeigen
  });

  async function run() {
    const t = targets.filter(t => t.item && t.rate > 0);
    if (!t.length) { err = 'Wähle eine Ware aus der Liste und eine Menge.'; return; }
    const bad = t.find(x => !opts.includes(x.item));
    if (bad) { err = '„' + bad.item + '“ ist keine herstellbare Ware. Wähle einen Eintrag aus der Liste.'; return; }
    busy = true; err = '';
    try {
      const r = await (await fetch('/api/plan', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ targets: t, exclude, use_surplus: useSurplus, goal, max_clock: maxClock / 100, sloop, allow }) })).json();
      localStorage.setItem('fgmap.plannerTargets', JSON.stringify(t));
      if (!r.ok) { err = r.error; res = null; } else res = r;
    } catch (e: any) { err = 'Der Rechner antwortet nicht: ' + e.message; } finally { busy = false; }
  }

  // --- Flussdiagramm (Layout in lib/flowlayout.ts) + Hervorhebung der Kette unter dem Mauszeiger
  const graph = $derived(res ? layout(res, fmtNum) : null);
  let hover = $state<FNode | null>(null);
  let view = $state<'diagramm' | 'baum'>('diagramm');
  // Alles, was vom überfahrenen Knoten abhängt oder ihn beliefert
  const lit = $derived.by(() => {
    if (!hover || !graph) return null;
    const on = new Set<FNode>([hover]), le = new Set<FEdge>();
    const walk = (n: FNode, dir: 'ins' | 'outs') => {
      for (const e of graph[dir].get(n) || []) {
        if (le.has(e)) continue;
        le.add(e);
        const o = dir === 'ins' ? e.a : e.b;
        on.add(o); walk(o, dir);
      }
    };
    walk(hover, 'ins'); walk(hover, 'outs');
    return { on, le };
  });
  const EDGE_COL = { raw: '#b07a2a', sur: '#3f8a63', mid: '#8a857c' };

  // --- Baumansicht: vom Ziel rückwärts, jede Ware eingerückt mit Menge und Maschine
  const tree = $derived.by(() => {
    if (!graph) return [];
    const rows: { depth: number; label: string; sub: string; rate: number; kind: string; again: boolean }[] = [];
    const seen = new Set<FNode>();
    const rec = (n: FNode, depth: number, rate: number, item: string) => {
      const again = seen.has(n);
      rows.push({ depth, label: item, sub: n.kind === 'step' ? (n.label !== item ? n.label + ' · ' : '') + n.sub : n.kind === 'raw' ? 'Rohstoff' : 'aus Überschuss', rate, kind: n.kind, again });
      if (again || n.kind !== 'step') return;
      seen.add(n);
      for (const e of graph.ins.get(n) || []) rec(e.a, depth + 1, e.rate, e.item);
    };
    for (const t of graph.nodes.filter(n => n.kind === 'target')) {
      if (t.data) {                                   // Zielschritt: selbst als Wurzel
        seen.add(t);
        rows.push({ depth: 0, label: t.label, sub: t.sub, rate: t.data.out[0]?.rate ?? 0, kind: 'target', again: false });
        for (const e of graph.ins.get(t) || []) rec(e.a, 1, e.rate, e.item);
      } else for (const e of graph.ins.get(t) || []) rec(e.a, 0, e.rate, e.item);
    }
    return rows;
  });

  // --- Freie Knoten zum Bauplatz
  const nodeHints = $derived.by(() => {
    if (!res || !$nodes) return [];
    const P: Record<string, number> = { pure: 3, normal: 2, impure: 1 };
    return res.raw.filter((r: any) => r.item !== 'Water').map((r: any) => {
      const free = $nodes!.filter(n => !n.used && n.item === r.item);
      const ref = site || centerOfFactory();
      const withD = free.map(n => ({ n, d: ref ? Math.hypot(n.pos[0] - ref.x, n.pos[1] - ref.y) : 0 }))
        .sort((a, b) => (P[b.n.purity || ''] || 0) - (P[a.n.purity || ''] || 0) || a.d - b.d);
      return { item: r.item, rate: r.rate, list: withD.slice(0, 4) };
    });
  });
  function centerOfFactory() {
    const f = $factory?.factories?.[0];
    return f ? { x: f.center[0], y: f.center[1] } : null;
  }
  const PUR: Record<string, string> = { pure: 'rein', normal: 'normal', impure: 'unrein' };

  let bpErr = $state('');
  async function blueprint(s: Step) {
    bpErr = '';
    const r = await fetch('/api/blueprint', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cls: s.cls, building: s.building, machines: s.machines, full_clock: (s as any).full_clock || 100, clock: s.clock }) });
    if (!r.ok) { bpErr = (await r.json().catch(() => ({}))).error || 'Blueprint fehlgeschlagen'; return; }
    const blob = await r.blob(), a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = decodeURIComponent((r.headers.get('Content-Disposition') || '').split("''")[1] || 'blueprint.zip');
    a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  }

  function toPin() {
    const t = res.targets.map((t: any) => fmtNum(t.rate) + '/min ' + t.item).join(', ');
    const lines = res.steps.map((s: Step) => `${fmtNum(s.machines)}× ${s.building}: ${s.recipe}`);
    const at = site || centerOfFactory() || { x: 0, y: 0 };
    savePin = { author: '', cat: 'geplant', color: '#f59a23', shape: 'point', geom: [[Math.round(at.x), Math.round(at.y)]],
      text: `Plan: ${t}\n${lines.join('\n')}\nRohstoffe: ${res.raw.map((r: any) => fmtNum(r.rate) + ' ' + r.item).join(', ')} · Strom ${fmtMW(res.power)}`.slice(0, 500) };
  }
  const opts = $derived(recipes.map(r => r.item));
  const altFor = (item: string) => recipes.find(r => r.item === item)?.recipes || [];
</script>

<div class="page">
  <h1>Rechner</h1>
  <p class="src">Nur Rezepte, die auf dem Server freigeschaltet sind. Bei „wenig Rohstoffe“ zählen seltene Rohstoffe stärker.</p>

  <div class="panel card form">
    {#each targets as t, i}
      <div class="row">
        <ItemPicker bind:value={t.item} items={opts} placeholder="Ware, z. B. Stahlträger oder Steel Beam" />
        <span class="rw"><input class="field rate" type="number" min="0.1" step="any" bind:value={t.rate} aria-label="Menge pro Minute" /><span class="muted">/min</span></span>
        {#if targets.length > 1}<button class="x" onclick={() => (targets = targets.filter((_, j) => j !== i))} aria-label="Ziel entfernen">✕</button>{/if}
      </div>
    {/each}
    <div class="row">
      {#if targets.length < 8}<button class="btn" onclick={() => (targets = [...targets, { item: '', rate: 10 }])}>Weiteres Ziel</button>{/if}
      <label class="tg"><input type="checkbox" bind:checked={useSurplus} /> Überschüsse der Fabrik nutzen</label>
    </div>
    <div class="row opts">
      <span class="ol">Optimieren auf</span>
      <div class="seg">{#each [['raw', 'wenig Rohstoffe'], ['machines', 'wenig Maschinen'], ['power', 'wenig Strom']] as [k, l]}
        <button class:on={goal === k} onclick={() => { goal = k as any; if (res) run(); }}>{l}</button>{/each}</div>
      <label class="tg" title="Mit Power Shards bis 250 %: weniger Maschinen, aber überproportional mehr Strom">Takt bis
        <select class="field sel" bind:value={maxClock} onchange={() => res && run()}>
          {#each [100, 150, 200, 250] as c}<option value={c}>{c} %{c > 100 ? ' (' + Math.ceil((c - 100) / 50) + ' Shards)' : ''}</option>{/each}
        </select></label>
      <label class="tg" title="Somersloop in jeder Maschine: doppelte Ausgabe, vierfacher Strom"><input type="checkbox" bind:checked={sloop} onchange={() => res && run()} /> Somersloops</label>
      <span style="flex:1"></span>
      <span style="flex:1"></span>
      <button class="btn primary" onclick={run} disabled={busy}>{busy ? 'Rechnet …' : 'Berechnen'}</button>
    </div>
    {#if err}<p class="err">{err}</p>{/if}
  </div>

  {#if res}
    {#if !res.steps.length && res.surplus_used.length}
      <div class="panel card note">Kein Neubau nötig: Die Fabrik erzeugt davon schon genug Überschuss
        ({res.surplus_used.map((u: any) => fmtNum(u.available) + '/min ' + u.item).join(', ')}). Ohne Häkchen bei „Überschüsse nutzen“ rechnet der Rechner eine eigene Anlage.</div>
    {/if}
    <div class="kpis">
      <div class="kpi panel"><div class="v num">{res.machines}</div><div class="l">Maschinen</div></div>
      <div class="kpi panel"><div class="v num">{fmtMW(res.power)}</div><div class="l">Strom</div></div>
      {#if res.shards}<div class="kpi panel"><div class="v num">{res.shards}</div><div class="l">Power Shards (höchstens)</div></div>{/if}
      {#if res.sloops}<div class="kpi panel"><div class="v num">{res.sloops}</div><div class="l">Somersloops</div></div>{/if}
      {#each res.raw as r}<div class="kpi panel"><div class="v num">{fmtNum(r.rate)}</div><div class="l">{$tn(r.item)} /min</div></div>{/each}
    </div>

    <div class="panel card chain">
      <div class="gh"><h2>Produktionskette</h2>
        <div class="seg">{#each [['diagramm', 'Diagramm'], ['baum', 'Baum']] as [k, l]}<button class:on={view === k} onclick={() => (view = k as any)}>{l}</button>{/each}</div>
      </div>
      {#if graph && view === 'diagramm'}
        <div class="flow">
          <svg width={graph.width + 4} height={graph.height + 4} class:dim={!!lit} role="img" aria-label="Produktionskette">
            {#each graph.edges as e (e.id)}
              <path d={edgePath(e)} class="edge" class:on={lit?.le.has(e)} stroke={EDGE_COL[e.kind]} stroke-width={e.w}><title>{$tn(e.item)}: {fmtNum(e.rate)}/min</title></path>
            {/each}
            {#each graph.edges as e (e.id + 'l')}
              <!-- Beschriftung am Ende der Kante, auf den Spaltenabstand gekürzt (sonst ragt sie in den Kasten davor) -->
              {@const t = fmtNum(e.rate) + ' ' + $tn(e.item)}
              {#if e.label || lit?.le.has(e)}
              <text x={e.b.x - 6} y={e.y2 - 4} class="el" class:on={lit?.le.has(e)} text-anchor="end">{t.length > LABEL_CHARS ? t.slice(0, LABEL_CHARS - 1) + '…' : t}<title>{$tn(e.item)}: {fmtNum(e.rate)}/min</title></text>
              {/if}
            {/each}
            {#each graph.nodes as n (n.id)}
              <g transform="translate({n.x},{n.y})" class="node {n.kind}" class:on={lit?.on.has(n)} role="presentation"
                 onmouseenter={() => (hover = n)} onmouseleave={() => (hover = null)}>
                <rect width={W} height={H} />
                <text x="10" y="22" class="t1">{$tn(n.label).length > 27 ? $tn(n.label).slice(0, 26) + '…' : $tn(n.label)}</text>
                <text x="10" y="42" class="t2">{n.data ? n.sub.replace(n.data.building, $tn(n.data.building)) : n.sub}</text>
              </g>
            {/each}
          </svg>
        </div>
        <p class="muted small">Linienstärke = Menge. Orange Linien kommen von Rohstoffknoten, grüne aus Überschüssen der Fabrik.
          Maus auf einen Kasten hebt seine Zulieferer und Abnehmer hervor.</p>
      {:else if graph}
        <ol class="tree">
          {#each tree as r}
            <li style="padding-left:{r.depth * 22}px" class={r.kind} class:again={r.again}>
              <span class="rt num">{fmtNum(r.rate)}/min</span><b>{$tn(r.label)}</b><span class="muted">{r.again ? 'siehe oben' : $tn(r.sub)}</span>
            </li>
          {/each}
        </ol>
      {/if}
    </div>

    <div class="grid2" style="margin-top:16px">
      <div class="panel card">
        <h2>Bauliste</h2>
        <table class="t">
          <thead><tr><th>Maschinen</th><th>Rezept</th><th class="n">Strom</th></tr></thead>
          <tbody>
            {#each res.steps as s}
              <tr><td>{s.full ? s.full + '×' + (s.full_clock !== 100 ? ' auf ' + s.full_clock + ' %' : '') + ' ' : ''}{s.clock ? (s.full ? '+ 1× ' : '1× ') + 'auf ' + s.clock + ' %' : ''}<div class="muted small">{$tn(s.building)}</div></td>
                <td>{$tn(s.recipe)}{#if s.alt} <span class="tag">alternativ</span>{/if}
                  <div class="muted small">{s.out.map(o => fmtNum(o.rate) + ' ' + $tn(o.item)).join(', ')}</div>
                  {#if altFor(s.out[0].item).length > 1}
                    <button class="lk" onclick={() => (recipeFor = recipeFor === s.out[0].item ? null : s.out[0].item)}>
                      Rezepte wählen ({(allow[s.out[0].item] || altFor(s.out[0].item).map(r => r.cls)).length} von {altFor(s.out[0].item).length} erlaubt)</button>
                    {#if recipeFor === s.out[0].item}
                      {@const it = s.out[0].item}
                      <div class="rpick">
                        {#each altFor(it) as r}
                          <label><input type="checkbox" checked={(allow[it] || altFor(it).map(x => x.cls)).includes(r.cls)}
                            onchange={e => {
                              const cur = new Set(allow[it] || altFor(it).map(x => x.cls));
                              (e.target as HTMLInputElement).checked ? cur.add(r.cls) : cur.delete(r.cls);
                              if (!cur.size) { (e.target as HTMLInputElement).checked = true; return; }   // mindestens eins
                              allow = { ...allow, [it]: [...cur] }; if (cur.size === altFor(it).length) { const a = { ...allow }; delete a[it]; allow = a; }
                              run();
                            }} /> {$tn(r.name)}{r.alt ? ' (alt.)' : ''}{r.cls === s.cls ? ' · verwendet' : ''}</label>
                        {/each}
                      </div>
                    {/if}
                  {/if}</td>
                <td class="n">{fmtMW(s.power)}
                  {#if s.bp}<div><button class="lk inl" onclick={() => blueprint(s)} title="Experimentell: auf Basis der mitgelieferten Blueprint-Vorlagen, im Spiel noch nicht geprüft">Blueprint ⤓</button></div>{/if}</td></tr>
            {/each}
          </tbody>
        </table>
        {#if bpErr}<p class="err small">{bpErr}</p>{/if}
        {#if res.steps.some((x: any) => x.bp)}<p class="muted small"><b>Blueprint ⤓</b> ist experimentell: Es baut auf den mitgelieferten Vorlagen „8x Constructor T5“ und „10x Smelter T5“ auf, setzt Rezept und Takt und lässt überzählige Maschinen weg. Im Spiel noch nicht geprüft — ZIP entpacken und nach <code>SaveGames/blueprints/{$status?.save?.session || "<Session>"}/</code> legen (Server) bzw. lokal testen.</p>{/if}
        {#if Object.keys(allow).length}<p class="small">Eingeschränkt: {Object.keys(allow).join(', ')} <button class="lk inl" onclick={() => { allow = {}; run(); }}>alle Rezepte wieder erlauben</button></p>{/if}
        {#if res.byproducts.length}<p class="small muted">Nebenprodukte: {res.byproducts.map((b: any) => fmtNum(b.rate) + ' ' + b.item).join(', ')}</p>{/if}
        {#if res.surplus_used.length}<p class="small muted">Aus Überschuss der Fabrik: {res.surplus_used.map((b: any) => fmtNum(b.rate) + ' von ' + fmtNum(b.available) + ' ' + b.item).join(', ')}</p>{/if}
      </div>

      <div class="panel card">
        <h2>Freie Knoten</h2>
        <p class="muted small">{site ? 'Sortiert nach Reinheit und Entfernung zum gewählten Bauplatz.' : 'Sortiert nach Reinheit und Entfernung zur größten Fabrik.'}
          Bauplatz: <a class="lk inl" href="#/karte?pick=bauplatz{site ? '&x=' + site.x + '&y=' + site.y + '&z=1.2' : ''}">{site ? site.x + ' / ' + site.y + ' m — auf der Karte ändern' : 'auf der Karte wählen'}</a>
          {#if site}<button class="lk inl" onclick={() => { site = null; localStorage.removeItem('fgmap.site'); }}>zurücksetzen</button>{/if}</p>
        {#each nodeHints as h}
          <h3>{$tn(h.item)} · {fmtNum(h.rate)}/min</h3>
          {#each h.list as { n, d }}
            <button class="lk" onclick={() => toMap('node:' + n.id, n.pos[0], n.pos[1])}>{PUR[n.purity || ''] || '?'} · {Math.round(d)} m entfernt · {n.pos[0]} / {n.pos[1]}</button>
          {:else}<p class="muted small">Kein freier Knoten dieser Art.</p>{/each}
        {/each}
        <button class="btn" onclick={toPin} style="margin-top:12px">Plan als Notiz auf die Karte</button>
      </div>
    </div>
  {/if}
</div>

{#if savePin}<PinEditor pin={savePin} onclose={() => (savePin = null)} />{/if}

<style>
  .form { display: flex; flex-direction: column; gap: 10px; margin-bottom: 14px; }
  .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .item { flex: 1; min-width: 220px; }
  .rate { width: 110px; }
  .rw { display: inline-flex; gap: 6px; align-items: center; }
  .x { background: none; border: none; color: var(--dim); }
  .tg { display: flex; gap: 8px; align-items: center; font-size: 13px; color: var(--text2); }
  .tg input { accent-color: var(--ficsit); }
  .err { color: var(--bad); margin: 0; }
  .note { border-left: 3px solid var(--ok); margin-bottom: 14px; }
  .page > .chain { max-width: none; }
  .gh { display: flex; align-items: center; gap: 16px; margin-bottom: 10px; }
  .gh h2 { margin: 0; }
  .gh .seg { display: inline-flex; }
  .gh .seg button { background: var(--steel); border: 1px solid var(--seam); padding: 3px 12px; font-size: 13px; color: var(--text2); margin-right: -1px; }
  .gh .seg button.on { color: #1b1c1e; background: var(--ficsit); border-color: var(--ficsit); }
  .flow { overflow: auto; max-height: 75vh; padding: 2px; }
  .edge { fill: none; opacity: .75; transition: opacity .12s; }
  .el { fill: var(--dim); font-size: 11px; paint-order: stroke; stroke: var(--plate); stroke-width: 3px; }
  svg.dim .edge:not(.on) { opacity: .08; }
  svg.dim .el:not(.on) { opacity: 0; }
  svg.dim .node:not(.on) { opacity: .3; }
  .edge.on { opacity: 1; }
  .el.on { fill: var(--text); }
  .node { cursor: default; transition: opacity .12s; }
  .node rect { fill: var(--plate2); stroke: var(--seam); }
  .node.raw rect { fill: #2a2620; stroke: var(--ficsit-dim); }
  .node.sur rect { fill: #1f2a24; stroke: #2b5a44; }
  .node.target rect { fill: var(--ficsit); stroke: var(--ficsit); }
  .node.target .t1, .node.target .t2 { fill: #1b1c1e; }
  .node .t1 { fill: var(--text); font-size: 13px; font-weight: 500; }
  .node .t2 { fill: var(--dim); font-size: 12px; }
  .tree { list-style: none; margin: 0; padding: 0; font-size: 13px; }
  .tree li { display: flex; gap: 10px; align-items: baseline; padding: 4px 0; border-bottom: 1px solid #2c2e31; }
  .tree .rt { min-width: 76px; text-align: right; color: var(--text2); }
  .tree li.raw b { color: #d9a24a; }
  .tree li.sur b { color: #6cc49a; }
  .tree li.again { opacity: .6; }
  .opts { gap: 10px 14px; }
  .ol { font-size: 13px; color: var(--text2); }
  .opts .seg { display: inline-flex; }
  .opts .seg button { background: var(--steel); border: 1px solid var(--seam); padding: 4px 10px; font-size: 13px; color: var(--text2); margin-right: -1px; }
  .opts .seg button.on { color: #1b1c1e; background: var(--ficsit); border-color: var(--ficsit); }
  .sel { width: auto; padding: 3px 6px; }
  .rpick { display: flex; flex-direction: column; gap: 2px; padding: 6px 0 4px 2px; font-size: 12.5px; }
  .rpick input { accent-color: var(--ficsit); }
  .lk.inl { display: inline; }
  .lk { background: none; border: none; color: var(--ficsit); padding: 2px 0; font-size: 12.5px; text-align: left; display: block; }
  .small { font-size: 12px; }
  h3 { font-size: 14px; margin: 10px 0 2px; color: var(--text2); }
</style>
