<script lang="ts">
  import { stations, live, factory, status, storage } from '../lib/api';
  import { matches } from '../lib/fuzzy';
  import ItemPicker from '../lib/ItemPicker.svelte';
  import { toMap } from '../lib/router';
  import { C, MODE_LABEL, fmtNum, dur, ago } from '../lib/fmt';
  import type { Station } from '../lib/types';
  import { tn, both } from '../lib/names';
  import { t, tr, lx, locale } from '../lib/i18n';

  let view = $state<'pruef' | 'routen' | 'zug' | 'fuell' | 'lager' | 'plan' | 'fahrzeuge'>('pruef');
  let sched = $state<any[] | null>(null);
  $effect(() => { if (view === 'pruef') fetch('/api/schedule').then(r => r.json()).then(d => (sched = d)); });
  const VERD: Record<string, [string, string]> = { bottleneck: [tr('bottleneck'), C.bad], tight: [tr('tight'), C.warn], ok: [tr('sufficient'), C.ok], unknown: [tr('not measured yet'), '#6f6b64'] };
  const schedSorted = $derived((sched || []).flatMap(r => r.flows.map((f: any) => ({ r, f })))
    .sort((a, b) => ['bottleneck', 'tight', 'unknown', 'ok'].indexOf(a.f.verdict) - ['bottleneck', 'tight', 'unknown', 'ok'].indexOf(b.f.verdict)
      || (b.f.need || 0) - (a.f.need || 0)));
  let lagerQ = $state('');
  // Lager: Summe je Ware über alle Container/Tanks, dazu die einzelnen Orte
  const lager = $derived.by(() => {
    const m = new Map<string, { item: string; amount: number; n: number; full: number; list: any[] }>();
    for (const c of $storage || []) for (const i of c.items) {
      const e = m.get(i.item) || { item: i.item, amount: 0, n: 0, full: 0, list: [] };
      e.amount += i.amount; e.n++; if ((c.fill ?? 0) > .98) e.full++; e.list.push(c); m.set(i.item, e);
    }
    return [...m.values()].filter(e => matches(lagerQ, both(e.item))).sort((a, b) => b.amount - a.amount);
  });
  let lagerOpen = $state<string | null>(null);
  const empty = $derived(($storage || []).filter(c => !c.items.length).length);
  let flowH = $state(24);
  let trainFlow = $state<{ hours: number; stations: Record<string, Record<string, { '+'?: number; '-'?: number }>> } | null>(null);
  $effect(() => { if (view === 'zug') fetch('/api/train-flow?h=' + flowH).then(r => r.json()).then(d => (trainFlow = d)); });
  const S = $derived($stations);
  const key = (s: Station) => 'station:' + s.id.split('.').pop();
  const go = (s: Station) => toMap(key(s), s.pos[0] / 100, s.pos[1] / 100);

  // Truck-Routen: Fahrzeug → Stationen, Durchsatz aus Rundenzeit, Bedarf aus der Warenbilanz
  const routes = $derived.by(() => {
    if (!S) return [];
    const byV = new Map<string, { id: string; type: string; round: number; last: number; per_min: number | null; stops: Station[] }>();
    for (const s of S.trucks) for (const v of s.vehicles || []) {
      const e = byV.get(v.id) || { id: v.id, type: v.type, round: v.round, last: v.last, per_min: v.per_min ?? null, stops: [] };
      e.stops.push(s); e.round = Math.max(e.round, v.round); e.last = Math.min(e.last, v.last);
      if (s.mode === 'load' && v.per_min) e.per_min = v.per_min;
      byV.set(v.id, e);
    }
    const bal = new Map(($factory?.balance || []).map(b => [b.item, b]));
    return [...byV.values()].map(r => {
      const item = r.stops.find(s => s.items[0])?.items[0]?.item || null;
      const lv = $live?.trucks.find(t => t.id === r.id);
      const stale = r.last > 3 * Math.max(r.round, 60);
      return { ...r, item, name: lv?.name || r.type + ' ' + r.id.split('_').pop(), fuel: lv?.fuel, stale,
               need: item ? bal.get(item)?.cons ?? null : null };
    }).sort((a, b) => (a.item || '~').localeCompare(b.item || '~', locale()));
  });

  const fills = $derived.by(() => {
    if (!S) return [];
    const rows: { s: Station; label: string; fill: number; item: string; mode: string }[] = [];
    for (const s of S.trucks) if (s.fill != null && s.items[0]) rows.push({ s, label: s.name, fill: s.fill, item: s.items[0].item, mode: s.mode });
    for (const s of S.trains) (s.platforms || []).forEach((p, i) => {
      if (p.fill != null && p.items[0]) rows.push({ s, label: s.name + ' · ' + tr('Platform {n}', { n: i + 1 }), fill: p.fill, item: p.items[0].item, mode: p.mode || s.mode });
    });
    return rows;
  });
  // Warnlogik: Beladestation voll = Abholung reicht nicht; Entladestation leer = Anlieferung reicht nicht
  const problems = $derived(fills.filter(r => (r.mode === 'load' && r.fill > .9) || (r.mode === 'unload' && r.fill < .05)));

  // Liniennetzplan: Zugrouten als U-Bahn-Linien, Halte auf einer Achse je Linie
  const LINE_COL = ['#f59a23', '#5b9bd5', '#4cc38a', '#b58be8', '#e2b93b', '#e07b9b', '#6cc4d8'];
  const plan = $derived.by(() => {
    if (!S) return null;
    const lines = S.routes.filter(r => r.stops.length > 1);
    const byIdent = new Map(S.trains.map(s => [s.ident!, s]));
    const shared = new Map<string, number>();
    lines.forEach(r => new Set(r.stops.map(s => s.ident)).forEach(i => shared.set(i, (shared.get(i) || 0) + 1)));
    return { lines: lines.map((r, i) => ({ r, color: LINE_COL[i % LINE_COL.length], stops: r.stops.map(s => ({ ...s, st: byIdent.get(s.ident), shared: (shared.get(s.ident) || 0) > 1 })) })) };
  });
  const trainAt = (ident: string) => {
    const st = S?.trains.find(t => t.ident === ident);
    return st ? ($live?.trains || []).filter(t => t.station === st.name) : [];
  };
