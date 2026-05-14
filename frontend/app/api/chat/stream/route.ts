/*
 * Author: L. Saetta
 * Version: 0.1.0
 * Last modified: 2026-05-11
 * License: MIT
 */

import { buildBackendHeaders } from "../_lib/authHeaders";

const ASSISTANT_API_URL =
  process.env.ASSISTANT_API_URL ??
  process.env.NEXT_PUBLIC_ASSISTANT_API_URL ??
  "http://127.0.0.1:8000";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: Request) {
  const body = await request.text();
  const response = await fetch(`${ASSISTANT_API_URL}/chat/stream`, {
    method: "POST",
    headers: buildBackendHeaders(request, {
      "Content-Type": "application/json",
    }),
    body,
  });

  if (!response.ok || !response.body) {
    return new Response(
      JSON.stringify({
        type: "error",
        message: `Assistant API returned HTTP ${response.status}`,
      }),
      {
        status: 502,
        headers: { "Content-Type": "application/json" },
      },
    );
  }

  const stream = new TransformStream();
  response.body.pipeTo(stream.writable);

  return new Response(stream.readable, {
    status: 200,
    headers: {
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "Content-Type": "text/event-stream",
      "X-Accel-Buffering": "no",
    },
  });
}
