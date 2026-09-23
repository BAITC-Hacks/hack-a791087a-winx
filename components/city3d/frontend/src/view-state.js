// Streamlit may re-evaluate the module on a Python rerun. Keep only public
// camera/error state on the page; a page reload starts clean. No persistent storage.
const STORE = Symbol.for('winx.city3d.view-state');

export function getViewState(page, key) {
  const cache = page[STORE] ||= new Map();
  if (!cache.has(key)) {
    if (cache.size >= 8) cache.delete(cache.keys().next().value);
    cache.set(key, { camera: null, error: null });
  }
  return cache.get(key);
}
