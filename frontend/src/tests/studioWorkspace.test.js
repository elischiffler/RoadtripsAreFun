import { beforeEach, expect, it, vi } from 'vitest';
import {
  readStudioWorkspace,
  saveStudioWorkspace,
  clearStudioWorkspace,
  STUDIO_WORKSPACE_KEY,
} from '../services/studioWorkspace';
import { clearStudioSession } from '../services/studioSession';

const session = { token: 'visitor-one', expires_at: Date.now() / 1000 + 3600 };
const inputs = {
  start_id: 'sf',
  destination_id: 'boise',
  departure_date: '2026-10-25',
  departure_time: '09:00',
  num_stops: '',
  budget: 180.25,
  traveler_count: 2,
  hotel_rooms: [{ adults: 2, child_ages: [] }],
  car_status: 'skipped',
  car: null,
  persona_weights: { nature: 1 },
  scheduling_policy: { late_driving: false },
  evening_interests: [],
};
const workspace = {
  presetId: 'medium-two-day',
  inputs,
  tab: 'details',
  job: {
    id: '00000000-0000-4000-8000-000000000001',
    phase: 'running',
    run: { preset_id: 'medium-two-day', inputs },
  },
};
beforeEach(() => {
  sessionStorage.clear();
  import.meta.env.VITE_BACKEND_SERVER = 'http://localhost:8000/';
});

it('keeps the exact draft, active run identifier and selected tab after reload', () => {
  expect(saveStudioWorkspace(session, workspace)).toBe(true);
  expect(readStudioWorkspace(session)).toMatchObject(workspace);
  expect(readStudioWorkspace(session).inputs.budget).toBe(180.25);
  expect(readStudioWorkspace(session).inputs.num_stops).toBe('');
});
it('never restores another visitor, expired session or backend workspace', () => {
  saveStudioWorkspace(session, workspace);
  expect(readStudioWorkspace({ ...session, token: 'visitor-two' })).toBeNull();
  expect(readStudioWorkspace({ ...session, expires_at: 1 })).toBeNull();
  import.meta.env.VITE_BACKEND_SERVER = 'http://localhost:8001/';
  expect(readStudioWorkspace(session)).toBeNull();
});
it('ignores corrupt cache, broken room arrays and unknown versions', () => {
  sessionStorage.setItem(STUDIO_WORKSPACE_KEY, '{');
  expect(readStudioWorkspace(session)).toBeNull();
  saveStudioWorkspace(session, { ...workspace, inputs: { ...inputs, hotel_rooms: null } });
  expect(readStudioWorkspace(session)).toBeNull();
  saveStudioWorkspace(session, workspace);
  const saved = JSON.parse(sessionStorage.getItem(STUDIO_WORKSPACE_KEY));
  sessionStorage.setItem(STUDIO_WORKSPACE_KEY, JSON.stringify({ ...saved, version: 2 }));
  expect(readStudioWorkspace(session)).toBeNull();
});
it('keeps a server reference if road geometry exceeds the storage quota', () => {
  const set = Storage.prototype.setItem;
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (key, value) {
    if (JSON.parse(value).result) throw new DOMException('Full', 'QuotaExceededError');
    return set.call(this, key, value);
  });
  expect(saveStudioWorkspace(session, { ...workspace, result: { large: 'geometry' } })).toBe(true);
  expect(readStudioWorkspace(session).job.id).toBe(workspace.job.id);
  expect(readStudioWorkspace(session).result).toBeNull();
});
it('reports unavailable storage before allowing a new paid run', () => {
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('Disabled');
  });
  expect(saveStudioWorkspace(session, workspace)).toBe(false);
});
it('clears private trip state when Studio access is cleared', () => {
  saveStudioWorkspace(session, workspace);
  sessionStorage.setItem('studioSession', JSON.stringify(session));
  clearStudioSession();
  expect(sessionStorage.getItem(STUDIO_WORKSPACE_KEY)).toBeNull();
  clearStudioWorkspace();
});
