/** Attach the current Cognito access token to browser calls into our API. */
export const backendAuthConfig = () => {
  const token = sessionStorage.getItem('accessToken');
  return token ? { headers: { Authorization: `Bearer ${token}` } } : {};
};
