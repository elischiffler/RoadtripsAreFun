import request from './protectedRequest';
import { getSession, isCurrentSession, SessionError } from './session';
import { getFreshRoutingAlgorithm } from './routingSettings';
import { preferenceWeights, roomInputs } from '../pages/TripSetup/setupModel';
import { schedulingPolicyFromDraft } from '../pages/TripSetup/dailyRhythm';
import { streamPlanningCandidate } from './tripRouteStream';
import { safeCandidateError } from './planningCandidateErrors';

const root = () => import.meta.env.VITE_BACKEND_SERVER + 'planning-candidates';
const canonical = (value) =>
  value && typeof value === 'object' && !Array.isArray(value)
    ? Object.fromEntries(
        Object.keys(value)
          .sort()
          .map((key) => [key, canonical(value[key])])
      )
    : Array.isArray(value)
      ? value.map(canonical)
      : value;

export function candidateTripInputs(draft) {
  return {
    num_stops: Number(draft.stops),
    traveler_count: Number(draft.travelers),
    persona_weights: preferenceWeights(draft),
    scheduling_policy: schedulingPolicyFromDraft(draft),
    reserve_meal_slots: true,
    start: `${draft.date}T${draft.time}:00`,
  };
}

export function candidateDraftKey(draft) {
  return JSON.stringify(
    canonical({
      start_query: draft.start.trim(),
      destination_query: draft.destination.trim(),
      ...candidateTripInputs(draft),
    })
  );
}

const validPoints = (points, latitudeFirst = true) =>
  Array.isArray(points) &&
  points.length >= 2 &&
  points.every(
    (point) =>
      Array.isArray(point) &&
      point.length === 2 &&
      point.every(Number.isFinite) &&
      Math.abs(point[latitudeFirst ? 0 : 1]) <= 90 &&
      Math.abs(point[latitudeFirst ? 1 : 0]) <= 180
  );

export const completeRoute = (route) =>
  route &&
  Number.isFinite(route.distance) &&
  route.distance >= 0 &&
  Number.isFinite(route.duration) &&
  route.duration >= 0 &&
  validPoints(route.coordinates) &&
  validPoints(route.geometry?.coordinates, false);

export function validateCandidate(data) {
  const proof = data?.one_day;
  if (
    typeof data?.candidate_id !== 'string' ||
    !/^[A-Za-z0-9_-]{16,128}$/.test(data.candidate_id) ||
    typeof data.input_key !== 'string' ||
    !/^[a-f0-9]{64}$/.test(data.input_key) ||
    !Number.isFinite(Date.parse(data.expires_at)) ||
    typeof proof?.eligible !== 'boolean' ||
    proof.threshold_seconds !== 43200 ||
    (proof.elapsed_seconds !== null &&
      (!Number.isFinite(proof.elapsed_seconds) || proof.elapsed_seconds < 0)) ||
    (data.candidate_route !== null && !completeRoute(data.candidate_route)) ||
    (proof.eligible &&
      (!(proof.elapsed_seconds < 43200) ||
        proof.elapsed_seconds === null ||
        !completeRoute(data.candidate_route)))
  )
    throw new Error('No verified trip option was returned. Your draft is kept.');
  return data;
}

const preserveSessionError = (error) => {
  if (error instanceof SessionError || error?.name === 'AbortError') throw error;
  throw safeCandidateError(error);
};

export async function registerCandidateRequest(requestId, signal) {
  try {
    const { data } = await request.post(
      `${root()}/requests`,
      { request_id: requestId },
      { signal }
    );
    if (data?.request_id !== requestId || !Number.isFinite(Date.parse(data.expires_at)))
      throw new Error('The trip option check could not be registered.');
    return data;
  } catch (error) {
    return preserveSessionError(error);
  }
}

export async function buildCandidatePayload(draft, initialRoute, requestId) {
  const session = getSession();
  const algorithm = await getFreshRoutingAlgorithm();
  if (!isCurrentSession(session)) throw new SessionError('session-changed');
  return {
    request_id: requestId,
    initial_route: initialRoute,
    ...candidateTripInputs(draft),
    ...(algorithm ? { algorithm } : {}),
  };
}

export async function assessPlanningCandidate(
  draft,
  initialRoute,
  requestId,
  signal,
  onProgress,
  preparedPayload
) {
  const session = getSession();
  const payload = preparedPayload ?? (await buildCandidatePayload(draft, initialRoute, requestId));
  if (!isCurrentSession(session) || signal?.aborted) throw new SessionError('session-changed');
  try {
    const data = await streamPlanningCandidate(payload, signal, onProgress);
    if (!isCurrentSession(session) || signal?.aborted) throw new SessionError('session-changed');
    return validateCandidate(data);
  } catch (error) {
    return preserveSessionError(error);
  }
}

export async function confirmPlanningCandidate(candidate, mode, draft, signal) {
  const session = getSession();
  const payload = {
    input_key: candidate.input_key,
    trip_mode: mode,
    traveler_count: Number(draft.travelers),
    ...(mode === 'overnight'
      ? { budget: Number(draft.budget), hotel_rooms: roomInputs(draft) }
      : {}),
  };
  try {
    const { data } = await request.post(
      `${root()}/${encodeURIComponent(candidate.candidate_id)}/confirm`,
      payload,
      { signal }
    );
    if (!isCurrentSession(session) || signal?.aborted) throw new SessionError('session-changed');
    const proof = data?.one_day_proof;
    const provenOneDay =
      proof?.status === 'validated' &&
      proof.threshold_seconds === 43200 &&
      Number.isFinite(proof.elapsed_seconds) &&
      proof.elapsed_seconds >= 0 &&
      proof.elapsed_seconds < 43200;
    if (
      !completeRoute(data) ||
      data.reserve_meal_slots !== true ||
      data.trip_mode !== mode ||
      (mode === 'one_day' && !provenOneDay)
    )
      throw new Error('The confirmed trip did not include a verified schedule.');
    return data;
  } catch (error) {
    return preserveSessionError(error);
  }
}

export async function cancelCandidateRequest(requestId, session) {
  if (!requestId || !isCurrentSession(session)) return;
  await request.delete(`${root()}/requests/${encodeURIComponent(requestId)}`);
}
