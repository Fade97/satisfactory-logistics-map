<script lang="ts">
  // „Was ist los?“ — Lage auf einen Blick: Mangel, Strom, Störungen, Änderungen seit dem letzten Besuch.
  import { onDestroy } from 'svelte';
  import { factory, live, status, stations, events, progress } from '../lib/api';
  import { toMap, go } from '../lib/router';
  import { C, fmtNum, fmtMW, ago, clock, dur } from '../lib/fmt';
  import { tn } from '../lib/names';
  import { t, tr, lx, lxr, locale } from '../lib/i18n';

  // Letzter Besuch: beim Verlassen der Seite speichern, nicht beim Öffnen — sonst ist „seit“ immer jetzt
  const LAST = 'fgmap.lastVisit';
  const since = +(localStorage.getItem(LAST) || 0) || Math.floor(Date.now() / 1000) - 86400;
  onDestroy(() => localStorage.setItem(LAST, String(Math.floor(Date.now() / 1000))));
  addEventListener('beforeunload', () => localStorage.setItem(LAST, String(Math.floor(Date.now() / 1000))));

  const f = $derived($factory);
  const power = $derived((f?.circuits || []).filter(c => c.cap > 0));
  // Mangel: Ware wird verbraucht, aber weniger erzeugt — nach Maschinen gewichtet, die darauf warten
  const shortages = $derived.by(() => {
    if (!f) return [];
    const waiting = new Map<string, number>();
    for (const m of f.machines) if (m.state === 'steht' && m.block === 'mangel' && m.why) {
      const it = m.why.replace(/^[^:]*: /, '');   // „fehlt: X“ / englischer Backend-Text „…: X“ waiting.set(it, (waiting.get(it) || 0) + 1);
    }
    return f.balance.map(b => ({ ...b, net: b.prod - b.cons, waiting: waiting.get(b.item) || 0 }))
      .filter(b => b.net < -0.5 || b.waiting >= 3)
      .sort((a, b) => b.waiting - a.waiting || a.net - b.net).slice(0, 8);
  });
  const troubles = $derived.by(() => {
    const out: { text: string; go: () => void; level: string }[] = [];
    for (const z of $live?.trains || []) if (z.derailed) out.push({ text: tr('Zug {name} entgleist', { name: z.name }), level: 'error', go: () => toMap('train:' + z.name, z.pos[0] / 100, z.pos[1] / 100) });
    for (const v of $live?.trucks || []) if (v.fuel === false && v.autopilot) out.push({ text: tr('{name} ohne Treibstoff', { name: v.name }), level: 'warn', go: () => toMap('truck:' + (v.id || v.name), v.pos[0] / 100, v.pos[1] / 100) });
    const nop = (f?.machines || []).filter(m => m.nopower);
    if (nop.length) out.push({ text: tr('{n} Maschinen ohne Stromanschluss ({names})', { n: nop.length, names: [...new Set(nop.map(m => m.name))].slice(0, 3).join(', ') }), level: 'error',
      go: () => toMap('machine:' + nop[0].id, nop[0].pos[0], nop[0].pos[1]) });
    for (const c of f?.circuits || []) if (c.fuse) out.push({ text: tr('Sicherung ausgelöst in Netz {id}', { id: c.id }), level: 'error', go: () => go('power') });
    const bal = new Map((f?.balance || []).map(b => [b.item, b.prod - b.cons]));
    // Brennstoffpuffer im Gebäude ist klein; Warnung nur, wenn die Fabrik den Brennstoff nicht nachliefert
    for (const g of f?.generators || []) if (g.fuel_minutes != null && g.fuel_minutes < 30 && g.producing && !g.cls?.includes('Integrated') && (bal.get(g.fuel || '') ?? 0) < 0)
      { out.push({ text: tr('{name}: Brennstoff reicht {dur}', { name: g.name, dur: dur(g.fuel_minutes) }), level: 'warn', go: () => toMap('generator:' + g.id, g.pos[0], g.pos[1]) }); break; }
    for (const x of f?.factories || []) if (x.status === 'aktiv' && x.starved >= 4 && x.starved / x.n > .3)
      out.push({ text: tr('{name}: {starved} von {n} Maschinen fehlt Material', { name: lxr(x.name), starved: x.starved, n: x.n }), level: 'warn', go: () => toMap('factory:' + x.key, x.center[0], x.center[1]) });
    for (const s of $stations?.trucks || []) if (s.mode === 'unload' && s.fill != null && s.fill < .02 && (s.vehicles || []).length)
      out.push({ text: tr('{name} ist leer', { name: s.name }), level: 'info', go: () => toMap('station:' + s.id.split('.').pop(), s.pos[0] / 100, s.pos[1] / 100) });
    return out;
  });
  // Ereignisse vor dem 30.09. nutzten noch „Maschinen stehen“ (inkl. voller Ausgänge) — ausblenden
  const recent = $derived($events.filter(e => e.t >= since && !(e.kind === 'stall' && e.text.includes('Maschinen stehen'))));
  const onlineP = $derived(($live?.players || []).filter(p => p.online));
  const counts = $derived.by(() => {
    const c = { run: 0, starved: 0, full: 0 };
    for (const m of f?.machines || []) { if (m.state === 'läuft' || m.state === 'teilweise') c.run++; else if (m.state === 'steht') m.block === 'voll' ? c.full++ : c.starved++; }
    return c;
  });
</script>

