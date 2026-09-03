import { NextResponse } from "next/server";
import { sanitizeQueue } from "../../panel-ground-truth/queuePrivacy";

const BACKEND = "http://127.0.0.1:8000/panel-ground-truth";

export async function GET() {
  try {
    const response = await fetch(BACKEND, { cache: "no-store", signal: AbortSignal.timeout(10_000) });
    const text = await response.text();
    if (!response.ok) return NextResponse.json({ detail: `Backend queue lỗi HTTP ${response.status}` }, { status: 502 });
    const payload = sanitizeQueue(JSON.parse(text));
    payload.items = payload.items.map((item) => ({
      ...item, image_url: item.image_url ? `/api/panel-ground-truth/${encodeURIComponent(item.review_id)}/image` : null,
    }));
    return NextResponse.json(payload);
  } catch (error) {
    return NextResponse.json({ detail: `Không kết nối được backend Panel GT: ${error instanceof Error ? error.message : "lỗi không xác định"}` }, { status: 502 });
  }
}
