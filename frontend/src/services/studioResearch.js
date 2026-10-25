import axios from 'axios';
import { getStudioSession, studioRequest } from './studioSession';
import { clearResearchCache, readResearchCache, saveResearchCache } from './studioResearchCache';

const scope = (study) =>
  JSON.stringify([
    'selection-research-v4-corridor',
    import.meta.env.VITE_BACKEND_SERVER,
    getStudioSession()?.token ?? null,
    study?.database ? 'database' : (study?.key ?? 'public'),
  ]);
const checkAborted = (signal) => {
  if (signal?.aborted) throw new DOMException('Request aborted', 'AbortError');
};
export async function readStudySnapshot(study) {
  const value = await readResearchCache(`study:${study.id}`, scope(study));
  return Array.isArray(value?.rows) &&
    Array.isArray(value.variants) &&
    value.counts &&
    value.design &&
    typeof value.dataset_hash === 'string' &&
    typeof value.state === 'string' &&
    Number.isSafeInteger(value.cursor) &&
    value.cursor >= 0
    ? value
    : null;
}

const KEY = 'studioResearchSelectionStudies';
const ARCHIVE_KEY = 'studioResearchSelectionArchivedStudies';
function readStudies(key) {
  try {
    const rows = JSON.parse(localStorage.getItem(key) || '[]');
    return Array.isArray(rows)
      ? [
          ...new Map(
            rows
              .filter((row) => row && typeof row.id === 'string' && typeof row.key === 'string')
              .map((row) => [row.id, row])
          ).values(),
        ]
      : [];
  } catch {
    return [];
  }
}
export const savedStudies = () => readStudies(KEY);
export const archivedStudies = () => readStudies(ARCHIVE_KEY);
export function savedStudyVersion() {
  try {
    return sessionStorage.getItem('studioResearchRealVersion') === 'previous'
      ? 'previous'
      : 'current';
  } catch {
    return 'current';
  }
}
export function rememberStudyVersion(version) {
  sessionStorage.setItem('studioResearchRealVersion', version);
}
export async function studyVersions(currentStudies, signal, archive = archivedStudies()) {
  // The incremental endpoint can return protocol metadata without transferring saved run records.
  const metadata = async (study) => ({
    study,
    snapshot: await studyRequest(study, '', 'get', signal, Number.MAX_SAFE_INTEGER),
  });
  const current = await Promise.all(currentStudies.map(metadata));
  const archived = await Promise.allSettled(
    archive
      .filter((study) => !currentStudies.some((active) => active.id === study.id))
      .map(metadata)
  );
  const primary = current.reduce(
    (largest, item) =>
      item.snapshot.counts.solver > largest.snapshot.counts.solver ? item : largest,
    current[0]
  );
  const previous = archived
    .filter((item) => item.status === 'fulfilled')
    .map((item) => item.value)
    .filter(
      (item) =>
        item.snapshot.counts.solver === primary?.snapshot.counts.solver &&
        item.snapshot.dataset_hash === primary?.snapshot.dataset_hash
    )
    .sort((a, b) => (b.snapshot.created_at ?? '').localeCompare(a.snapshot.created_at ?? ''))[0];
  const label = (items) =>
    [
      ...new Set(
        items
          .flatMap(({ snapshot }) =>
            snapshot.variants.map((variant) => variant.config?.time_limit_seconds)
          )
          .filter(Number.isFinite)
      ),
    ].join(' / ');
  return {
    currentLabel: label(current),
    previous: previous ? { study: previous.study, label: label([previous]) } : null,
  };
}
// Database references grant read access through Studio; control capabilities stay browser-local.
export async function loadStudyLibrary(signal) {
  checkAborted(signal);
  // The small library must be current: campaigns can be replaced outside this browser.
  const { data } = await studioRequest('get', 'research/saved', undefined, signal);
  const local = new Map(
    [...archivedStudies(), ...savedStudies()].map((study) => [study.id, study])
  );
  const studies = data.studies.map((study) => local.get(study.id) || study);
  const library = { current: studies.slice(0, 1), archived: studies.slice(1) };
  checkAborted(signal);
  return library;
}
export async function researchCatalog(signal) {
  const owner = scope();
  const cached = await readResearchCache('catalog', owner);
  checkAborted(signal);
  if (Array.isArray(cached?.trips) && Array.isArray(cached?.personas)) return cached;
  const data = (
    await axios.get(`${import.meta.env.VITE_BACKEND_SERVER}studio/research/catalog`, { signal })
  ).data;
  checkAborted(signal);
  await saveResearchCache('catalog', owner, data);
  return data;
}
export async function studyRequest(study, action = '', method = 'get', signal, after) {
  const owner = scope(study);
  const cacheKey = `study:${study.id}`;
  const metadataKey = `metadata:${study.id}`;
  const metadataOnly = after === Number.MAX_SAFE_INTEGER;
  const cacheable = method === 'get' && !action;
  const cached = cacheable ? await readStudySnapshot(study) : null;
  checkAborted(signal);
  if (cached?.state === 'complete' && Array.isArray(cached.rows))
    return metadataOnly ? { ...cached, rows: [] } : cached;
  if (cacheable && metadataOnly) {
    const metadata = await readResearchCache(metadataKey, owner);
    checkAborted(signal);
    if (metadata?.variants && metadata?.counts) return metadata;
  }
  // Restoring an active study needs only changes after the cached full snapshot.
  const cursor =
    cacheable && !metadataOnly && cached && Number.isSafeInteger(cached.cursor)
      ? cached.cursor
      : after;
  const data = await requestStudy(study, action, method, signal, cursor);
  checkAborted(signal);
  if (!cacheable) {
    if (method !== 'get') {
      clearResearchCache(cacheKey);
      clearResearchCache(metadataKey);
    }
    return data;
  }
  if (metadataOnly) {
    await saveResearchCache(metadataKey, owner, data);
    return data;
  }
  if (Array.isArray(data.rows) && (cached || cursor == null || cursor === 0)) {
    const rows = new Map((cached?.rows ?? []).map((row) => [row.id, row]));
    data.rows.forEach((row) => rows.set(row.id, row));
    const snapshot = { ...data, rows: [...rows.values()] };
    await saveResearchCache(cacheKey, owner, snapshot);
    return snapshot;
  }
  return data;
}

