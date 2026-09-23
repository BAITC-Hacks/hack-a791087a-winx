export function createTapTracker() {
  const active = new Map();
  let canceled = false;
  const distance = (start, event) => Math.hypot(event.clientX - start[0], event.clientY - start[1]);
  return {
    start(event) {
      if (event.button !== 0) return;
      if (!active.size) canceled = false;
      active.set(event.pointerId, [event.clientX, event.clientY]);
      if (active.size > 1) canceled = true;
    },
    move(event) {
      const start = active.get(event.pointerId);
      if (start && distance(start, event) > 6) canceled = true;
    },
    end(event) {
      const start = active.get(event.pointerId);
      const isTap = Boolean(start && !canceled && active.size === 1 && distance(start, event) <= 6);
      active.delete(event.pointerId);
      return isTap;
    },
    cancel(event) {
      active.delete(event.pointerId);
      canceled = true;
    },
  };
}
