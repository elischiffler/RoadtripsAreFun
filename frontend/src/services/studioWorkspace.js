// One private workspace per browser tab and Studio session. Never a planning authority.
export const STUDIO_WORKSPACE_KEY = 'roadtrips.studio.workspace.v1';
const object = (value) => value != null && typeof value === 'object' && !Array.isArray(value);
const numericInput = (value) =>
  value === '' || (typeof value === 'number' && Number.isFinite(value));
const uuid = (value) =>
  typeof value === 'string' && /^[a-f\d]{8}(-[a-f\d]{4}){3}-[a-f\d]{12}$/i.test(value);

export function validStudioInputs(inputs) {
  return (
    object(inputs) &&
    ['start_id', 'destination_id', 'departure_date', 'departure_time', 'car_status'].every(
      (key) => typeof inputs[key] === 'string'
    ) &&
    ['num_stops', 'budget', 'traveler_count'].every((key) => numericInput(inputs[key])) &&
    object(inputs.persona_weights) &&
    Object.values(inputs.persona_weights).every(
      (value) => typeof value === 'number' && Number.isFinite(value)
    ) &&
    object(inputs.scheduling_policy) &&
    typeof inputs.scheduling_policy.late_driving === 'boolean' &&
    Array.isArray(inputs.evening_interests) &&
    inputs.evening_interests.every((value) => typeof value === 'string') &&
    (inputs.car == null || object(inputs.car)) &&
    Array.isArray(inputs.hotel_rooms) &&
    inputs.hotel_rooms.every(
      (room) =>
        object(room) &&
        numericInput(room.adults) &&
        Array.isArray(room.child_ages) &&
        room.child_ages.every(numericInput)
    )
  );
}

export function readStudioWorkspace(session) {
  try {
    const data = JSON.parse(sessionStorage.getItem(STUDIO_WORKSPACE_KEY));
    if (
      !session ||
      session.expires_at * 1000 <= Date.now() ||
      data?.version !== 1 ||
      data.session !== session.token ||
      data.backend !== import.meta.env.VITE_BACKEND_SERVER ||
      typeof data.presetId !== 'string' ||
      !validStudioInputs(data.inputs)
    )
      return null;
    const job =
      data.job &&
      uuid(data.job.id) &&
      ['running', 'complete'].includes(data.job.phase) &&
      (data.job.phase !== 'running' ||
        (object(data.job.run) &&
          validStudioInputs(data.job.run.inputs) &&
          typeof data.job.run.preset_id === 'string'))
        ? data.job
        : null;
    const result =
      object(data.result) && object(data.result.snapshot) && Array.isArray(data.result.stages)
        ? data.result
        : null;
    return {
      presetId: data.presetId,
      inputs: data.inputs,
      tab: ['route', 'itinerary', 'details'].includes(data.tab) ? data.tab : 'route',
      job,
      result,
    };
  } catch {
    return null;
  }
}

export function saveStudioWorkspace(session, workspace) {
  if (!session || session.expires_at * 1000 <= Date.now()) return false;
  const data = {
    version: 1,
    session: session.token,
    backend: import.meta.env.VITE_BACKEND_SERVER,
    ...workspace,
  };
  try {
    sessionStorage.setItem(STUDIO_WORKSPACE_KEY, JSON.stringify(data));
    return true;
  } catch {
    // Long road geometry can exceed sessionStorage's quota. Keep the saved job reference.
    try {
      sessionStorage.setItem(STUDIO_WORKSPACE_KEY, JSON.stringify({ ...data, result: null }));
      return true;
    } catch {
      return false;
    }
  }
}

export function clearStudioWorkspace() {
  try {
    sessionStorage.removeItem(STUDIO_WORKSPACE_KEY);
  } catch {
    // Storage may be disabled; expiry still gates the in-memory workspace.
  }
}
