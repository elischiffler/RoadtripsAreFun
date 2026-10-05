import axios from '../../services/protectedRequest';
import { streamAgentMessage } from './agentProgress';
import { backendAuthConfig } from '../../services/backendAuth';
import { getFreshRoutingAlgorithm } from '../../services/routingSettings';
import { getSession, ensureSession, isCurrentSession, SessionError } from '../../services/session';

/**
 * agentChat — API helper for the conversational chat agent.
 *
 * Mirrors getRoute.jsx: a thin axios wrapper that POSTs to the backend. On
 * success it returns the AgentChatResponse. On error it logs (console.error)
 * and returns a structured failure — { ok: false, status: <http status|null> }
 * — so callers can distinguish a transient 503 ("try again") from other faults.
 *
 * Contract (chat-agent-design.md §3, frozen):
 *
 *   POST {VITE_BACKEND_SERVER}agent/chat
 *   Request  (AgentChatRequest):
 *     {
 *       partitionKey: <Cognito access token string>,
 *       chatId: <string>,          // scopes conversation memory
 *       message: <string>,
 *       clientContext?: { hasRoute: bool, stops?: int, hotelBudget?: int }
 *     }
 *   Response (AgentChatResponse):
 *     {
 *       reply: string,
 *       toolsUsed: string[],
 *       tripProfile: object | null,
 *       validationIssues: { [field]: string },
 *       actions: [{ type: string, chatId?: string, payload?: object }],
 *       extractedFields: string[], // keys identified by the per-turn JSON extraction
 *       provider: string | null,
 *       usage: { promptTokens, completionTokens } | null
 *     }
 *
 * @param {object}  opts
 * @param {string}  opts.accessToken   – Cognito access token (sent as partitionKey)
 * @param {string|number} opts.chatId  – chat id; always coerced to String
 * @param {string}  opts.message       – the user's free-text message
 * @param {object}  [opts.clientContext] – optional best-effort UI state hint
 * @returns {Promise<object>} the AgentChatResponse on success, or a structured
 *   failure { ok: false, status: number|null } on error.
 */
export const sendAgentMessage = async ({
  accessToken,
  chatId,
  message,
  clientContext,
  onProgress,
  locationConfirmation,
  locationConfirmations,
}) => {
  try {
    const started = getSession();
    await ensureSession();
    if (!isCurrentSession(started)) throw new SessionError('session-changed');
    const data = {
      partitionKey: accessToken,
      chatId: String(chatId),
      message,
      ...(locationConfirmation ? { locationConfirmation } : {}),
      ...(locationConfirmations ? { locationConfirmations } : {}),
    };
    if (clientContext) {
      const context = { ...clientContext };
      delete context.algorithm;
      const algorithm = await getFreshRoutingAlgorithm();
      data.clientContext = { ...context, ...(algorithm ? { algorithm } : {}) };
    }

    if (!isCurrentSession(started)) throw new SessionError('session-changed');
    const config = backendAuthConfig();
    if (onProgress) {
      return await streamAgentMessage(
        `${import.meta.env.VITE_BACKEND_SERVER}agent/chat/stream`,
        data,
        config,
        onProgress
      );
    }
    const response = await axios.post(
      `${import.meta.env.VITE_BACKEND_SERVER}agent/chat`,
      data,
      config
    );

    return response.data;
  } catch (error) {
    // Log any errors encountered during the request
    if (error instanceof SessionError) return { ok: false, status: null, sessionError: error.code };
    console.error('Error sending agent message; status=%s', error.response?.status ?? 'network');
    // Return a structured failure (not just null) so the caller can tell a
    // transient "try again" (503) apart from other faults and message the user
    // appropriately. The turn produced no reply, so there's no agent to recover.
    return { ok: false, status: error.response?.status ?? null };
  }
};
