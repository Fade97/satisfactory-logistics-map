<script lang="ts">
  // Detail card for every map object.
  import type { MapObj } from './mapview';
  import { live, stations, factory, flow } from './api';
  import { C, MODE_LABEL, STATE_COLOR, machineColor, fmtNum, fmtMW, dur } from './fmt';
  import type { Station } from './types';
  import { tn } from './names';
  import { t, tr, lx, locale } from './i18n';

  let { o, onpick, onfollow, following = false, onpin }: {
    o: MapObj; onpick: (key: string) => void; onfollow?: () => void; following?: boolean; onpin?: (o: MapObj) => void;
  } = $props();
  const d = $derived(o.data);
  let show3d = $state(false);
  /** Belts/pipes near the factory: each point at most 15 m from one of its machines, clipped outside */
  function near(ms: any[]) {
    const R = 15, cell = 30, grid = new Map<string, any[]>();
    for (const m of ms) { const k = Math.floor(m.pos[0] / cell) + ',' + Math.floor(m.pos[1] / cell); if (!grid.has(k)) grid.set(k, []); grid.get(k)!.push(m); }
    const ok = (x: number, y: number) => {
      const gx = Math.floor(x / cell), gy = Math.floor(y / cell);
      for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++)
        for (const m of grid.get((gx + dx) + ',' + (gy + dy)) || []) if ((m.pos[0] - x) ** 2 + (m.pos[1] - y) ** 2 <= (R + 10) ** 2) return true;
      return false;
    };
    const out: number[][][] = [];
    for (const p of Object.values($flow || {}).flat()) {
      let cur: number[][] = [];
      for (const q of p) { if (ok(q[0], q[1])) cur.push(q); else { if (cur.length > 1) out.push(cur); cur = []; } }
      if (cur.length > 1) out.push(cur);
    }
    return out;
  }
  const PT: Record<string, string> = { freight: tr('Freight'), fluid: tr('Fluid'), empty: tr('empty') };
  const KIND: Record<string, string> = { collectible: tr('Collectible'), station: '', player: tr('Player'), train: tr('Train'), truck: tr('Vehicle'), machine: tr('Machine'),
    generator: tr('Generator'), node: tr('Resource nodes'), pin: tr('Note'), factory: tr('Factory') };
  // Purity arrives in English from the backend; the values are shared i18n keys (i18n/de/parts.ts)
  const PUR: Record<string, string> = { pure: 'pure', normal: 'normal', impure: 'impure' };

  const liveSt = $derived(o.kind === 'station' ? $live?.stations?.[d.id.split('.').pop()] : null);
  const vehName = (id: string) => $live?.trucks.find(t => t.id === id)?.name;

  // counterpart stations via a shared vehicle
  const links = $derived.by(() => {
    if (o.kind !== 'station' || d.kind !== 'truck' || !$stations) return [];
    const mine = new Set((d.vehicles || []).map((v: any) => v.id));
    return $stations.trucks.filter(s => s.id !== d.id && (s.vehicles || []).some(v => mine.has(v.id)))
      .map(s => ({ s, vs: (s.vehicles || []).filter(v => mine.has(v.id)) }));
  });
  const route = $derived.by(() => {
    if (o.kind !== 'truck' || !$stations) return [];
    return $stations.trucks.filter(s => (s.vehicles || []).some(v => v.id === d.id));
  });
  const trainRoutes = $derived(o.kind === 'station' && d.kind === 'train' && $stations
    ? $stations.routes.filter(r => r.stops.some(s => s.ident === d.ident)) : []);
  const sameItem = $derived.by(() => {
    if (o.kind !== 'station' || !$stations || !d.items[0]) return [];
    const it = d.items[0].item, linked = new Set(links.map(l => l.s.id));
    return [...$stations.trucks, ...$stations.trains].filter((s: Station) => s.id !== d.id && s.mode !== d.mode && !linked.has(s.id)
      && s.items.some(i => i.item === it));
  });
  const cluster = $derived(o.kind === 'factory' ? d : null);
  const members = $derived.by(() => {
    if (!cluster || !$factory) return [];
    const ids = new Set(cluster.ids || []);
    return $factory.machines.filter(m => ids.has(m.id));
  });
  const stalled = $derived(members.filter(m => m.state === 'stopped' && m.block !== 'full'));
  const key = (s: Station) => 'station:' + s.id.split('.').pop();
  const fillPct = (f: number | null | undefined) => f == null ? null : Math.round(f * 100);
</script>

