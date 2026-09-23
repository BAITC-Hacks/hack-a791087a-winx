import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';

const event = (pointerId, x, y, extra = {}) => ({ pointerId, clientX: x, clientY: y, button: 0, ...extra });

test('a pinch or canceled gesture never becomes a district tap', async () => {
  assert.ok(existsSync(new URL('./tap.js', import.meta.url)), 'Pointer tracking must distinguish pinch from tap');
  const { createTapTracker } = await import('./tap.js');
  const tap = createTapTracker();
  tap.start(event(1, 100, 100));
  tap.start(event(2, 200, 100));
  tap.move(event(1, 80, 100));
  assert.equal(tap.end(event(2, 200, 100)), false);
  assert.equal(tap.end(event(1, 80, 100)), false);
  tap.start(event(3, 100, 100));
  tap.cancel(event(3, 100, 100));
  assert.equal(tap.end(event(3, 100, 100)), false);
  tap.start(event(4, 100, 100));
  assert.equal(tap.end(event(4, 101, 101)), true);
});

test('right-clicks, drags returning to origin, and unmatched releases do not select', async () => {
  assert.ok(existsSync(new URL('./tap.js', import.meta.url)), 'Pointer tracking must distinguish pinch from tap');
  const { createTapTracker } = await import('./tap.js');
  const tap = createTapTracker();
  tap.start(event(1, 10, 10, { button: 2 }));
  assert.equal(tap.end(event(1, 10, 10)), false);
  tap.start(event(2, 10, 10));
  tap.move(event(2, 30, 10));
  assert.equal(tap.end(event(2, 10, 10)), false);
  assert.equal(tap.end(event(3, 10, 10)), false);
});
