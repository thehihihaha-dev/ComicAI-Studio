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

type BackendStatus = "checking" | "online" | "offline";

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  useEffect(() => {
    fetch("http://127.0.0.1:8000/projects/")
      .then((response) => response.json())
      .then((data) => {
        setProjects(data.projects);
      });
  }, []);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("checking");
  const [aiStatus, setAiStatus] = useState<BackendStatus>("checking");

  useEffect(() => {
    async function checkBackend() {
      try {
        const response = await fetch("http://127.0.0.1:8000/health");

        if (!response.ok) {
          throw new Error("Backend returned an error");
        }

        const data = await response.json();

        if (data.status === "healthy") {
          setBackendStatus("online");
        } else {
          setBackendStatus("offline");
        }
        if (data.ai_engine === "online") {
          setAiStatus("online");
        } else {
          setAiStatus("offline");
        }
      } catch {
        setBackendStatus("offline");
        setAiStatus("offline");
      }
    }

    checkBackend();
  }, []);

  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-6 py-8">
        <header className="flex items-center justify-between border-b border-white/10 pb-5">
          <div>
            <h1 className="text-xl font-semibold">ComicAI Studio</h1>
            <p className="text-sm text-white/50">AI Creator Platform</p>
          </div>

          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/60">
            v0.0.1
          </span>
        </header>

        <section className="flex flex-1 items-center">
          <div className="w-full">
            <p className="mb-4 text-sm text-white/50">
              Create. Understand. Transform.
            </p>

            <h2 className="max-w-3xl text-5xl font-semibold tracking-tight">
              Turn stories into
              <span className="text-white/50"> content with AI.</span>
            </h2>

            <p className="mt-6 max-w-2xl text-lg leading-8 text-white/55">
              ComicAI Studio helps creators analyze source material, generate
              scripts, voices, subtitles and videos from one workspace.
            </p>

            <div className="mt-8 flex gap-3">
              <p className="mt-4 text-sm text-white/50">
                Total projects: {projects.length}
              </p>
              <div className="mt-6 space-y-3">
                {projects.map((project) => (
                  <Link
                    key={project.id}
                    href={`/projects/${project.id}`}
                    className="rounded-xl border border-white/10 bg-white/5 p-4"
                  >
                    <p className="font-medium">{project.name}</p>
                    <p className="mt-1 text-sm text-white/50">
                      {project.content_type} · {project.status}
                    </p>
                  </Link>
                ))}
              </div>
              <Link
                href="/new-project"
                className="rounded-xl bg-white px-5 py-3 font-medium text-black transition hover:bg-white/90"
              >
                New Project
              </Link>

              <button className="rounded-xl border border-white/10 bg-white/5 px-5 py-3 font-medium text-white transition hover:bg-white/10">
                Open Project
              </button>
            </div>

            <div className="mt-12 grid gap-4 md:grid-cols-3">
              <StatusCard title="Frontend" status="Running" state="online" />

              <StatusCard
                title="Backend"
                status={
                  backendStatus === "checking"
                    ? "Checking..."
                    : backendStatus === "online"
                      ? "Online"
                      : "Offline"
                }
                state={backendStatus}
              />

              <StatusCard
                title="AI Engine"
                status={
                  aiStatus === "checking"
                    ? "Checking..."
                    : aiStatus === "online"
                      ? "Online"
                      : "Offline"
                }
                state={aiStatus}
              />
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

function StatusCard({
  title,
  status,
  state,
}: {
  title: string;
  status: string;
  state: BackendStatus;
}) {
  const dotClass =
    state === "online"
      ? "bg-emerald-400"
      : state === "checking"
        ? "bg-yellow-400"
        : "bg-red-400";

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
      <div className="flex items-center justify-between">
        <p className="font-medium">{title}</p>
        <span className={`h-2.5 w-2.5 rounded-full ${dotClass}`} />
      </div>

      <p className="mt-2 text-sm text-white/40">{status}</p>
    </div>
  );
}
