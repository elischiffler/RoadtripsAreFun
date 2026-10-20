import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import axios from 'axios';
import { downloadStudy, savedStudies, rerunStudy } from '../services/studioResearch';

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }));
const sources = [
  { id: 'main', key: 'main-key' },
  { id: 'pilot', key: 'pilot-key' },
];
let exported;
beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
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
    'studioResearchStudies',
    JSON.stringify([sources[0], sources[0], null, sources[1]])
  );
  expect(savedStudies()).toEqual(sources);
});

it('archives historical access and replaces the active batch only after a successful rerun creation', async () => {
  localStorage.setItem('studioResearchStudies', JSON.stringify(sources));
  const replacement = { id: 'rerun', key: 'new-key' };
  axios.post.mockResolvedValueOnce({ data: replacement });
  expect(await rerunStudy(sources[0], sources)).toEqual(replacement);
  expect(savedStudies()).toEqual([replacement]);
  expect(JSON.parse(localStorage.getItem('studioResearchArchivedStudies'))).toEqual(sources);
  expect(axios.post.mock.calls[0][2].headers['X-Studio-Batch-Key']).toBe('main-key');
  axios.post.mockRejectedValueOnce(new Error('active batch'));
  await expect(rerunStudy(replacement, [replacement])).rejects.toThrow('active batch');
  expect(savedStudies()).toEqual([replacement]);
  expect(JSON.parse(localStorage.getItem('studioResearchArchivedStudies'))).toEqual(sources);
});
