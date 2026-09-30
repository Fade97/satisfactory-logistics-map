<script lang="ts">
  // Kiosk für einen Nebenbildschirm: Karte (folgt einem Spieler) + Feed + Kennzahlen, optional rotierend.
  // #/kiosk?follow=<Spieler>&rotate=30
  import { onMount, onDestroy } from 'svelte';
  import { factory, live, status } from '../lib/api';
  import { route } from '../lib/router';
  import { fmtMW, fmtNum, C } from '../lib/fmt';
  import MapPage from './MapPage.svelte';
  import Power from './Power.svelte';
  import Production from './Production.svelte';
  import Logistics from './Logistics.svelte';
  import EventFeed from '../lib/EventFeed.svelte';
  import { tn } from '../lib/names';

  const q = $route.q;
  const rotate = +(q.get('rotate') || 0);
  const pages = ['map', 'production', 'power', 'logistics'];
  let idx = $state(0);
  let t: number;
  onMount(() => { if (rotate) t = window.setInterval(() => (idx = (idx + 1) % pages.length), rotate * 1000); });
  onDestroy(() => clearInterval(t));

  // Fester Spieler aus ?follow=, sonst der erste, der online ist (offline wird nicht verfolgt — MapPage pausiert dann)
  const who = $derived(q.get('follow') || ($live?.players.find(p => p.online === true)?.name ?? ''));
  const f = $derived($factory);
  const power = $derived((f?.circuits || []).reduce((a, c) => ({ use: a.use + c.use, cap: a.cap + c.cap }), { use: 0, cap: 0 }));
  const stalled = $derived((f?.machines || []).filter(m => m.state === 'steht' && m.block !== 'voll').length);
  const deficit = $derived((f?.balance || []).map(b => ({ item: b.item, net: b.prod - b.cons })).filter(b => b.net < -0.5).sort((a, b) => a.net - b.net).slice(0, 4));
  const moving = $derived(($live?.trains || []).filter(t => (t.speed || 0) > 5).length);
  let now = $state(new Date());
  const tick = setInterval(() => (now = new Date()), 10000);
  onDestroy(() => clearInterval(tick));
</script>

<div class="kiosk">
  <div class="main">
    {#if pages[idx] === 'map'}{#key who}<MapPage kiosk followKey={who ? 'player:' + who : ''} />{/key}
    {:else if pages[idx] === 'production'}<Production />
    {:else if pages[idx] === 'power'}<Power />
    {:else}<Logistics />{/if}
  </div>
  <aside>
    <div class="top">
      <div class="clk num">{now.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}</div>
      <div class="muted">{$status?.frm.ok ? 'live' : 'aus dem Save'}{$live?.session ? ' · Spielzeit ' + $live.session.clock : ''}</div>
    </div>
    <div class="tiles">
      <div class="tile panel"><div class="v num" style="color:{power.cap && power.use / power.cap > .9 ? C.bad : 'inherit'}">{fmtMW(power.use)}</div><div class="l">von {fmtMW(power.cap)} Strom</div></div>
      <div class="tile panel"><div class="v num" style="color:{stalled ? C.warn : 'inherit'}">{stalled}</div><div class="l">Maschinen mit Materialmangel</div></div>
      <div class="tile panel"><div class="v num">{moving}/{$live?.trains.length ?? 0}</div><div class="l">Züge unterwegs</div></div>
      <div class="tile panel"><div class="v num">{($live?.players || []).filter(p => p.online).length}</div><div class="l">Spieler online</div></div>
    </div>
    {#if deficit.length}
      <div class="def"><h3>Größter Mangel</h3>
        {#each deficit as d}<div class="dr"><span>{$tn(d.item)}</span><span class="num" style="color:{C.bad}">{fmtNum(d.net)}/min</span></div>{/each}</div>
    {/if}
    <div class="feed"><h3>Ereignisse</h3><EventFeed compact /></div>
    <a class="exit" href="#/map">Kiosk verlassen</a>
  </aside>
</div>

<style>
  .kiosk { display: grid; grid-template-columns: 1fr 340px; height: 100%; }
  .main { position: relative; min-width: 0; overflow: hidden; }
  aside { background: var(--plate); border-left: 2px solid var(--ficsit); display: flex; flex-direction: column; padding: 16px; gap: 16px; min-height: 0; }
  .clk { font-family: var(--cond); font-weight: 700; font-size: 48px; line-height: 1; }
  .tiles { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .tile { background: var(--plate2); padding: 10px 12px; }
  .v { font-family: var(--cond); font-weight: 700; font-size: 28px; line-height: 1.1; }
  .l { color: var(--dim); font-size: 12.5px; }
  h3 { color: var(--text2); margin-bottom: 6px; }
  .dr { display: flex; justify-content: space-between; font-size: 14px; padding: 2px 0; }
  .feed { flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
  .exit { color: var(--dim); font-size: 12px; }
  @media (max-width: 900px) { .kiosk { grid-template-columns: 1fr; grid-template-rows: 1fr auto; } aside { max-height: 45vh; overflow: auto; } }
</style>
