import { CognitoIdentityProviderClient } from '@aws-sdk/client-cognito-identity-provider';
import config from '../../config';

export const cognitoClient = new CognitoIdentityProviderClient({
  region: config.region,
  maxAttempts: 1, // A rotated refresh token must not be blindly retried by the SDK.
  ...(import.meta.env.VITE_COGNITO_ENDPOINT
    ? { endpoint: import.meta.env.VITE_COGNITO_ENDPOINT }
    : {}),
});
