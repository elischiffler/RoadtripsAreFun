/** Attach the current Cognito access token to browser calls into our API. */
export const backendAuthConfig = () => {
  const token = sessionStorage.getItem('accessToken');
  const identityToken = sessionStorage.getItem('idToken');
  return token
    ? {
        headers: {
          Authorization: `Bearer ${token}`,
          ...(identityToken ? { 'X-Cognito-Id-Token': identityToken } : {}),
        },
      }
    : {};
};
