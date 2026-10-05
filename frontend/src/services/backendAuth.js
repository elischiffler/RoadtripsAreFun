import { getSession } from './session';

/** Advisory snapshot; protectedRequest replaces credentials immediately before dispatch. */
export const backendAuthConfig = () => {
  const { accessToken, idToken } = getSession();
  return accessToken
    ? {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          ...(idToken ? { 'X-Cognito-Id-Token': idToken } : {}),
        },
      }
    : {};
};
