"use client";

import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

type Project = {
  id: string;
  name: string;
  content_type: string;
  status: string;
  created_at: string;
  thumbnail_url: string | null;
};

type BackendStatus = "checking" | "online" | "offline";

const FALLBACK_PROJECTS: Project[] = [
  {
    id: "92961605-5553-4df1-b74e-9a3bed5e14f5",
    name: "Vợ trong game của tôi là Idol nổi tiếng ngoài đời",
    content_type: "short",
    status: "ready",
    created_at: "2026-08-22T23:00:00Z",
    thumbnail_url: "/page_01.jpg",
  },
];

export default function Home() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("checking");
  const [aiStatus, setAiStatus] = useState<BackendStatus>("checking");

  // New Project Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [contentType, setContentType] = useState<"short" | "long">("short");
  const [storyStyle, setStoryStyle] = useState<
    "dramatic" | "humorous" | "romantic"
  >("dramatic");
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  useEffect(() => {
    async function loadProjects() {
      try {
        const response = await fetch("http://127.0.0.1:8000/projects/", {
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error(`Failed to load projects: status ${response.status}`);
        }

        const data = await response.json();
        if (data && Array.isArray(data.projects)) {
          setProjects(data.projects);
        } else {
          setProjects(FALLBACK_PROJECTS);
        }
      } catch (error) {
        console.warn(
          "Could not load projects from backend, using fallback mock data:",
          error,
        );
        setProjects(FALLBACK_PROJECTS);
      } finally {
        setProjectsLoading(false);
      }
    }

    void loadProjects();
  }, []);

  async function deleteProject(project: Project) {
    const confirmed = window.confirm(
      `Xóa project “${project.name}”? Tất cả ảnh và dữ liệu của project cũng sẽ bị xóa.`,
    );

    if (!confirmed) return;

    setDeletingId(project.id);

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/projects/${project.id}`,
        { method: "DELETE" },
      );

      if (!response.ok) throw new Error("Failed to delete project");

      setProjects((current) =>
        current.filter((item) => item.id !== project.id),
      );
      setOpenMenuId(null);
    } catch (error) {
      console.error("Delete project error:", error);
      window.alert("Không thể xóa project. Vui lòng thử lại.");
    } finally {
      setDeletingId(null);
    }
  }

  useEffect(() => {
    async function checkBackend() {
      try {
        const response = await fetch("http://127.0.0.1:8000/health");

        if (!response.ok) throw new Error("Backend returned an error");

        const data = await response.json();
        setBackendStatus(data.status === "healthy" ? "online" : "offline");
        setAiStatus(data.ai_engine === "online" ? "online" : "offline");
      } catch {
        setBackendStatus("offline");
        setAiStatus("offline");
      }
    }

    void checkBackend();
  }, []);

  async function handleCreateProject(e: React.FormEvent) {
    e.preventDefault();
    if (!projectName.trim()) {
      setCreateError("Vui lòng nhập tên dự án.");
      return;
    }

    setIsCreating(true);
    setCreateError("");

    try {
      const payload = {
        name: projectName.trim(),
        content_type: contentType,
        story_style: contentType === "short" ? storyStyle : undefined,
      };

      const response = await fetch("http://127.0.0.1:8000/projects/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`);
      }

      const newProj = await response.json();
      setIsModalOpen(false);
      setProjectName("");
      router.push(`/projects/${newProj.id}`);
    } catch (err: unknown) {
      console.error("Backend create project failed:", err);
      setCreateError(
        "Không thể tạo dự án trên server. Vui lòng đảm bảo backend đang chạy tại port 8000 và thử lại.",
      );
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white">
      <div className="mx-auto max-w-7xl px-6 py-8 sm:px-10 lg:px-12">
        <header className="flex items-center justify-between border-b border-white/10 pb-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-violet-400 via-fuchsia-400 to-indigo-400 bg-clip-text text-transparent drop-shadow-[0_0_25px_rgba(168,85,247,0.35)]">
              ComicAI Studio
            </h1>
            <p className="mt-1 text-sm text-white/50">AI Creator Platform</p>
          </div>

          <div className="flex items-center gap-3 text-xs text-white/45">
            <StatusDot label="Backend" state={backendStatus} />
            <StatusDot label="AI" state={aiStatus} />
          </div>
        </header>

        <button
          type="button"
          onClick={() => {
            setCreateError("");
            setIsModalOpen(true);
          }}
          className="group mt-8 w-full flex min-h-36 items-center justify-center rounded-2xl border border-purple-500/20 bg-zinc-900/70 py-6 px-8 text-center transition hover:border-purple-500/60 hover:shadow-[0_0_25px_rgba(168,85,247,0.15)] cursor-pointer backdrop-blur-sm"
        >
          <div className="flex flex-col items-center">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-purple-500/30 bg-purple-500/10 text-xl font-bold text-purple-300 shadow-sm transition group-hover:scale-105 group-hover:border-purple-400 group-hover:bg-purple-500/20 group-hover:text-purple-200">
              +
            </span>
            <h2 className="mt-3 text-xl sm:text-2xl font-semibold tracking-tight text-white group-hover:text-purple-200 transition">
              New Project
            </h2>
            <p className="mt-1 text-xs sm:text-sm text-zinc-400">
              Bắt đầu một video truyện tranh mới
            </p>
          </div>
        </button>

        <section className="mt-12">
          <div className="flex items-end justify-between border-b border-white/10 pb-4">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.22em] text-white/35">
                Workspace
              </p>
              <h2 className="mt-2 text-2xl font-semibold">Your Projects</h2>
            </div>
            <p className="text-sm text-white/40">
              {projects.length} project{projects.length === 1 ? "" : "s"}
            </p>
          </div>

          {projectsLoading ? (
            <p className="py-12 text-sm text-white/40">Loading projects...</p>
          ) : projects.length === 0 ? (
            <div className="py-16 text-center text-white/40">
              Chưa có project. Hãy tạo project đầu tiên của bạn.
            </div>
          ) : (
            <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
              {projects.map((project, index) => (
                <article
                  key={project.id}
                  className="group relative rounded-2xl border border-white/10 bg-white/[0.035] transition hover:-translate-y-1 hover:border-white/25 hover:bg-white/[0.06]"
                >
                  <Link
                    href={`/projects/${project.id}`}
                    className="block overflow-hidden rounded-2xl"
                    aria-label={`Mở project ${project.name}`}
                  >
                    <div
                      className={`relative aspect-[4/3] overflow-hidden border-b border-white/10 bg-gradient-to-br ${projectGradient(index)}`}
                    >
                      {project.thumbnail_url && (
                        <Image
                          src={project.thumbnail_url}
                          alt={`Thumbnail của ${project.name}`}
                          fill
                          unoptimized
                          sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 20vw"
                          className="object-cover transition duration-300 group-hover:scale-[1.03]"
                        />
                      )}
                      <div className="absolute inset-0 bg-gradient-to-t from-black/65 via-transparent to-transparent" />
                      <div className="absolute inset-0 flex items-end p-5">
                        <span className="rounded-full border border-white/15 bg-black/25 px-2.5 py-1 text-[11px] uppercase tracking-wider text-white/70 backdrop-blur-sm">
                          {project.content_type}
                        </span>
                      </div>
                    </div>

                    <div className="p-4 pb-12">
                      <h3 className="truncate font-medium text-white">
                        {project.name}
                      </h3>
                      <div className="mt-3 flex items-center justify-between text-xs text-white/40">
                        <span className="capitalize">{project.status}</span>
                        <span>{formatDate(project.created_at)}</span>
                      </div>
                    </div>
                  </Link>

                  <button
                    type="button"
                    onClick={() =>
                      setOpenMenuId((current) =>
                        current === project.id ? null : project.id,
                      )
                    }
                    className="absolute bottom-2 right-2 z-10 flex h-8 w-9 items-center justify-center rounded-lg text-lg leading-none text-white/50 transition hover:bg-white/10 hover:text-white"
                    aria-label={`Tùy chọn cho ${project.name}`}
                    aria-expanded={openMenuId === project.id}
                  >
                    …
                  </button>

                  {openMenuId === project.id && (
                    <div className="absolute bottom-11 right-2 z-20 min-w-36 rounded-xl border border-white/10 bg-[#181818] p-1.5 shadow-2xl">
                      <button
                        type="button"
                        onClick={() => void deleteProject(project)}
                        disabled={deletingId === project.id}
                        className="w-full rounded-lg px-3 py-2 text-left text-sm text-red-400 transition hover:bg-red-500/10 disabled:opacity-50"
                      >
                        {deletingId === project.id
                          ? "Đang xóa..."
                          : "Xóa project"}
                      </button>
                    </div>
                  )}
                </article>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Modal Tạo Dự Án Mới */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
          <div className="relative w-full max-w-lg rounded-2xl border border-white/15 bg-[#121216] p-6 shadow-2xl text-left">
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-white/10">
              <div>
                <h3 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                  <span className="text-purple-400">✨</span> Tạo Dự Án Mới
                </h3>
                <p className="text-xs text-white/50 mt-0.5">
                  Thiết lập thông số và phong cách kể chuyện AI
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-white/50 hover:bg-white/10 hover:text-white transition"
              >
                ✕
              </button>
            </div>

            {/* Form */}
            <form onSubmit={handleCreateProject} className="mt-5 space-y-4">
              {/* Tên dự án */}
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-white/70 mb-1.5">
                  Tên truyện / Dự án
                </label>
                <input
                  type="text"
                  placeholder="VD: Solo Leveling - Hôn Lễ Thánh Đường"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-white/30 focus:border-purple-500 focus:bg-white/10 focus:outline-none transition"
                  autoFocus
                />
              </div>

              {/* Định dạng video */}
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-white/70 mb-1.5">
                  Định dạng video
                </label>
                <div className="grid grid-cols-2 gap-2.5">
                  <button
                    type="button"
                    onClick={() => setContentType("short")}
                    className={`p-3 rounded-xl border text-left transition ${
                      contentType === "short"
                        ? "border-purple-500 bg-purple-500/15 text-white ring-1 ring-purple-500/40"
                        : "border-white/10 bg-white/[0.03] text-white/60 hover:text-white hover:border-white/20"
                    }`}
                  >
                    <div className="text-sm font-semibold flex items-center gap-1.5">
                      <span>📱</span> Shorts (9:16)
                    </div>
                    <div className="text-[11px] text-white/40 mt-1">
                      Video ngắn TikTok, Reels, Shorts
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => setContentType("long")}
                    className={`p-3 rounded-xl border text-left transition ${
                      contentType === "long"
                        ? "border-purple-500 bg-purple-500/15 text-white ring-1 ring-purple-500/40"
                        : "border-white/10 bg-white/[0.03] text-white/60 hover:text-white hover:border-white/20"
                    }`}
                  >
                    <div className="text-sm font-semibold flex items-center gap-1.5">
                      <span>🖥️</span> Long-form (16:9)
                    </div>
                    <div className="text-[11px] text-white/40 mt-1">
                      Video review dài YouTube
                    </div>
                  </button>
                </div>
              </div>

              {/* Phong cách kể chuyện (khi chọn Shorts 9:16) */}
              {contentType === "short" && (
                <div className="rounded-xl border border-purple-500/20 bg-purple-950/20 p-3.5 space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold uppercase tracking-wider text-purple-200">
                      Phong cách kể chuyện (AI Script Style)
                    </label>
                    <span className="text-[10px] font-mono text-purple-300/70 bg-purple-500/20 px-1.5 py-0.5 rounded">
                      NamMinhNeural
                    </span>
                  </div>

                  <select
                    value={storyStyle}
                    onChange={(e) =>
                      setStoryStyle(
                        e.target.value as "dramatic" | "humorous" | "romantic",
                      )
                    }
                    className="w-full rounded-lg border border-purple-500/30 bg-[#161320] px-3 py-2 text-xs font-medium text-white focus:border-purple-400 focus:outline-none cursor-pointer"
                  >
                    <option value="dramatic">
                      ⚡ dramatic — Kịch tính / Gay cấn (Mặc định)
                    </option>
                    <option value="humorous">
                      🎭 humorous — Hài hước / Cà khịa
                    </option>
                    <option value="romantic">
                      💖 romantic — Lãng mạn / Ngọt ngào
                    </option>
                  </select>

                  <p className="text-[11px] text-purple-200/60 leading-relaxed">
                    {storyStyle === "dramatic" &&
                      "Nhịp câu ngắn, dồn dập, đẩy mạnh mâu thuẫn cao trào và tình thế ngặt nghèo."}
                    {storyStyle === "humorous" &&
                      "Từ lóng dí dỏm, châm biếm sâu cay biểu cảm và tình huống khó đỡ của nhân vật."}
                    {storyStyle === "romantic" &&
                      "Giọng văn nhẹ nhàng, sâu lắng, tập trung vào rung động cảm xúc ngọt ngào."}
                  </p>
                </div>
              )}

              {createError && (
                <p className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 px-3 py-1.5 rounded-lg">
                  {createError}
                </p>
              )}

              {/* Buttons */}
              <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-white/10">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-medium text-white/60 hover:text-white hover:bg-white/10 transition"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={isCreating}
                  className="px-5 py-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold text-xs transition shadow-lg shadow-purple-950/50 disabled:opacity-50 flex items-center gap-2 cursor-pointer"
                >
                  {isCreating ? (
                    <>
                      <div className="h-3 w-3 rounded-full border-2 border-white border-t-transparent animate-spin" />
                      <span>Đang tạo...</span>
                    </>
                  ) : (
                    <span>🚀 Tạo Dự Án Ngay</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}

function StatusDot({ label, state }: { label: string; state: BackendStatus }) {
  const dotClass =
    state === "online"
      ? "bg-emerald-400"
      : state === "checking"
        ? "bg-yellow-400"
        : "bg-red-400";

  return (
    <span className="flex items-center gap-1.5">
      <span className={`h-1.5 w-1.5 rounded-full ${dotClass}`} />
      {label}
    </span>
  );
}

function projectGradient(index: number) {
  const gradients = [
    "from-indigo-500/35 via-violet-500/15 to-transparent",
    "from-emerald-500/30 via-cyan-500/10 to-transparent",
    "from-orange-500/30 via-rose-500/10 to-transparent",
    "from-sky-500/30 via-blue-500/10 to-transparent",
    "from-fuchsia-500/30 via-purple-500/10 to-transparent",
  ];

  return gradients[index % gradients.length];
}

function formatDate(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "";

  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
  }).format(date);
}
