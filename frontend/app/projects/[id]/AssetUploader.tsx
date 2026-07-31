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

  async function loadAssets(targetPage = page) {
    const response = await fetch(
      `http://127.0.0.1:8000/assets/project/${projectId}?page=${targetPage}&limit=${PAGE_LIMIT}&t=${Date.now()}`,
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
