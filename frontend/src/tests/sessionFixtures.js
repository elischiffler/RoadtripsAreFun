import { acceptSignIn } from '../services/session';

export const fixtureToken = (sub = 'user', exp = Date.now() / 1000 + 3600, kind = 'access') =>
  `header.${btoa(JSON.stringify({ iss: 'fixture', sub, exp, token_use: kind }))}.signature`;
export function fixtureSession(sub = 'user', exp, refreshToken) {
  const result = {
    AccessToken: fixtureToken(sub, exp),
    IdToken: fixtureToken(sub, exp, 'id'),
    ...(refreshToken ? { RefreshToken: refreshToken } : {}),
  };
  acceptSignIn(result);
  return result;
}
