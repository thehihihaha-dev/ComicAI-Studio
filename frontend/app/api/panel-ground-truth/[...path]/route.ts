import { NextRequest, NextResponse } from "next/server";

const BACKEND = "http://127.0.0.1:8000/panel-ground-truth";

async function forward(request: NextRequest, path: string[]) {
  try {
    const response = await fetch(`${BACKEND}/${path.map(encodeURIComponent).join("/")}`, {
      method: request.method,
      headers: request.method === "POST" ? { "Content-Type": "application/json" } : undefined,
      body: request.method === "POST" ? await request.text() : undefined,
      cache: "no-store", signal: AbortSignal.timeout(10_000),
    });
    return new NextResponse(await response.arrayBuffer(), { status: response.status,
      headers: { "Content-Type": response.headers.get("Content-Type") || "application/octet-stream" } });
  } catch (error) {
    return NextResponse.json({ detail: `Không kết nối được backend Panel GT: ${error instanceof Error ? error.message : "lỗi không xác định"}` }, { status: 502 });
  }
}

export async function GET(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return forward(request, (await params).path);
}
export async function POST(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return forward(request, (await params).path);
}
