import { useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Reveal } from "@/components/ui/Reveal";
import { TopBar } from "@/components/TopBar";
import { api, type DatasetLoadResponse } from "@/lib/api";

export function Dataset({ onDone }: { onDone: (data: DatasetLoadResponse) => void }) {
  const [busy, setBusy] = useState<"sample" | "file" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const run = async (kind: "sample" | "file") => {
    setBusy(kind);
    setError(null);
    try {
      const data = kind === "sample" ? await api.loadSample() : await api.loadFile(file!);
      onDone(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong reading that file.");
      setBusy(null);
    }
  };

  return (
    <div className="min-h-screen bg-bg">
      <TopBar right="Step 1 of 4" />

      <div className="mx-auto max-w-[900px] px-8 py-14 lg:px-0">
        <h1 className="text-5xl text-ink">Now, bring your own mess</h1>
        <p className="mt-3 max-w-[50ch] text-[15px] text-ink-soft">
          Your spreadsheet, or the sample one, explained step by step.
        </p>

        <div className="mt-10 grid gap-4 md:grid-cols-2">
          <Reveal>
            <div className="flex h-full flex-col gap-4 border border-white/10 bg-white/[0.025] p-6">
              <h2 className="text-2xl text-ink">Use your own data</h2>
              <label
                className={`flex flex-col items-center gap-2 border border-dashed px-6 py-8 text-center text-sm text-ink-soft transition-colors ${
                  dragOver ? "border-hero bg-hero/5" : "border-white/15"
                }`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  const f = e.dataTransfer.files[0];
                  if (f) setFile(f);
                }}
              >
                <span className="font-semibold text-ink">Choose a file</span>
                <span>or drop it here</span>
                <input
                  ref={inputRef}
                  type="file"
                  accept=".csv,text/csv"
                  hidden
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
                <Button
                  type="button"
                  variant="ghost"
                  onClick={(e) => {
                    e.preventDefault();
                    inputRef.current?.click();
                  }}
                >
                  Browse
                </Button>
              </label>
              {file && <p className="text-sm font-semibold text-ink">{file.name}</p>}
              <div className="mt-auto">
                <Button
                  glow
                  disabled={!file || busy !== null}
                  onClick={() => run("file")}
                >
                  {busy === "file" ? "Reading it" : "Use this file"}
                  <span aria-hidden>&rarr;</span>
                </Button>
              </div>
            </div>
          </Reveal>

          <Reveal delay={0.08}>
            <div className="flex h-full flex-col gap-4 border border-white/10 bg-white/[0.025] p-6">
              <h2 className="text-2xl text-ink">Just want to see it work?</h2>
              <p className="text-sm text-ink-soft">A sample sales sheet, already messy.</p>
              <div className="mt-auto">
                <Button
                  variant="ghost"
                  disabled={busy !== null}
                  onClick={() => run("sample")}
                >
                  {busy === "sample" ? "Loading it" : "Try the sample"}
                  <span aria-hidden>&rarr;</span>
                </Button>
              </div>
            </div>
          </Reveal>
        </div>

        {error && <p className="mt-6 text-sm text-fail">{error}</p>}
      </div>
    </div>
  );
}
