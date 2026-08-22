import Link from "next/link";
import ProjectWorkspace from "./ProjectWorkspace";

export default async function ProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [projectResponse, assetsResponse] = await Promise.all([
    fetch(`http://127.0.0.1:8000/projects/${id}`, { cache: "no-store" }),
    fetch(`http://127.0.0.1:8000/assets/project/${id}?page=1&limit=100`, { cache: "no-store" }),
  ]);
  const project = await projectResponse.json();
  const assetData = await assetsResponse.json();
  const assets = assetData.items ?? [];
  const analyzed = assets.length > 0 && assets.every((asset: { vision_status: string; dialogue_status: string }) => asset.vision_status === "no_dialogue" || (asset.vision_status === "completed" && asset.dialogue_status === "completed"));
  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white lg:h-dvh lg:overflow-hidden">
      <div className="mx-auto max-w-[1520px] px-4 sm:px-7 lg:flex lg:h-full lg:min-h-0 lg:flex-col lg:overflow-hidden lg:px-10">
        <header className="flex h-16 shrink-0 items-center border-b border-white/10">
          <Link href="/" className="mr-3 flex h-8 w-8 items-center justify-center rounded-md text-white/45 transition hover:bg-white/5 hover:text-white" aria-label="Về dự án">←</Link>
          <div><p className="text-sm font-semibold tracking-tight">ComicAI Studio</p><h1 className="mt-0.5 text-xs font-normal text-white/40">{project.name} · {project.content_type === "short" ? "Video ngắn" : "Video dài"} · {assetData.total ?? 0} trang · {analyzed ? "Đã phân tích" : "Đang chuẩn bị"}</h1></div>
          <Link href={`/projects/${id}/ocr-benchmark`} className="ml-auto rounded-lg border border-white/10 px-3 py-2 text-xs text-white/55 transition hover:bg-white/5 hover:text-white">OCR Ground Truth</Link>
          <Link href={`/projects/${id}/reading-order-benchmark`} className="ml-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-white/55 transition hover:bg-white/5 hover:text-white">Reading Order GT</Link>
          <Link href={`/projects/${id}/reader-correctness`} className="ml-2 rounded-lg border border-violet-400/30 px-3 py-2 text-xs text-violet-200 transition hover:bg-violet-500/10">Reader Correctness GT</Link>
        </header>
        <ProjectWorkspace projectId={id} />
      </div>
    </main>
  );
}
