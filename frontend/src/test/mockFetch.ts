import { vi } from "vitest";

type Route = {
  method: string;
  match: (path: string) => boolean;
  respond: (path: string) => { status: number; body?: unknown };
};

/** Minimal router-style fetch stub for tests: register routes by method +
 * path predicate, install as global fetch. Keeps API-layer tests free of
 * a real backend while still exercising the real fetch-based client. */
export function installMockFetch(routes: Route[]): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const path = url.replace(/^https?:\/\/[^/]+/, "");
      const method = (init?.method ?? "GET").toUpperCase();
      const route = routes.find((r) => r.method === method && r.match(path));
      if (!route) {
        throw new Error(`Unhandled mock fetch: ${method} ${path}`);
      }
      const { status, body } = route.respond(path);
      return {
        ok: status >= 200 && status < 300,
        status,
        json: async () => body,
      } as Response;
    })
  );
}

export function route(
  method: string,
  match: string | ((path: string) => boolean),
  respond: unknown | ((path: string) => { status: number; body?: unknown })
): Route {
  const matchFn = typeof match === "string" ? (path: string) => path.includes(match) : match;
  const respondFn =
    typeof respond === "function"
      ? (respond as (path: string) => { status: number; body?: unknown })
      : () => ({ status: 200, body: respond });
  return { method, match: matchFn, respond: respondFn };
}
