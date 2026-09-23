export function createSceneLifecycle(onError) {
  const reported = new Set();
  const cleanup = [];
  let disposed = false;

  function report(code) {
    if (reported.has(code)) return;
    reported.add(code);
    try { onError(code); } catch { /* Error reporting must not escape browser callbacks. */ }
  }

  function release(action) {
    try { action(); } catch { report('render_failed'); }
  }

  return {
    report,
    run(callback, ...args) {
      try { return callback(...args); } catch { report('render_failed'); return undefined; }
    },
    addCleanup(action) {
      if (disposed) release(action);
      else cleanup.push(action);
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      while (cleanup.length) release(cleanup.pop());
    },
  };
}
