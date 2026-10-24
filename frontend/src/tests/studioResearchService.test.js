import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import axios from 'axios';
import { Blob as NativeBlob } from 'node:buffer';
import {
  loadStudyLibrary,
  studyRequest,
  downloadStudy,
  savedStudies,
  rerunStudy,
  studyVersions,
  savedStudyVersion,
  rememberStudyVersion,
  researchCatalog,
} from '../services/studioResearch';
import {
  clearResearchCache,
  readResearchCache,
  saveResearchCache,
} from '../services/studioResearchCache';
import { clearStudioSession } from '../services/studioSession';

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }));
const sources = [
  { id: 'main', key: 'main-key' },
  { id: 'pilot', key: 'pilot-key' },
];
let exported;
beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  sessionStorage.clear();
  clearResearchCache();
  exported = null;
  vi.stubGlobal('URL', {
    createObjectURL: vi.fn((blob) => {
      exported = blob;
      return 'blob:fixture';
    }),
    revokeObjectURL: vi.fn(),
  });
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  localStorage.clear();
  sessionStorage.clear();
  clearResearchCache();
});
const exportedText = () =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsText(exported);
  });

it('combines CSV exports with one header and preserves original source IDs and quoted newlines', async () => {
  axios.get
    .mockResolvedValueOnce({ data: 'id,study_id,message\r\n1,main,"first\nsecond"\r\n' })
    .mockResolvedValueOnce({ data: 'id,study_id,message\r\n1,pilot,finished\r\n' });
  await downloadStudy(sources, 'csv');
  const text = await exportedText();
  expect(text.match(/id,study_id,message/g)).toHaveLength(1);
  expect(text).toContain('1,main,"first\nsecond"');
  expect(text).toContain('1,pilot,finished');
  expect(axios.get.mock.calls.map(([, config]) => config.headers['X-Studio-Batch-Key'])).toEqual([
    'main-key',
    'pilot-key',
  ]);
  expect(text).not.toContain('main-key');
});

it('retains original protocols in the combined JSON export and deduplicates saved capabilities', async () => {
  const documents = sources.map(({ id }) => ({
    id,
    protocol: { cases: [{ repeat: 1 }], identity: { revision: id } },
  }));
  axios.get
    .mockResolvedValueOnce({ data: documents[0] })
    .mockResolvedValueOnce({ data: documents[1] });
  await downloadStudy(sources, 'json');
  expect(JSON.parse(await exportedText())).toEqual({ schema_version: 1, studies: documents });
  localStorage.setItem(
    'studioResearchSelectionStudies',
    JSON.stringify([sources[0], sources[0], null, sources[1]])
  );
  expect(savedStudies()).toEqual(sources);
});

it('archives historical access and replaces the active batch only after a successful rerun creation', async () => {
  localStorage.setItem('studioResearchSelectionStudies', JSON.stringify(sources));
  const replacement = { id: 'rerun', key: 'new-key' };
  axios.post.mockResolvedValueOnce({ data: replacement });
  expect(await rerunStudy(sources[0], sources)).toEqual(replacement);
  expect(savedStudies()).toEqual([replacement]);
  expect(JSON.parse(localStorage.getItem('studioResearchSelectionArchivedStudies'))).toEqual(
    sources
  );
  expect(axios.post.mock.calls[0][2].headers['X-Studio-Batch-Key']).toBe('main-key');
  axios.post.mockRejectedValueOnce(new Error('active batch'));
  await expect(rerunStudy(replacement, [replacement])).rejects.toThrow('active batch');
  expect(savedStudies()).toEqual([replacement]);
  expect(JSON.parse(localStorage.getItem('studioResearchSelectionArchivedStudies'))).toEqual(
    sources
  );
});

