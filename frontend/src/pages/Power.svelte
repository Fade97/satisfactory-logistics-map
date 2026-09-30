<script lang="ts">
  import { factory, series, status } from '../lib/api';
  import { toMap } from '../lib/router';
  import { fmtMW, fmtNum, dur, C, SERIES, ago } from '../lib/fmt';
  import { CIRCUIT_COLORS } from '../lib/scene';
  import LineChart from '../lib/LineChart.svelte';
  import { tn } from '../lib/names';

  const f = $derived($factory);
  const circuits = $derived((f?.circuits || []).filter(c => (c.cap > 0 || c.n_mach > 0) && c.id !== -1));
  const nopower = $derived((f?.machines || []).filter(m => m.nopower));
  let range = $state(86400);
  let hist = $state<Record<number, any[]>>({});

  async function load() {
    const out: Record<number, any[]> = {};
    for (const c of circuits.slice(0, 6)) {
      const k = 'power:' + c.id + ':';
      const r = await series([k + 'prod', k + 'use', k + 'cap'], Date.now() / 1000 - range);
      out[c.id] = [
        { key: 'use', label: 'Verbrauch', points: r.data[k + 'use'] || [], color: SERIES[0] },
        { key: 'cap', label: 'Kapazität', points: r.data[k + 'cap'] || [], color: SERIES[1], dash: true },
      ];
    }
    hist = out;
  }
  $effect(() => { void range; void circuits.length; load(); });

  const gens = $derived.by(() => {
    const m = new Map<string, { fuel: string; n: number; cap: number; rate: number; running: number; minLeft: number | null; list: any[] }>();
    for (const g of f?.generators || []) {
      const k = g.name + '|' + (g.fuel || '—');
      const e = m.get(k) || { fuel: g.fuel || '—', n: 0, cap: 0, rate: 0, running: 0, minLeft: null, list: [] };
      e.n++; e.cap += g.cap; e.rate += g.producing ? g.fuel_rate || 0 : 0; if (g.producing) e.running++;
      if (g.fuel_minutes != null) e.minLeft = e.minLeft == null ? g.fuel_minutes : Math.min(e.minLeft, g.fuel_minutes);
      e.list.push(g); m.set(k, e);
    }
    return [...m.entries()].map(([k, v]) => ({ name: k.split('|')[0], ...v })).sort((a, b) => b.cap - a.cap);
  });
  const fuelBalance = $derived.by(() => {
    const b = new Map((f?.balance || []).map(x => [x.item, x]));
    return gens.filter(g => g.fuel !== '—').map(g => {
      const x = b.get(g.fuel);
      // Verbrauch der Ware ohne die Kraftwerke selbst = was andere Maschinen abzweigen
      const other = Math.max(0, (x?.cons ?? 0) - g.rate);
      return { fuel: g.fuel, need: g.rate, other, prod: x?.prod ?? 0 };
    });
  });
  const load_ = (c: any) => c.cap ? c.use / c.cap : 0;
</script>

