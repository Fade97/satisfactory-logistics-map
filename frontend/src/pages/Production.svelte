<script lang="ts">
  import { factory, nodes, status, sink } from '../lib/api';
  import { toMap } from '../lib/router';
  import { fmtNum, fmtMW, STATE_COLOR, machineColor, C, dur, ago } from '../lib/fmt';
  import LineChart from '../lib/LineChart.svelte';
  import { matches } from '../lib/fuzzy';
  import { series } from '../lib/api';
  import { tn, both } from '../lib/names';
  import { t, tr, lx, locale } from '../lib/i18n';

  let view = $state<'bilanz' | 'stehend' | 'fabriken' | 'knoten'>('bilanz');
  let q = $state('');
  let sortK = $state<'item' | 'net' | 'prod' | 'cons'>('net');
  let sortDir = $state(1);
  let only = $state<'alle' | 'mangel' | 'ueberschuss'>('alle');
  let open = $state<string | null>(null);
  let hist = $state<any>(null);

  const f = $derived($factory);
  const counts = $derived.by(() => {
    const c: Record<string, number> = {};
    for (const m of f?.machines || []) c[m.state] = (c[m.state] || 0) + 1;
    return c;
  });
  const bal = $derived.by(() => {
    const rows = (f?.balance || []).map(b => ({ ...b, net: b.prod - b.cons, net_max: b.prod_max - b.cons_max }))
      .filter(b => matches(q, both(b.item)))
      .filter(b => only === 'alle' || (only === 'mangel' ? b.net < -0.05 : b.net > 0.05));
    const k = sortK;
    return rows.sort((a, b) => k === 'item' ? a.item.localeCompare(b.item, locale()) * sortDir : ((a as any)[k] - (b as any)[k]) * sortDir);
  });
  function sortBy(k: typeof sortK) { if (sortK === k) sortDir = -sortDir; else { sortK = k; sortDir = k === 'item' ? 1 : k === 'net' ? 1 : -1; } }

  let showFull = $state(false);
  const facOf = $derived(new Map((f?.factories || []).flatMap(x => (x.ids || []).map(id => [id, x] as const))));
  const starvedN = $derived((f?.machines || []).filter(m => m.state === 'steht' && m.block !== 'voll').length);
  const stalled = $derived((f?.machines || []).filter(m => (m.state === 'steht' || m.state === 'teilweise') && (showFull || m.block !== 'voll'))
    .filter(m => matches(q, both(m.recipe || m.name), m.why, ...m.out.map(o => both(o.item)))));
  const reasons = $derived.by(() => {
    const r = new Map<string, number>();
    for (const m of stalled) if (m.state === 'steht') { const k = m.why || tr('Grund unbekannt'); r.set(k, (r.get(k) || 0) + 1); }
    return [...r.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10);
  });
  const facs = $derived((f?.factories || []).filter(x => matches(q, x.name, ...x.out.map(o => both(o.item)))));
  const nodeStats = $derived.by(() => {
    const m = new Map<string, { item: string; pure: number; normal: number; impure: number; used: number; free: number; list: any[] }>();
    for (const n of $nodes || []) {
      if (!n.item || n.kind === 'geyser') continue;
      const e = m.get(n.item) || { item: n.item, pure: 0, normal: 0, impure: 0, used: 0, free: 0, list: [] };
      if (n.purity) (e as any)[n.purity]++;
      n.used ? e.used++ : e.free++; e.list.push(n); m.set(n.item, e);
    }
    return [...m.values()].filter(e => matches(q, both(e.item))).sort((a, b) => a.item.localeCompare(b.item, locale()));
  });
  const PUR: Record<string, string> = { pure: 'rein', normal: 'normal', impure: 'unrein' };

  async function toggle(item: string) {
    open = open === item ? null : item; hist = null;
    if (open) {
      const r = await series(['prod:' + item, 'cons:' + item], Date.now() / 1000 - 86400);
      hist = [{ key: 'p', label: tr('Produktion'), points: r.data['prod:' + item] || [] },
              { key: 'c', label: tr('Verbrauch'), points: r.data['cons:' + item] || [] }];
    }
  }
  const machinesFor = (item: string) => (f?.machines || []).filter(m => m.out.some(o => o.item === item) || m.inp.some(i => i.item === item));
</script>

