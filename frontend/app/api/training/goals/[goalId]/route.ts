/*
 * Author: L. Saetta
 * Version: 0.1.0
 * Last modified: 2026-07-16
 * License: MIT
 */

import { NextResponse } from "next/server";

import { buildBackendHeaders } from "../../../_lib/authHeaders";

const ASSISTANT_API_URL =
  process.env.ASSISTANT_API_URL ??
  process.env.NEXT_PUBLIC_ASSISTANT_API_URL ??
  "http://127.0.0.1:8000";

type RouteContext = { params: Promise<{ goalId: string }> };

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function PATCH(request: Request, context: RouteContext) {
  const { goalId } = await context.params;
  try {
    const response = await fetch(`${ASSISTANT_API_URL}/training/goals/${goalId}`, {
      method: "PATCH",
      headers: buildBackendHeaders(request, { "Content-Type": "application/json" }),
      body: await request.text(),
    });
    const body = await response.json().catch(() => null);
    if (!response.ok) {
      return NextResponse.json(
        { message: body?.detail ?? `Assistant API returned HTTP ${response.status}` },
        { status: response.status },
      );
    }
    return NextResponse.json(body);
  } catch {
    return NextResponse.json({ message: "Assistant API is unavailable" }, { status: 502 });
  }
}
