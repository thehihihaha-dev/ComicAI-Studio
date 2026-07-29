export default async function ProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const response = await fetch(`http://127.0.0.1:8000/projects/${id}`, {
    cache: "no-store",
  });

  const project = await response.json();
  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white">
      <div className="mx-auto max-w-5xl px-6 py-12">
        <h1 className="text-3xl font-semibold">{project.name}</h1>
        <div className="mt-3 flex gap-3 text-sm text-white/50">
          <span>Type: {project.content_type}</span>
          <span>•</span>
          <span>Status: {project.status}</span>
        </div>
        <div className="mt-10 grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-white/10 bg-white/5 p-5">
            <h2 className="font-medium">Assets</h2>
            <p className="mt-2 text-sm text-white/50">
              Upload images, PDF, ZIP or video.
            </p>
          </div>

          <div className="rounded-xl border border-white/10 bg-white/5 p-5">
            <h2 className="font-medium">AI Pipeline</h2>
            <p className="mt-2 text-sm text-white/50">
              OCR, translation, summary, script and video.
            </p>
          </div>
        </div>
        <p className="mt-2 text-white/50">ComicAI Studio project workspace.</p>
        <p className="mt-4 text-sm text-white/40">Project ID: {id}</p>
      </div>
    </main>
  );
}
