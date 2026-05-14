/*
 * Author: L. Saetta
 * Version: 0.1.0
 * Last modified: 2026-05-12
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
  const formData = await request.formData();

  try {
    const response = await fetch(`${ASSISTANT_API_URL}/nutrition/plan`, {
      method: "POST",
      headers: buildBackendHeaders(request),
      body: formData,
    });

    if (!response.ok) {
      return NextResponse.json(
        { message: `Assistant API returned HTTP ${response.status}` },
        { status: response.status === 415 || response.status === 422 ? response.status : 502 },
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
