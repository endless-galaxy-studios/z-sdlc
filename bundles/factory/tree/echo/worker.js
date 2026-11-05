// The factory's echo service as a Cloudflare Worker (z-sdlc factory bundle; factory.json's smoke.echo_host).
// factory-smoke's credential-mask and services jobs send throwaway credentials through the agent sandbox's
// proxy to this host and read the echoed request headers, one per line, to prove the proxy injected them.
// It answers any request with its method, URL, query arguments and headers as indented JSON, and stores
// nothing. Deploy it on a workers.dev address (no zone bot protection there), then set smoke.echo_host.
//
// /mcp is a stand-in MCP server (streamable HTTP, stateless, JSON responses) for smoke's mcp-services job.
// Its header_digest tool returns the SHA-256 of the Authorization header it received, never the header, so
// smoke can check outside the agent that the throwaway credential arrived. Its not_allowed tool is one the
// factory must refuse to call: it says so if it ever runs.
const TOOLS = [
  { name: "header_digest", description: "The SHA-256 of the Authorization header this request carried.",
    inputSchema: { type: "object", properties: {} } },
  { name: "not_allowed", description: "A tool the factory's tool list leaves out; calling it must be refused.",
    inputSchema: { type: "object", properties: {} } },
];

async function sha256(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function mcp(request) {
  if (request.method !== "POST") return new Response(null, { status: 405, headers: { allow: "POST" } });
  let message;
  try {
    message = await request.json();
  } catch {
    return Response.json({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "parse error" } }, { status: 400 });
  }
  if (message.id === undefined || message.id === null) return new Response(null, { status: 202 });
  const reply = (result) => Response.json({ jsonrpc: "2.0", id: message.id, result });
  const params = message.params || {};
  switch (message.method) {
    case "initialize":
      return reply({ protocolVersion: params.protocolVersion || "2025-06-18", capabilities: { tools: {} },
                     serverInfo: { name: "factory-echo", version: "1" } });
    case "ping":
      return reply({});
    case "tools/list":
      return reply({ tools: TOOLS });
    case "tools/call": {
      const text = params.name === "header_digest"
        ? `authorization-sha256=${await sha256(request.headers.get("authorization") || "")}`
        : params.name === "not_allowed" ? "not_allowed ran: the factory let a refused tool through" : null;
      if (text === null) return Response.json({ jsonrpc: "2.0", id: message.id, error: { code: -32602, message: "unknown tool" } });
      return reply({ content: [{ type: "text", text }] });
    }
    default:
      return Response.json({ jsonrpc: "2.0", id: message.id, error: { code: -32601, message: "method not found" } });
  }
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/mcp") return mcp(request);
    const headers = {};
    for (const [name, value] of request.headers) {
      headers[name.replace(/(^|-)([a-z])/g, (_, dash, c) => dash + c.toUpperCase())] = value;
    }
    const body = { args: Object.fromEntries(url.searchParams), headers, method: request.method, url: request.url };
    return new Response(JSON.stringify(body, null, 2) + "\n", {
      headers: { "content-type": "application/json", "cache-control": "no-store" },
    });
  },
};
