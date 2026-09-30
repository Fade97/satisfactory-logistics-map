<script lang="ts">
  import { series, factory, progress, events, status } from '../lib/api';
  import { fmtNum, SERIES, clock } from '../lib/fmt';
  import LineChart from '../lib/LineChart.svelte';
  import ItemPicker from '../lib/ItemPicker.svelte';
  import { tn } from '../lib/names';

  let range = $state(86400);
  let items = $state<string[]>(JSON.parse(localStorage.getItem('fgmap.histItems') || '[]'));
  let prod = $state<any[]>([]), machines = $state<any[]>([]), growth = $state<Record<string, any[]>>({});
  const all = $derived(($factory?.balance || []).map(b => b.item));

  $effect(() => { localStorage.setItem('fgmap.histItems', JSON.stringify(items)); });
  $effect(() => {
    // Standard: die vier Waren mit der größten Produktion
    if (!items.length && $factory) items = [...$factory.balance].sort((a, b) => b.prod - a.prod).slice(0, 4).map(b => b.item);
  });
  async function load() {
    const since = Date.now() / 1000 - range;
    if (items.length) {
      const r = await series(items.map(i => 'prod:' + i), since);
      prod = items.map((it, i) => ({ key: it, label: $tn(it), points: r.data['prod:' + it] || [], color: SERIES[i % SERIES.length] }));
    } else prod = [];
    const m = await series(['machines:läuft', 'machines:teilweise', 'machines:steht'], since);
    machines = [['läuft', SERIES[2]], ['teilweise', SERIES[4]], ['steht', SERIES[5]]].map(([k, c]) => ({ key: k, label: k, points: m.data['machines:' + k] || [], color: c }));
    const g = await series(['count:*'], Date.now() / 1000 - 400 * 86400);
    growth = g.data;
  }
  $effect(() => { void range; void items.length; load(); });

  const builds = $derived($events.filter(e => e.kind === 'build' || e.kind === 'progress'));
  const G = (k: string) => growth['count:' + k] || [];
  const last = (k: string) => { const g = G(k); return g.length ? g[g.length - 1][1] : null; };
  const delta = (k: string) => { const g = G(k); return g.length > 1 ? g[g.length - 1][1] - g[0][1] : null; };
</script>

<div class="page">
  <h1>Verlauf</h1>
  <p class="src">Minutenwerte der letzten 48 Stunden, danach Stundenmittel für 90 Tage, danach Tageswerte. Aufgezeichnet seit {growth['count:machines']?.[0] ? new Date(growth['count:machines'][0][0] * 1000).toLocaleDateString('de-DE') : 'heute'}.</p>

  <div class="kpis">
    <div class="kpi panel"><div class="v">{fmtNum(($status?.save?.playtime || 0) / 3600)} h</div><div class="l">Spielzeit</div></div>
    <div class="kpi panel"><div class="v">{$factory?.machines.length ?? '–'}</div><div class="l">Maschinen{delta('machines') ? ' · ' + (delta('machines')! > 0 ? '+' : '') + delta('machines') + ' seit Aufzeichnung' : ''}</div></div>
    <div class="kpi panel"><div class="v">{fmtNum(last('rail_km'))} km</div><div class="l">Gleise</div></div>
    <div class="kpi panel"><div class="v">{fmtNum(last('belt_km'))} km</div><div class="l">Förderbänder</div></div>
    <div class="kpi panel"><div class="v">{$progress?.n_schematics ?? '–'}</div><div class="l">Freischaltungen · {$progress?.phase || ''}</div></div>
  </div>

  <div class="seg">
    {#each [[10800, '3 h'], [86400, '24 h'], [172800, '48 h'], [604800, '7 Tage'], [2592000, '30 Tage'], [7776000, '90 Tage']] as [s, l]}
      <button class:on={range === s} onclick={() => (range = +s)}>{l}</button>
    {/each}
  </div>

  <div class="panel card">
    <div class="hd"><h2>Produktion je Ware</h2>
      <div class="pick">
        {#each items as it, i}<span class="chip"><i style="background:{SERIES[i % SERIES.length]}"></i>{$tn(it)}<button onclick={() => (items = items.filter(x => x !== it))} aria-label="{it} entfernen">✕</button></span>{/each}
        {#if items.length < 6}
          <span class="add"><ItemPicker items={all.filter(i => !items.includes(i))} placeholder="Ware hinzufügen" clearOnPick onpick={v => (items = [...items, v])} /></span>
        {/if}
      </div>
    </div>
    <LineChart series={prod} unit="/min" height={260} />
  </div>

  <div class="grid2" style="margin-top:16px">
    <div class="panel card"><h2>Maschinenzustand</h2><LineChart series={machines} unit="Maschinen" height={200} /></div>
    <div class="panel card"><h2>Fabrikwachstum</h2>
      <LineChart series={[{ key: 'm', label: 'Maschinen', points: G('machines') }]} height={200} />
    </div>
  </div>

  <div class="panel card" style="margin-top:16px">
    <h2>Änderungsprotokoll</h2>
    <p class="muted small">Vergleich aufeinanderfolgender Autosaves: gebaute und abgerissene Maschinen, dazu neue Freischaltungen.</p>
    <ol class="log">
      {#each builds as e (e.id)}
        <li><span class="t num">{new Date(e.t * 1000).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' })} {clock(e.t)}</span><span>{e.text}</span></li>
      {:else}<li class="muted">Noch keine Änderungen erfasst. Der erste Vergleich kommt mit dem nächsten Autosave, nach etwa 5 Minuten.</li>{/each}
    </ol>
  </div>
</div>

<style>
  .seg { display: inline-flex; flex-wrap: wrap; margin-bottom: 14px; }
  .seg button { background: var(--plate); border: 1px solid var(--seam); padding: 4px 12px; font-size: 13px; color: var(--text2); margin-right: -1px; }
  .seg button.on { color: #1b1c1e; background: var(--ficsit); border-color: var(--ficsit); }
  .hd { display: flex; flex-wrap: wrap; gap: 10px 20px; align-items: center; margin-bottom: 10px; }
  .hd h2 { margin: 0; }
  .pick { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
  .chip { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--seam); padding: 2px 4px 2px 8px; font-size: 13px; }
  .chip i { width: 12px; height: 3px; }
  .chip button { background: none; border: none; color: var(--dim); font-size: 11px; }
  .add { position: relative; }
  .add { width: 220px; display: inline-flex; }
  .small { font-size: 12px; }
  .log { list-style: none; padding: 0; margin: 8px 0 0; max-height: 400px; overflow: auto; }
  .log li { display: flex; gap: 12px; padding: 5px 0; border-bottom: 1px solid #2c2e31; font-size: 13px; }
  .log .t { color: var(--dim); flex: none; min-width: 90px; }
</style>
