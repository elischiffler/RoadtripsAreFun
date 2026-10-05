// Local, in-memory browser fixtures. No AWS, providers or database connections.
import http from "node:http";
const issuer = "https://cognito-idp.us-west-1.amazonaws.com/us-west-1_fixture";
const token = (sub, kind) =>
  `header.${Buffer.from(JSON.stringify({ iss: issuer, sub, exp: Math.floor(Date.now() / 1000) + 3600, token_use: kind })).toString("base64url")}.fixture`;
let refreshMode = "ready";
let rejectStream = false;
let refreshes = 0;
let turns = 0;
let mismatches = 0;
const requests = [];
const chats = new Map();
const subject = (value) => {
  try {
    return JSON.parse(Buffer.from(value.split(".")[1], "base64url")).sub;
  } catch {
    return null;
  }
};
const json = (response, status, value) => {
  response.writeHead(status, { "Content-Type": "application/json" });
  response.end(JSON.stringify(value));
};
http
  .createServer(async (request, response) => {
    response.setHeader("Access-Control-Allow-Origin", "http://127.0.0.1:5175");
    response.setHeader(
      "Access-Control-Allow-Headers",
      "content-type,authorization,x-cognito-id-token,x-amz-target,x-amz-user-agent,amz-sdk-invocation-id,amz-sdk-request",
    );
    response.setHeader(
      "Access-Control-Allow-Methods",
      "GET,POST,PUT,DELETE,OPTIONS",
    );
    if (request.method === "OPTIONS") {
      response.writeHead(204);
      response.end();
      return;
    }
    let raw = "";
    for await (const chunk of request) raw += chunk;
    const data = raw ? JSON.parse(raw) : {};
    if (request.url === "/fixture/control") {
      refreshMode = data.refreshMode ?? refreshMode;
      rejectStream = data.rejectStream ?? rejectStream;
      json(response, 200, { ok: true });
      return;
    }
    if (request.url === "/fixture/status") {
      json(response, 200, { refreshes, turns, mismatches, requests });
      return;
    }
    const target = request.headers["x-amz-target"];
    if (target) {
      const refreshing = target.endsWith(".GetTokensFromRefreshToken");
      if (refreshing) {
        refreshes++;
        if (refreshMode === "revoked") {
          json(response, 400, {
            __type: "NotAuthorizedException",
            message: "Fixture refresh revoked",
          });
          return;
        }
        if (refreshMode === "outage") {
          json(response, 500, {
            __type: "InternalErrorException",
            message: "Fixture outage",
          });
          return;
        }
      }
      const sub = refreshing
        ? data.RefreshToken.split(":")[0]
        : data.AuthParameters.USERNAME.startsWith("other")
          ? "other"
          : "user";
      json(response, 200, {
        AuthenticationResult: {
          AccessToken: token(sub, "access"),
          IdToken: token(sub, "id"),
          RefreshToken: sub + ":fixture-refresh",
          ExpiresIn: 3600,
          TokenType: "Bearer",
        },
      });
      return;
    }
    requests.push({ method: request.method, path: request.url });
    const bearer = request.headers.authorization?.slice(7);
    const bodyToken = data.PartitionKey ?? data.partitionKey;
    if (bodyToken && bodyToken !== bearer) mismatches++;
    const owner = subject(bearer);
    if (!owner) {
      json(response, 401, { detail: "Invalid authentication token" });
      return;
    }
    if (request.url === "/routing-settings") {
      json(response, 200, { can_select_algorithm: false });
      return;
    }
    if (request.url === "/chats" && request.method === "GET") {
      json(response, 200, Array.from(chats.get(owner)?.values() ?? []));
      return;
    }
    if (
      request.url.startsWith("/chats/create/") ||
      request.url.startsWith("/chats/update/")
    ) {
      if (!chats.has(owner)) chats.set(owner, new Map());
      chats.get(owner).set(data.ChatData.chatId, [data.ChatData, data.ChatLog]);
      json(response, 200, { ok: true });
      return;
    }
    if (request.url === "/agent/chat/stream") {
      if (rejectStream) {
        rejectStream = false;
        json(response, 401, { detail: "Invalid authentication token" });
        return;
      }
      turns++;
      response.writeHead(200, { "Content-Type": "application/x-ndjson" });
      response.end(
        JSON.stringify({
          type: "result",
          response: {
            reply: "Fixture turn completed once.",
            actions: [],
            tripProfile: {},
            toolsUsed: [],
          },
        }) + "\n",
      );
      return;
    }
    json(response, 404, { detail: "Unknown fixture route" });
  })
  .listen(18090, "127.0.0.1", () =>
    console.log("Session fixtures at http://127.0.0.1:18090"),
  );
