import axios from 'axios';
import { studioRequest } from './studioSession';

const KEY = 'studioResearchStudies';
export function savedStudies() {
  try {
    const rows = JSON.parse(localStorage.getItem(KEY) || '[]');
    return Array.isArray(rows)
      ? rows.filter((row) => typeof row.id === 'string' && typeof row.key === 'string')
      : [];
  } catch {
    return [];
  }
}
export function rememberStudy(study) {
  const rows = [study, ...savedStudies().filter((row) => row.id !== study.id)];
  localStorage.setItem(KEY, JSON.stringify(rows));
}
export async function researchCatalog(signal) {
  return (
    await axios.get(`${import.meta.env.VITE_BACKEND_SERVER}studio/research/catalog`, { signal })
  ).data;
}
export async function createStudy(id, design) {
  const study = (await studioRequest('post', 'research/batches', { id, design })).data;
  rememberStudy(study);
  return study;
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
export async function downloadStudy(study, format) {
  const data = await studyRequest(study, `export?format=${format}`);
  const blob = new Blob([typeof data === 'string' ? data : JSON.stringify(data, null, 2)], {
    type: format === 'csv' ? 'text/csv' : 'application/json',
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `study-${study.id}.${format}`;
  link.click();
  URL.revokeObjectURL(url);
}