<div class="page">
  <h1>Strom</h1>
  <p class="src">{f ? (f.source === 'frm' ? 'Live-Werte je Netz' : 'Aus dem Save ' + ago($status?.save?.mtime) + ' — Verbrauch geschätzt aus Laufzeit × Nennleistung') : 'lädt …'}</p>

  {#if nopower.length}
    <div class="panel card warnbox">
      <h2>Ohne Stromanschluss · {nopower.length} Maschinen</h2>
      <p class="muted small">Diese Maschinen hängen an keinem Stromnetz und laufen deshalb nicht.</p>
      <div class="np">
        {#each nopower as m}<button class="lk" onclick={() => toMap('machine:' + m.id, m.pos[0], m.pos[1])}>{$tn(m.name)}{m.recipe ? ' · ' + $tn(m.recipe) : ''} <span class="muted">{m.pos[0]} / {m.pos[1]}</span></button>{/each}
      </div>
    </div>
  {/if}
  <div class="nets">
    {#each circuits as c, i (c.id)}
      {@const pct = load_(c)}
      <div class="panel card net">
        <div class="hd"><span class="sw" style="background:{CIRCUIT_COLORS[Math.abs(c.id) % CIRCUIT_COLORS.length]}"></span><h2>Netz {c.id}</h2>
          {#if c.fuse}<span class="tag bad">⚠ Sicherung ausgelöst</span>{/if}
          <span class="muted small">{c.n_mach} Verbraucher{c.n_gen != null ? ' · ' + c.n_gen + ' Generatoren' : ''}</span></div>
        <div class="big">
          <div><span class="v num">{fmtMW(c.use)}</span><span class="l">Verbrauch</span></div>
          <div><span class="v num">{fmtMW(c.cap)}</span><span class="l">Kapazität</span></div>
          <div><span class="v num" style="color:{c.cap - c.use < 0 ? C.bad : 'inherit'}">{fmtMW(c.cap - c.use)}</span><span class="l">Reserve</span></div>
          <div><span class="v num muted">{fmtMW(c.max_use)}</span><span class="l">Spitzenbedarf</span></div>
        </div>
        <div class="meter" role="meter" aria-valuenow={Math.round(pct * 100)} aria-valuemin="0" aria-valuemax="100" aria-label="Auslastung">
          <i style="width:{Math.min(100, pct * 100)}%;background:{pct > .95 ? C.bad : pct > .8 ? C.warn : 'var(--ficsit)'}"></i>
          {#if c.cap && c.max_use}<b style="left:{Math.min(100, c.max_use / c.cap * 100)}%" title="Spitzenbedarf, wenn alle Maschinen voll laufen"></b>{/if}
        </div>
        <div class="muted small">{Math.round(pct * 100)} % ausgelastet{c.max_use > c.cap ? ' · Spitzenbedarf übersteigt Kapazität um ' + fmtMW(c.max_use - c.cap) : ''}</div>
        {#if c.battery_cap}
          <div class="bat"><span>Batterie</span><div class="meter sm"><i style="width:{c.battery}%;background:{C.ok}"></i></div><span class="num">{Math.round(c.battery)} %</span>
            {#if c.battery_empty && c.battery_empty !== '00:00:00'}<span class="muted">leer in {c.battery_empty}</span>{/if}</div>
        {/if}
        {#if hist[c.id]}<div class="ch"><LineChart series={hist[c.id]} unit="MW" height={170} area /></div>{/if}
      </div>
    {:else}<p class="muted">Keine Stromnetze gefunden.</p>{/each}
  </div>
  <div class="seg">
    {#each [[21600, '6 h'], [86400, '24 h'], [604800, '7 Tage'], [2592000, '30 Tage']] as [s, l]}<button class:on={range === s} onclick={() => (range = +s)}>{l}</button>{/each}
  </div>

  <div class="grid2" style="margin-top:16px">
    <div class="panel card">
      <h2>Kraftwerke</h2>
      <table class="t">
        <thead><tr><th>Typ</th><th>Brennstoff</th><th class="n">Anzahl</th><th class="n">Leistung</th><th class="n">Bedarf /min</th><th class="n">Puffer reicht</th></tr></thead>
        <tbody>
          {#each gens as g}
            <tr class="click" onclick={() => toMap('generator:' + g.list[0].id, g.list[0].pos[0], g.list[0].pos[1])}>
              <td>{$tn(g.name)}</td><td>{$tn(g.fuel)}</td><td class="n">{g.running}/{g.n}</td><td class="n">{fmtMW(g.cap)}</td>
              <td class="n">{g.rate ? fmtNum(g.rate) : '—'}</td>
              <td class="n" style="color:{g.minLeft != null && g.minLeft < 60 ? C.warn : 'inherit'}">{g.minLeft != null ? dur(g.minLeft) : '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
      <p class="muted small">„Puffer reicht“ = kürzeste Laufzeit eines Generators aus seinem eigenen Brennstofflager, ohne Nachschub.</p>
    </div>
    <div class="panel card">
      <h2>Brennstoff-Versorgung</h2>
      {#each fuelBalance as b}
        {@const ok = b.prod >= (b.need + b.other) * .98}
        <div class="fb"><span>{$tn(b.fuel)}</span>
          <span class="num">{fmtNum(b.prod)} erzeugt / {fmtNum(b.need)} verbrannt{b.other > .5 ? ' + ' + fmtNum(b.other) + ' in Maschinen' : ''}</span>
          <span class="tag" style="color:{ok ? C.ok : C.warn};border-color:{ok ? '#2b5a44' : '#5a4b1f'}">{ok ? 'gedeckt' : 'Lager schrumpft'}</span></div>
      {:else}<p class="muted">Keine Brennstoff-Kraftwerke.</p>{/each}
      <p class="muted small">Vergleicht die Produktion der Ware mit dem Verbrauch aller laufenden Generatoren. Liegt die Produktion darunter, zehren die Kraftwerke vom Lager.</p>
    </div>
  </div>
</div>

<style>
  .warnbox { border-left: 3px solid var(--bad); margin-bottom: 16px; }
  .np { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 0 16px; }
  .lk { background: none; border: none; text-align: left; padding: 3px 0; font-size: 13px; }
  .lk:hover { color: var(--ficsit); }
  .nets { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); }
  .hd { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }
  .hd h2 { margin: 0; }
  .sw { width: 14px; height: 4px; }
  .tag.bad { color: var(--bad); border-color: var(--bad); }
  .big { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 10px; }
  .big div { display: flex; flex-direction: column; }
  .v { font-family: var(--cond); font-weight: 700; font-size: 24px; line-height: 1.1; }
  .l { color: var(--dim); font-size: 12px; }
  .meter { height: 10px; background: #34363a; position: relative; margin-bottom: 4px; }
  .meter i { position: absolute; left: 0; top: 0; bottom: 0; }
  .meter b { position: absolute; top: -3px; bottom: -3px; width: 2px; background: var(--text); }
  .meter.sm { height: 6px; flex: 1; margin: 0; }
  .bat { display: flex; align-items: center; gap: 10px; font-size: 13px; margin-top: 10px; }
  .ch { margin-top: 12px; }
  .small { font-size: 12px; }
  .seg { display: inline-flex; margin-top: 10px; }
  .seg button { background: var(--plate); border: 1px solid var(--seam); padding: 4px 12px; font-size: 13px; color: var(--text2); margin-right: -1px; }
  .seg button.on { background: var(--ficsit); color: #1b1c1e; border-color: var(--ficsit); }
  .fb { display: grid; grid-template-columns: 1fr auto auto; gap: 12px; align-items: center; padding: 6px 0; border-bottom: 1px solid #2c2e31; font-size: 13px; }
  @media (max-width: 760px) { .nets { grid-template-columns: 1fr; } .big { grid-template-columns: repeat(2, 1fr); } .fb { grid-template-columns: 1fr; gap: 2px; } }
</style>
