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
    const response = await fetch("http://127.0.0.1:8000/projects/");
    const data = await response.json();

    setProjects(data.projects);
  }
  useEffect(() => {
    fetch("http://127.0.0.1:8000/projects/")
      .then((response) => response.json())
      .then((data) => {
        setProjects(data.projects);
      });
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
          </select>
        </div>
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