<div class="page">
  <div class="head">
    <h1>{$t('Lage')}</h1>
    <span class="src">{$status?.frm.ok ? $t('Live-Daten') : $t('Stand des Saves {ago}', { ago: ago($status?.save?.mtime) })} · {onlineP.length ? $t('{names} online', { names: onlineP.map(p => p.name).join(', ') }) : $t('niemand online')}{$live?.session ? ' · ' + $t('Spieltag {day}, {clock}', { day: $live.session.day, clock: $live.session.clock }) : ''}</span>
  </div>

  <div class="kpis">
    {#each power as c}
      {@const pct = c.cap ? c.use / c.cap : 0}
      <button class="kpi panel" onclick={() => go('power')}>
        <div class="v num">{fmtMW(c.use)}<small> / {fmtMW(c.cap)}</small></div>
        <div class="bar"><i style="width:{Math.min(100, pct * 100)}%;background:{pct > .95 ? C.bad : pct > .8 ? C.warn : 'var(--ficsit)'}"></i></div>
        <div class="l">{$t('Strom Netz {id}', { id: c.id })}{c.fuse ? ' · ' + $t('Sicherung raus') : ''}</div>
      </button>
    {/each}
    <button class="kpi panel" onclick={() => go('production')}><div class="v num">{counts.run}<small> / {f?.machines.length ?? '–'}</small></div><div class="l">{$t('Maschinen laufen')}</div></button>
    <button class="kpi panel" onclick={() => go('production')}><div class="v num" style="color:{counts.starved ? C.bad : 'inherit'}">{counts.starved}</div><div class="l">{$t('mit Materialmangel · {n} warten auf Abnahme', { n: counts.full })}</div></button>
    <div class="kpi panel"><div class="v num">{$progress?.n_schematics ?? '–'}</div><div class="l">{$t('Freischaltungen · aktuell {active}', { active: $progress?.active || '–' })}</div></div>
  </div>

  <div class="cols">
    <section class="panel card">
      <h2>{$t('Braucht Aufmerksamkeit')}</h2>
      {#each troubles as x}
        <button class="it {x.level}" onclick={x.go}><span class="mk"></span>{x.text}</button>
      {:else}<p class="muted">{$t('Keine Störungen. Fabriken mit Status „im Aufbau“, „Puffer“ oder „stillgelegt“ melden nichts.')}</p>{/each}
    </section>

    <section class="panel card">
      <h2>{$t('Mangelware')}</h2>
      <table class="t">
        <thead><tr><th>{$t('Ware')}</th><th class="n">{$t('Saldo /min')}</th><th class="n">{$t('wartende Maschinen')}</th></tr></thead>
        <tbody>
          {#each shortages as s}
            <tr class="click" onclick={() => go('planner', { item: s.item, rate: Math.max(1, Math.round(-s.net || 10)) })}>
              <td>{$tn(s.item)}{#if s.net >= 0}<div class="muted small">{$t('genug erzeugt, kommt aber nicht an')}</div>{/if}</td>
              <td class="n" style="color:{s.net < 0 ? C.bad : 'inherit'}">{fmtNum(s.net)}</td><td class="n">{s.waiting || '–'}</td></tr>
          {:else}<tr><td colspan="3" class="muted">{$t('Keine Ware im Minus.')}</td></tr>{/each}
        </tbody>
      </table>
      <p class="muted small">{$t('Zeile anklicken öffnet den Rechner mit der fehlenden Menge.')}</p>
    </section>

    <section class="panel card wide">
      <h2>{$t('Seit deinem letzten Besuch')} <span class="muted small">({new Date(since * 1000).toLocaleString(locale(), { dateStyle: 'short', timeStyle: 'short' })})</span></h2>
      <ol class="log">
        {#each recent.slice(0, 40) as e (e.id)}
          <li class={e.level}><span class="t num">{clock(e.t)}</span><span>{$lx(e.text)}</span></li>
        {:else}<li class="muted">{$t('Nichts Neues.')}</li>{/each}
      </ol>
    </section>
  </div>
</div>

<style>
  .head { display: flex; align-items: baseline; gap: 16px; flex-wrap: wrap; }
  .kpi { text-align: left; border: none; color: var(--text); }
  button.kpi:hover .l { color: var(--text2); }
  .kpi small { font-size: 16px; color: var(--dim); font-weight: 600; }
  .kpi .bar { margin: 6px 0 4px; }
  .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .wide { grid-column: 1 / -1; }
  .it { display: flex; align-items: center; gap: 10px; width: 100%; background: none; border: none; text-align: left; padding: 6px 0; border-bottom: 1px solid #2c2e31; }
  .it:hover { color: var(--ficsit); }
  .mk { width: 8px; height: 8px; flex: none; border-radius: 50%; background: var(--dim); }
  .warn .mk { background: var(--warn); border-radius: 0; transform: rotate(45deg); }
  .error .mk { background: var(--bad); border-radius: 0; }
  .small { font-size: 12px; font-weight: 400; font-family: var(--body); }
  .log { list-style: none; padding: 0; margin: 0; columns: 2 340px; column-gap: 28px; }
  .log li { display: flex; gap: 10px; padding: 3px 0; font-size: 13px; break-inside: avoid; color: var(--text2); }
  .log li.error { color: var(--text); }
  .log .t { color: var(--dim); flex: none; }
  @media (max-width: 900px) { .cols { grid-template-columns: 1fr; } }
</style>
