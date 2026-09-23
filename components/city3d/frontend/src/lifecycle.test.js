import test from 'node:test';
import assert from 'node:assert/strict';
import { createSceneLifecycle } from './lifecycle.js';

test('reports a lifecycle error once and contains a throwing error callback', () => {
  const calls = [];
  const lifecycle = createSceneLifecycle(code => {
    calls.push(code);
    throw new Error('consumer failure');
  });

  lifecycle.report('context_lost');
  lifecycle.report('context_lost');

  assert.deepEqual(calls, ['context_lost']);
});

test('isolates cleanup failures and disposes registered resources once in reverse order', () => {
  const errors = [];
  const released = [];
  const lifecycle = createSceneLifecycle(code => errors.push(code));
  lifecycle.addCleanup(() => released.push('first'));
  lifecycle.addCleanup(() => { throw new Error('cleanup failure'); });
  lifecycle.addCleanup(() => released.push('last'));

  lifecycle.dispose();
  lifecycle.dispose();

  assert.deepEqual(released, ['last', 'first']);
  assert.deepEqual(errors, ['render_failed']);
});

test('contains callback errors and reports render failure once', () => {
  const errors = [];
  const lifecycle = createSceneLifecycle(code => errors.push(code));

  assert.equal(lifecycle.run(() => { throw new Error('render failure'); }), undefined);
  assert.equal(lifecycle.run(() => { throw new Error('another failure'); }), undefined);

  assert.deepEqual(errors, ['render_failed']);
});
