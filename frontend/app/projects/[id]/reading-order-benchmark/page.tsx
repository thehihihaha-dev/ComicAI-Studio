import Link from "next/link";
import ReadingOrderReview from "./ReadingOrderReview";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <main className="min-h-screen bg-[#09090b] text-white">
    <header className="flex h-16 items-center border-b border-white/10 px-5"><Link href={`/projects/${id}`} className="mr-4 text-white/45">←</Link><div><h1 className="text-sm font-semibold">Reading Order Ground Truth</h1><p className="text-xs text-white/35">Human validation · MANGA_RTL · prediction visible</p></div></header>
    <ReadingOrderReview projectId={id} />
  </main>;
}
