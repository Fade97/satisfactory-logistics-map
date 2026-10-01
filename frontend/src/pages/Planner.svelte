<script lang="ts">
  // Production planner: targets → LP in the backend → flow diagram, build list, free nodes, save as note.
  import { onMount } from 'svelte';
  import { nodes, factory, status } from '../lib/api';
  import { route, toMap } from '../lib/router';
  import { fmtNum, fmtMW } from '../lib/fmt';
  import PinEditor from '../lib/PinEditor.svelte';
  import ItemPicker from '../lib/ItemPicker.svelte';
  import { layout, edgePath, W, H, LABEL_CHARS, type FNode, type FEdge } from '../lib/flowlayout';
  import { tn } from '../lib/names';
  import { t, tr, lxr } from '../lib/i18n';

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
  let allow = $state<Record<string, string[]>>(SAVED.allow || {});      // item → allowed recipe classes
  let recipeFor = $state<string | null>(null);                          // open recipe picker
  let res = $state<any>(null), busy = $state(false), err = $state('');
  let site = $state<{ x: number; y: number } | null>(JSON.parse(localStorage.getItem('fgmap.site') || 'null'));
  $effect(() => localStorage.setItem('fgmap.planner', JSON.stringify({ useSurplus, goal, maxClock, sloop, allow })));
  let savePin = $state<any>(null);

  onMount(async () => {
    recipes = await (await fetch('/api/recipes')).json();
    const q = $route.q;
    const last = JSON.parse(localStorage.getItem('fgmap.plannerTargets') || 'null');
    if (q.get('item')) { targets = [{ item: q.get('item')!, rate: +(q.get('rate') || 10) }]; run(); }
    else if (last?.length) { targets = last; run(); }                 // back from the map: show the last plan again
  });

  async function run() {
    const tg = targets.filter(x => x.item && x.rate > 0);
    if (!tg.length) { err = tr('Pick an item from the list and an amount.'); return; }
    const bad = tg.find(x => !opts.includes(x.item));
    if (bad) { err = tr('“{item}” is not a craftable item. Pick an entry from the list.', { item: bad.item }); return; }
    busy = true; err = '';
    try {
      const r = await (await fetch('/api/plan', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ targets: tg, exclude, use_surplus: useSurplus, goal, max_clock: maxClock / 100, sloop, allow }) })).json();
      localStorage.setItem('fgmap.plannerTargets', JSON.stringify(tg));
      if (!r.ok) { err = lxr(r.error); res = null; } else res = r;
    } catch (e: any) { err = tr('The planner is not responding: {msg}', { msg: e.message }); } finally { busy = false; }
  }

  // --- Flow diagram (layout in lib/flowlayout.ts) + highlighting of the chain under the pointer
  const graph = $derived(res ? layout(res, fmtNum) : null);
  let hover = $state<FNode | null>(null);
  let view = $state<'diagram' | 'tree'>('diagram');
  // everything that depends on or supplies the hovered node
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

  // --- Tree view: backwards from the target, each item indented with amount and machine
  const tree = $derived.by(() => {
    if (!graph) return [];
    const rows: { depth: number; label: string; sub: string; rate: number; kind: string; again: boolean }[] = [];
    const seen = new Set<FNode>();
    const rec = (n: FNode, depth: number, rate: number, item: string) => {
      const again = seen.has(n);
      rows.push({ depth, label: item, sub: n.kind === 'step' ? (n.label !== item ? n.label + ' · ' : '') + n.sub : n.kind === 'raw' ? tr('Resource') : tr('from surplus'), rate, kind: n.kind, again });
      if (again || n.kind !== 'step') return;
      seen.add(n);
      for (const e of graph.ins.get(n) || []) rec(e.a, depth + 1, e.rate, e.item);
    };
    for (const tn_ of graph.nodes.filter(n => n.kind === 'target')) {
      if (tn_.data) {                                 // target step: itself as the root
        seen.add(tn_);
        rows.push({ depth: 0, label: tn_.label, sub: tn_.sub, rate: tn_.data.out[0]?.rate ?? 0, kind: 'target', again: false });
        for (const e of graph.ins.get(tn_) || []) rec(e.a, 1, e.rate, e.item);
      } else for (const e of graph.ins.get(tn_) || []) rec(e.a, 0, e.rate, e.item);
    }
    return rows;
  });

  // --- Free nodes near the build site
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
  const PUR: Record<string, string> = { pure: 'pure', normal: 'normal', impure: 'impure' };

  let bpErr = $state('');
  async function blueprint(s: Step) {
    bpErr = '';
    const r = await fetch('/api/blueprint', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cls: s.cls, building: s.building, machines: s.machines, full_clock: (s as any).full_clock || 100, clock: s.clock }) });
    if (!r.ok) { const e = (await r.json().catch(() => ({}))).error; bpErr = e ? lxr(e) : tr('Blueprint failed'); return; }
    const blob = await r.blob(), a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = decodeURIComponent((r.headers.get('Content-Disposition') || '').split("''")[1] || 'blueprint.zip');
    a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  }

  function toPin() {
    const tg = res.targets.map((x: any) => fmtNum(x.rate) + '/min ' + x.item).join(', ');
    const lines = res.steps.map((s: Step) => `${fmtNum(s.machines)}× ${s.building}: ${s.recipe}`);
    const at = site || centerOfFactory() || { x: 0, y: 0 };
    savePin = { author: '', cat: 'planned', color: '#f59a23', shape: 'point', geom: [[Math.round(at.x), Math.round(at.y)]],
      text: [tr('Plan: {targets}', { targets: tg }), ...lines,
             tr('Resources: {raw} · Power {power}', { raw: res.raw.map((r: any) => fmtNum(r.rate) + ' ' + r.item).join(', '), power: fmtMW(res.power) })].join('\n').slice(0, 500) };
  }
  const opts = $derived(recipes.map(r => r.item));
  const altFor = (item: string) => recipes.find(r => r.item === item)?.recipes || [];
