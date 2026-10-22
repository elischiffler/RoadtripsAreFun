// Tests/builds have no reason to contact live AI or other external services.
// Mocked fetch/request functions still work; real TCP/DNS/HTTP is blocked.
const net = require("node:net");
const dns = require("node:dns");
const http = require("node:http");
const https = require("node:https");

function denied() {
  throw new Error("Offline validation prohibits real network connections");
}

const connect = net.Socket.prototype.connect;
net.Socket.prototype.connect = function (...args) {
  const first = Array.isArray(args[0]) ? args[0][0] : args[0];
  if (
    (typeof first === "object" && first?.path && !first?.port) ||
    typeof first === "string"
  ) {
    return connect.apply(this, args); // Local Unix/pipe IPC only.
  }
  return denied();
};
dns.lookup = denied;
dns.resolve = denied;
http.request = denied;
http.get = denied;
https.request = denied;
https.get = denied;
globalThis.fetch = async function () {
  return denied();
};
