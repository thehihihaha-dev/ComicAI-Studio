"use client";

import Link from "next/link";
import Image from "next/image";
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

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("checking");
  const [aiStatus, setAiStatus] = useState<BackendStatus>("checking");

  useEffect(() => {
    async function loadProjects() {
      try {
        const response = await fetch("http://127.0.0.1:8000/projects/");

        if (!response.ok) throw new Error("Failed to load projects");

        const data = await response.json();
        setProjects(data.projects ?? []);
      } catch (error) {
        console.error("Projects error:", error);
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

  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white">
      <div className="mx-auto max-w-7xl px-6 py-8 sm:px-10 lg:px-12">
        <header className="flex items-center justify-between border-b border-white/10 pb-6">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              ComicAI Studio
            </h1>
            <p className="mt-1 text-sm text-white/45">AI Creator Platform</p>
          </div>

          <div className="flex items-center gap-3 text-xs text-white/45">
            <StatusDot label="Backend" state={backendStatus} />
            <StatusDot label="AI" state={aiStatus} />
          </div>
        </header>

        <Link
          href="/new-project"
          className="group mt-10 flex min-h-52 items-center justify-center rounded-3xl border border-violet-300/20 bg-gradient-to-br from-indigo-600/45 via-violet-600/30 to-fuchsia-500/15 p-8 text-center shadow-[0_20px_80px_-40px_rgba(124,58,237,0.8)] transition hover:border-violet-200/40 hover:from-indigo-500/55 hover:via-violet-500/40 hover:to-fuchsia-400/20"
        >
          <div>
            <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-white/25 bg-white/15 text-2xl shadow-lg transition group-hover:scale-105 group-hover:bg-white group-hover:text-violet-700">
              +
            </span>
            <h2 className="mt-5 text-3xl font-semibold tracking-tight">
              New Project
            </h2>
            <p className="mt-2 text-sm text-white/45">
              Bắt đầu một video truyện tranh mới
            </p>
          </div>
        </Link>

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