async function requestStudy(study, action, method, signal, after) {
  if (study.database) {
    if (method !== 'get') throw new Error('Saved database results are read-only.');
    return (
      await studioRequest(
        'get',
        `research/saved/${study.id}${action ? `/${action}` : ''}`,
        undefined,
        signal,
        after == null ? undefined : { after }
      )
    ).data;
  }
  const url = `${import.meta.env.VITE_BACKEND_SERVER}studio/research/batches/${study.id}${action ? `/${action}` : ''}`;
  const config = {
    signal,
    headers: { 'X-Studio-Batch-Key': study.key },
    params: after == null ? undefined : { after },
  };
  return (method === 'post' ? await axios.post(url, {}, config) : await axios.get(url, config))
    .data;
}
export async function downloadStudy(studies, format) {
  const sources = await Promise.all(
    studies.map((study) => studyRequest(study, `export?format=${format}`))
  );
  let data;
  if (format === 'json') data = { schema_version: 1, studies: sources };
  else {
    const header = sources[0]?.split('\n', 1)[0];
    if (!header || sources.some((source) => source.split('\n', 1)[0] !== header))
      throw new Error('Export columns do not match');
    data =
      [
        header,
        ...sources.map((source) => source.slice(source.indexOf('\n') + 1).replace(/\r?\n$/, '')),
      ].join('\n') + '\n';
  }
  const blob = new Blob([typeof data === 'string' ? data : JSON.stringify(data, null, 2)], {
    type: format === 'csv' ? 'text/csv' : 'application/json',
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `trip-research.${format}`;
  link.click();
  URL.revokeObjectURL(url);
}

export async function rerunStudy(study, previousStudies) {
  const { data } = await axios.post(
    `${import.meta.env.VITE_BACKEND_SERVER}studio/research/batches/${study.id}/rerun`,
    { id: crypto.randomUUID() },
    { headers: { 'X-Studio-Batch-Key': study.key } }
  );
  if (typeof data.id !== 'string' || typeof data.key !== 'string')
    throw new Error('Invalid rerun response');
  const archived = archivedStudies();
  localStorage.setItem(
    ARCHIVE_KEY,
    JSON.stringify([
      ...new Map([...archived, ...previousStudies].map((source) => [source.id, source])).values(),
    ])
  );
  localStorage.setItem(KEY, JSON.stringify([data]));
  rememberStudyVersion('current');
  clearResearchCache();
  return data;
}
