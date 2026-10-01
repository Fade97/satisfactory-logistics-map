<script lang="ts">
  import { onMount } from 'svelte';
  import { start, status, live, online } from './lib/api';
  import { route, go, PAGE_ALIAS } from './lib/router';
  import { ago } from './lib/fmt';
  import MapPage from './pages/MapPage.svelte';
  import Production from './pages/Production.svelte';
  import Power from './pages/Power.svelte';
  import Logistics from './pages/Logistics.svelte';
  import History from './pages/History.svelte';
  import Kiosk from './pages/Kiosk.svelte';
  import Overview from './pages/Overview.svelte';
  import Planner from './pages/Planner.svelte';
  import EventFeed from './lib/EventFeed.svelte';
  import { prefs } from './lib/prefs';
  import { t, tr, lx, lxr } from './lib/i18n';

  onMount(() => {
    start();
    // without a route (plain call of the root URL) open the chosen start page
    if (!location.hash || location.hash === '#' || location.hash === '#/') go(PAGE_ALIAS[$prefs.start] || $prefs.start);
  });
  let showPrefs = $state(false);

  const NAV = [
    ['overview', tr('Overview'), '◉'], ['map', tr('Map'), '◧'], ['production', tr('Production'), '⚙'], ['power', tr('Power'), 'ϟ'],
    ['logistics', tr('Logistics'), '⇄'], ['history', tr('History'), '∿'], ['planner', tr('Planner'), '∑'],
  ];
  let feedOpen = $state(false);

  // show the data source honestly: live (FRM) or state of the last save
  const src = $derived.by(() => {
    const s = $status;
    if (!$online) return { cls: 'bad', text: tr('offline · last known state') };
    if (!s) return { cls: '', text: tr('loading …') };
    if (s.frm.ok) return { cls: $live?.paused ? 'paused' : 'ok', text: $live?.paused ? tr('live · game paused') : tr('live') };
    return { cls: 'save', text: tr('save {ago}', { ago: ago(s.save?.mtime) }) };
  });
  const srcTitle = $derived(!$status ? '' : $status.frm.ok ? tr('Live data from the server, every 5 seconds')
    : [$status.frm.configured === false ? tr('Without the live mod (FicsIt Remote Monitoring):')
        : tr('No live data (FicsIt Remote Monitoring), last seen {ago}.', { ago: ago($status.frm.since) }),
      tr('Positions and machines come from the last save ({file}).', { file: $status.save?.file || '?' }),
      $status.save_error ? tr('Last fetch failed: {error}', { error: lxr($status.save_error) }) : ''].filter(Boolean).join(' '));
  const title = $derived($status?.title || 'Satisfactory');
  $effect(() => { document.title = title + ' · ' + $t('Logistics Map'); });
  // UI language: save first (prefs writes to localStorage immediately), then reload
  function setUi(v: string) {
    prefs.update(p => ({ ...p, ui: v === 'de' ? 'de' : 'en' }));
    location.reload();
  }
</script>

