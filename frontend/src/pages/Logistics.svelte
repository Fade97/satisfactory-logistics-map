<script lang="ts">
  import { stations, live, factory, status, storage } from '../lib/api';
  import { matches } from '../lib/fuzzy';
  import ItemPicker from '../lib/ItemPicker.svelte';
  import { toMap } from '../lib/router';
  import { C, MODE_DE, fmtNum, dur, ago } from '../lib/fmt';
  import type { Station } from '../lib/types';
  import { tn, both } from '../lib/names';

  let view = $state<'pruef' | 'routen' | 'zug' | 'fuell' | 'lager' | 'plan' | 'fahrzeuge'>('pruef');
  let sched = $state<any[] | null>(null);
  $effect(() => { if (view === 'pruef') fetch('/api/schedule').then(r => r.json()).then(d => (sched = d)); });
  const VERD: Record<string, [string, string]> = { engpass: ['Engpass', C.bad], knapp: ['knapp', C.warn], ok: ['reicht', C.ok], unbekannt: ['noch nicht gemessen', '#6f6b64'] };
  const schedSorted = $derived((sched || []).flatMap(r => r.flows.map((f: any) => ({ r, f })))
    .sort((a, b) => ['engpass', 'knapp', 'unbekannt', 'ok'].indexOf(a.f.verdict) - ['engpass', 'knapp', 'unbekannt', 'ok'].indexOf(b.f.verdict)
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
    }).sort((a, b) => (a.item || '~').localeCompare(b.item || '~', 'de'));
  });

  const fills = $derived.by(() => {
    if (!S) return [];
    const rows: { s: Station; label: string; fill: number; item: string; mode: string }[] = [];
    for (const s of S.trucks) if (s.fill != null && s.items[0]) rows.push({ s, label: s.name, fill: s.fill, item: s.items[0].item, mode: s.mode });
    for (const s of S.trains) (s.platforms || []).forEach((p, i) => {
      if (p.fill != null && p.items[0]) rows.push({ s, label: s.name + ' · Gleis ' + (i + 1), fill: p.fill, item: p.items[0].item, mode: p.mode || s.mode });
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
  <h1>Logistik</h1>
  <p class="src">{S ? S.trucks.length + ' Truckstationen, ' + S.trains.length + ' Bahnhöfe, ' + S.routes.length + ' Zugfahrpläne · Stand ' + ago($status?.save?.mtime) : 'lädt …'}</p>

  <div class="seg">
    {#each [['pruef', 'Fahrplan-Prüfung'], ['routen', 'Truck-Routen'], ['zug', 'Zugdurchsatz'], ['fuell', 'Füllstände'], ['lager', 'Lager'], ['plan', 'Liniennetz Zug'], ['fahrzeuge', 'Fahrzeuge']] as [k, l]}
      <button class:on={view === k} onclick={() => (view = k as any)}>{l}</button>
    {/each}
  </div>

  {#if view === 'pruef'}
    <div class="panel card tbl">
      <table class="t">
        <thead><tr><th>Route</th><th>Ware</th><th class="n">schafft /min</th><th class="n">Bedarf /min</th><th>Bewertung</th><th class="n hide-m">Runde</th></tr></thead>
        <tbody>
          {#each schedSorted as { r, f }}
            <tr>
              <td>{r.name}<div class="muted small">{r.kind === 'zug' ? 'Zug · ' + r.wagons + ' Wagen' : 'Truck'} · {r.stops.join(' → ')}</div></td>
              <td>{$tn(f.item)}</td>
              <td class="n">{f.cap != null ? fmtNum(f.cap) : '–'}{#if f.moved}<div class="muted small">gemessen {fmtNum(f.moved)}</div>{/if}</td>
              <td class="n">{f.need != null ? fmtNum(f.need) : '–'}</td>
              <td><span class="tag" style="color:{VERD[f.verdict][1]};border-color:{VERD[f.verdict][1]}55">{VERD[f.verdict][0]}</span>
                {#if f.verdict === 'engpass' && f.cap}<div class="muted small">{Math.ceil(f.need / f.cap)}× so viele Fahrzeuge oder kürzere Runde nötig</div>{/if}</td>
              <td class="n hide-m">{r.round ? dur(r.round / 60) : '–'}</td>
            </tr>
          {:else}<tr><td colspan="6" class="muted">lädt …</td></tr>{/each}
        </tbody>
      </table>
      <p class="muted small"><b>Schafft</b> = volle Ladung je Runde ÷ Rundenzeit (Obergrenze). <b>Bedarf</b> = Soll-Verbrauch der Maschinen im Umkreis von 250 m um die Entladestationen.
        Zug-Rundenzeiten werden aus den Live-Daten gemessen (Ankunft am ersten Halt bis zur nächsten) — „noch nicht gemessen“ füllt sich, sobald Züge fahren.</p>
    </div>
  {:else if view === 'routen'}
    <div class="panel card tbl">
      <table class="t">
        <thead><tr><th>Fahrzeug</th><th>Ware</th><th>Stationen</th><th class="n">Runde</th><th class="n">bis /min</th><th class="n hide-m">Verbrauch /min</th></tr></thead>
        <tbody>
          {#each routes as r (r.id)}
            <tr>
              <td>{r.name}<div class="muted small">{r.type}{r.fuel === false ? ' · kein Treibstoff' : ''}{r.stale ? ' · seit ' + dur(r.last / 60) + ' nicht angedockt' : ''}</div></td>
              <td>{$tn(r.item) || '—'}</td>
              <td>{#each r.stops as s}<button class="lk" onclick={() => go(s)}><span class="dot" style="background:{C[s.mode]}"></span>{s.name}</button>{/each}</td>
              <td class="n">{dur(r.round / 60)}</td>
              <td class="n">{r.per_min ? fmtNum(r.per_min) : '—'}</td>
              <td class="n hide-m muted">{r.need != null ? fmtNum(r.need) : '—'}</td>
            </tr>
          {:else}<tr><td colspan="6" class="muted">Keine Truck-Routen im Save.</td></tr>{/each}
        </tbody>
      </table>
      <p class="muted small">„bis /min“ = volle Ladung ÷ Rundenzeit, also die Obergrenze. Wie voll ein Fahrzeug tatsächlich fährt, steht nicht im Save.
        „Verbrauch“ = was alle Maschinen der Fabrik von dieser Ware verbrauchen.</p>
    </div>

  {:else if view === 'zug'}
    <div class="seg small">
      {#each [[6, '6 h'], [24, '24 h'], [168, '7 Tage']] as [h, l]}<button class:on={flowH === h} onclick={() => (flowH = +h)}>{l}</button>{/each}
    </div>
    <div class="panel card tbl">
      <table class="t">
        <thead><tr><th>Bahnhof</th><th>Ware</th><th class="n">beladen /min</th><th class="n">entladen /min</th></tr></thead>
        <tbody>
          {#each Object.entries(trainFlow?.stations || {}).sort((a, b) => a[0].localeCompare(b[0], 'de')) as [st, items]}
            {#each Object.entries(items) as [it, v], i}
              <tr class:click={i === 0} onclick={() => { const s = S?.trains.find(x => x.name === st); if (s) go(s); }}>
                <td>{i === 0 ? st : ''}</td><td>{$tn(it)}</td>
                <td class="n">{v['+'] ? fmtNum(v['+']) : '–'}</td><td class="n">{v['-'] ? fmtNum(v['-']) : '–'}</td></tr>
            {/each}
          {:else}
            <tr><td colspan="4" class="muted">Noch keine Messwerte. Der Durchsatz wird ab jetzt aus den Live-Daten gezählt, wenn ein Zug an einem Bahnhof steht und sich seine Ladung ändert — die Tabelle füllt sich, sobald jemand spielt (bei pausiertem Server fahren keine Züge).</td></tr>
          {/each}
        </tbody>
      </table>
      <p class="muted small">Gemessen, nicht geschätzt: Ladungsänderung angedockter Züge zwischen zwei Live-Abfragen (alle 5 s), gemittelt über den gewählten Zeitraum inklusive Pausen der Züge.</p>
    </div>
  {:else if view === 'lager'}
    <div class="lh2"><input class="field" style="max-width:280px" type="search" bind:value={lagerQ} placeholder="Ware filtern, z. B. Schrauben" />
      <span class="muted small">{($storage || []).length} Container und Tanks · {empty} leer · {($storage || []).filter(c => (c.fill ?? 0) > .98).length} voll</span></div>
    <div class="panel card tbl">
      <table class="t">
        <thead><tr><th>Ware</th><th class="n">Bestand</th><th class="n">Lager</th><th class="n">davon voll</th></tr></thead>
        <tbody>
          {#each lager as e (e.item)}
            <tr class="click" onclick={() => (lagerOpen = lagerOpen === e.item ? null : e.item)}>
              <td>{$tn(e.item)}</td><td class="n">{fmtNum(e.amount)}</td><td class="n">{e.n}</td><td class="n">{e.full || '–'}</td></tr>
            {#if lagerOpen === e.item}
              <tr class="exp"><td colspan="4"><div class="lg">
                {#each e.list.sort((a, b) => (b.fill ?? 0) - (a.fill ?? 0)) as c}
                  <button class="lk" onclick={() => toMap('', c.pos[0], c.pos[1])}>
                    <span class="bar mini"><i style="width:{(c.fill ?? 0) * 100}%;background:{(c.fill ?? 0) > .98 ? C.bad : '#c3bfb7'}"></i></span>
                    {fmtNum(c.items.find((i: any) => i.item === e.item)?.amount)} · {c.cls.includes('Tank') ? 'Tank' : 'Container'} · {c.pos[0]} / {c.pos[1]} · {c.z} m</button>
                {/each}
              </div></td></tr>
            {/if}
          {/each}
        </tbody>
      </table>
      <p class="muted small">Stand des letzten Saves. Ein volles Lager meldet sich nur, wenn davor Maschinen stauen — ein volles Endlager ohne Zulauf ist gewollt.</p>
    </div>
  {:else if view === 'fuell'}
    {#if problems.length}
      <div class="panel card warnbox"><h2>Braucht Aufmerksamkeit</h2>
        {#each problems as p}
          <button class="lk" onclick={() => go(p.s)}><span class="dot" style="background:{C.bad}"></span>{p.label}
            <span class="muted">{p.mode === 'load' ? 'fast voll: Abholung reicht nicht' : 'leer: Anlieferung reicht nicht'} · {$tn(p.item)}</span></button>
        {/each}
      </div>
    {/if}
    <div class="fills">
      {#each fills.sort((a, b) => b.fill - a.fill) as r}
        <button class="fr" onclick={() => go(r.s)}>
          <span class="nm">{r.label}<span class="muted small">{MODE_DE[r.mode]} · {$tn(r.item)}</span></span>
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
            <div class="lh"><span class="lbadge" style="background:{l.color}">{l.r.name}</span>{#if !l.r.self_driving}<span class="muted small">Autopilot aus</span>{/if}</div>
            <div class="track" style="--c:{l.color}">
              {#each l.stops as s, i}
                <button class="stop" class:shared={s.shared} onclick={() => s.st && go(s.st)}>
                  <span class="node"></span>
                  <span class="sn">{s.name}</span>
                  {#if trainAt(s.ident).length}<span class="tr">▶ Zug hier</span>{/if}
                </button>
              {/each}
              <span class="loop" title="Fahrplan beginnt wieder am Anfang">↺</span>
            </div>
          </div>
        {:else}<p class="muted">Keine Zugfahrpläne mit mindestens zwei Halten.</p>{/each}
        <p class="muted small">Umrandete Halte werden von mehreren Linien angefahren. Die Reihenfolge ist die des Fahrplans, nicht der Streckenverlauf.</p>
      </div>
    {/if}

  {:else}
    <div class="panel card tbl">
      <table class="t">
        <thead><tr><th>Name</th><th>Typ</th><th>Zustand</th><th class="n">Tempo</th><th class="hide-m">Ladung</th></tr></thead>
        <tbody>
          {#each [...($live?.trains || []).map(t => ({ ...t, typ: 'Zug', k: 'train:' + t.name })), ...($live?.trucks || []).map(t => ({ ...t, typ: t.type, k: 'truck:' + (t.id || t.name) }))] as v}
            <tr class="click" onclick={() => toMap(v.k, v.pos[0] / 100, v.pos[1] / 100)}>
              <td>{v.name}</td><td>{v.typ}</td>
              <td>{(v as any).derailed ? '⚠ entgleist' : (v as any).fuel === false ? '⚠ kein Treibstoff' : (v as any).status || ((v as any).autopilot ? 'Autopilot' : '—')}</td>
              <td class="n">{v.speed != null ? fmtNum(v.speed) + ' km/h' : '—'}</td>
              <td class="hide-m">{(v as any).cargo ? $tn((v as any).cargo.item) + ' ' + fmtNum((v as any).cargo.amount) : (v as any).payload ? fmtNum((v as any).payload) + ' t' : '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
      {#if $live?.source === 'save'}<p class="muted small">Live-Daten fehlen gerade — Positionen und Ladung stammen aus dem letzten Save.</p>{/if}
      <p class="muted small">Drohnen: Auf diesem Server gibt es noch keine Drohnenhäfen. Sobald einer gebaut ist, erscheinen sie hier.</p>
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
