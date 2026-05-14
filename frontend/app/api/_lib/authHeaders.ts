/*
 * Author: L. Saetta
 * Version: 0.1.0
 * Last modified: 2026-05-14
 * License: MIT
 */

export function buildBackendHeaders(
  request: Request,
  init?: HeadersInit,
): Headers {
  const headers = new Headers(init);
  const authenticatedUser = request.headers.get("x-authenticated-user");

  if (authenticatedUser) {
    headers.set("X-Authenticated-User", authenticatedUser);
  }

  return headers;
}