it('finds the previous full matrix and reads version metadata without fetching its run records', async () => {
  localStorage.setItem('studioResearchSelectionStudies', JSON.stringify([sources[0]]));
  localStorage.setItem(
    'studioResearchSelectionArchivedStudies',
    JSON.stringify([
      sources[1],
      { id: 'previous', key: 'old-key' },
      { id: 'unavailable', key: 'lost-key' },
    ])
  );
  axios.get.mockImplementation((url) => {
    if (url.includes('unavailable')) return Promise.reject(new Error('unavailable'));
    const pilot = url.includes('pilot');
    return Promise.resolve({
      data: {
        counts: { solver: pilot ? 7 : 6300 },
        dataset_hash: 'fixed',
        created_at: pilot ? '2030-12-03' : '2030-12-02',
        variants: [{ config: { time_limit_seconds: url.includes('main') ? 15 : 5 } }],
      },
    });
  });
  const versions = await studyVersions([sources[0]]);
  expect(versions).toEqual({
    currentLabel: '15',
    previous: { study: { id: 'previous', key: 'old-key' }, label: '5' },
  });
  expect(
    axios.get.mock.calls.every(([, config]) => config.params.after === Number.MAX_SAFE_INTEGER)
  ).toBe(true);
  rememberStudyVersion('previous');
  expect(savedStudyVersion()).toBe('previous');
  expect(savedStudies()).toEqual([sources[0]]);
  rememberStudyVersion('current');
  expect(savedStudyVersion()).toBe('current');
});

it('discovers database studies without browser keys and uses session-scoped read-only requests', async () => {
  sessionStorage.setItem(
    'studioSession',
    JSON.stringify({ token: 'fixture-session', expires_at: Date.now() / 1000 + 3600 })
  );
  axios.get.mockResolvedValueOnce({
    data: {
      studies: [
        { id: 'current', database: true },
        { id: 'previous', database: true },
      ],
    },
  });
  const library = await loadStudyLibrary();
  expect(library.current).toEqual([{ id: 'current', database: true }]);
  expect(library.archived).toEqual([{ id: 'previous', database: true }]);
  expect(axios.get.mock.calls[0][1].headers).toEqual({ 'X-Studio-Session': 'fixture-session' });
  axios.get.mockResolvedValueOnce({ data: { rows: [] } });
  await studyRequest(library.current[0], '', 'get', undefined, 123);
  expect(axios.get.mock.calls[1][0]).toContain('research/saved/current');
  expect(axios.get.mock.calls[1][1].params).toEqual({ after: 123 });
  await expect(studyRequest(library.current[0], 'pause', 'post')).rejects.toThrow('read-only');
  expect(axios.post).not.toHaveBeenCalled();
  expect(localStorage.length).toBe(0);
});

const snapshot = (changes = {}) => ({
  state: 'complete',
  cursor: 1,
  counts: { solver: 1, pipeline: 0, total: 1 },
  design: { trips: ['medium-2d'], stops_per_day: [2] },
  variants: [{ id: 'baseline', config: { time_limit_seconds: 15 } }],
  dataset_hash: 'fixed',
  rows: [{ id: 1, solver_status: 'OPTIMAL' }],
  ...changes,
});

it('reuses completed study results and metadata without another request', async () => {
  const data = snapshot();
  axios.get.mockResolvedValueOnce({ data });
  expect(await studyRequest(sources[0], '', 'get', undefined, 0)).toEqual(data);
  expect(await studyRequest(sources[0], '', 'get', undefined, 0)).toEqual(data);
  expect(await studyVersions([sources[0]], undefined, [])).toEqual({
    currentLabel: '15',
    previous: null,
  });
  expect(axios.get).toHaveBeenCalledTimes(1);
});

it('resumes an active study from its cached cursor and retains earlier rows and corrections', async () => {
  axios.get.mockResolvedValueOnce({ data: snapshot({ state: 'running' }) });
  await studyRequest(sources[0], '', 'get', undefined, 0);
  axios.get.mockResolvedValueOnce({
    data: snapshot({
      cursor: 3,
      rows: [
        { id: 1, solver_status: 'FEASIBLE' },
        { id: 2, solver_status: 'OPTIMAL' },
      ],
    }),
  });
  const restored = await studyRequest(sources[0], '', 'get', undefined, 0);
  expect(axios.get.mock.calls[1][1].params).toEqual({ after: 1 });
  expect(restored.rows).toEqual([
    { id: 1, solver_status: 'FEASIBLE' },
    { id: 2, solver_status: 'OPTIMAL' },
  ]);
  expect(await studyRequest(sources[0], '', 'get', undefined, 0)).toEqual(restored);
  expect(axios.get).toHaveBeenCalledTimes(2);
});

