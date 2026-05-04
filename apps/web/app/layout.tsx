import type { Metadata } from "next";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "Lunar MineOps AI OS",
  description:
    "Mission Readiness Agent for Lunar ISRU - validate autonomous excavation-to-processing concepts before launch.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <div className="border-b border-line bg-paper">
          <div className="mx-auto max-w-[1280px] px-6 py-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                aria-hidden
                className="h-6 w-6 rounded-sm border border-ink relative overflow-hidden"
              >
                <div className="absolute inset-0 bg-ink" />
                <div className="absolute right-0 bottom-0 h-3 w-3 rounded-full bg-paper border border-ink translate-x-[3px] translate-y-[3px]" />
              </div>
              <div className="leading-none">
                <div className="text-[13px] font-semibold tracking-tight">
                  Lunar MineOps AI OS
                </div>
                <div className="text-[10px] uppercase tracking-[0.14em] text-muted mt-0.5">
                  Mission Readiness Agent · Simulation Only · Not Flight Critical
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3 text-[11px] text-muted">
              <span>v0.1.0</span>
            </div>
          </div>
        </div>
        <main className="mx-auto max-w-[1280px] px-6 py-8">{children}</main>
        <footer className="border-t border-line mt-16">
          <div className="mx-auto max-w-[1280px] px-6 py-4 text-[11px] text-muted flex justify-between">
            <span>
              Source-grounded with NASA/PDS public sources. Synthetic terrain,
              simulation only.
            </span>
            <span>Anthropic Claude tool-use loop runs server-side only.</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