<div class="page">
  <h1>{$t('Produktion')}</h1>
  <p class="src">{f ? (f.source === 'frm' ? $t('Live-Werte') : $t('Aus dem Save {ago} — Ist-Raten sind Mittel über die letzten 5–10 Minuten', { ago: ago($status?.save?.mtime) })) : $t('lädt …')}</p>

  <div class="kpis">
    <div class="kpi panel"><div class="v">{f?.machines.length ?? '–'}</div><div class="l">{$t('Maschinen')}</div></div>
    <div class="kpi panel"><div class="v" style="color:{C.ok}">{counts['läuft'] ?? 0}</div><div class="l">{$t('laufen voll')}</div></div>
    <div class="kpi panel"><div class="v" style="color:{C.warn}">{counts['teilweise'] ?? 0}</div><div class="l">{$t('laufen teilweise')}</div></div>
    <div class="kpi panel"><div class="v" style="color:{C.bad}">{starvedN}</div><div class="l">{$t('Materialmangel')}</div></div>
    <div class="kpi panel"><div class="v muted">{(counts['steht'] ?? 0) - starvedN}</div><div class="l">{$t('warten, Ausgang voll')}</div></div>
    <div class="kpi panel"><div class="v">{f?.factories.length ?? '–'}</div><div class="l">{$t('Fabriken erkannt')}</div></div>
    {#if $sink}
      <div class="kpi panel" title="AWESOME Sink">
        <div class="v num">{$sink.coupons}<small> {$t('Coupons')}</small></div>
        {#if $sink.pct != null}<div class="bar" style="margin:4px 0"><i style="width:{$sink.pct * 100}%;background:var(--ficsit)"></i></div>{/if}
        <div class="l">{$sink.per_min != null ? $t('{n} Punkte/min', { n: fmtNum($sink.per_min) }) + ' · ' : ''}{$sink.to_coupon != null ? $t('{n} bis zum nächsten', { n: fmtNum($sink.to_coupon) }) : $t('{n} Punkte', { n: fmtNum($sink.points) })}</div>
      </div>
    {/if}
  </div>

  <div class="bar2">
    <div class="seg">
      {#each [['bilanz', $t('Warenbilanz')], ['stehend', $t('Materialmangel')], ['fabriken', $t('Fabriken')], ['knoten', $t('Rohstoffknoten')]] as [k, l]}
        <button class:on={view === k} onclick={() => (view = k as any)}>{l}</button>
      {/each}
    </div>
    <input class="field srch" type="search" bind:value={q} placeholder={$t('Ware oder Fabrik filtern, z. B. Kupfer')} />
  </div>

  {#if view === 'bilanz'}
    <div class="seg small">
      {#each [['alle', $t('Alle Waren')], ['mangel', $t('Nur Mangel')], ['ueberschuss', $t('Nur Überschuss')]] as [k, l]}<button class:on={only === k} onclick={() => (only = k as any)}>{l}</button>{/each}
    </div>
    <div class="panel card tbl">
      <table class="t">
        <thead><tr>
          <th class="sort" onclick={() => sortBy('item')}>{$t('Ware')}</th>
          <th class="n sort" onclick={() => sortBy('prod')}>{$t('Produktion /min')}</th>
          <th class="n sort" onclick={() => sortBy('cons')}>{$t('Verbrauch /min')}</th>
          <th class="n sort" onclick={() => sortBy('net')}>{$t('Saldo')}</th>
          <th class="hide-m">{$t('Auslastung')}</th>
          <th class="n hide-m">{$t('Soll-Saldo')}</th>
        </tr></thead>
        <tbody>
          {#each bal as b (b.item)}
            <tr class="click" onclick={() => toggle(b.item)}>
              <td>{$tn(b.item)} <span class="muted small">{b.n_prod}↑ {b.n_cons}↓</span></td>
              <td class="n">{fmtNum(b.prod)}</td>
              <td class="n">{fmtNum(b.cons)}</td>
              <td class="n" style="color:{b.net < -0.05 ? C.bad : b.net > 0.05 ? C.ok : 'inherit'}">{b.net > 0 ? '+' : ''}{fmtNum(b.net)}</td>
              <td class="hide-m"><div class="bar" title={$t('Ist-Produktion im Verhältnis zur möglichen')}><i style="width:{b.prod_max ? Math.min(100, b.prod / b.prod_max * 100) : 0}%;background:var(--text2)"></i></div></td>
              <td class="n hide-m muted">{b.net_max > 0 ? '+' : ''}{fmtNum(b.net_max)}</td>
            </tr>
            {#if open === b.item}
              <tr class="exp"><td colspan="6">
                <div class="expbox">
                  <div class="ch"><h3>{$t('Letzte 24 Stunden')}</h3>{#if hist}<LineChart series={hist} unit="/min" height={180} />{:else}<p class="muted">{$t('lädt …')}</p>{/if}</div>
                  <div class="ms"><h3>{$t('Maschinen')}</h3>
                    {#each machinesFor(b.item).slice(0, 14) as m}
                      {@const rn = fmtNum((m.out.find(o => o.item === b.item) || m.inp.find(i => i.item === b.item))!.rate)}
                      <button class="lk" onclick={() => toMap('machine:' + m.id, m.pos[0], m.pos[1])}>
                        <span class="dot" style="background:{machineColor(m)}"></span>{$tn(m.recipe || m.name)}
                        <span class="muted">{m.out.some(o => o.item === b.item) ? $t('erzeugt {n}/min', { n: rn }) : $t('braucht {n}/min', { n: rn })}</span></button>
                    {/each}
                  </div>
                </div>
              </td></tr>
            {/if}
          {:else}<tr><td colspan="6" class="muted">{$t('Keine Ware passt zum Filter.')}</td></tr>{/each}
        </tbody>
      </table>
    </div>

  {:else if view === 'stehend'}
    <div class="grid2">
      <div class="panel card"><h2>{$t('Häufigste Gründe')}</h2>
        <label class="tg"><input type="checkbox" bind:checked={showFull} /> {$t('auch Maschinen mit vollem Ausgang zeigen')}</label>
        {#each reasons as [r, n]}
          <button class="reason" onclick={() => (q = r.replace(/^[^:]+: /, ''))}><span class="num">{n}×</span>{$lx(r)}</button>
        {:else}<p class="muted">{$t('Keine stehenden Maschinen.')}</p>{/each}
        <p class="muted small">{$t('„Ausgang voll“ heißt meist: Abnehmer fehlt oder Band zu langsam. „fehlt“: Zufuhr reicht nicht.')}
          {$t('Der Grund wird aus den Maschinen-Inventaren im Save geschätzt.')}</p>
      </div>
    </div>
    <div class="panel card tbl" style="margin-top:16px">
      <table class="t">
        <thead><tr><th>{$t('Maschine')}</th><th>{$t('Zustand')}</th><th>{$t('Grund')}</th><th class="n hide-m">{$t('seit')}</th><th class="hide-m">{$t('Fabrik')}</th></tr></thead>
        <tbody>
          {#each stalled.slice(0, 400) as m (m.id)}
            {@const fc = facOf.get(m.id)}
            <tr class="click" onclick={() => toMap('machine:' + m.id, m.pos[0], m.pos[1])}>
              <td>{$tn(m.recipe || m.name)}<div class="muted small">{$tn(m.name)}</div></td>
              <td><span class="dot" style="background:{machineColor(m)}"></span> {$t(m.state)} {m.pct} %</td>
              <td>{m.why ? $lx(m.why) : '—'}</td>
              <td class="n hide-m">{m.since != null ? dur(m.since / 60) : '—'}</td>
              <td class="hide-m muted">{fc?.name ? $lx(fc.name) : '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

  {:else if view === 'fabriken'}
    <p class="muted">{$t('Maschinen im Abstand von höchstens 60 m bilden eine Fabrik; der Name kommt vom Hauptprodukt. Umbenennen geht auf der Karte in der Fabrik-Detailansicht.')}</p>
    <div class="fgrid">
      {#each facs as x (x.key)}
        <button class="panel fc" onclick={() => toMap('factory:' + x.key, x.center[0], x.center[1])}>
          <h3>{$lx(x.name)}</h3>
          <div class="stbar">{#each ['läuft', 'teilweise'] as s}{#if x.states[s]}<i style="flex:{x.states[s]};background:{STATE_COLOR[s]}" title="{x.states[s]} {$t(s)}"></i>{/if}{/each}{#if x.full}<i style="flex:{x.full};background:#8a857c" title={$t('{n} warten (Ausgang voll)', { n: x.full })}></i>{/if}{#if x.starved}<i style="flex:{x.starved};background:{C.bad}" title={$t('{n} Materialmangel', { n: x.starved })}></i>{/if}</div>
          <div class="muted small">{$t('{n} Maschinen', { n: x.n })} · {fmtMW(x.power)}{x.starved ? ' · ' + $t('{n} mit Materialmangel', { n: x.starved }) : ''}</div>
          <div class="io">{#each x.out.slice(0, 3) as o}<span>{$tn(o.item)} <b class="num">{fmtNum(o.rate)}</b></span>{/each}</div>
        </button>
      {/each}
    </div>

  {:else}
    <div class="panel card tbl">
      <table class="t">
        <thead><tr><th>{$t('Rohstoff')}</th><th class="n">{$t('rein')}</th><th class="n">{$t('normal')}</th><th class="n">{$t('unrein')}</th><th class="n">{$t('belegt')}</th><th class="n">{$t('frei')}</th></tr></thead>
        <tbody>
          {#each nodeStats as e (e.item)}
            <tr class="click" onclick={() => (open = open === e.item ? null : e.item)}>
              <td>{$tn(e.item)}</td><td class="n">{e.pure}</td><td class="n">{e.normal}</td><td class="n">{e.impure}</td>
              <td class="n">{e.used}</td><td class="n" style="color:{e.free ? C.ok : 'inherit'}">{e.free}</td></tr>
            {#if open === e.item}
              <tr class="exp"><td colspan="6"><div class="nodes">
                {#each e.list.filter(n => !n.used).sort((a, b) => (b.purity === 'pure' ? 2 : b.purity === 'normal' ? 1 : 0) - (a.purity === 'pure' ? 2 : a.purity === 'normal' ? 1 : 0)) as n}
                  <button class="lk" onclick={() => toMap('node:' + n.id, n.pos[0], n.pos[1])}>{$t('frei')} · {PUR[n.purity] ? $t(PUR[n.purity]) : '?'} · {n.pos[0]} / {n.pos[1]} m</button>
                {/each}
              </div></td></tr>
            {/if}
          {/each}
        </tbody>
      </table>
      <p class="muted small">{$t('Reinheit nach Community-Daten (satisfactory-savegame-prometheus-exporter, MIT). Freie Knoten zum Anzeigen anklicken; auf der Karte lässt sich die Ebene „Rohstoffknoten“ einschalten.')}</p>
    </div>
  {/if}
</div>

<style>
  .bar2 { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-bottom: 12px; }
  .srch { max-width: 260px; }
  .seg { display: inline-flex; flex-wrap: wrap; }
  .seg button { background: var(--plate); border: 1px solid var(--seam); padding: 6px 12px; font-family: var(--cond); font-weight: 600; font-size: 15px; color: var(--text2); margin-right: -1px; }
  .seg button.on { color: #1b1c1e; background: var(--ficsit); border-color: var(--ficsit); position: relative; }
  .seg.small { margin-bottom: 10px; }
  .seg.small button { font-size: 13px; padding: 3px 10px; font-family: var(--body); font-weight: 500; }
  .tbl { padding: 4px 8px 8px; overflow-x: auto; }
  .small { font-size: 12px; }
  td .bar { width: 120px; margin-top: 7px; }
  .exp td { background: var(--steel); }
  .expbox { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; padding: 8px 4px; }
  .ch, .ms { min-width: 0; }
  .lk { display: flex; gap: 7px; align-items: center; width: 100%; background: none; border: none; padding: 3px 0; text-align: left; font-size: 13px; flex-wrap: wrap; }
  .lk:hover { color: var(--ficsit); }
  .reason { display: flex; gap: 10px; width: 100%; background: none; border: none; text-align: left; padding: 4px 0; }
  .reason .num { color: var(--dim); min-width: 36px; text-align: right; }
  .reason:hover { color: var(--ficsit); }
  .fgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 12px; }
  .tg { display: flex; gap: 8px; align-items: center; font-size: 13px; color: var(--text2); margin-bottom: 8px; }
  .tg input { accent-color: var(--ficsit); }
  .kpi small { font-size: 15px; color: var(--dim); }
  .fc { text-align: left; border: none; padding: 12px 14px; display: flex; flex-direction: column; gap: 6px; }
  .fc:hover h3 { color: var(--ficsit); }
  .stbar { display: flex; height: 6px; gap: 2px; }
  .stbar i { display: block; }
  .io { display: flex; flex-direction: column; font-size: 12.5px; color: var(--text2); }
  .io span { display: flex; justify-content: space-between; }
  .nodes { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }
  @media (max-width: 760px) { .expbox { grid-template-columns: 1fr; } .srch { max-width: none; } }
</style>
