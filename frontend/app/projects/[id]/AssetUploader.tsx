"use client";
import { useEffect, useState } from "react";
interface Asset {
  id: string;
  project_id: string;
  filename: string;
  file_type: string;
  file_path: string;
  page_order: number;
  created_at: string;
  status: string;
  ocr_text: string | null;
  ocr_blocks: {
    text: string;
    confidence: number;
    box: number[][];
  }[];
  vision_status: string;

  vision_regions: {
    id: number;
    type: string;
    block_ids: number[];
    recovered?: boolean;
    confidence?: number;
  }[];

  reading_order: number[];
  dialogue_status: string;

  dialogues: {
    order: number;
    region_id: number;
    raw_text: string;
    clean_text: string;
    confidence: number;
    needs_review: boolean;
    reason: string;
    ocr_confidence: number;
    text_similarity: number;
    correction_score: number;
  }[];
  url: string;
}
export default function AssetUploader({ projectId }: { projectId: string }) {
  const PAGE_LIMIT = 9;
  const [files, setFiles] = useState<File[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalAssets, setTotalAssets] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");
  const [selectedAssets, setSelectedAssets] = useState<string[]>([]);
  const [ocrProgress, setOcrProgress] = useState({
    status: "idle",
    total: 0,
    completed: 0,
    processing: 0,
    failed: 0,
    percent: 0,
  });
  useEffect(() => {
    fetch(
      `http://127.0.0.1:8000/assets/project/${projectId}?page=${page}&limit=${PAGE_LIMIT}`,
    )
      .then((response) => response.json())
      .then((data) => {
        setAssets(data.items);
        setTotalPages(data.total_pages);
        setTotalAssets(data.total);
      });
  }, [projectId, page]);
  useEffect(() => {
    async function loadProgress() {
      const response = await fetch(
        `http://127.0.0.1:8000/assets/project/${projectId}/progress`,
        {
          cache: "no-store",
        },
      );

      const data = await response.json();
      setOcrProgress(data);
    }

    loadProgress();

    const interval = setInterval(loadProgress, 2000);

    return () => clearInterval(interval);
  }, [projectId]);
  async function loadAssets(targetPage = page) {
    const response = await fetch(
      `http://127.0.0.1:8000/assets/project/${projectId}?page=${targetPage}&limit=${PAGE_LIMIT}`,
      {
        cache: "no-store",
      },
    );

    const data = await response.json();

    setAssets(data.items);
    setTotalPages(data.total_pages);
    setTotalAssets(data.total);
  }
  async function uploadFiles() {
    setUploading(true);
    setMessage("");

    try {
      const formData = new FormData();
      formData.append("project_id", projectId);

      files.forEach((file) => {
        formData.append("files", file);
      });

      const response = await fetch("http://127.0.0.1:8000/assets/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Upload failed");
      }

      const data = await response.json();
      console.log(data);

      await loadAssets(page);

      setFiles([]);
      setMessage(`Uploaded ${files.length} images successfully.`);
    } catch (error) {
      console.error(error);
      setMessage("Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  }
  function toggleAssetSelection(assetId: string) {
    setSelectedAssets((current) =>
      current.includes(assetId)
        ? current.filter((id) => id !== assetId)
        : [...current, assetId],
    );
  }
  async function deleteSelectedAssets() {
    if (selectedAssets.length === 0) return;

    const confirmed = window.confirm(
      `Delete ${selectedAssets.length} selected assets?`,
    );

    if (!confirmed) return;

    try {
      const response = await fetch("http://127.0.0.1:8000/assets/batch/", {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(selectedAssets),
      });

      if (!response.ok) {
        throw new Error("Delete failed");
      }

      const data = await response.json();

      setSelectedAssets([]);
      setMessage(`Deleted ${data.deleted_count} assets successfully.`);

      const remainingAssets = totalAssets - data.deleted_count;

      if (page > 1 && remainingAssets <= (page - 1) * PAGE_LIMIT) {
        setPage(page - 1);
      } else {
        await loadAssets();
      }
    } catch (error) {
      console.error(error);
      setMessage("Delete failed. Please try again.");
    }
  }
  async function startOcrProcessing() {
    setMessage("Starting image analysis...");

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/assets/project/${projectId}/process`,
        {
          method: "POST",
        },
      );

      if (!response.ok) {
        throw new Error("Failed to start OCR");
      }

      const data = await response.json();

      if (data.queued === 0) {
        setMessage("No new images need processing.");
      } else {
        setMessage(`Analyzing ${data.queued} images...`);
      }
    } catch (error) {
      console.error(error);
      setMessage("Could not start image analysis.");
    }
  }
  async function pollLayoutStatus(assetId: string) {
    const interval = setInterval(async () => {
      try {
        const response = await fetch(
          `http://127.0.0.1:8000/assets/project/${projectId}?page=${page}&limit=${PAGE_LIMIT}&t=${Date.now()}`,
          {
            cache: "no-store",
          },
        );

        const data = await response.json();

        const currentAsset = data.items.find(
          (asset: Asset) => asset.id === assetId,
        );

        if (!currentAsset) return;

        if (
          currentAsset.vision_status === "completed" ||
          currentAsset.vision_status === "failed"
        ) {
          clearInterval(interval);
          await loadAssets();
        }
      } catch (error) {
        console.error("Layout polling error:", error);
      }
    }, 2000);
  }

  async function analyzeLayout(assetId: string) {
    try {
      const response = await fetch(
        `http://127.0.0.1:8000/assets/${assetId}/analyze-layout`,
        {
          method: "POST",
        },
      );

      if (!response.ok) {
        throw new Error("Failed to start layout analysis");
      }

      // Đổi UI sang processing ngay
      setAssets((currentAssets) =>
        currentAssets.map((asset) =>
          asset.id === assetId
            ? {
                ...asset,
                vision_status: "processing",
              }
            : asset,
        ),
      );

      pollLayoutStatus(assetId);
    } catch (error) {
      console.error("Layout analysis error:", error);
      setMessage("Could not analyze layout.");
    }
  }
  return (
    <div className="mt-4">
      <label className="inline-flex cursor-pointer items-center rounded-lg border border-white/20 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10">
        + Thêm file
        <input
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files) {
              setFiles(Array.from(e.target.files));
            }
          }}
        />
      </label>

      {files.length > 0 && (
        <p className="mt-3 text-sm text-white/60">
          {files.length} images selected
        </p>
      )}

      {files.length > 0 && (
        <button
          onClick={uploadFiles}
          disabled={uploading}
          className="mt-4 rounded-lg bg-white px-4 py-2 text-sm font-medium text-black disabled:cursor-not-allowed disabled:opacity-50"
        >
          {uploading ? "Uploading..." : "Upload Images"}
        </button>
      )}
      {message && <p className="mt-3 text-sm text-white/60">{message}</p>}
      <p className="mt-4 text-sm text-white/50">
        Uploaded assets: {totalAssets}
      </p>
      {totalAssets > 0 && ocrProgress.status !== "processing" && (
        <button
          onClick={startOcrProcessing}
          className="mt-3 rounded-lg border border-white/20 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10"
        >
          Analyze Images
        </button>
      )}
      {ocrProgress.status === "processing" && (
        <div className="mt-3">
          <p className="text-sm text-white/60">
            Analyzing images... {ocrProgress.completed} / {ocrProgress.total}
          </p>

          <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full bg-white transition-all"
              style={{ width: `${ocrProgress.percent}%` }}
            />
          </div>

          <p className="mt-1 text-xs text-white/40">{ocrProgress.percent}%</p>
        </div>
      )}
      {totalAssets > 0 && ocrProgress.status === "completed" && (
        <p className="mt-2 text-sm text-green-400">● Ready for AI</p>
      )}

      <div className="mt-4 grid grid-cols-3 gap-3">
        {assets.map((asset) => (
          <div
            key={asset.id}
            onClick={() => toggleAssetSelection(asset.id)}
            className={`cursor-pointer rounded-lg border p-2 ${
              selectedAssets.includes(asset.id)
                ? "border-white bg-white/10"
                : "border-white/10"
            }`}
          >
            <img
              src={asset.url}
              alt={asset.filename}
              className="aspect-[2/3] w-full rounded-md object-cover"
            />

            <p className="mt-2 text-center text-xs text-white/50">
              Page {asset.page_order}
            </p>
            <button
              onClick={(event) => {
                event.stopPropagation();
                analyzeLayout(asset.id);
              }}
              disabled={asset.vision_status === "processing"}
              className="mt-2 w-full rounded-lg border border-white/20 px-2 py-2 text-xs text-white transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {asset.vision_status === "processing"
                ? "Analyzing Layout..."
                : asset.vision_status === "completed"
                  ? "Analyze Again"
                  : "Analyze Layout"}
            </button>

            {asset.vision_status === "completed" && (
              <div className="mt-2 text-center text-xs text-green-400">
                Layout ✓ · {asset.vision_regions?.length ?? 0} regions
              </div>
            )}

            {asset.vision_status === "completed" &&
              asset.reading_order?.length > 0 && (
                <div className="mt-1 text-center text-xs text-white/40">
                  Order: {asset.reading_order.join(" → ")}
                </div>
              )}
            {asset.dialogue_status === "completed" && (
              <p className="mt-1 text-center text-xs text-green-400">
                Dialogue ✓
              </p>
            )}

            {asset.dialogue_status === "needs_review" && (
              <p className="mt-1 text-center text-xs text-yellow-400">
                Dialogue ⚠ Needs Review
              </p>
            )}
          </div>
        ))}
      </div>
      {selectedAssets.length > 0 && (
        <p className="mt-3 text-sm text-white/60">
          Selected: {selectedAssets.length}
        </p>
      )}
      {selectedAssets.length > 0 && (
        <button
          onClick={deleteSelectedAssets}
          className="mt-3 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white"
        >
          Delete Selected ({selectedAssets.length})
        </button>
      )}
      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between">
          <button
            onClick={() =>
              setPage((currentPage) => Math.max(1, currentPage - 1))
            }
            disabled={page === 1}
            className="rounded-lg border border-white/10 px-4 py-2 text-sm disabled:opacity-40"
          >
            Previous
          </button>

          <span className="text-sm text-white/50">
            Page {page} / {totalPages}
          </span>

          <button
            onClick={() => setPage((currentPage) => currentPage + 1)}
            disabled={page === totalPages}
            className="rounded-lg border border-white/10 px-4 py-2 text-sm disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