</script>

<div class="page">
  <h1>{$t('Logistics')}</h1>
  <p class="src">{S ? $t('{trucks} truck stations, {trains} train stations, {routes} train timetables · updated {ago}', { trucks: S.trucks.length, trains: S.trains.length, routes: S.routes.length, ago: ago($status?.save?.mtime) }) : $t('loading …')}</p>

  <div class="seg">
    {#each [['pruef', $t('Schedule check')], ['routen', $t('Truck routes')], ['zug', $t('Train throughput')], ['fuell', $t('Fill levels')], ['lager', $t('Storage')], ['plan', $t('Train network')], ['fahrzeuge', $t('Vehicles')]] as [k, l]}
      <button class:on={view === k} onclick={() => (view = k as any)}>{l}</button>
    {/each}
  </div>

  {#if view === 'pruef'}
    <div class="panel card tbl">
      <table class="t">
        <thead><tr><th>{$t('Route')}</th><th>{$t('Item')}</th><th class="n">{$t('capacity /min')}</th><th class="n">{$t('Demand /min')}</th><th>{$t('Verdict')}</th><th class="n hide-m">{$t('Round trip')}</th></tr></thead>
        <tbody>
          {#each schedSorted as { r, f }}
            <tr>
              <td>{r.name}<div class="muted small">{r.kind === 'zug' ? $t('Train · {n} wagons', { n: r.wagons }) : $t('Truck')} · {r.stops.join(' → ')}</div></td>
              <td>{$tn(f.item)}</td>
              <td class="n">{f.cap != null ? fmtNum(f.cap) : '–'}{#if f.moved}<div class="muted small">{$t('measured {n}', { n: fmtNum(f.moved) })}</div>{/if}</td>
              <td class="n">{f.need != null ? fmtNum(f.need) : '–'}</td>
              <td><span class="tag" style="color:{VERD[f.verdict][1]};border-color:{VERD[f.verdict][1]}55">{VERD[f.verdict][0]}</span>
                {#if f.verdict === 'bottleneck' && f.cap}<div class="muted small">{$t('needs {n}× as many vehicles or a shorter round trip', { n: Math.ceil(f.need / f.cap) })}</div>{/if}</td>
              <td class="n hide-m">{r.round ? dur(r.round / 60) : '–'}</td>
            </tr>
          {:else}<tr><td colspan="6" class="muted">{$t('loading …')}</td></tr>{/each}
        </tbody>
      </table>
      <p class="muted small"><b>{$t('Handles')}</b> {$t('= full load per trip ÷ round-trip time (upper limit).')} <b>{$t('Demand')}</b> {$t('= target consumption of machines within 250 m of the unloading stations.')}
        {$t('Train round-trip times are measured from live data (from one arrival at the first stop to the next) — “not measured yet” fills in once trains are running.')}</p>
    </div>
  {:else if view === 'routen'}
    <div class="panel card tbl">
      <table class="t">
        <thead><tr><th>{$t('Vehicle')}</th><th>{$t('Item')}</th><th>{$t('Stations')}</th><th class="n">{$t('Round trip')}</th><th class="n">{$t('up to /min')}</th><th class="n hide-m">{$t('Consumption /min')}</th></tr></thead>
        <tbody>
          {#each routes as r (r.id)}
            <tr>
              <td>{r.name}<div class="muted small">{r.type}{r.fuel === false ? ' · ' + $t('out of fuel') : ''}{r.stale ? ' · ' + $t('not docked for {t}', { t: dur(r.last / 60) }) : ''}</div></td>
              <td>{$tn(r.item) || '—'}</td>
              <td>{#each r.stops as s}<button class="lk" onclick={() => go(s)}><span class="dot" style="background:{C[s.mode]}"></span>{s.name}</button>{/each}</td>
              <td class="n">{dur(r.round / 60)}</td>
              <td class="n">{r.per_min ? fmtNum(r.per_min) : '—'}</td>
              <td class="n hide-m muted">{r.need != null ? fmtNum(r.need) : '—'}</td>
            </tr>
          {:else}<tr><td colspan="6" class="muted">{$t('No truck routes in the save.')}</td></tr>{/each}
        </tbody>
      </table>
      <p class="muted small">{$t('“Up to /min” = full load ÷ round-trip time, so the upper limit. How full a vehicle actually travels is not in the save.')}
        {$t('“Consumption” = how much of this item all machines in the factory consume.')}</p>
    </div>

  {:else if view === 'zug'}
    <div class="seg small">
      {#each [[6, '6 h'], [24, '24 h'], [168, $t('7 days')]] as [h, l]}<button class:on={flowH === h} onclick={() => (flowH = +h)}>{l}</button>{/each}
    </div>
    <div class="panel card tbl">
      <table class="t">
        <thead><tr><th>{$t('Rail station')}</th><th>{$t('Item')}</th><th class="n">{$t('loaded /min')}</th><th class="n">{$t('unloaded /min')}</th></tr></thead>
        <tbody>
          {#each Object.entries(trainFlow?.stations || {}).sort((a, b) => a[0].localeCompare(b[0], locale())) as [st, items]}
            {#each Object.entries(items) as [it, v], i}
              <tr class:click={i === 0} onclick={() => { const s = S?.trains.find(x => x.name === st); if (s) go(s); }}>
                <td>{i === 0 ? st : ''}</td><td>{$tn(it)}</td>
                <td class="n">{v['+'] ? fmtNum(v['+']) : '–'}</td><td class="n">{v['-'] ? fmtNum(v['-']) : '–'}</td></tr>
            {/each}
          {:else}
            <tr><td colspan="4" class="muted">{$t('No measurements yet. From now on, throughput is counted from live data whenever a train is at a station and its cargo changes — the table fills in once someone plays (trains do not run while the server is paused).')}</td></tr>
          {/each}
        </tbody>
      </table>
      <p class="muted small">{$t('Measured, not estimated: cargo change of docked trains between two live polls (every 5 s), averaged over the selected period including train idle time.')}</p>
    </div>
  {:else if view === 'lager'}
    <div class="lh2"><input class="field" style="max-width:280px" type="search" bind:value={lagerQ} placeholder={$t('Filter by item, e.g. screws')} />
      <span class="muted small">{$t('{n} containers and tanks · {empty} empty · {full} full', { n: ($storage || []).length, empty, full: ($storage || []).filter(c => (c.fill ?? 0) > .98).length })}</span></div>
    <div class="panel card tbl">
      <table class="t">
        <thead><tr><th>{$t('Item')}</th><th class="n">{$t('Stock')}</th><th class="n">{$t('Storage')}</th><th class="n">{$t('of which full')}</th></tr></thead>
        <tbody>
          {#each lager as e (e.item)}
            <tr class="click" onclick={() => (lagerOpen = lagerOpen === e.item ? null : e.item)}>
              <td>{$tn(e.item)}</td><td class="n">{fmtNum(e.amount)}</td><td class="n">{e.n}</td><td class="n">{e.full || '–'}</td></tr>
            {#if lagerOpen === e.item}
              <tr class="exp"><td colspan="4"><div class="lg">
                {#each e.list.sort((a, b) => (b.fill ?? 0) - (a.fill ?? 0)) as c}
                  <button class="lk" onclick={() => toMap('', c.pos[0], c.pos[1])}>
                    <span class="bar mini"><i style="width:{(c.fill ?? 0) * 100}%;background:{(c.fill ?? 0) > .98 ? C.bad : '#c3bfb7'}"></i></span>
                    {fmtNum(c.items.find((i: any) => i.item === e.item)?.amount)} · {c.cls.includes('Tank') ? $t('Tank') : $t('Container')} · {c.pos[0]} / {c.pos[1]} · {c.z} m</button>
                {/each}
              </div></td></tr>
            {/if}
          {/each}
        </tbody>
      </table>
      <p class="muted small">{$t('As of the last save. A full container only raises a warning if machines before it back up — a full end storage with nothing flowing in is intentional.')}</p>
    </div>
  {:else if view === 'fuell'}
    {#if problems.length}
      <div class="panel card warnbox"><h2>{$t('Needs attention')}</h2>
        {#each problems as p}
          <button class="lk" onclick={() => go(p.s)}><span class="dot" style="background:{C.bad}"></span>{p.label}
            <span class="muted">{p.mode === 'load' ? $t('almost full: pickup is not keeping up') : $t('empty: delivery is not keeping up')} · {$tn(p.item)}</span></button>
        {/each}
      </div>
    {/if}
    <div class="fills">
      {#each fills.sort((a, b) => b.fill - a.fill) as r}
        <button class="fr" onclick={() => go(r.s)}>
          <span class="nm">{r.label}<span class="muted small">{MODE_LABEL[r.mode] ? $t(MODE_LABEL[r.mode]) : r.mode} · {$tn(r.item)}</span></span>
          <span class="bar"><i style="width:{r.fill * 100}%;background:{(r.mode === 'load' && r.fill > .9) || (r.mode === 'unload' && r.fill < .05) ? C.bad : C[r.mode as 'load'] || '#c3bfb7'}"></i></span>
          <span class="num">{Math.round(r.fill * 100)} %</span>
        </button>
      {/each}
    </div>

  {:else if view === 'plan'}
    {#if plan}
      <div class="panel card">
        {#each plan.lines as l}
          <div class="line">
            <div class="lh"><span class="lbadge" style="background:{l.color}">{l.r.name}</span>{#if !l.r.self_driving}<span class="muted small">{$t('Autopilot off')}</span>{/if}</div>
            <div class="track" style="--c:{l.color}">
              {#each l.stops as s, i}
                <button class="stop" class:shared={s.shared} onclick={() => s.st && go(s.st)}>
                  <span class="node"></span>
                  <span class="sn">{s.name}</span>
                  {#if trainAt(s.ident).length}<span class="tr">▶ {$t('Train here')}</span>{/if}
                </button>
              {/each}
              <span class="loop" title={$t('Timetable starts over from the beginning')}>↺</span>
            </div>
          </div>
        {:else}<p class="muted">{$t('No train timetables with at least two stops.')}</p>{/each}
        <p class="muted small">{$t('Outlined stops are served by several lines. The order is the timetable order, not the track layout.')}</p>
      </div>
    {/if}

  {:else}
    <div class="panel card tbl">
      <table class="t">
        <thead><tr><th>{$t('Name')}</th><th>{$t('Type')}</th><th>{$t('State')}</th><th class="n">{$t('Speed')}</th><th class="hide-m">{$t('Cargo')}</th></tr></thead>
        <tbody>
          {#each [...($live?.trains || []).map(t => ({ ...t, typ: tr('Train'), k: 'train:' + t.name })), ...($live?.trucks || []).map(t => ({ ...t, typ: t.type, k: 'truck:' + (t.id || t.name) }))] as v}
            <tr class="click" onclick={() => toMap(v.k, v.pos[0] / 100, v.pos[1] / 100)}>
              <td>{v.name}</td><td>{v.typ}</td>
              <td>{(v as any).derailed ? '⚠ ' + $t('derailed') : (v as any).fuel === false ? '⚠ ' + $t('out of fuel') : (v as any).status ? $lx((v as any).status) : ((v as any).autopilot ? $t('Autopilot') : '—')}</td>
              <td class="n">{v.speed != null ? fmtNum(v.speed) + ' km/h' : '—'}</td>
              <td class="hide-m">{(v as any).cargo ? $tn((v as any).cargo.item) + ' ' + fmtNum((v as any).cargo.amount) : (v as any).payload ? fmtNum((v as any).payload) + ' t' : '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
      {#if $live?.source === 'save'}<p class="muted small">{$t('Live data is currently unavailable — positions and cargo come from the last save.')}</p>{/if}
      <p class="muted small">{$t('Drones: there are no drone ports on this server yet. They will appear here once one is built.')}</p>
    </div>
  {/if}
</div>

<style>
  .seg { display: inline-flex; flex-wrap: wrap; margin-bottom: 14px; }
  .seg button { background: var(--plate); border: 1px solid var(--seam); padding: 6px 12px; font-family: var(--cond); font-weight: 600; font-size: 15px; color: var(--text2); margin-right: -1px; }
  .seg button.on { color: #1b1c1e; background: var(--ficsit); border-color: var(--ficsit); }
  .tbl { padding: 4px 8px 8px; overflow-x: auto; }
  .seg.small { margin: -4px 0 12px; }
  .lh2 { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; }
  .lg { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 0 16px; }
  .lg .lk { display: flex; gap: 8px; align-items: center; }
  .bar.mini { width: 50px; height: 5px; flex: none; }
  .exp td { background: var(--steel); }
  .seg.small button { font-size: 13px; padding: 3px 10px; font-family: var(--body); font-weight: 500; }
  .small { font-size: 12px; }
  .lk { display: flex; align-items: center; gap: 7px; background: none; border: none; padding: 2px 0; text-align: left; font-size: 13px; flex-wrap: wrap; }
  .lk:hover { color: var(--ficsit); }
  .warnbox { margin-bottom: 14px; border-left: 3px solid var(--bad); }
  .fills { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 2px 20px; }
  .fr { display: grid; grid-template-columns: 1fr 120px 44px; gap: 10px; align-items: center; background: none; border: none; border-bottom: 1px solid #2c2e31; padding: 6px 0; text-align: left; }
  .fr:hover .nm { color: var(--ficsit); }
  .fr .nm { display: flex; flex-direction: column; min-width: 0; }
  .fr .num { text-align: right; font-size: 13px; }
  .line { margin-bottom: 22px; }
  .lh { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
  .lbadge { color: #1b1c1e; font-family: var(--cond); font-weight: 700; padding: 1px 10px; font-size: 15px; }
  .track { display: flex; align-items: flex-start; overflow-x: auto; padding: 4px 0 8px; position: relative; }
  .stop { position: relative; display: flex; flex-direction: column; align-items: center; min-width: 120px; background: none; border: none; padding: 0 6px; }
  .stop::before { content: ''; position: absolute; top: 7px; left: 0; right: 0; height: 4px; background: var(--c); }
  .stop:first-child::before { left: 50%; }
  .node { position: relative; width: 18px; height: 18px; border-radius: 50%; background: var(--steel); border: 4px solid var(--c); z-index: 1; }
  .stop.shared .node { border-color: var(--text); box-shadow: 0 0 0 3px var(--c); }
  .sn { font-size: 13px; margin-top: 6px; text-align: center; max-width: 130px; }
  .stop:hover .sn { color: var(--ficsit); }
  .tr { font-size: 11px; color: var(--ficsit); }
  .loop { color: var(--dim); font-size: 18px; padding: 0 8px; align-self: flex-start; }
  @media (max-width: 760px) { .fills { grid-template-columns: 1fr; } .fr { grid-template-columns: 1fr 80px 40px; } }
</style>
