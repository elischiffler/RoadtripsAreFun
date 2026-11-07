import { beforeEach, expect, it, vi } from 'vitest';
import request from '../services/protectedRequest';
import {
  createShareLink,
  changeSharing,
  connectSharedTrip,
  viewShareLink,
  getSharing,
  viewConnectedTrip,
  listSharedTrips,
  leaveSharedTrip,
} from '../services/tripSharing';
const { publicPost } = vi.hoisted(() => ({ publicPost: vi.fn() }));
vi.mock('axios', () => ({ default: { create: () => ({ post: publicPost }) } }));
vi.mock('../services/protectedRequest', () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));
beforeEach(() => {
  vi.resetAllMocks();
  import.meta.env.VITE_BACKEND_SERVER = 'http://localhost:8000/';
  publicPost.mockResolvedValue({ data: { title: 'Trip' } });
  request.get.mockResolvedValue({ data: [] });
  request.post.mockResolvedValue({ data: {} });
  request.delete.mockResolvedValue({ data: {} });
});
it('keeps capability in POST body, never URL/query or account-bearing public headers', async () => {
  const token = 'a'.repeat(43);
  await viewShareLink(token);
  expect(publicPost).toHaveBeenCalledWith(
    'http://localhost:8000/trip-sharing/view',
    { token },
    { signal: undefined, timeout: 15000 }
  );
  await connectSharedTrip(token, 'Sam');
  expect(request.post).toHaveBeenCalledWith(
    'http://localhost:8000/trip-sharing/connect',
    { token, display_name: 'Sam' },
    expect.any(Object)
  );
  for (const mock of [publicPost, request.post])
    for (const args of mock.mock.calls) expect(args[0]).not.toContain(token);
});
it('owner mutations carry revision and opaque sharing identity, member requests do not target owner chat writes', async () => {
  const trip = { chatId: 7, savedRevision: 'b'.repeat(64) };
  await getSharing(trip);
  await createShareLink(trip);
  await changeSharing(trip, 'opaque', 'link');
  await changeSharing(trip, 'opaque', 'member', 'm');
  await changeSharing(trip, 'opaque', 'all');
  expect(request.post).toHaveBeenCalledWith(
    'http://localhost:8000/chats/7/sharing/link',
    { expected_revision: 'b'.repeat(64) },
    expect.any(Object)
  );
  expect(request.delete).toHaveBeenCalledWith(
    'http://localhost:8000/chats/7/sharing/link?share_id=opaque',
    expect.any(Object)
  );
  request.get.mockClear();
  request.post.mockClear();
  request.delete.mockClear();
  await listSharedTrips();
  await viewConnectedTrip('opaque');
  await leaveSharedTrip('opaque');
  const paths = [...request.get.mock.calls, ...request.delete.mock.calls].map((c) => c[0]);
  expect(paths.every((p) => p.startsWith('http://localhost:8000/shared-trips'))).toBe(true);
  expect(request.post).not.toHaveBeenCalled();
});
