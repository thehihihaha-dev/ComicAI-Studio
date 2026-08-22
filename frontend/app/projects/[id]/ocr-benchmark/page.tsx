import Link from "next/link";
import OcrBenchmarkReview from "./OcrBenchmarkReview";

export default async function OcrBenchmarkPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <main className="min-h-screen bg-[#09090b] text-white">
    <header className="mx-auto flex h-16 max-w-6xl items-center border-b border-white/10 px-5">
      <Link href={`/projects/${id}`} className="mr-4 text-white/45 hover:text-white">←</Link>
      <div><h1 className="text-sm font-semibold">OCR Ground Truth Benchmark</h1><p className="text-xs text-white/35">Human transcription · predictions hidden</p></div>
    </header>
    <OcrBenchmarkReview projectId={id} />
  </main>;
}
