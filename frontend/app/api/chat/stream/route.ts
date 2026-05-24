/*
 * Author: L. Saetta
 * Version: 0.1.0
 * Last modified: 2026-05-24
 * License: MIT
 */

import { buildBackendHeaders } from "../../_lib/authHeaders";

const ASSISTANT_API_URL =
  process.env.ASSISTANT_API_URL ??
  process.env.NEXT_PUBLIC_ASSISTANT_API_URL ??
  "http://127.0.0.1:8000";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const STREAM_HEADERS = {
  "Cache-Control": "no-cache, no-transform",
  Connection: "keep-alive",
  "Content-Type": "text/event-stream",
  "X-Accel-Buffering": "no",
};

function streamError(message: string) {
  return new Response(
    `event: error\ndata: ${JSON.stringify({
      type: "error",
      conversation_id: "",
      delta: message,
    })}\n\n`,
    {
      status: 200,
      headers: STREAM_HEADERS,
    },
  );
}

export async function POST(request: Request) {
  const body = await request.text();
  let response: Response;

  try {
    response = await fetch(`${ASSISTANT_API_URL}/chat/stream`, {
      method: "POST",
      cache: "no-store",
      headers: buildBackendHeaders(request, {
        "Content-Type": "application/json",
      }),
      body,
      signal: request.signal,
    });
  } catch (error) {
    console.error("assistant_api chat stream fetch failed", error);
    return streamError("Assistant API connection failed before streaming started.");
  }

  if (!response.ok || !response.body) {
    return streamError(`Assistant API returned HTTP ${response.status}`);
  }

  return new Response(response.body, {
    status: 200,
    headers: STREAM_HEADERS,
  });
}
