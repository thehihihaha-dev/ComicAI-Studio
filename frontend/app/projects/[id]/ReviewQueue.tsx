"use client";
import Image from "next/image";
import { useEffect, useState } from "react";

interface ReviewItem {
  asset_id: string;
  filename: string;
  page_order: number;
  region_id: number;
  raw_text: string;
  clean_text: string;
  recovered_text?: string | null;
  correction_score?: number | null;
  recovery_confidence?: number | null;
  reason?: string;
  image_url: string;
}

export default function ReviewQueue({ projectId }: { projectId: string }) {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);

  async function loadReviewQueue() {
    try {
      const response = await fetch(
        `http://127.0.0.1:8000/assets/project/${projectId}/review-queue`,
        {
          cache: "no-store",
        },
      );

      if (!response.ok) {
        throw new Error("Failed to load review queue");
      }

      const data = await response.json();
      setItems(data.items ?? []);
    } catch (error) {
      console.error("Review queue error:", error);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function fetchReviewQueue() {
      try {
        const response = await fetch(
          `http://127.0.0.1:8000/assets/project/${projectId}/review-queue`,
          {
            cache: "no-store",
          },
        );

        if (!response.ok) {
          throw new Error("Failed to load review queue");
        }

        const data = await response.json();

        if (!cancelled) {
          setItems(data.items ?? []);
          setLoading(false);
        }
      } catch (error) {
        console.error("Review queue error:", error);

        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void fetchReviewQueue();

    return () => {
      cancelled = true;
    };
  }, [projectId]);

  async function verifyDialogue(item: ReviewItem, verifiedText: string) {
    const text = verifiedText.trim();

    if (!text) return;

    const key = `${item.asset_id}-${item.region_id}`;
    setSavingId(key);

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/assets/${item.asset_id}/dialogues/${item.region_id}/verify`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            verified_text: text,
          }),
        },
      );

      if (!response.ok) {
        throw new Error("Failed to verify dialogue");
      }

      await loadReviewQueue();
    } catch (error) {
      console.error("Dialogue verification error:", error);
    } finally {
      setSavingId(null);
    }
  }

  if (loading) {
    return (
      <p className="mt-4 text-sm text-white/50">Loading review queue...</p>
    );
  }

  if (items.length === 0) {
    return (
      <div className="mt-4 rounded-lg border border-green-500/20 bg-green-500/5 p-4">
        <p className="text-sm text-green-400">
          ✓ No dialogue requires manual review
        </p>
      </div>
    );
  }

  return (
    <div className="mt-5 space-y-4">
      <div>
        <p className="text-sm font-medium text-yellow-400">
          ⚠ {items.length} dialogue
          {items.length !== 1 ? "s" : ""} need review
        </p>
      </div>

      {items.map((item) => {
        const suggestedText =
          item.recovered_text || item.clean_text || item.raw_text;

        const key = `${item.asset_id}-${item.region_id}`;

        return (
          <ReviewCard
            key={key}
            item={item}
            defaultText={suggestedText}
            saving={savingId === key}
            onSave={(text) => verifyDialogue(item, text)}
          />
        );
      })}
    </div>
  );
}

function ReviewCard({
  item,
  defaultText,
  saving,
  onSave,
}: {
  item: ReviewItem;
  defaultText: string;
  saving: boolean;
  onSave: (text: string) => void;
}) {
  const [text, setText] = useState(defaultText);

  return (
    <div className="rounded-xl border border-yellow-500/20 bg-yellow-500/5 p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">
          Page {item.page_order} · Region {item.region_id}
        </p>

        {item.correction_score != null && (
          <span className="text-xs text-white/40">
            Score: {Math.round(item.correction_score * 100)}%
          </span>
        )}
      </div>

      <div className="relative mt-3 h-72 w-full">
        <Image
          src={item.image_url}
          alt={item.filename}
          fill
          sizes="(max-width: 768px) 100vw, 50vw"
          className="rounded-lg object-contain"
        />
      </div>

      <div className="mt-4 space-y-3 text-sm">
        <div>
          <p className="text-xs text-white/40">OCR</p>
          <p className="mt-1 text-white/70">{item.raw_text}</p>
        </div>

        <div>
          <p className="text-xs text-white/40">AI suggestion</p>
          <p className="mt-1 text-white">
            {item.recovered_text || item.clean_text}
          </p>
        </div>

        {item.reason && (
          <div>
            <p className="text-xs text-white/40">Why review?</p>
            <p className="mt-1 text-xs text-white/50">{item.reason}</p>
          </div>
        )}

        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={4}
          className="w-full rounded-lg border border-white/10 bg-black/30 p-3 text-sm text-white outline-none focus:border-white/30"
        />

        <div className="flex gap-2">
          <button
            onClick={() => onSave(item.recovered_text || item.clean_text)}
            disabled={saving}
            className="rounded-lg border border-white/20 px-3 py-2 text-xs text-white transition hover:bg-white/10 disabled:opacity-50"
          >
            Accept AI
          </button>

          <button
            onClick={() => onSave(text)}
            disabled={saving}
            className="rounded-lg bg-white px-3 py-2 text-xs font-medium text-black disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Correction"}
          </button>
        </div>
      </div>
    </div>
  );
}
