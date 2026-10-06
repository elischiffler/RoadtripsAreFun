import {
  InitiateAuthCommand,
  InitiateAuthCommandInput,
  SignUpCommand,
  ConfirmSignUpCommand,
} from '@aws-sdk/client-cognito-identity-provider';
import config from '../../config';
import { cognitoClient } from './cognito';
import {
  acceptSignIn,
  getSession,
  hasUsableSession,
  isCurrentSession,
  SessionError,
} from './session';
export { cognitoClient } from './cognito';

export const isAuthenticated = (): boolean => hasUsableSession();

export const signIn = async (username: string, password: string) => {
  const session = getSession();
  const params: InitiateAuthCommandInput = {
    AuthFlow: 'USER_PASSWORD_AUTH',
    ClientId: config.clientId,
    AuthParameters: {
      USERNAME: username,
      PASSWORD: password,
    },
  };
  const command = new InitiateAuthCommand(params);
  const { AuthenticationResult } = await cognitoClient.send(command);
  if (!isCurrentSession(session)) throw new SessionError('session-changed');
  acceptSignIn(AuthenticationResult);
  return AuthenticationResult;
};

export const signUp = async (email: string, password: string) => {
  const username = crypto.randomUUID(); // Generate a unique username
  const params = {
    ClientId: config.clientId,
    Username: username,
    Password: password,
    UserAttributes: [
      {
        Name: 'email',
        Value: email,
      },
    ],
  };
  try {
    const command = new SignUpCommand(params);
    const response = await cognitoClient.send(command);
    console.log('Sign up success: ', response);
    return { Username: username, ...response }; // Return the generated username
  } catch (error) {
    console.error('Error signing up: ', error);
    throw error;
  }
};

export const confirmSignUp = async (username: string, code: string) => {
  const params = {
    ClientId: config.clientId,
    Username: username,
    ConfirmationCode: code,
  };
  try {
    const command = new ConfirmSignUpCommand(params);
    await cognitoClient.send(command);
    console.log('User confirmed successfully');
    return true;
  } catch (error) {
    console.error('Error confirming sign up: ', error);
    throw error;
  }
};
