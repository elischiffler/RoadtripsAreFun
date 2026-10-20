import axios from 'axios';

const KEY = 'studioResearchStudies';
export function savedStudies() {
  try {
    const rows = JSON.parse(localStorage.getItem(KEY) || '[]');
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
export async function researchCatalog(signal) {
  return (
    await axios.get(`${import.meta.env.VITE_BACKEND_SERVER}studio/research/catalog`, { signal })
  ).data;
}
export async function studyRequest(study, action = '', method = 'get', signal, after) {
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
