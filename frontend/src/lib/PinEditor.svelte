<script lang="ts">
  // Notiz anlegen/bearbeiten oder eine Fabrik umbenennen — beides verlangt das gemeinsame Passwort.
  import { password, author, post, checkPassword } from './api';
  import { t, tr, lx, lxr } from './i18n';

  let { pin, onclose }: { pin: any; onclose: (saved: boolean) => void } = $props();
  const CATS: [string, string, string][] = [
    ['geplant', tr('Geplant'), '#f59a23'], ['problem', tr('Problem'), '#e5484d'], ['rohstoff', tr('Rohstoff'), '#4cc38a'],
    ['treffpunkt', tr('Treffpunkt'), '#5b9bd5'], ['notiz', tr('Notiz'), '#c3bfb7'],
  ];
  const isFactory = !!pin.factory;
  let text = $state(isFactory ? pin.factory.name : pin.text || '');
  let fstatus = $state(isFactory ? pin.factory.status || 'aktiv' : 'aktiv');
  const FST: [string, string, string][] = [
    ['aktiv', tr('Aktiv'), tr('Warnungen bei Materialmangel')], ['aufbau', tr('Im Aufbau'), tr('keine Warnungen')],
    ['puffer', tr('Puffer/Vorrat'), tr('Stillstand gewollt')], ['stillgelegt', tr('Stillgelegt'), tr('keine Warnungen')],
  ];
  let cat = $state(pin.cat || 'geplant');
  let pw = $state($password);
  let name = $state($author);
  let err = $state(''), busy = $state(false);

  async function save() {
    err = ''; busy = true;
    try {
      if (!$password || pw !== $password) {
        if (!(await checkPassword(pw))) throw new Error(tr('Das Passwort stimmt nicht. Frag den Betreiber der Karte nach dem aktuellen.'));
        password.set(pw);
      }
      author.set(name.trim());
      if (isFactory) await post('factory-name', { key: pin.factory.key, name: text.trim() === pin.factory.auto ? '' : text.trim(), status: fstatus, author: name.trim() });
      else await post('pins', { ...pin, text: text.trim(), cat, color: CATS.find(c => c[0] === cat)![2], author: name.trim() || 'anonym' });
      onclose(true);
    } catch (e: any) { err = lxr(e.message); } finally { busy = false; }
  }
  async function del() {
    if (!confirm(tr('Notiz löschen?'))) return;
    busy = true;
    try { await post('pins/' + pin.id + '/delete', {}); onclose(true); } catch (e: any) { err = lxr(e.message); } finally { busy = false; }
  }
</script>

<div class="modal" role="dialog" aria-modal="true" aria-label={isFactory ? $t('Fabrik umbenennen') : $t('Notiz')}>
  <button class="bg" aria-label={$t('Schließen')} onclick={() => onclose(false)}></button>
  <form class="panel box" onsubmit={e => { e.preventDefault(); save(); }}>
    <h2>{isFactory ? $t('Fabrik bearbeiten') : pin.id ? $t('Notiz bearbeiten') : $t('Neue Notiz')}</h2>
    {#if isFactory}
      <label>{$t('Name')}<input class="field" bind:value={text} maxlength="60" /></label>
      <p class="muted small">{$t('Automatischer Name: {auto}. Leer lassen stellt ihn wieder her.', { auto: $lx(pin.factory.auto) })}</p>
      <div class="cats">
        {#each FST as [k, l, h]}<button type="button" class:on={fstatus === k} onclick={() => (fstatus = k)} title={h}>{l}</button>{/each}
      </div>
      <p class="muted small">{FST.find(x => x[0] === fstatus)?.[2]}</p>
    {:else}
      <div class="cats">
        {#each CATS as [k, l, c]}<button type="button" class:on={cat === k} onclick={() => (cat = k)}><span class="dot" style="background:{c}"></span>{l}</button>{/each}
      </div>
      <label>{$t('Text')}<textarea class="field" bind:value={text} rows="4" maxlength="500" placeholder={$t('Was soll hier hin?')}></textarea></label>
    {/if}
    <div class="two">
      <label>{$t('Dein Name')}<input class="field" bind:value={name} maxlength="40" autocomplete="nickname" /></label>
      <label>{$t('Passwort')}<input class="field" type="password" bind:value={pw} autocomplete="current-password" /></label>
    </div>
    {#if err}<p class="err">{err}</p>{/if}
    <div class="act">
      {#if pin.id}<button type="button" class="btn" onclick={del} disabled={busy}>{$t('Löschen')}</button>{/if}
      <span style="flex:1"></span>
      <button type="button" class="btn" onclick={() => onclose(false)}>{$t('Abbrechen')}</button>
      <button class="btn primary" disabled={busy || (!isFactory && !text.trim()) || !pw}>{$t('Speichern')}</button>
    </div>
  </form>
</div>

<style>
  .modal { position: fixed; inset: 0; z-index: 100; display: grid; place-items: center; padding: 12px; }
  .bg { position: absolute; inset: 0; background: #000a; border: none; }
  .box { position: relative; width: min(460px, 100%); padding: 18px; display: flex; flex-direction: column; gap: 12px; }
  label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: var(--text2); }
  .two { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .cats { display: flex; flex-wrap: wrap; gap: 4px; }
  .cats button { background: var(--steel); border: 1px solid var(--seam); padding: 4px 10px; font-size: 13px; display: inline-flex; gap: 6px; align-items: center; }
  .cats button.on { border-color: var(--ficsit); }
  .act { display: flex; gap: 8px; }
  .err { color: var(--bad); margin: 0; font-size: 13px; }
  .small { font-size: 12px; margin: -6px 0 0; }
  textarea { resize: vertical; }
</style>
