import axios from './protectedRequest';
import { backendAuthConfig } from './backendAuth';

const usableCar = (car) =>
  car &&
  Number.isInteger(Number(car.year)) &&
  Number(car.year) >= 1984 &&
  Number(car.year) <= 2100 &&
  typeof car.make === 'string' &&
  car.make.trim() &&
  typeof car.model === 'string' &&
  car.model.trim();
export function tripCarChoices(trip) {
  const profile = trip.tripProfile;
  if (profile?.car_status === 'skipped') return { car_status: 'skipped', car: null };
  if (usableCar(profile?.car))
    return {
      car_status: 'provided',
      car: { year: Number(profile.car.year), make: profile.car.make, model: profile.car.model },
    };
  const [year, make, model] = trip.carDetails ?? [];
  const legacy = { year: Number(year), make, model };
  return usableCar(legacy)
    ? { car_status: 'provided', car: legacy }
    : { car_status: 'skipped', car: null };
}
export async function saveTripCar(trip, choices) {
  const response = await axios.put(
    import.meta.env.VITE_BACKEND_SERVER + `chats/${trip.chatId}/car`,
    {
      ...choices,
      expected_agent_chat_id: trip.agentChatId || null,
    },
    { ...backendAuthConfig(), timeout: 15000 }
  );
  return { ...response.data, savedRevision: response.headers?.['x-trip-revision'] ?? null };
}
export function applyTripCar(trip, choices) {
  const car = choices.car;
  return {
    ...trip,
    savedRevision: choices.savedRevision ?? null,
    carDetails: car ? [String(car.year), car.make, car.model] : ['', '', ''],
    carBudget: null,
    tripProfile: { ...trip.tripProfile, car_status: choices.car_status, car },
  };
}
