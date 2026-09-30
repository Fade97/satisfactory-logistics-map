<script lang="ts">
  // Detailkarte für jedes Kartenobjekt.
  import type { MapObj } from './mapview';
  import { live, stations, factory, flow } from './api';
  import { C, MODE_DE, STATE_COLOR, machineColor, fmtNum, fmtMW, dur } from './fmt';
  import type { Station } from './types';
  import { tn } from './names';

  let { o, onpick, onfollow, following = false, onpin }: {
    o: MapObj; onpick: (key: string) => void; onfollow?: () => void; following?: boolean; onpin?: (o: MapObj) => void;
  } = $props();
  const d = $derived(o.data);
  let show3d = $state(false);
  /** Bänder/Rohre nahe der Fabrik: jeder Punkt höchstens 15 m von einer ihrer Maschinen, außerhalb abgeschnitten */
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
  const PT: Record<string, string> = { freight: 'Fracht', fluid: 'Flüssig', empty: 'leer' };
  const KIND: Record<string, string> = { collectible: 'Sammelobjekt', station: '', player: 'Spieler', train: 'Zug', truck: 'Fahrzeug', machine: 'Maschine',
    generator: 'Generator', node: 'Rohstoffknoten', pin: 'Notiz', factory: 'Fabrik' };

  const liveSt = $derived(o.kind === 'station' ? $live?.stations?.[d.id.split('.').pop()] : null);
  const vehName = (id: string) => $live?.trucks.find(t => t.id === id)?.name;

  // Gegenstellen per gemeinsamem Fahrzeug
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
  const stalled = $derived(members.filter(m => m.state === 'steht' && m.block !== 'voll'));
  const key = (s: Station) => 'station:' + s.id.split('.').pop();
  const fillPct = (f: number | null | undefined) => f == null ? null : Math.round(f * 100);
</script>

