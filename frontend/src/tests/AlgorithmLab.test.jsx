import { fixtureSession, fixtureToken } from './sessionFixtures';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axios from 'axios';
import AlgorithmLab from '../pages/AlgorithmLab/AlgorithmLab';
import GlobalHeader from '../components/GlobalHeader';
import { invalidateRoutingSettings } from '../services/routingSettings';
import { renderWithProviders } from './testUtils';

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }));
vi.mock('../components/Map', () => ({ default: () => <div>Live route map</div> }));

const inputs = {
  start_id: 'sf',
  destination_id: 'monterey',
  departure_date: '2026-10-06',
  departure_time: '09:00',
  num_stops: 2,
  traveler_count: 2,
  hotel_rooms: [{ adults: 2, child_ages: [] }],
  budget: 150,
  car_status: 'skipped',
  car: null,
  persona_weights: { nature: 0.8, history: 0.2 },
  scheduling_policy: {
    preferred_hotel_arrival: '18:00',
    latest_hotel_arrival: '20:00',
    latest_destination_arrival: null,
    morning_restart: '09:00',
    late_driving: false,
    late_cutoff: '24:00',
  },
  evening_interests: [],
};
const quickTrips = [
  {
    id: 'family',
    label: 'Medium two-day',
    description: 'Family trip with an early evening.',
    inputs: {
      ...inputs,
      departure_date: '2026-10-08',
      departure_time: '07:00',
      num_stops: 4,
      traveler_count: 4,
      hotel_rooms: [{ adults: 2, child_ages: [7, 12] }],
      budget: 180,
      car_status: 'provided',
      car: { year: 2023, make: 'Toyota', model: 'RAV4' },
      persona_weights: { nature: 0.6, history: 0.4 },
      scheduling_policy: {
        ...inputs.scheduling_policy,
        preferred_hotel_arrival: '17:00',
        latest_hotel_arrival: '19:00',
        latest_destination_arrival: '19:00',
        morning_restart: '08:00',
      },
      evening_interests: ['food'],
    },
  },
  {
    id: 'budget',
    label: 'Tight hotel budget',
    description: 'Three travelers sharing a room.',
    inputs: {
      ...inputs,
      start_id: 'monterey',
      destination_id: 'sf',
      departure_time: '08:30',
      traveler_count: 3,
      hotel_rooms: [{ adults: 3, child_ages: [] }],
      budget: 60,
      evening_interests: ['food'],
    },
  },
];
const catalog = {
  schema_version: 1,
  attributes: ['nature', 'history'],
  endpoints: [
    { id: 'sf', label: 'San Francisco' },
    { id: 'monterey', label: 'Monterey' },
  ],
  benchmarks: quickTrips,
  presets: [
    { id: 'coast', label: 'Coastal nature', inputs },
    {
      id: 'culture',
      label: 'Culture trip',
      inputs: { ...inputs, persona_weights: { nature: 0.2, history: 0.8 } },
    },
    ...quickTrips,
  ],
  limits: { min_stops: 1, max_stops: 10, max_rooms: 4, max_guests_per_room: 6, max_child_age: 17 },
};
const response = () => ({
  schema_version: 1,
  mode: 'live',
  input_snapshot: inputs,
  snapshot: { id: 'live-1', label: 'Fresh live discovery', source: 'Live provider discovery' },
  explanation: {
    weights: { nature: 0.8, history: 0.2 },
    candidates: [
      {
        provider_id: 'forest',
        name: 'Forest walk',
        slot: 0,
        utility: 0.76,
        selected: true,
        reason: 'selected',
        objective_coefficient: 123456,
        provenance: { ratings: 'synthetic' },
        contributions: [
          { attribute: 'nature', weight: 0.8, rating: 0.9, contribution: 0.72 },
          { attribute: 'history', weight: 0.2, rating: 0.2, contribution: 0.04 },
        ],
      },
    ],
    solver: {
      status: 'OPTIMAL',
      objective_value: 123456,
      best_bound: 123456,
      wall_time_seconds: 0.004,
      requested_stops: 2,
      selected_count: 1,
      eligible_count: 1,
      utility_threshold: 0.6,
    },
  },
  route: null,
  itinerary: null,
  stages: [
    { name: 'selection', status: 'complete', detail: 'Attraction selection finished.' },
    { name: 'scheduling', status: 'not_run', detail: 'Selection-only fixture.' },
  ],
  error: null,
});
function login(sub = 'owner', expiry = Date.now() / 1000 + 600) {
  fixtureSession(sub);
  sessionStorage.setItem('accessToken', fixtureToken(sub, expiry));
  sessionStorage.setItem('idToken', fixtureToken(sub, expiry, 'id'));
}
function capability() {
  return {
    data: {
      can_select_algorithm: true,
      algorithms: ['cp_sat'],
      default: 'cp_sat',
      expires_at: Date.now() / 1000 + 600,
    },
  };
}
async function mount() {
  const view = renderWithProviders(<AlgorithmLab />, { initialPath: '/algorithm' });
  await screen.findByRole('button', { name: 'Run live route' });
  return view;
}

