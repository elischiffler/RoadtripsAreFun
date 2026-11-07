import { loadRouteAlternatives } from '../services/routeAlternatives';
import { beforeEach, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from './testUtils';
import { fixtureSession } from './sessionFixtures';
import { getSession } from '../services/session';
import { newSetupDraft } from '../pages/TripSetup/setupModel';
import TripSetupPage from '../pages/TripSetup/TripSetupPage';
import client from 'axios';
import {
  resolveTripLocation,
  estimateStructuredRoute,
  planStructuredItinerary,
} from '../services/tripPlanner';

vi.mock('axios');
vi.mock('../services/tripPlanner', async (original) => ({
  ...(await original()),
  resolveTripLocation: vi.fn(),
  estimateStructuredRoute: vi.fn(),
  planStructuredItinerary: vi.fn(),
}));

import {
  assessPlanningCandidate,
  buildCandidatePayload,
  cancelCandidateRequest,
  confirmPlanningCandidate,
  registerCandidateRequest,
} from '../services/planningCandidates';
vi.mock('../services/planningCandidates', () => ({
  assessPlanningCandidate: vi.fn(),
  buildCandidatePayload: vi.fn(),
  cancelCandidateRequest: vi.fn(async () => {}),
  confirmPlanningCandidate: vi.fn(),
  registerCandidateRequest: vi.fn(),
}));
vi.mock('../services/routeAlternatives', () => ({
  loadRouteAlternatives: vi.fn(async () => ({ places: [] })),
}));
const origin = { address: 'Boulder, Colorado', latitude: 40, longitude: -105 };
const destination = { address: 'Fort Morgan, Colorado', latitude: 40.2, longitude: -103.8 };
const route = {
  coordinates: [
    [40, -105],
    [40.2, -103.8],
  ],
  geometry: {
    type: 'LineString',
    coordinates: [
      [-105, 40],
      [-103.8, 40.2],
    ],
  },
  duration: 3600,
  distance: 50000,
  cost: 0,
  departure_time: '2027-06-01T09:00:00-06:00',
  start_timezone: 'America/Denver',
  stops: [{ name: 'Fixture stop', type: 'end', arrival_time: '2027-06-01T10:00:00-06:00' }],
};

beforeEach(() => {
  vi.resetAllMocks();
  loadRouteAlternatives.mockResolvedValue({ places: [] });
  sessionStorage.clear();
  fixtureSession();
  import.meta.env.VITE_BACKEND_SERVER = 'http://fixture/';
  sessionStorage.setItem(
    'roadtrips.setup.v1.' + encodeURIComponent(getSession().owner),
    JSON.stringify({
      version: 1,
      step: 4,
      draft: {
        ...newSetupDraft(),
        start: 'Boulder',
        destination: 'Fort Morgan',
        date: '2027-06-01',
        carStatus: 'skipped',
      },
    })
  );
  client.get.mockResolvedValue({ data: [] });
  client.post.mockResolvedValue({ status: 201, data: {} });
  resolveTripLocation.mockImplementation(async (query) => [
    query === 'Boulder' ? origin : destination,
  ]);
  estimateStructuredRoute.mockResolvedValue(route);
  cancelCandidateRequest.mockResolvedValue(undefined);
  registerCandidateRequest.mockResolvedValue({});
  buildCandidatePayload.mockResolvedValue({ immutable: true });
  assessPlanningCandidate.mockResolvedValue({
    candidate_id: 'fixture-candidate',
    input_key: 'f'.repeat(64),
    expires_at: '2099-01-01T00:00:00Z',
    one_day: { eligible: true, elapsed_seconds: 7200, threshold_seconds: 43200 },
    candidate_route: route,
  });
  confirmPlanningCandidate.mockResolvedValue(route);
  planStructuredItinerary.mockResolvedValue([
    { date: 'Tuesday, June 01 2027', stops: route.stops },
  ]);
});

it('persists a completed first trip through the actual saved-trip lifecycle before claiming success', async () => {
  renderWithProviders(<TripSetupPage />);
  await userEvent.click(await screen.findByRole('button', { name: 'Check trip options' }));
  await userEvent.click(await screen.findByRole('button', { name: 'Finish in one day' }));
  await screen.findByText('Trip saved.');
  expect(client.post).toHaveBeenCalledTimes(1);
  expect(client.post.mock.calls[0][0]).toBe('http://fixture/chats/create/1');
  expect(client.post.mock.calls[0][1].ChatData.isComplete).toBe(true);
  expect(client.post.mock.calls[0][1].ChatData.route.departure_time).toBe(route.departure_time);
  expect(client.post.mock.calls[0][1].ChatLog.id).toBe(1);
});
