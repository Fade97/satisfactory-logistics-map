<script lang="ts">
  // Map legend: symbols and colours.
  import { C } from '../fmt';
  import { t } from '../i18n';
</script>

<div class="legend panel">
  <div><span class="dot" style="background:{C.load}"></span> {$t('Load')} <span class="dot" style="background:{C.unload}"></span> {$t('Unload')} <span class="dot" style="background:{C.mixed}"></span> {$t('mixed')}</div>
  <div><span class="sq"></span> {$t('Train station')} · <span class="dot" style="background:{C.neutral}"></span> {$t('Truck station')} · {$t('bar = fill level')}</div>
  <div><span class="dot" style="background:{C.accent};box-shadow:0 0 0 2px {C.light}"></span> {$t('Player')} · <span class="sq" style="background:{C.train}"></span> {$t('Train')} · <span class="dia"></span> {$t('Vehicle')}</div>
  <div><span class="sq sm" style="background:{C.ok}"></span> {$t('running')} <span class="sq sm" style="background:{C.warn}"></span> {$t('partial')} <span class="sq sm" style="background:{C.bad}"></span> {$t('Missing input')} <span class="sq sm" style="background:{C.full}"></span> {$t('Output full')}</div>
  <div>{$t('Factory outline: green running · yellow some shortage · red severe shortage')}</div>
  <div class="muted">{$t('Map image:')} satisfactory.wiki.gg · CC BY-NC-SA</div>
</div>

<style>
  .legend { position: absolute; left: 12px; bottom: 44px; padding: 10px 14px; font-size: 12.5px; display: flex; flex-direction: column; gap: 4px; z-index: 9; }
  .legend .dot { margin: 0 3px 0 6px; }
  .sq { display: inline-block; width: 10px; height: 10px; background: #c3bfb7; border-radius: 2px; vertical-align: -1px; }
  .sq.sm { width: 8px; height: 8px; margin-left: 6px; }
  .dia { display: inline-block; width: 8px; height: 8px; background: var(--ficsit); transform: rotate(45deg); margin: 0 3px; }
  @media (max-width: 760px) { .legend { bottom: 40px; right: 12px; } }
</style>
