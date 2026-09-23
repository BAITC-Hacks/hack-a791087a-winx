import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';

test('camera and failure state survive renderer module re-evaluation on the same page', async () => {
  assert.ok(existsSync(new URL('./view-state.js', import.meta.url)), 'A persistent page-local view store must exist');
  const first = await import('./view-state.js?first');
  const second = await import('./view-state.js?second');
  const page = {};
  const view = first.getViewState(page, 'city-one');
  view.camera = { position: [1, 2, 3], target: [0, 0, 0] };
  view.error = 'context_lost';
  assert.equal(second.getViewState(page, 'city-one'), view);
  assert.notEqual(second.getViewState(page, 'city-two'), view);
  assert.equal(second.getViewState({}, 'city-one').error, null);
});

test('unmounted instance cache is bounded', async () => {
  assert.ok(existsSync(new URL('./view-state.js', import.meta.url)), 'A persistent page-local view store must exist');
  const { getViewState } = await import('./view-state.js');
  const page = {};
  getViewState(page, 'oldest').error = 'old';
  for (let i = 0; i < 20; i++) getViewState(page, `view-${i}`);
  assert.equal(getViewState(page, 'oldest').error, null);
});
