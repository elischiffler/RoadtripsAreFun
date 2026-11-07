import axios from 'axios';
import request from './protectedRequest';

// Separate public transport: never attach account credentials to a capability read.
const publicRequest = () => axios.create({ withCredentials: false });
const base = () => import.meta.env.VITE_BACKEND_SERVER;
const ownerPath = (trip) => `${base()}chats/${trip.chatId}/sharing`;
const config = (signal) => ({ signal, timeout: 15000 });
export const getSharing = async (trip, signal) =>
  (await request.get(ownerPath(trip), config(signal))).data;
export const createShareLink = async (trip) =>
  (
    await request.post(
      ownerPath(trip) + '/link',
      { expected_revision: trip.savedRevision },
      config()
    )
  ).data;
export const changeSharing = async (trip, shareId, action, memberId) =>
  (
    await request.delete(
      ownerPath(trip) +
        (action === 'link' ? '/link' : action === 'member' ? `/members/${memberId}` : '') +
        `?share_id=${encodeURIComponent(shareId)}`,
      config()
    )
  ).data;
export const viewShareLink = async (token, signal) =>
  (await publicRequest().post(base() + 'trip-sharing/view', { token }, config(signal))).data;
export const connectSharedTrip = async (token, displayName) =>
  (
    await request.post(
      base() + 'trip-sharing/connect',
      { token, display_name: displayName },
      config()
    )
  ).data;
export const listSharedTrips = async (signal) =>
  (await request.get(base() + 'shared-trips', config(signal))).data;
export const viewConnectedTrip = async (id, signal) =>
  (await request.get(base() + `shared-trips/${id}`, config(signal))).data;
export const leaveSharedTrip = async (id) =>
  request.delete(base() + `shared-trips/${id}/membership`, config());
export const shareLinkUrl = (token) => `${window.location.origin}/share#token=${token}`;
export const shareToken = (hash) => {
  const match = /^#token=([A-Za-z0-9_-]{43})$/.exec(hash);
  return match?.[1] ?? null;
};
export const sharingError = (error) =>
  error.response?.status === 404
    ? 'This shared trip is unavailable. Its owner may have stopped sharing it.'
    : error.response?.status === 409
      ? 'This trip or its sharing access changed. Reload before continuing.'
      : 'Trip sharing is temporarily unavailable. Please try again.';

// A pending capability survives an in-app sign-in only in process memory. It is
// never written to router state, session/local storage or a loggable URL. A hard
// refresh after removing the fragment requires reopening the original link.
let pendingToken = null;
export const captureShareToken = (hash) => {
  const token = shareToken(hash);
  if (hash) pendingToken = token;
  return pendingToken;
};
export const clearShareToken = () => {
  pendingToken = null;
};