<div class="det">
  <div class="k">{KIND[o.kind] || (d.kind === 'train' ? $t('Train station') : $t('Truck station'))} · {Math.round(o.x)} / {Math.round(o.y)} m</div>
  <h2>{o.kind === 'machine' ? $tn(d.recipe || d.name) : o.kind === 'pin' ? (d.text.split('\n')[0] || $t('Note')) : (o.label || d.name)}</h2>

  {#if o.kind === 'station'}
    <div class="row"><span class="tag"><span class="dot" style="background:{C[d.mode]}"></span>{$t(MODE_LABEL[d.mode])}</span>
      {#if liveSt}<span class="tag">{liveSt.status === 'Error' ? '⚠ ' + $t('Error') : (liveSt.activity || liveSt.status || $t('ready'))}{liveSt.rate ? ' · ' + fmtNum(liveSt.rate) + '/min' : ''}</span>{/if}
    </div>
    {#if d.kind === 'train'}
      <table class="t">
        <thead><tr><th>{$t('Platform')}</th><th>{$t('Item')}</th><th class="n">{$t('buffer')}</th></tr></thead>
        <tbody>
        {#each d.platforms as p}
          <tr><td>{PT[p.type]}<div class="muted small">{p.mode ? $t(MODE_LABEL[p.mode]) : '—'}</div></td>
            <td>{p.items.map((i: any) => $tn(i.item)).join(', ') || '—'}</td>
            <td class="n">{p.items.map((i: any) => fmtNum(i.amount)).join(', ') || '—'}
              {#if p.fill != null}<div class="bar mini"><i style="width:{p.fill * 100}%;background:{p.fill > .9 ? C.bad : '#c3bfb7'}"></i></div>{/if}</td></tr>
        {/each}
        </tbody>
      </table>
      {#each trainRoutes as r}
        <div class="sec"><h3>{r.name}</h3><div class="muted small">{r.stops.map(s => s.name).join(' → ')}</div></div>
      {/each}
    {:else}
      <table class="t"><thead><tr><th>{$t('Item')}</th><th class="n">{$t('buffer')}</th></tr></thead><tbody>
        {#each d.items as i}<tr><td>{$tn(i.item)}</td><td class="n">{fmtNum(i.amount)}</td></tr>
        {:else}<tr><td colspan="2" class="muted">{(d.vehicles || []).length ? $t('Buffer empty right now') : $t('Empty. The station has not been used yet.')}</td></tr>{/each}
      </tbody></table>
      {#if d.fill != null}<div class="fill"><div class="bar"><i style="width:{d.fill * 100}%;background:{d.fill > .9 ? C.bad : d.fill < .1 ? C.warn : 'var(--text2)'}"></i></div><span class="num">{$t('{n} % full', { n: fillPct(d.fill) })}</span></div>{/if}
      <div class="sec"><h3>{$t('Connected by truck')}</h3>
        {#each links as l}
          <button class="lk" onclick={() => onpick(key(l.s))}><span class="dot" style="background:{C[l.s.mode]}"></span><b>{l.s.name}</b></button>
          {#each l.vs as v}
            <div class="via">{vehName(v.id) || v.type} · {$t('round trip {t}', { t: dur(v.round / 60) })}{#if v.per_min} · {$t('up to {n}/min', { n: fmtNum(v.per_min) })}{/if}
              {#if v.last > 3 * Math.max(v.round, 60)}<span class="warn"> · {$t('not seen for {t}', { t: dur(v.last / 60) })}</span>{/if}</div>
          {/each}
        {:else}<div class="muted small">{$t('No vehicle docks here.')}</div>{/each}
      </div>
    {/if}
    {#if sameItem.length}
      <div class="sec"><h3>{links.length ? $t('Same item, not connected') : $t('{item}: counterparts', { item: $tn(d.items[0].item) })}</h3>
        {#each sameItem.slice(0, 8) as s}<button class="lk" onclick={() => onpick(key(s))}><span class="dot" style="background:{C[s.mode]}"></span>{s.name}</button>{/each}
      </div>
    {/if}

  {:else if o.kind === 'player'}
    <div class="row"><span class="tag">{d.online === null ? $t('as of the save') : d.online ? (d.dead ? $t('dead') : $t('online')) : $t('offline')}</span>
      {#if d.hp != null}<span class="tag">HP {d.hp}</span>{/if}{#if d.speed}<span class="tag">{fmtNum(d.speed)} km/h</span>{/if}</div>
    {#if onfollow}
      <button class="btn" class:on={following} onclick={onfollow}>{following ? $t('Stop following') : $t('Follow {name}', { name: d.name })}</button>
      {#if d.online !== true && !following}<p class="muted small">{$t('{name} is not online right now — the map will follow from their next login.', { name: d.name })}</p>{/if}
    {/if}
    {#if d.inventory?.length}
      <table class="t"><thead><tr><th>{$t('Inventory')}</th><th class="n">{$t('Amount')}</th></tr></thead><tbody>
        {#each d.inventory as i}<tr><td>{i.Name}</td><td class="n">{fmtNum(i.Amount)}</td></tr>{/each}</tbody></table>
    {/if}

  {:else if o.kind === 'train' || o.kind === 'truck'}
    <div class="row">
      {#if d.status}<span class="tag">{d.status}</span>{/if}
      {#if d.speed != null}<span class="tag">{fmtNum(d.speed)} km/h</span>{/if}
      {#if d.derailed}<span class="tag bad">{$t('derailed')}</span>{/if}
      {#if d.fuel === false}<span class="tag bad">{$t('out of fuel')}</span>{/if}
      {#if o.dim}<span class="tag">{$t('Position from the save')}</span>{/if}
    </div>
    {#if d.station}<p>{$t('Destination:')} <b>{d.station}</b></p>{/if}
    {#if d.cargo}<p>{$t('Cargo:')} {$tn(d.cargo.item)} · {fmtNum(d.cargo.amount)}</p>{/if}
    {#if d.payload}<p>{$t('Cargo:')} {fmtNum(d.payload)} t</p>{/if}
    {#if onfollow}<button class="btn" class:on={following} onclick={onfollow}>{following ? $t('Stop following') : $t('Follow this vehicle')}</button>{/if}
    {#if o.kind === 'truck'}
      <div class="sec"><h3>{$t('Route · {n} stations', { n: route.length })}</h3>
        {#each route as s}<button class="lk" onclick={() => onpick(key(s))}><span class="dot" style="background:{C[s.mode]}"></span>{s.name}</button>
        {:else}<div class="muted small">{$t('No station knows this vehicle.')}</div>{/each}</div>
    {/if}

  {:else if o.kind === 'machine'}
    <div class="row"><span class="tag"><span class="dot" style="background:{machineColor(d)}"></span>{d.state === 'stopped' && d.block === 'full' ? $t('waiting (output full)') : $t(d.state)} · {d.pct} %</span>
      <span class="tag">{$tn(d.name)}</span>{#if d.clock !== 1}<span class="tag">{$t('Clock {n} %', { n: Math.round(d.clock * 100) })}</span>{/if}
      {#if d.alt}<span class="tag">{$t('Alternate recipe')}</span>{/if}{#if d.purity}<span class="tag">{$t('{p} node', { p: PUR[d.purity] ? $t(PUR[d.purity]) : d.purity })}</span>{/if}</div>
    {#if d.why}<p class:why={d.block !== 'full'} class:muted={d.block === 'full'}>{$lx(d.why)}{d.block === 'full' ? ' — ' + $t('buffer, no action needed') : ''}</p>{/if}
    <table class="t"><thead><tr><th>{$t('Item')}</th><th class="n">{$t('Actual')}</th><th class="n">{$t('Target /min')}</th></tr></thead><tbody>
      {#each d.out as p}<tr><td>{$tn(p.item)}</td><td class="n">{fmtNum(p.rate)}</td><td class="n">{fmtNum(p.max)}</td></tr>{/each}
      {#each d.inp as p}<tr><td class="muted">← {$tn(p.item)}</td><td class="n">{fmtNum(p.rate)}</td><td class="n">{fmtNum(p.max)}</td></tr>{/each}
    </tbody></table>
    <p class="muted small">{fmtMW(d.power)} · {$t('Grid {n}', { n: d.circuit ?? '—' })}{d.by ? ' · ' + $t('built by {name}', { name: d.by }) : ''}{d.since != null ? ' · ' + $t('in this state for {t}', { t: dur(d.since / 60) }) : ''}</p>

  {:else if o.kind === 'generator'}
    <div class="row"><span class="tag">{d.producing ? $t('producing') : $t('stopped')}</span><span class="tag">{fmtMW(d.cap)}</span></div>
    {#if d.fuel}<p>{$t('Fuel:')} <b>{$tn(d.fuel)}</b>{d.fuel_rate ? ' · ' + fmtNum(d.fuel_rate) + '/min' : ''}</p>{/if}
    {#if d.fuel_minutes != null}<p>{$t('Fuel in the building lasts')} <b>{dur(d.fuel_minutes)}</b></p>{/if}

  {:else if o.kind === 'node'}
    <div class="row"><span class="tag">{$tn(d.item) || '?'}</span><span class="tag">{PUR[d.purity] ? $t(PUR[d.purity]) : $t('Purity unknown')}</span>
      <span class="tag">{d.used ? $t('occupied') : $t('free')}</span></div>
    {#if d.used}<p>{$tn(d.extractor)} · {fmtNum(d.rate)} /min</p>{/if}

  {:else if o.kind === 'factory'}
    <div class="row"><span class="tag">{$t('{n} machines', { n: d.n })}</span><span class="tag">{fmtMW(d.power)}</span>
      {#if d.renamed}<span class="tag" title={$t('Automatic name: {name}', { name: $lx(d.auto) })}>{$t('renamed')}</span>{/if}
      {#if d.status && d.status !== 'active'}<span class="tag">{$t(({ building: 'under construction', buffer: 'buffer', decommissioned: 'decommissioned' } as any)[d.status] || d.status)}</span>{/if}</div>
    <div class="states">{#each Object.entries(d.states).filter(([s]) => s !== 'stopped') as [s, n]}<span><span class="dot" style="background:{STATE_COLOR[s]}"></span>{n} {$t(s)}</span>{/each}
      {#if d.full}<span><span class="dot" style="background:#8a857c"></span>{$t('{n} waiting (output full)', { n: d.full })}</span>{/if}
      {#if d.starved}<span><span class="dot" style="background:{C.bad}"></span>{$t('{n} missing input', { n: d.starved })}</span>{/if}</div>
    <div class="grid">
      <div><h3>{$t('Supplies')}</h3>{#each d.out as p}<div class="io"><span>{$tn(p.item)}</span><span class="num">{fmtNum(p.rate)}</span></div>{:else}<div class="muted small">{$t('nothing net')}</div>{/each}</div>
      <div><h3>{$t('Needs')}</h3>{#each d.inp as p}<div class="io"><span>{$tn(p.item)}</span><span class="num">{fmtNum(p.rate)}</span></div>{:else}<div class="muted small">{$t('nothing from outside')}</div>{/each}</div>
    </div>
    {#if stalled.length}
      <div class="sec"><h3>{$t('Missing input')}</h3>
        {#each stalled.slice(0, 12) as m}<button class="lk" onclick={() => onpick('machine:' + m.id)}><span class="dot" style="background:{C.bad}"></span>{$tn(m.recipe || m.name)}<span class="muted small">&nbsp;{$lx(m.why)}</span></button>{/each}
      </div>
    {/if}
    <div class="acts">
      <button class="btn" onclick={() => (show3d = true)}>{$t('3D view')}</button>
      {#if onpin}<button class="btn" onclick={() => onpin(o)}>{$t('Rename / set status')}</button>{/if}
    </div>
    {#if show3d}
      {#await import('./Factory3D.svelte')}
        <p class="muted small">{$t('Loading 3D view …')}</p>
      {:then F}
        <F.default machines={members} title={d.name} onclose={() => (show3d = false)}
          flow={near(members)} />
      {:catch e}
        <p class="err3d">{$t('The 3D view could not be loaded ({err}). Reload the page and try again.', { err: e?.message || e })}</p>
      {/await}
    {/if}

  {:else if o.kind === 'collectible'}
    <p>{d.kind === 'droppod' ? $t('Not collected yet. Height {z} m — crash site, not looted yet.', { z: d.pos[2] }) : $t('Not collected yet. Height {z} m.', { z: d.pos[2] })}</p>
    <p class="muted small">{$t('As of the last save; collected objects disappear with the next autosave.')}</p>
  {:else if o.kind === 'pin'}
    <p class="pre">{d.text}</p>
    <p class="muted small">{d.author} · {new Date(d.t * 1000).toLocaleString(locale(), { dateStyle: 'short', timeStyle: 'short' })}</p>
    {#if onpin}<button class="btn" onclick={() => onpin(o)}>{$t('Edit')}</button>{/if}
  {/if}
</div>

<style>
  .det { padding: 14px 16px 16px; }
  .k { color: var(--dim); font-size: 12px; }
  h2 { margin: 2px 26px 10px 0; line-height: 1.15; }
  h3 { font-size: 14px; color: var(--text2); margin-bottom: 4px; }
  .row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
  .tag.bad { border-color: var(--bad); color: var(--bad); }
  .sec { margin-top: 14px; }
  .lk { display: flex; align-items: center; gap: 7px; width: 100%; background: none; border: none; padding: 4px 0; text-align: left; color: var(--text); }
  .lk:hover b, .lk:hover { color: var(--ficsit); }
  .via { font-size: 12px; color: var(--dim); padding-left: 16px; margin-bottom: 2px; }
  .warn { color: var(--warn); }
  .small { font-size: 12px; }
  p { margin: 6px 0; }
  .why { color: var(--warn); }
  .fill { display: flex; align-items: center; gap: 10px; margin: 8px 0; font-size: 12px; color: var(--dim); }
  .fill .bar { flex: 1; }
  .bar.mini { height: 3px; margin-top: 3px; }
  .states { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 13px; margin-bottom: 10px; }
  .states span { display: inline-flex; align-items: center; gap: 5px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 8px; }
  .io { display: flex; justify-content: space-between; font-size: 13px; gap: 8px; }
  .pre { white-space: pre-wrap; }
  .btn { margin-top: 10px; }
  .err3d { color: var(--bad); font-size: 13px; }
  .acts { display: flex; gap: 8px; flex-wrap: wrap; }
</style>
