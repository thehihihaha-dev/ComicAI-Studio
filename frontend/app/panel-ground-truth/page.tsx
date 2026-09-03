import Link from "next/link";
import PanelGroundTruth from "./PanelGroundTruth";

export default function Page() {
  return <main className="min-h-screen bg-[#09090b] text-white">
    <header className="flex h-16 items-center border-b border-white/10 px-5">
      <Link href="/" className="mr-4 text-white/45">←</Link>
      <div><h1 className="text-sm font-semibold">Human Panel Ground Truth</h1><p className="text-xs text-white/35">4 trang · chỉ đánh dấu ô truyện · prediction được ẩn</p></div>
    </header>
    <PanelGroundTruth />
  </main>;
}
