/*
 * Author: L. Saetta
 * Version: 0.1.0
 * Last modified: 2026-08-28
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

export async function POST(request: Request) {
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ message: "Invalid report request" }, { status: 400 });
  }

  try {
    const response = await fetch(`${ASSISTANT_API_URL}/training/reports`, {
      method: "POST",
      cache: "no-store",
      headers: buildBackendHeaders(request, {
        "Content-Type": "application/json",
      }),
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      return NextResponse.json(
        { message: `Assistant API returned HTTP ${response.status}` },
        { status: response.status === 422 ? 422 : 502 },
      );
    }

    return NextResponse.json(await response.json());
  } catch {
    return NextResponse.json(
      { message: "Assistant API is unavailable" },
      { status: 502 },
    );
  }
}