<div class="det">
  <div class="k">{KIND[o.kind] || (d.kind === 'train' ? 'Zugbahnhof' : 'Truckstation')} · {Math.round(o.x)} / {Math.round(o.y)} m</div>
  <h2>{o.kind === 'machine' ? $tn(d.recipe || d.name) : o.kind === 'pin' ? (d.text.split('\n')[0] || 'Notiz') : (o.label || d.name)}</h2>

  {#if o.kind === 'station'}
    <div class="row"><span class="tag"><span class="dot" style="background:{C[d.mode]}"></span>{MODE_DE[d.mode]}</span>
      {#if liveSt}<span class="tag">{liveSt.status === 'Error' ? '⚠ Fehler' : (liveSt.activity || liveSt.status || 'bereit')}{liveSt.rate ? ' · ' + fmtNum(liveSt.rate) + '/min' : ''}</span>{/if}
    </div>
    {#if d.kind === 'train'}
      <table class="t">
        <thead><tr><th>Plattform</th><th>Ware</th><th class="n">Puffer</th></tr></thead>
        <tbody>
        {#each d.platforms as p}
          <tr><td>{PT[p.type]}<div class="muted small">{p.mode ? MODE_DE[p.mode] : '—'}</div></td>
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
      <table class="t"><thead><tr><th>Ware</th><th class="n">Puffer</th></tr></thead><tbody>
        {#each d.items as i}<tr><td>{$tn(i.item)}</td><td class="n">{fmtNum(i.amount)}</td></tr>
        {:else}<tr><td colspan="2" class="muted">{(d.vehicles || []).length ? 'Puffer gerade leer' : 'Leer. Die Station wurde noch nicht benutzt.'}</td></tr>{/each}
      </tbody></table>
      {#if d.fill != null}<div class="fill"><div class="bar"><i style="width:{d.fill * 100}%;background:{d.fill > .9 ? C.bad : d.fill < .1 ? C.warn : 'var(--text2)'}"></i></div><span class="num">{fillPct(d.fill)} % voll</span></div>{/if}
      <div class="sec"><h3>Per Truck verbunden</h3>
        {#each links as l}
          <button class="lk" onclick={() => onpick(key(l.s))}><span class="dot" style="background:{C[l.s.mode]}"></span><b>{l.s.name}</b></button>
          {#each l.vs as v}
            <div class="via">{vehName(v.id) || v.type} · Runde {dur(v.round / 60)}{#if v.per_min} · bis {fmtNum(v.per_min)}/min{/if}
              {#if v.last > 3 * Math.max(v.round, 60)}<span class="warn"> · seit {dur(v.last / 60)} nicht da</span>{/if}</div>
          {/each}
        {:else}<div class="muted small">Kein Fahrzeug dockt hier an.</div>{/each}
      </div>
    {/if}
    {#if sameItem.length}
      <div class="sec"><h3>{links.length ? 'Gleiche Ware, ohne Verbindung' : $tn(d.items[0].item) + ': Gegenstellen'}</h3>
        {#each sameItem.slice(0, 8) as s}<button class="lk" onclick={() => onpick(key(s))}><span class="dot" style="background:{C[s.mode]}"></span>{s.name}</button>{/each}
      </div>
    {/if}

  {:else if o.kind === 'player'}
    <div class="row"><span class="tag">{d.online === null ? 'Stand des Saves' : d.online ? (d.dead ? 'tot' : 'online') : 'offline'}</span>
      {#if d.hp != null}<span class="tag">HP {d.hp}</span>{/if}{#if d.speed}<span class="tag">{fmtNum(d.speed)} km/h</span>{/if}</div>
    {#if onfollow}
      <button class="btn" class:on={following} onclick={onfollow}>{following ? 'Folgen beenden' : 'Karte folgt ' + d.name}</button>
      {#if d.online !== true && !following}<p class="muted small">{d.name} ist gerade nicht online — die Karte folgt ab dem nächsten Login.</p>{/if}
    {/if}
    {#if d.inventory?.length}
      <table class="t"><thead><tr><th>Inventar</th><th class="n">Menge</th></tr></thead><tbody>
        {#each d.inventory as i}<tr><td>{i.Name}</td><td class="n">{fmtNum(i.Amount)}</td></tr>{/each}</tbody></table>
    {/if}

  {:else if o.kind === 'train' || o.kind === 'truck'}
    <div class="row">
      {#if d.status}<span class="tag">{d.status}</span>{/if}
      {#if d.speed != null}<span class="tag">{fmtNum(d.speed)} km/h</span>{/if}
      {#if d.derailed}<span class="tag bad">entgleist</span>{/if}
      {#if d.fuel === false}<span class="tag bad">kein Treibstoff</span>{/if}
      {#if o.dim}<span class="tag">Position aus dem Save</span>{/if}
    </div>
    {#if d.station}<p>Ziel: <b>{d.station}</b></p>{/if}
    {#if d.cargo}<p>Ladung: {$tn(d.cargo.item)} · {fmtNum(d.cargo.amount)}</p>{/if}
    {#if d.payload}<p>Ladung: {fmtNum(d.payload)} t</p>{/if}
    {#if onfollow}<button class="btn" class:on={following} onclick={onfollow}>{following ? 'Folgen beenden' : 'Karte folgt diesem Fahrzeug'}</button>{/if}
    {#if o.kind === 'truck'}
      <div class="sec"><h3>Route · {route.length} Stationen</h3>
        {#each route as s}<button class="lk" onclick={() => onpick(key(s))}><span class="dot" style="background:{C[s.mode]}"></span>{s.name}</button>
        {:else}<div class="muted small">Keine Station kennt dieses Fahrzeug.</div>{/each}</div>
    {/if}

  {:else if o.kind === 'machine'}
    <div class="row"><span class="tag"><span class="dot" style="background:{machineColor(d)}"></span>{d.state === 'steht' && d.block === 'voll' ? 'wartet (Ausgang voll)' : d.state} · {d.pct} %</span>
      <span class="tag">{$tn(d.name)}</span>{#if d.clock !== 1}<span class="tag">Takt {Math.round(d.clock * 100)} %</span>{/if}
      {#if d.alt}<span class="tag">Alternativrezept</span>{/if}{#if d.purity}<span class="tag">Knoten {d.purity}</span>{/if}</div>
    {#if d.why}<p class:why={d.block !== 'voll'} class:muted={d.block === 'voll'}>{d.why}{d.block === 'voll' ? ' — Puffer, kein Handlungsbedarf' : ''}</p>{/if}
    <table class="t"><thead><tr><th>Ware</th><th class="n">Ist</th><th class="n">Soll /min</th></tr></thead><tbody>
      {#each d.out as p}<tr><td>{$tn(p.item)}</td><td class="n">{fmtNum(p.rate)}</td><td class="n">{fmtNum(p.max)}</td></tr>{/each}
      {#each d.inp as p}<tr><td class="muted">← {$tn(p.item)}</td><td class="n">{fmtNum(p.rate)}</td><td class="n">{fmtNum(p.max)}</td></tr>{/each}
    </tbody></table>
    <p class="muted small">{fmtMW(d.power)} · Netz {d.circuit ?? '—'}{d.by ? ' · gebaut von ' + d.by : ''}{d.since != null ? ' · Zustand seit ' + dur(d.since / 60) : ''}</p>

  {:else if o.kind === 'generator'}
    <div class="row"><span class="tag">{d.producing ? 'erzeugt' : 'steht'}</span><span class="tag">{fmtMW(d.cap)}</span></div>
    {#if d.fuel}<p>Brennstoff: <b>{$tn(d.fuel)}</b>{d.fuel_rate ? ' · ' + fmtNum(d.fuel_rate) + '/min' : ''}</p>{/if}
    {#if d.fuel_minutes != null}<p>Vorrat im Gebäude reicht <b>{dur(d.fuel_minutes)}</b></p>{/if}

  {:else if o.kind === 'node'}
    <div class="row"><span class="tag">{$tn(d.item) || '?'}</span><span class="tag">{({ pure: 'rein', normal: 'normal', impure: 'unrein' } as any)[d.purity] || 'Reinheit unbekannt'}</span>
      <span class="tag">{d.used ? 'belegt' : 'frei'}</span></div>
    {#if d.used}<p>{$tn(d.extractor)} · {fmtNum(d.rate)} /min</p>{/if}

  {:else if o.kind === 'factory'}
    <div class="row"><span class="tag">{d.n} Maschinen</span><span class="tag">{fmtMW(d.power)}</span>
      {#if d.renamed}<span class="tag" title="Automatischer Name: {d.auto}">umbenannt</span>{/if}
      {#if d.status && d.status !== 'aktiv'}<span class="tag">{({ aufbau: 'im Aufbau', puffer: 'Puffer', stillgelegt: 'stillgelegt' } as any)[d.status]}</span>{/if}</div>
    <div class="states">{#each Object.entries(d.states).filter(([s]) => s !== 'steht') as [s, n]}<span><span class="dot" style="background:{STATE_COLOR[s]}"></span>{n} {s}</span>{/each}
      {#if d.full}<span><span class="dot" style="background:#8a857c"></span>{d.full} warten (Ausgang voll)</span>{/if}
      {#if d.starved}<span><span class="dot" style="background:{C.bad}"></span>{d.starved} Materialmangel</span>{/if}</div>
    <div class="grid">
      <div><h3>Liefert</h3>{#each d.out as p}<div class="io"><span>{$tn(p.item)}</span><span class="num">{fmtNum(p.rate)}</span></div>{:else}<div class="muted small">nichts netto</div>{/each}</div>
      <div><h3>Braucht</h3>{#each d.inp as p}<div class="io"><span>{$tn(p.item)}</span><span class="num">{fmtNum(p.rate)}</span></div>{:else}<div class="muted small">nichts von außen</div>{/each}</div>
    </div>
    {#if stalled.length}
      <div class="sec"><h3>Materialmangel</h3>
        {#each stalled.slice(0, 12) as m}<button class="lk" onclick={() => onpick('machine:' + m.id)}><span class="dot" style="background:{C.bad}"></span>{$tn(m.recipe || m.name)}<span class="muted small">&nbsp;{m.why || ''}</span></button>{/each}
      </div>
    {/if}
    <div class="acts">
      <button class="btn" onclick={() => (show3d = true)}>3D-Ansicht</button>
      {#if onpin}<button class="btn" onclick={() => onpin(o)}>Name und Status ändern</button>{/if}
    </div>
    {#if show3d}
      {#await import('./Factory3D.svelte')}
        <p class="muted small">3D-Ansicht lädt …</p>
      {:then F}
        <F.default machines={members} title={d.name} onclose={() => (show3d = false)}
          flow={near(members)} />
      {:catch e}
        <p class="err3d">3D-Ansicht ließ sich nicht laden ({e?.message || e}). Seite neu laden und nochmal versuchen.</p>
      {/await}
    {/if}

  {:else if o.kind === 'collectible'}
    <p>Noch nicht eingesammelt. Höhe {d.pos[2]} m{d.kind === 'droppod' ? ' — Absturzstelle, noch nicht geplündert' : ''}.</p>
    <p class="muted small">Stand des letzten Saves; eingesammelte Objekte verschwinden mit dem nächsten Autosave.</p>
  {:else if o.kind === 'pin'}
    <p class="pre">{d.text}</p>
    <p class="muted small">{d.author} · {new Date(d.t * 1000).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' })}</p>
    {#if onpin}<button class="btn" onclick={() => onpin(o)}>Bearbeiten</button>{/if}
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