it('does not treat metadata-only responses as a cached full study', async () => {
  axios.get.mockResolvedValueOnce({ data: snapshot({ rows: [] }) });
  await studyRequest(sources[0], '', 'get', undefined, Number.MAX_SAFE_INTEGER);
  axios.get.mockResolvedValueOnce({ data: snapshot() });
  expect((await studyRequest(sources[0], '', 'get', undefined, 0)).rows).toHaveLength(1);
  expect(axios.get.mock.calls[1][1].params).toEqual({ after: 0 });
});

it('keeps cached results private to a capability and the current Studio session', async () => {
  axios.get.mockResolvedValue({ data: snapshot() });
  await studyRequest(sources[0]);
  await studyRequest({ ...sources[0], key: 'different-key' });
  sessionStorage.setItem(
    'studioSession',
    JSON.stringify({ token: 'visitor', expires_at: Date.now() / 1000 + 60 })
  );
  await studyRequest(sources[0]);
  expect(axios.get).toHaveBeenCalledTimes(3);
  clearStudioSession();
  expect(
    Object.keys(sessionStorage).filter((key) => key.startsWith('roadtrips.studio.research.'))
  ).toEqual([]);
  await studyRequest(sources[0]);
  expect(axios.get).toHaveBeenCalledTimes(4);
});

it('reuses the library and catalog, and honors cancellation even for cached responses', async () => {
  sessionStorage.setItem(
    'studioSession',
    JSON.stringify({ token: 'visitor', expires_at: Date.now() / 1000 + 60 })
  );
  axios.get.mockResolvedValueOnce({ data: { studies: [{ id: 'current', database: true }] } });
  expect(await loadStudyLibrary()).toEqual(await loadStudyLibrary());
  axios.get.mockResolvedValueOnce({ data: { trips: [], personas: [] } });
  expect(await researchCatalog()).toEqual(await researchCatalog());
  expect(axios.get).toHaveBeenCalledTimes(2);
  const controller = new AbortController();
  controller.abort();
  await expect(loadStudyLibrary(controller.signal)).rejects.toMatchObject({ name: 'AbortError' });
  await expect(researchCatalog(controller.signal)).rejects.toMatchObject({ name: 'AbortError' });
  expect(axios.get).toHaveBeenCalledTimes(2);
});

it('falls back to same-tab memory when session storage is unavailable', async () => {
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('quota');
  });
  await saveResearchCache('large', 'visitor', { rows: [1, 2] });
  expect(await readResearchCache('large', 'visitor')).toEqual({ rows: [1, 2] });
  expect(await readResearchCache('large', 'someone-else')).toBeNull();
});

it('compresses large results and restores them in a fresh page session module', async () => {
  vi.stubGlobal('Blob', NativeBlob);
  const value = { rows: Array.from({ length: 1000 }, (_, id) => ({ id, status: 'OPTIMAL' })) };
  await saveResearchCache('large', 'visitor', value);
  const stored = JSON.parse(sessionStorage.getItem('roadtrips.studio.research.v1.large'));
  expect(stored.encoding).toBe('gzip');
  expect(stored.data.length).toBeLessThan(JSON.stringify(value).length / 2);
  vi.resetModules();
  const reloaded = await import('../services/studioResearchCache');
  expect(await reloaded.readResearchCache('large', 'visitor')).toEqual(value);
  reloaded.clearResearchCache();
});

it('invalidates saved snapshots after a successful control action', async () => {
  axios.get.mockResolvedValue({ data: snapshot() });
  await studyRequest(sources[0]);
  axios.post.mockResolvedValueOnce({ data: { state: 'paused' } });
  await studyRequest(sources[0], 'pause', 'post');
  await studyRequest(sources[0]);
  expect(axios.get).toHaveBeenCalledTimes(2);
});
