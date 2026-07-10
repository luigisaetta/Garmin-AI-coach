/*
 * Author: L. Saetta
 * Version: 0.1.0
 * Last modified: 2026-07-10
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
  const requestUrl = new URL(request.url);
  const backendUrl = new URL(`${ASSISTANT_API_URL}/training/metrics`);
  const beginDate = requestUrl.searchParams.get("begin_date");
  const endDate = requestUrl.searchParams.get("end_date");

  if (beginDate) {
    backendUrl.searchParams.set("begin_date", beginDate);
  }
  if (endDate) {
    backendUrl.searchParams.set("end_date", endDate);
  }

  try {
    const response = await fetch(backendUrl, {
      cache: "no-store",
      headers: buildBackendHeaders(request),
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