{#if $route.page === 'kiosk'}
  <Kiosk />
{:else}
<div class="shell">
  <header>
    <a class="brand" href="#/overview" aria-label={$t('Go to overview')}>
      <svg viewBox="0 0 256 256" width="24" height="24" aria-hidden="true"><path fill="var(--ficsit)" fill-rule="evenodd" d="M16 16H196L240 60V240H16Z M56 240V141.72L121.36 76.35A40 40 0 1 1 149.65 104.64L96 158.28V240Z"/><circle cx="160" cy="66" r="17" fill="var(--ficsit)"/></svg>
      <span>{title}</span>
    </a>
    <nav>
      {#each NAV as [id, label, ic]}
        <a href="#/{id}" class:on={$route.page === id}><span class="ic" aria-hidden="true">{ic}</span><span class="lb">{label}</span></a>
      {/each}
    </nav>
    <span class="spacer"></span>
    {#if $live?.session}<span class="clock hide-m" title={$t('Game day {day}', { day: $live.session.day })}>{$live.session.is_day ? '☀' : '☾'} {$live.session.clock}</span>{/if}
    <span class="src {src.cls}" title={srcTitle}><i></i>{src.text}</span>
    <button class="hbtn" class:on={feedOpen} onclick={() => (feedOpen = !feedOpen)} aria-label={$t('Events')} title={$t('Events')}>≡</button>
    <button class="hbtn me" class:on={showPrefs} onclick={() => (showPrefs = !showPrefs)} title={$t('My view')} aria-label={$t('My view')}>{$prefs.me ? $prefs.me.slice(0, 1).toUpperCase() : '☺'}</button>
    <a class="hbtn hide-m" href="#/kiosk" title={$t('Kiosk view for a second screen')} aria-label={$t('Kiosk')}>⛶</a>
  </header>
  <main>
    {#if $status && !$status.save}
      <div class="setup panel">
        <h2>{$t('No save yet')}</h2>
        {#if $status.save_error}<p>{$lx($status.save_error)}</p>
        {:else}<p>{$t('The service is fetching the first save …')}</p>{/if}
        <p class="muted small">{$t('Set via')} <code>SAVE_SOURCE</code> {$t('(folder, SFTP, FTP or server API) — see the README. The next attempt runs automatically in one minute.')}</p>
      </div>
    {/if}
    {#if $route.page === 'production'}<Production />
    {:else if $route.page === 'power'}<Power />
    {:else if $route.page === 'logistics'}<Logistics />
    {:else if $route.page === 'history'}<History />
    {:else if $route.page === 'overview'}<Overview />
    {:else if $route.page === 'planner'}<Planner />
    {:else}<MapPage />{/if}
    {#if showPrefs}
      <aside class="prefs panel">
        <h2>{$t('My view')}</h2>
        <p class="muted small">{$t('Only applies to this browser.')}</p>
        <label>{$t('I am')}
          <select class="field" bind:value={$prefs.me}>
            <option value="">{$t('— nobody —')}</option>
            {#each ($live?.players || []) as p}<option value={p.name}>{p.name}</option>{/each}
          </select></label>
        <label class="ck"><input type="checkbox" bind:checked={$prefs.followMe} disabled={!$prefs.me} /> {$t('Map follows me while I’m online')}</label>
        <label>{$t('Start page')}
          <select class="field" bind:value={$prefs.start}>
            <option value="overview">{$t('Overview')}</option><option value="map">{$t('Map (last position)')}</option><option value="production">{$t('Production')}</option>
          </select></label>
        <label>{$t('Language')}
          <select class="field" value={$prefs.ui} onchange={e => setUi(e.currentTarget.value)}>
            <option value="en">English</option><option value="de">Deutsch</option>
          </select></label>
        <label>{$t('Item names')}
          <select class="field" bind:value={$prefs.lang}>
            <option value="en">{$t('English (as in the game)')}</option><option value="de">{$t('German')}</option>
          </select></label>
        <button class="btn" onclick={() => (showPrefs = false)}>{$t('Done')}</button>
      </aside>
    {/if}
    {#if feedOpen}
      <aside class="feed panel"><EventFeed onclose={() => (feedOpen = false)} /></aside>
    {/if}
  </main>
</div>
{/if}

<style>
  .shell { display: flex; flex-direction: column; height: 100%; }
  header { display: flex; align-items: center; gap: 4px; height: 48px; padding: 0 10px 0 12px; background: var(--plate);
           border-bottom: 2px solid var(--ficsit); flex: none; }
  .brand { display: flex; align-items: center; gap: 8px; color: var(--text); text-decoration: none; margin-right: 14px;
           font-family: var(--cond); font-weight: 700; font-size: 19px; }
  nav { display: flex; height: 100%; }
  nav a { display: flex; align-items: center; gap: 6px; padding: 0 12px; color: var(--text2); text-decoration: none;
          font-family: var(--cond); font-weight: 600; font-size: 16px; border-bottom: 3px solid transparent; margin-bottom: -2px; }
  nav a:hover { color: var(--text); }
  nav a.on { color: var(--ficsit); border-bottom-color: var(--ficsit); }
  nav .ic { font-size: 14px; opacity: .8; }
  .spacer { flex: 1; }
  .clock { font-family: var(--cond); font-size: 15px; color: var(--text2); margin-right: 10px; font-variant-numeric: tabular-nums; }
  .src { display: inline-flex; align-items: center; gap: 7px; font-size: 13px; color: var(--text2); padding: 3px 10px;
         border: 1px solid var(--seam); margin-right: 6px; white-space: nowrap; cursor: help; }
  .src i { width: 8px; height: 8px; border-radius: 50%; background: var(--dim); }
  .src.ok i { background: var(--ok); box-shadow: 0 0 0 3px #4cc38a33; }
  .src.paused i { background: var(--warn); }
  .src.save i { background: var(--warn); }
  .src.save { color: var(--warn); border-color: #5a4b1f; }
  .src.bad i { background: var(--bad); }
  .hbtn { width: 36px; height: 34px; display: grid; place-items: center; background: none; border: 1px solid transparent;
          color: var(--text2); font-size: 18px; text-decoration: none; }
  .hbtn:hover, .hbtn.on { border-color: var(--seam); color: var(--text); }
  main { flex: 1; position: relative; min-height: 0; }
  .hbtn.me { font-family: var(--cond); font-weight: 700; font-size: 16px; }
  .prefs { position: absolute; top: 10px; right: 10px; width: 300px; z-index: 31; padding: 14px 16px; display: flex; flex-direction: column; gap: 10px;
           box-shadow: 0 10px 30px #0008; }
  .prefs label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: var(--text2); }
  .prefs .ck { flex-direction: row; align-items: center; gap: 8px; }
  .prefs .ck input { accent-color: var(--ficsit); }
  .prefs p { margin: -6px 0 0; }
  .small { font-size: 12px; }
  .setup { position: absolute; top: 20px; left: 50%; transform: translateX(-50%); width: min(560px, calc(100% - 24px)); z-index: 40;
           padding: 16px 20px; box-shadow: 0 10px 30px #0008; border-left: 3px solid var(--warn); }
  .setup p { margin: 8px 0 0; overflow-wrap: anywhere; }
  .setup code { color: var(--ficsit); }
  .feed { position: absolute; top: 10px; right: 10px; bottom: 10px; width: 360px; z-index: 30; display: flex; flex-direction: column;
          box-shadow: 0 10px 30px #0008; }

  @media (max-width: 760px) {
    header { padding: 0 6px 0 10px; }
    .brand span { display: none; }
    .brand { margin-right: 4px; }
    nav { position: fixed; left: 0; right: 0; bottom: 0; height: calc(56px + env(safe-area-inset-bottom)); padding-bottom: env(safe-area-inset-bottom);
          background: var(--plate); border-top: 1px solid var(--seam); z-index: 40; justify-content: space-around; }
    nav a { flex-direction: column; gap: 0; justify-content: center; font-size: 12px; padding: 0 4px; border-bottom: none;
            border-top: 3px solid transparent; margin: 0; flex: 1; }
    nav a.on { border-top-color: var(--ficsit); }
    nav .ic { font-size: 18px; }
    main { padding-bottom: calc(56px + env(safe-area-inset-bottom)); }
    .feed { left: 6px; right: 6px; width: auto; bottom: calc(62px + env(safe-area-inset-bottom)); }
  }
</style>
