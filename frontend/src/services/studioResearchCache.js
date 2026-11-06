const PREFIX = 'roadtrips.studio.research.v1.';
const memory = new Map();
let generation = 0;

export async function readResearchCache(key, scope) {
  const cached = memory.get(key);
  if (cached?.scope === scope) return cached.value;
  const started = generation;
  try {
    const entry = JSON.parse(sessionStorage.getItem(PREFIX + key));
    if (entry?.scope !== scope) return null;
    let text = entry.data;
    if (entry.encoding === 'gzip') {
      const bytes = Uint8Array.from(atob(text), (char) => char.charCodeAt(0));
      text = await new Response(
        new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))
      ).text();
    } else if (entry.encoding !== 'json') return null;
    const value = JSON.parse(text);
    if (started !== generation) return null;
    if (memory.get(key) !== cached)
      return memory.get(key)?.scope === scope ? memory.get(key).value : null;
    memory.set(key, { scope, value });
    return value;
  } catch {
    return null;
  }
}

export async function saveResearchCache(key, scope, value) {
  const entry = { scope, value };
  memory.set(key, entry);
  try {
    // If the replacement exceeds quota, a reload must fetch again instead of restoring old rows.
    sessionStorage.removeItem(PREFIX + key);
    let data = JSON.stringify(value);
    let encoding = 'json';
    if (data.length > 20000 && typeof CompressionStream !== 'undefined' && Blob.prototype.stream) {
      const bytes = new Uint8Array(
        await new Response(
          new Blob([data]).stream().pipeThrough(new CompressionStream('gzip'))
        ).arrayBuffer()
      );
      data = btoa(Array.from(bytes, (byte) => String.fromCharCode(byte)).join(''));
      encoding = 'gzip';
    }
    // A slower compression must not replace a newer response or restore a cleared session.
    if (memory.get(key) === entry)
      sessionStorage.setItem(PREFIX + key, JSON.stringify({ scope, encoding, data }));
  } catch {
    // Retain same-tab navigation caching when storage is disabled or its quota is exhausted.
  }
}

export function clearResearchCache(key) {
  generation += 1;
  if (key != null) memory.delete(key);
  else memory.clear();
  try {
    if (key != null) sessionStorage.removeItem(PREFIX + key);
    else {
      for (const name of Object.keys(sessionStorage)) {
        if (name.startsWith(PREFIX)) sessionStorage.removeItem(name);
      }
    }
  } catch {
    // Session and backend scope still prevent reuse of another visitor's in-memory data.
  }
}
