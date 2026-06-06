/**
 * CalcBudget — unit tests for the pure hotel-budget calculation.
 *
 * calcGasBudget makes network calls so we test it separately via mocks.
 * calcHotelBudget is pure math — no mocking needed.
 */
import { describe, it, expect } from 'vitest';
import { calcHotelBudget } from '../pages/ChatPage/CalcBudget';

describe('calcHotelBudget', () => {
  // Duration thresholds:
  //   7 hours of driving per day = 7 * 3600 = 25 200 s
  //   Each stop adds 2 hours = 7 200 s

  it('returns 0 when total drive time is under 7 hours (no overnight)', async () => {
    // 6 h drive, 0 stops → 21 600 s total < 25 200 s
    const budget = await calcHotelBudget(6 * 3600, 0);
    expect(budget).toBe(0);
  });

  it('returns $100 for exactly one overnight (7 h drive, no stops)', async () => {
    // Just over the threshold: 25 201 s → 1 hotel night → $100
    const budget = await calcHotelBudget(25201, 0);
    expect(budget).toBe(100);
  });

  it('returns $200 for two overnight stays', async () => {
    // 15 h drive, 0 stops → 54 000 s → loop: 54000-25200=28800 > 25200 → count=1, 28800-25200=3600 not > 25200 → count=2 → $200
    const budget = await calcHotelBudget(15 * 3600, 0);
    expect(budget).toBe(200);
  });

  it('accounts for stops adding to total duration', async () => {
    // 5 h drive + 2 stops (2 h each) = 18 000 + 14 400 = 32 400 s → 1 hotel night → $100
    const budget = await calcHotelBudget(5 * 3600, 2);
    expect(budget).toBe(100);
  });

  it('returns 0 when stops keep total under threshold', async () => {
    // 3 h drive + 1 stop → 10 800 + 7 200 = 18 000 s < 25 200 s
    const budget = await calcHotelBudget(3 * 3600, 1);
    expect(budget).toBe(0);
  });
});
