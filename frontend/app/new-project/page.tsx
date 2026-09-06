"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
type Project = {
  id: string;
  name: string;
  content_type: string;
  status: string;
  created_at: string;
};

export default function NewProjectPage() {
  const [name, setName] = useState("");
  const [contentType, setContentType] = useState("short");
  const [storyStyle, setStoryStyle] = useState<"dramatic" | "humorous" | "romantic">("dramatic");
  const [message, setMessage] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);

  async function createProject() {
    if (!name.trim()) {
      setMessage("Please enter a project name.");
      return;
    }
    setMessage("Creating project...");
    try {
      const response = await fetch("http://127.0.0.1:8000/projects/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: name,
          content_type: contentType,
          story_style: contentType === "short" ? storyStyle : undefined,
        }),
      });
      const data = await response.json();

      setMessage(`Project "${data.name}" created successfully.`);
      setName("");
      await loadProjects();
    } catch {
      setMessage("Could not create project. Please try again.");
    }
  }
  async function loadProjects() {
    try {
      const response = await fetch("http://127.0.0.1:8000/projects/", {
        cache: "no-store",
      });
      if (response.ok) {
        const data = await response.json();
        if (data && Array.isArray(data.projects)) {
          setProjects(data.projects);
        }
      }
    } catch {
      // Safe fallback
    }
  }
  useEffect(() => {
    void loadProjects();
  }, []);

  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white">
      <div className="mx-auto max-w-3xl px-6 py-12">
        <Link
          href="/"
          className="mb-6 inline-block text-sm text-white/50 hover:text-white"
        >
          ← Back to Home
        </Link>
        <h1 className="text-3xl font-semibold">Create New Project</h1>

        <p className="mt-2 text-white/50">
          Start a new ComicAI Studio project.
        </p>
        <div className="mt-8">
          <label className="mb-2 block text-sm font-medium">Project Name</label>

          <input
            type="text"
            placeholder="e.g. Solo Leveling Review"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-lg border border-white/10 bg-white/5 px-4 py-3 outline-none"
          />
        </div>
        <div className="mt-6">
          <label className="mb-2 block text-sm font-medium">Content Type</label>

          <select
            value={contentType}
            onChange={(e) => setContentType(e.target.value)}
            className="w-full rounded-lg border border-white/10 bg-white/5 px-4 py-3 outline-none"
          >
            <option value="short">Short</option>
            <option value="long">Long</option>
            <option value="short">Short (9:16 Shorts/TikTok)</option>
            <option value="long">Long (16:9 YouTube)</option>
          </select>
        </div>

        {contentType === "short" && (
          <div className="mt-6 rounded-lg border border-purple-500/20 bg-purple-950/20 p-4">
            <label className="mb-2 block text-sm font-medium text-purple-200">
              Phong cách kể chuyện (AI Script Style)
            </label>
            <select
              value={storyStyle}
              onChange={(e) =>
                setStoryStyle(
                  e.target.value as "dramatic" | "humorous" | "romantic",
                )
              }
              className="w-full rounded-lg border border-purple-500/30 bg-[#161320] px-4 py-3 text-white outline-none cursor-pointer"
            >
              <option value="dramatic">⚡ dramatic — Kịch tính / Gay cấn (Mặc định)</option>
              <option value="humorous">🎭 humorous — Hài hước / Cà khịa</option>
              <option value="romantic">💖 romantic — Lãng mạn / Ngọt ngào</option>
            </select>
            <p className="mt-2 text-xs text-purple-300/60">
              Giọng đọc trí tuệ nhân tạo: vi-VN-NamMinhNeural (+12% rate)
            </p>
          </div>
        )}

        <button
          onClick={createProject}
          className="mt-8 rounded-lg bg-white px-5 py-3 font-medium text-black transition hover:bg-white/90"
        >
          Create Project
        </button>
        {message && <p className="mt-4 text-sm text-white/60">{message}</p>}
        <div className="mt-10">
          <h2 className="text-xl font-semibold">Projects</h2>
          <p className="mt-2 text-sm text-white/50">
            Total projects: {projects.length}
          </p>
          <div className="mt-4 space-y-3">
            {projects.map((project: Project) => (
              <div
                key={project.id}
                className="rounded-xl border border-white/10 bg-white/5 p-4"
              >
                <p className="font-medium">{project.name}</p>
                <p className="mt-1 text-sm text-white/50">
                  {project.content_type} · {project.status}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
