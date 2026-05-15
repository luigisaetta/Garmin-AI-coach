/*
 * Author: L. Saetta
 * Version: 0.1.0
 * Last modified: 2026-05-15
 * License: MIT
 */

import { NextResponse } from "next/server";

import { buildBackendHeaders } from "../../../../_lib/authHeaders";

const ASSISTANT_API_URL =
  process.env.ASSISTANT_API_URL ??
  process.env.NEXT_PUBLIC_ASSISTANT_API_URL ??
  "http://127.0.0.1:8000";

type RouteContext = {
  params: Promise<{
    entryDate: string;
  }>;
};

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: Request, context: RouteContext) {
  const { entryDate } = await context.params;
  const body = await request.text();

  try {
    const response = await fetch(
      `${ASSISTANT_API_URL}/nutrition/diary-entries/${entryDate}/rewrite`,
      {
        method: "POST",
        headers: buildBackendHeaders(request, {
          "Content-Type": "application/json",
        }),
        body,
      },
    );

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
