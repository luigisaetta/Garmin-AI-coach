/*
 * Author: L. Saetta
 * Version: 0.1.0
 * Last modified: 2026-07-16
 * License: MIT
 */

import { NextResponse } from "next/server";

import { buildBackendHeaders } from "../../_lib/authHeaders";

const ASSISTANT_API_URL =
  process.env.ASSISTANT_API_URL ??
  process.env.NEXT_PUBLIC_ASSISTANT_API_URL ??
  "http://127.0.0.1:8000";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request) {
  const backendUrl = new URL(`${ASSISTANT_API_URL}/training/goals`);
  const status = new URL(request.url).searchParams.get("status");
  if (status) backendUrl.searchParams.set("status", status);
  return forward(request, backendUrl);
}

export async function POST(request: Request) {
  return forward(request, new URL(`${ASSISTANT_API_URL}/training/goals`), "POST");
}

async function forward(request: Request, backendUrl: URL, method = "GET") {
  try {
    const response = await fetch(backendUrl, {
      method,
      cache: "no-store",
      headers: buildBackendHeaders(
        request,
        method === "POST" ? { "Content-Type": "application/json" } : undefined,
      ),
      body: method === "POST" ? await request.text() : undefined,
    });
    const body = await response.json().catch(() => null);
    if (!response.ok) {
      return NextResponse.json(
        { message: body?.detail ?? `Assistant API returned HTTP ${response.status}` },
        { status: response.status },
      );
    }
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json({ message: "Assistant API is unavailable" }, { status: 502 });
  }
}
