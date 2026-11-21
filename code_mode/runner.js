"use strict";

// Runs only inside the OS sandbox. stdout is a private line protocol, never a
// user-facing console. The host remains the sole authority for every tool call.
const readline = require("node:readline");
const vm = require("node:vm");

const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
const queue = [];
const waiters = [];
input.on("line", (line) => {
  const waiter = waiters.shift();
  if (waiter) waiter(line);
  else queue.push(line);
});
input.on("close", () => {
  for (const waiter of waiters.splice(0)) waiter(null);
});
function nextLine() {
  if (queue.length) return Promise.resolve(queue.shift());
  return new Promise((resolve) => waiters.push(resolve));
}
function send(value) {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

async function main() {
  const first = await nextLine();
  if (first === null) throw new Error("input_closed");
  const request = JSON.parse(first);
  if (typeof request.code !== "string") throw new Error("invalid_code");
  let callId = 0;
  async function call(name, args = {}) {
    if (typeof name !== "string" || args === null || typeof args !== "object" || Array.isArray(args)) {
      throw new Error("invalid_tool_request");
    }
    const id = ++callId;
    send({ kind: "call", id, name, args });
    const line = await nextLine();
    if (line === null) throw new Error("bridge_closed");
    const response = JSON.parse(line);
    if (response.kind !== "reply" || response.id !== id) throw new Error("invalid_bridge_reply");
    if (!response.ok) throw new Error(`tool_error:${response.error || "denied"}`);
    return response.value;
  }
  const tools = Object.freeze({
    call,
    github: Object.freeze({
      listIssues: (args = {}) => call("github.list_issues", args),
      listPullRequests: (args = {}) => call("github.list_pull_requests", args),
      getCiStatus: (args = {}) => call("github.ci_status", args),
    }),
    railway: Object.freeze({
      listDeployments: (args = {}) => call("railway.list_deployments", args),
      getServiceStatus: (args = {}) => call("railway.service_status", args),
    }),
  });
  // bubblewrap may set PWD even after --clearenv. Remove this last inert
  // variable so an escaped vm reference still finds no environment data.
  for (const key of Object.keys(process.env)) delete process.env[key];
  // This context reduces accidental access and bans module imports. The
  // security boundary is the outer bubblewrap process, not Node's vm module.
  const context = vm.createContext(Object.freeze({ tools }), {
    codeGeneration: { strings: false, wasm: false },
  });
  const script = new vm.Script(`(async () => {\n${request.code}\n})()`, {
    filename: "generated-code.js",
    importModuleDynamically: () => { throw new Error("module_import_denied"); },
  });
  const value = await script.runInContext(context, { timeout: 1000 });
  send({ kind: "result", value: value === undefined ? null : value });
}

main().catch((error) => {
  const message = String(error && error.message || "execution_error").slice(0, 160);
  const code = error && error.code === "ERR_SCRIPT_EXECUTION_TIMEOUT" ? "timeout" : "code_error";
  send({ kind: "error", code, error: message });
  process.exitCode = 1;
}).finally(() => {
  input.close();
  process.stdin.destroy();
});