beforeEach(() => {
  vi.resetAllMocks();
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute('open', '');
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute('open');
  };
  sessionStorage.clear();
  invalidateRoutingSettings();
  login();
  import.meta.env.VITE_BACKEND_SERVER = 'http://localhost:8000/';
  axios.get.mockImplementation((url) =>
    Promise.resolve(
      url.endsWith('routing-settings')
        ? capability()
        : url.endsWith('algorithm-lab/runs')
          ? { data: { runs: [], groups: [], next_offset: null } }
          : { data: structuredClone(catalog) }
    )
  );
  axios.post.mockResolvedValue({ data: response() });
});
afterEach(() => {
  vi.useRealTimers();
  invalidateRoutingSettings();
  sessionStorage.clear();
});

describe('Algorithm Lab access and lifecycle', () => {
  it.each(['missing', 'non-owner', 'unavailable'])(
    'does not load private presets for %s access',
    async (kind) => {
      if (kind === 'missing') sessionStorage.clear();
      else if (kind === 'non-owner')
        axios.get.mockResolvedValue({ data: { can_select_algorithm: false } });
      else axios.get.mockRejectedValue(new Error('offline'));
      renderWithProviders(
        <>
          <GlobalHeader />
          <AlgorithmLab />
        </>
      );
      await waitFor(() => expect(screen.getByText('Owner access required')).toBeInTheDocument());
      expect(axios.get.mock.calls.every(([url]) => url.endsWith('routing-settings'))).toBe(true);
      expect(screen.queryByRole('link', { name: 'Algorithm Lab' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Run live route' })).not.toBeInTheDocument();
    }
  );

  it('shows the server-authorized navigation link', async () => {
    renderWithProviders(<GlobalHeader />);
    expect(await screen.findByRole('link', { name: 'Algorithm Lab' })).toHaveAttribute(
      'href',
      '/algorithm'
    );
  });

  it('keeps the presentation page free of the global header', async () => {
    renderWithProviders(
      <>
        <GlobalHeader />
        <AlgorithmLab />
      </>,
      { initialPath: '/algorithm' }
    );
    await screen.findByRole('button', { name: 'Run live route' });
    expect(document.querySelector('.global-header')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to trip chat' })).toHaveAttribute(
      'href',
      '/chat'
    );
  });

  it('retries a failed catalog request', async () => {
    let attempts = 0;
    axios.get.mockImplementation((url) => {
      if (url.endsWith('routing-settings')) return Promise.resolve(capability());
      return ++attempts === 1
        ? Promise.reject(new Error('offline'))
        : Promise.resolve({ data: catalog });
    });
    renderWithProviders(<AlgorithmLab />);
    await userEvent.click(await screen.findByRole('button', { name: 'Retry preset loading' }));
    expect(await screen.findByRole('button', { name: 'Run live route' })).toBeInTheDocument();
  });

  it.each(['logout', 'account switch', 'expiry'])(
    'removes private results and ignores an in-flight response on %s',
    async (action) => {
      let resolveRun;
      axios.post.mockImplementation(
        () =>
          new Promise((resolve) => {
            resolveRun = resolve;
          })
      );
      await mount();
      await userEvent.click(screen.getByRole('button', { name: 'Run live route' }));
      const signal = axios.post.mock.calls[0][2].signal;
      act(() => {
        if (action === 'logout') sessionStorage.clear();
        else if (action === 'account switch') {
          login('other');
          axios.get.mockResolvedValue({ data: { can_select_algorithm: false } });
        } else {
          vi.useFakeTimers();
          vi.setSystemTime(Date.now() + 700000);
        }
        window.dispatchEvent(new Event(action === 'expiry' ? 'focus' : 'auth-changed'));
      });
      await act(async () => resolveRun({ data: response() }));
      expect(signal.aborted).toBe(true);
      expect(screen.getByText('Owner access required')).toBeInTheDocument();
      expect(screen.queryByText('OPTIMAL')).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Run live route' })).not.toBeInTheDocument();
    }
  );
});

describe('Algorithm Lab experiments', () => {
  it('opens presets in a modal and dismisses without changing the form or starting a run', async () => {
    await mount();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Trip presets' }));
    expect(screen.getByRole('dialog', { name: 'Choose a trip preset' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Coastal nature/ })).toHaveAttribute(
      'aria-pressed',
      'true'
    );
    await userEvent.click(screen.getByRole('button', { name: 'Close presets' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByText('Selected trip: Coastal nature')).toBeInTheDocument();
    expect(screen.getByLabelText('Travelers')).toHaveValue(2);
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('fills the entire form from a trip card without running, and replaces all fields on the next choice', async () => {
    await mount();
    await userEvent.click(screen.getByRole('button', { name: 'Trip presets' }));
    await userEvent.click(screen.getByRole('button', { name: /Medium two-day/ }));
    expect(axios.post).not.toHaveBeenCalled();
    expect(screen.queryByRole('dialog', { name: 'Choose a trip preset' })).not.toBeInTheDocument();
    expect(screen.getByText('Selected trip: Medium two-day')).toBeInTheDocument();
    expect(screen.getByLabelText('Travelers')).toHaveValue(4);
    expect(screen.getByLabelText('Departure date')).toHaveValue('2026-10-08');
    expect(screen.getByLabelText('Departure time')).toHaveValue('07:00');
    await userEvent.click(screen.getByText('Rooms and travelers'));
    expect(screen.getByLabelText('Room 1 child 2 age')).toHaveValue(12);
    await userEvent.click(screen.getByText('Car and evening schedule'));
    expect(screen.getByLabelText('Car model')).toHaveValue('RAV4');
    expect(screen.getByLabelText('latest hotel arrival')).toHaveValue('19:00');
    await userEvent.click(screen.getByRole('button', { name: 'Run live route' }));
    await screen.findByText('OPTIMAL');
    expect(axios.post.mock.calls[0][1]).toEqual({
      mode: 'live',
      preset_id: 'family',
      inputs: quickTrips[0].inputs,
    });
    await userEvent.click(screen.getByRole('button', { name: 'Trip presets' }));
    await userEvent.click(screen.getByRole('button', { name: /Tight hotel budget/ }));
    expect(screen.queryByText('OPTIMAL')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Start')).toHaveValue('monterey');
    expect(screen.getByLabelText('Destination')).toHaveValue('sf');
    expect(screen.getByLabelText('Hotel target / room / night (USD)')).toHaveValue(60);
    expect(screen.getByLabelText('Travelers')).toHaveValue(3);
    expect(screen.queryByLabelText('Room 1 child 2 age')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Car model')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Run live route' }));
    await screen.findByText('OPTIMAL');
    expect(axios.post.mock.calls[1][1].inputs).toEqual(quickTrips[1].inputs);
    await userEvent.click(screen.getByRole('button', { name: 'Trip presets' }));
    await userEvent.click(screen.getByRole('button', { name: /Medium two-day/ }));
    fireEvent.change(screen.getByLabelText('Room 1 child 2 age'), { target: { value: '13' } });
    await userEvent.click(screen.getByRole('button', { name: 'Reset preset' }));
    expect(screen.getByLabelText('Room 1 child 2 age')).toHaveValue(12);
    await userEvent.click(screen.getByRole('button', { name: 'Trip presets' }));
    expect(screen.getByRole('button', { name: /Medium two-day/ })).toHaveAttribute(
      'aria-pressed',
      'true'
    );
  });

  it('sends edited inputs and both tokens, displays actual contributions, and clears stale success on edits', async () => {
    await mount();
    fireEvent.change(screen.getByLabelText('Maximum attractions'), { target: { value: '3' } });
    fireEvent.change(screen.getByLabelText('Interest nature percentage'), {
      target: { value: '60' },
    });
    await userEvent.click(screen.getByRole('button', { name: 'Run live route' }));
    expect(await screen.findByText('OPTIMAL')).toBeInTheDocument();
    const [, request, config] = axios.post.mock.calls[0];
    expect(request).toMatchObject({
      mode: 'live',
      preset_id: 'coast',
      inputs: { num_stops: 3, persona_weights: { nature: 0.6 } },
    });
    expect(config.headers).toEqual({
      Authorization: `Bearer ${sessionStorage.getItem('accessToken')}`,
      'X-Cognito-Id-Token': sessionStorage.getItem('idToken'),
    });
    expect(screen.getByText('Live provider run')).toBeInTheDocument();
    expect(request).not.toHaveProperty('snapshot_id');
    expect(screen.queryByLabelText('Run mode')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Candidate snapshot')).not.toBeInTheDocument();
    await userEvent.click(screen.getByText('Forest walk'));
    expect(
      screen.getByRole('table', { name: 'Score contributions for Forest walk' })
    ).toHaveTextContent('0.72');
    fireEvent.change(screen.getByLabelText('Departure time'), { target: { value: '10:00' } });
    expect(screen.queryByText('OPTIMAL')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Reset preset' }));
    expect(screen.getByLabelText('Maximum attractions')).toHaveValue(2);
    expect(screen.getByLabelText('Interest nature percentage')).toHaveValue(80);
  });

  it('prevents duplicate submissions and discards a cancelled response', async () => {
    let resolveRun;
    axios.post.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRun = resolve;
        })
    );
    await mount();
    await userEvent.dblClick(screen.getByRole('button', { name: 'Run live route' }));
    expect(axios.post).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Running…' })).toBeDisabled();
    expect(screen.getByLabelText('Interest nature percentage')).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Cancel and reset' }));
    await act(async () => resolveRun({ data: response() }));
    expect(screen.queryByText('OPTIMAL')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Run live route' })).toBeEnabled();
  });

  it('does not claim same-snapshot comparisons for fresh live discoveries', async () => {
    await mount();
    await userEvent.click(screen.getByRole('button', { name: 'Run live route' }));
    await screen.findByText('OPTIMAL');
    const next = response();
    next.snapshot.id = 'live-2';
    next.explanation.weights = { nature: 0.2, history: 0.8 };
    next.explanation.candidates[0].name = 'Historic market';
    axios.post.mockResolvedValue({ data: next });
    await userEvent.click(screen.getByRole('button', { name: 'Trip presets' }));
    await userEvent.click(screen.getByRole('button', { name: /Culture trip/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Run live route' }));
    expect(await screen.findByText('Historic market')).toBeInTheDocument();
    expect(screen.queryByText('Same snapshot comparison')).not.toBeInTheDocument();
    expect(axios.post.mock.calls.every(([, body]) => body.mode === 'live')).toBe(true);
  });

  it('reveals short explanations by keyboard or tap and keeps the long formula in a disclosure', async () => {
    await mount();
    const help = screen.getByRole('button', { name: 'About trip weights' });
    fireEvent.focus(help);
    expect(await screen.findByRole('tooltip')).toHaveTextContent('sum to 100%');
    fireEvent.keyDown(help, { key: 'Escape' });
    fireEvent.blur(help);
    await waitFor(() => expect(screen.queryByRole('tooltip')).not.toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: 'Run live route' }));
    await screen.findByText('OPTIMAL');
    expect(screen.getByLabelText('Experiment output')).toHaveFocus();
    await userEvent.click(screen.getByRole('button', { name: 'About integer objective' }));
    expect(await screen.findByRole('tooltip')).toHaveTextContent('not a percentage');
    const formula = screen.getByText('Constraints and objective formula').closest('details');
    expect(formula).not.toHaveAttribute('open');
    await userEvent.click(screen.getByText('Constraints and objective formula'));
    expect(formula).toHaveAttribute('open');
    expect(formula).toHaveTextContent('maximize sum(c[i] × x[i])');
  });

  it('keeps a live provider failure distinct from replay and preserves selection diagnostics', async () => {
    const data = response();
    data.mode = 'live';
    data.error = { code: 'schedule_failed', message: 'No hotel offers available.' };
    data.stages[1] = { name: 'scheduling', status: 'failed', detail: 'No verified offers.' };
    axios.post.mockResolvedValue({ data });
    await mount();
    await userEvent.click(screen.getByRole('button', { name: 'Run live route' }));
    expect(await screen.findByText('OPTIMAL')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('No hotel offers available.');
    expect(screen.getByText('Live provider run')).toBeInTheDocument();
    expect(screen.queryByText('Replay · frozen candidate fixture')).not.toBeInTheDocument();
    expect(axios.post.mock.calls[0][1]).not.toHaveProperty('snapshot_id');
    expect(screen.getByText(/No completed road route is available/)).toBeInTheDocument();
  });

  it('renders a live route and the shared itinerary with truthful feasible status', async () => {
    const data = response();
    data.mode = 'live';
    data.explanation.solver.status = 'FEASIBLE';
    data.route = {
      distance: 100000,
      duration: 7200,
      cost: 150,
      geometry: {
        coordinates: [
          [-122, 37],
          [-121, 36],
        ],
      },
      warnings: ['Room quote is above target.'],
      stops: [{ name: 'Forest walk', type: 'attraction' }],
    };
    data.itinerary = [
      {
        date: '2026-10-06',
        stops: [{ name: 'Forest visit', time: '11:00', address: 'Trailhead', kind: 'arrival' }],
      },
    ];
    axios.post.mockResolvedValue({ data });
    await mount();
    await userEvent.click(screen.getByRole('button', { name: 'Run live route' }));
    expect(await screen.findByText('Live route map')).toBeInTheDocument();
    expect(screen.getByText('Forest visit')).toBeInTheDocument();
    expect(screen.getByText(/Optimality was not proved/)).toBeInTheDocument();
    expect(screen.getByText('Room quote is above target.')).toBeInTheDocument();
  });

  it('renders rejected malformed diagnostics without inventing score contributions', async () => {
    const data = response();
    data.explanation.candidates = [
      { name: 'Malformed place', provider_id: null, selected: false, reason: 'invalid_candidate' },
      {
        name: 'Duplicate place',
        provider_id: null,
        selected: false,
        reason: 'duplicate_provider_id',
      },
    ];
    axios.post.mockResolvedValue({ data });
    await mount();
    await userEvent.click(screen.getByRole('button', { name: 'Run live route' }));
    await userEvent.click(await screen.findByText('Malformed place'));
    expect(
      screen
        .getByRole('table', { name: 'Score contributions for Malformed place' })
        .querySelectorAll('tbody tr')
    ).toHaveLength(0);
    expect(screen.getByText('Duplicate place')).toBeInTheDocument();
    expect(screen.getByText('invalid candidate · slot unassigned')).toBeInTheDocument();
  });

  it.each([422, 503, 401])('handles HTTP %s without showing old output', async (status) => {
    await mount();
    await userEvent.click(screen.getByRole('button', { name: 'Run live route' }));
    await screen.findByText('OPTIMAL');
    axios.post.mockRejectedValue({
      response: {
        status,
        data: {
          detail:
            status === 422
              ? [{ loc: ['body', 'inputs', 'traveler_count'], msg: 'Room occupants do not match.' }]
              : undefined,
        },
      },
    });
    await userEvent.click(screen.getByRole('button', { name: 'Run live route' }));
    if (status === 401)
      expect(await screen.findByText('Owner access required')).toBeInTheDocument();
    else
      expect(await screen.findByRole('alert')).toHaveTextContent(
        status === 422 ? 'Room occupants do not match.' : 'Check your connection'
      );
    expect(screen.queryByText('OPTIMAL')).not.toBeInTheDocument();
  });

  it('edits room occupancy, car and scheduling values without modifying saved chats', async () => {
    await mount();
    await userEvent.click(screen.getByText('Rooms and travelers'));
    await userEvent.click(screen.getByRole('button', { name: 'Add child to room 1' }));
    fireEvent.change(screen.getByLabelText('Room 1 child 1 age'), { target: { value: '9' } });
    fireEvent.change(screen.getByLabelText('Travelers'), { target: { value: '3' } });
    await userEvent.click(screen.getByText('Car and evening schedule'));
    await userEvent.selectOptions(screen.getByLabelText('Car choice'), 'provided');
    fireEvent.change(screen.getByLabelText('Car year'), { target: { value: '2020' } });
    fireEvent.change(screen.getByLabelText('Car make'), { target: { value: 'Toyota' } });
    fireEvent.change(screen.getByLabelText('Car model'), { target: { value: 'Prius' } });
    await userEvent.click(screen.getByLabelText('Allow late driving'));
    await userEvent.click(screen.getByLabelText('food'));
    await userEvent.click(screen.getByRole('button', { name: 'Run live route' }));
    await screen.findByText('OPTIMAL');
    expect(axios.post.mock.calls[0][1].inputs).toMatchObject({
      traveler_count: 3,
      hotel_rooms: [{ adults: 2, child_ages: [9] }],
      car_status: 'provided',
      car: { year: 2020, make: 'Toyota', model: 'Prius' },
      scheduling_policy: { late_driving: true },
      evening_interests: ['food'],
    });
    expect(axios.post).toHaveBeenCalledTimes(1);
  });
});