</script>

<div class="page">
  <h1>{$t('Planner')}</h1>
  <p class="src">{$t('Only recipes unlocked on the server. With “fewest resources”, rare resources count more.')}</p>

  <div class="panel card form">
    {#each targets as tg, i}
      <div class="row">
        <ItemPicker bind:value={tg.item} items={opts} placeholder={$t('Item, e.g. Steel Beam')} />
        <span class="rw"><input class="field rate" type="number" min="0.1" step="any" bind:value={tg.rate} aria-label={$t('Amount per minute')} /><span class="muted">/min</span></span>
        {#if targets.length > 1}<button class="x" onclick={() => (targets = targets.filter((_, j) => j !== i))} aria-label={$t('Remove target')}>✕</button>{/if}
      </div>
    {/each}
    <div class="row">
      {#if targets.length < 8}<button class="btn" onclick={() => (targets = [...targets, { item: '', rate: 10 }])}>{$t('Add target')}</button>{/if}
      <label class="tg"><input type="checkbox" bind:checked={useSurplus} /> {$t('Use factory surplus')}</label>
    </div>
    <div class="row opts">
      <span class="ol">{$t('Optimize for')}</span>
      <div class="seg">{#each [['raw', $t('fewest resources')], ['machines', $t('fewest machines')], ['power', $t('least power')]] as [k, l]}
        <button class:on={goal === k} onclick={() => { goal = k as any; if (res) run(); }}>{l}</button>{/each}</div>
      <label class="tg" title={$t('With Power Shards up to 250 %: fewer machines, but disproportionately more power')}>{$t('Clock up to')}
        <select class="field sel" bind:value={maxClock} onchange={() => res && run()}>
          {#each [100, 150, 200, 250] as c}<option value={c}>{c} %{c > 100 ? ' (' + $t('{n} shards', { n: Math.ceil((c - 100) / 50) }) + ')' : ''}</option>{/each}
        </select></label>
      <label class="tg" title={$t('Somersloop in every machine: double output, four times the power')}><input type="checkbox" bind:checked={sloop} onchange={() => res && run()} /> Somersloops</label>
      <span style="flex:1"></span>
      <span style="flex:1"></span>
      <button class="btn primary" onclick={run} disabled={busy}>{busy ? $t('Calculating …') : $t('Calculate')}</button>
    </div>
    {#if err}<p class="err">{err}</p>{/if}
  </div>

  {#if res}
    {#if !res.steps.length && res.surplus_used.length}
      <div class="panel card note">{$t('Nothing to build: the factory already has enough surplus ({list}).', { list: res.surplus_used.map((u: any) => fmtNum(u.available) + '/min ' + $tn(u.item)).join(', ') })}
        {$t('Untick “Use factory surplus” to plan a separate setup.')}</div>
    {/if}
    <div class="kpis">
      <div class="kpi panel"><div class="v num">{res.machines}</div><div class="l">{$t('Machines')}</div></div>
      <div class="kpi panel"><div class="v num">{fmtMW(res.power)}</div><div class="l">{$t('Power')}</div></div>
      {#if res.shards}<div class="kpi panel"><div class="v num">{res.shards}</div><div class="l">{$t('Power Shards (at most)')}</div></div>{/if}
      {#if res.sloops}<div class="kpi panel"><div class="v num">{res.sloops}</div><div class="l">Somersloops</div></div>{/if}
      {#each res.raw as r}<div class="kpi panel"><div class="v num">{fmtNum(r.rate)}</div><div class="l">{$tn(r.item)} /min</div></div>{/each}
    </div>

    <div class="panel card chain">
      <div class="gh"><h2>{$t('Production chain')}</h2>
        <div class="seg">{#each [['diagram', $t('Diagram')], ['tree', $t('Tree')]] as [k, l]}<button class:on={view === k} onclick={() => (view = k as any)}>{l}</button>{/each}</div>
      </div>
      {#if graph && view === 'diagram'}
        <div class="flow">
          <svg width={graph.width + 4} height={graph.height + 4} class:dim={!!lit} role="img" aria-label={$t('Production chain')}>
            {#each graph.edges as e (e.id)}
              <path d={edgePath(e)} class="edge" class:on={lit?.le.has(e)} stroke={EDGE_COL[e.kind]} stroke-width={e.w}><title>{$tn(e.item)}: {fmtNum(e.rate)}/min</title></path>
            {/each}
            {#each graph.edges as e (e.id + 'l')}
              <!-- label at the end of the edge, truncated to the column gap (otherwise it overlaps the box before it) -->
              {@const lbl = fmtNum(e.rate) + ' ' + $tn(e.item)}
              {#if e.label || lit?.le.has(e)}
              <text x={e.b.x - 6} y={e.y2 - 4} class="el" class:on={lit?.le.has(e)} text-anchor="end">{lbl.length > LABEL_CHARS ? lbl.slice(0, LABEL_CHARS - 1) + '…' : lbl}<title>{$tn(e.item)}: {fmtNum(e.rate)}/min</title></text>
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
        <p class="muted small">{$t('Line width = amount. Orange lines come from resource nodes, green ones from factory surplus.')}
          {$t('Hover over a box to highlight its suppliers and consumers.')}</p>
      {:else if graph}
        <ol class="tree">
          {#each tree as r}
            <li style="padding-left:{r.depth * 22}px" class={r.kind} class:again={r.again}>
              <span class="rt num">{fmtNum(r.rate)}/min</span><b>{$tn(r.label)}</b><span class="muted">{r.again ? $t('see above') : $tn(r.sub)}</span>
            </li>
          {/each}
        </ol>
      {/if}
    </div>

    <div class="grid2" style="margin-top:16px">
      <div class="panel card">
        <h2>{$t('Build list')}</h2>
        <table class="t">
          <thead><tr><th>{$t('Machines')}</th><th>{$t('Recipe')}</th><th class="n">{$t('Power')}</th></tr></thead>
          <tbody>
            {#each res.steps as s}
              <tr><td>{s.full ? s.full + '× ' + (s.full_clock !== 100 ? $t('at {c} %', { c: s.full_clock }) + ' ' : '') : ''}{s.clock ? (s.full ? '+ 1× ' : '1× ') + $t('at {c} %', { c: s.clock }) : ''}<div class="muted small">{$tn(s.building)}</div></td>
                <td>{$tn(s.recipe)}{#if s.alt} <span class="tag">{$t('alternate')}</span>{/if}
                  <div class="muted small">{s.out.map(o => fmtNum(o.rate) + ' ' + $tn(o.item)).join(', ')}</div>
                  {#if altFor(s.out[0].item).length > 1}
                    <button class="lk" onclick={() => (recipeFor = recipeFor === s.out[0].item ? null : s.out[0].item)}>
                      {$t('Choose recipes ({n} of {total} allowed)', { n: (allow[s.out[0].item] || altFor(s.out[0].item).map(r => r.cls)).length, total: altFor(s.out[0].item).length })}</button>
                    {#if recipeFor === s.out[0].item}
                      {@const it = s.out[0].item}
                      <div class="rpick">
                        {#each altFor(it) as r}
                          <label><input type="checkbox" checked={(allow[it] || altFor(it).map(x => x.cls)).includes(r.cls)}
                            onchange={e => {
                              const cur = new Set(allow[it] || altFor(it).map(x => x.cls));
                              (e.target as HTMLInputElement).checked ? cur.add(r.cls) : cur.delete(r.cls);
                              if (!cur.size) { (e.target as HTMLInputElement).checked = true; return; }   // at least one
                              allow = { ...allow, [it]: [...cur] }; if (cur.size === altFor(it).length) { const a = { ...allow }; delete a[it]; allow = a; }
                              run();
                            }} /> {$tn(r.name)}{r.alt ? ' (' + $t('alt.') + ')' : ''}{r.cls === s.cls ? ' · ' + $t('in use') : ''}</label>
                        {/each}
                      </div>
                    {/if}
                  {/if}</td>
                <td class="n">{fmtMW(s.power)}
                  {#if s.bp}<div><button class="lk inl" onclick={() => blueprint(s)} title={$t('Experimental: based on the bundled blueprint templates, not yet tested in game')}>Blueprint ⤓</button></div>{/if}</td></tr>
            {/each}
          </tbody>
        </table>
        {#if bpErr}<p class="err small">{bpErr}</p>{/if}
        {#if res.steps.some((x: any) => x.bp)}<p class="muted small"><b>Blueprint ⤓</b> {$t('is experimental: it builds on the bundled templates “8x Constructor T5” and “10x Smelter T5”, sets recipe and clock speed, and leaves out surplus machines.')} {$t('Not yet tested in game — unzip it and put it in')} <code>SaveGames/blueprints/{$status?.save?.session || "<Session>"}/</code> {$t('(server), or test it locally.')}</p>{/if}
        {#if Object.keys(allow).length}<p class="small">{$t('Restricted: {items}', { items: Object.keys(allow).map(x => $tn(x)).join(', ') })} <button class="lk inl" onclick={() => { allow = {}; run(); }}>{$t('allow all recipes again')}</button></p>{/if}
        {#if res.byproducts.length}<p class="small muted">{$t('Byproducts: {list}', { list: res.byproducts.map((b: any) => fmtNum(b.rate) + ' ' + $tn(b.item)).join(', ') })}</p>{/if}
        {#if res.surplus_used.length}<p class="small muted">{$t('From factory surplus: {list}', { list: res.surplus_used.map((b: any) => $t('{n} of {total}', { n: fmtNum(b.rate), total: fmtNum(b.available) }) + ' ' + $tn(b.item)).join(', ') })}</p>{/if}
      </div>

      <div class="panel card">
        <h2>{$t('Free nodes')}</h2>
        <p class="muted small">{site ? $t('Sorted by purity and distance to the selected build site.') : $t('Sorted by purity and distance to the largest factory.')}
          {$t('Build site:')} <a class="lk inl" href="#/map?pick=site{site ? '&x=' + site.x + '&y=' + site.y + '&z=1.2' : ''}">{site ? site.x + ' / ' + site.y + ' m — ' + $t('change on the map') : $t('pick on the map')}</a>
          {#if site}<button class="lk inl" onclick={() => { site = null; localStorage.removeItem('fgmap.site'); }}>{$t('reset')}</button>{/if}</p>
        {#each nodeHints as h}
          <h3>{$tn(h.item)} · {fmtNum(h.rate)}/min</h3>
          {#each h.list as { n, d }}
            <button class="lk" onclick={() => toMap('node:' + n.id, n.pos[0], n.pos[1])}>{PUR[n.purity || ''] ? $t(PUR[n.purity || '']) : '?'} · {$t('{d} m away', { d: Math.round(d) })} · {n.pos[0]} / {n.pos[1]}</button>
          {:else}<p class="muted small">{$t('No free node of this type.')}</p>{/each}
        {/each}
        <button class="btn" onclick={toPin} style="margin-top:12px">{$t('Save plan as map note')}</button>
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
