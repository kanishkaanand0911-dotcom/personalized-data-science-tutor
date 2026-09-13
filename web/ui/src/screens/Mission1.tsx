import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { LessonHeader } from "@/components/lesson/LessonHeader";
import { MascotTeachingPanel } from "@/components/lesson/MascotTeachingPanel";
import { DatasetPreview } from "@/components/lesson/DatasetPreview";
import { LessonComplete } from "@/components/lesson/LessonComplete";
import { Fade } from "@/components/ui/Fade";
import { analyzeColumn, describeColumn } from "@/lessons/columnFacts";
import { introLine, rowColumnFact, roleExampleFact } from "@/lessons/personalize";
import type { DatasetSummary } from "@/lib/api";

type Phase = "explain" | "demonstrate" | "pick1" | "reveal1" | "pick2" | "reveal2" | "python" | "complete";

const EXPLORE_POINTS = 5;
const COMPLETE_POINTS = 10;
const PYTHON_POINTS = 5;

export function Mission1({
  dataset,
  role,
  pointsTotal,
  onPointsChange,
  onComplete,
  onSkip,
}: {
  dataset: DatasetSummary;
  role: string | null;
  pointsTotal: number;
  onPointsChange: (points: number) => void;
  onComplete: () => void;
  onSkip: () => void;
}) {
  const [phase, setPhase] = useState<Phase>("explain");
  const [col1, setCol1] = useState<string | null>(null);
  const [col2, setCol2] = useState<string | null>(null);
  const [earned, setEarned] = useState(0);

  const ctx = {
    role,
    experience: null,
    goal: null,
    datasetName: dataset.name,
    rows: dataset.rows,
    cols: dataset.cols,
    columns: dataset.columns,
  };

  const explore = (column: string, which: 1 | 2) => {
    if (which === 1) setCol1(column);
    else setCol2(column);
  };

  const revealFor = (column: string | null) =>
    column ? describeColumn(analyzeColumn(column, dataset.preview, dataset.missing)) : "";

  const award = (n: number) => {
    setEarned((e) => e + n);
    onPointsChange(pointsTotal + n);
  };

  const phaseOrder: Phase[] = ["explain", "demonstrate", "pick1", "reveal1", "pick2", "reveal2", "python", "complete"];
  const progress = phaseOrder.indexOf(phase) / (phaseOrder.length - 1);

  let mascotMessage = "";
  let mood: "neutral" | "happy" | "confused" = "neutral";
  if (phase === "explain") mascotMessage = introLine(ctx);
  else if (phase === "demonstrate")
    mascotMessage = "Here is a real peek at it. Pick any column above and I will tell you what it actually is.";
  else if (phase === "pick1") mascotMessage = col1 ? `Good choice. Ready when you are.` : "Click a column name above to pick one.";
  else if (phase === "reveal1") {
    mascotMessage = revealFor(col1);
    mood = "happy";
  } else if (phase === "pick2")
    mascotMessage = col2 ? "Good choice. Ready when you are." : "One more - pick a different column.";
  else if (phase === "reveal2") {
    mascotMessage = revealFor(col2);
    mood = "happy";
  } else if (phase === "python")
    mascotMessage = "You've done all of this by clicking. Here's the same thing in actual Python code.";

  return (
    <div className="min-h-screen bg-bg">
      <LessonHeader
        mission="Stage 1"
        title="Python & Data Fundamentals"
        points={pointsTotal}
        progress={progress}
        skipLabel="Skip basics"
        onSkip={phase === "complete" ? undefined : onSkip}
      />

      <div className="mx-auto max-w-[640px] px-6 py-8">
        {phase !== "complete" && <MascotTeachingPanel message={mascotMessage} mood={mood} />}

        {phase === "explain" && (
          <Fade k="stats">
            <div className="mt-6 flex gap-8">
              <StatChip value={dataset.rows} label="rows" />
              <StatChip value={dataset.cols} label="columns" />
            </div>
            <div className="mt-5 space-y-2">
              <FactCallout text={rowColumnFact()} />
              <FactCallout text={roleExampleFact(ctx)} />
            </div>
          </Fade>
        )}

        {phase === "python" && (
          <Fade k="python">
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
              In Python, this looks like
            </p>
            <div className="mt-3 space-y-3">
              <CodeBlock
                code={'import pandas as pd\ndf = pd.read_csv("your_file.csv")'}
                explain="This reads your spreadsheet into a DataFrame - pandas' name for a table - so Python can work with it."
              />
              <CodeBlock
                code="df.shape"
                explain={`Tells you the size: (${dataset.rows}, ${dataset.cols}) means ${dataset.rows} rows and ${dataset.cols} columns - the same numbers you saw above.`}
              />
              <CodeBlock
                code="df.columns"
                explain="Lists every column name - exactly the ones you just explored by clicking, just printed instead."
              />
            </div>
          </Fade>
        )}

        {(phase === "demonstrate" || phase === "pick1" || phase === "reveal1" || phase === "pick2" || phase === "reveal2") && (
          <Fade k="preview">
            <div className="mt-6">
              <DatasetPreview
                columns={dataset.columns}
                rows={dataset.preview}
                selectedColumn={phase === "pick2" || phase === "reveal2" ? col2 : col1}
                onSelectColumn={
                  phase === "pick1" || phase === "demonstrate"
                    ? (c) => explore(c, 1)
                    : phase === "pick2"
                      ? (c) => explore(c, 2)
                      : undefined
                }
              />
            </div>
          </Fade>
        )}

        <div className="mt-7 flex justify-center">
          {phase === "explain" && (
            <Button variant="flat" onClick={() => setPhase("demonstrate")}>
              Show me <span aria-hidden>&rarr;</span>
            </Button>
          )}
          {phase === "demonstrate" && (
            <Button variant="flat" onClick={() => setPhase("pick1")}>
              Let&rsquo;s pick one <span aria-hidden>&rarr;</span>
            </Button>
          )}
          {phase === "pick1" && (
            <Button
              variant="flat"
              disabled={!col1}
              onClick={() => {
                award(EXPLORE_POINTS);
                setPhase("reveal1");
              }}
            >
              What is it? <span aria-hidden>&rarr;</span>
            </Button>
          )}
          {phase === "reveal1" && (
            <Button variant="flat" onClick={() => setPhase("pick2")}>
              Try another column <span aria-hidden>&rarr;</span>
            </Button>
          )}
          {phase === "pick2" && (
            <Button
              variant="flat"
              disabled={!col2 || col2 === col1}
              onClick={() => {
                award(EXPLORE_POINTS);
                setPhase("reveal2");
              }}
            >
              What is it? <span aria-hidden>&rarr;</span>
            </Button>
          )}
          {phase === "reveal2" && (
            <Button
              variant="flat"
              onClick={() => {
                award(PYTHON_POINTS);
                setPhase("python");
              }}
            >
              Show me the code <span aria-hidden>&rarr;</span>
            </Button>
          )}
          {phase === "python" && (
            <Button
              variant="flat"
              onClick={() => {
                award(COMPLETE_POINTS);
                setPhase("complete");
              }}
            >
              Finish this stage <span aria-hidden>&rarr;</span>
            </Button>
          )}
        </div>

        {phase === "complete" && (
          <LessonComplete
            title="Python & Data Fundamentals"
            pointsEarned={earned}
            pointsTotal={pointsTotal}
            nextLabel="Start cleaning the data"
            onNext={onComplete}
          />
        )}
      </div>
    </div>
  );
}

function StatChip({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <div className="font-display text-3xl font-bold text-ink">{value}</div>
      <div className="text-xs text-ink-soft">{label}</div>
    </div>
  );
}

function FactCallout({ text }: { text: string }) {
  return (
    <div className="rounded-md border border-line bg-surface px-3 py-2 text-xs text-ink-soft">
      {text}
    </div>
  );
}

function CodeBlock({ code, explain }: { code: string; explain: string }) {
  return (
    <div>
      <pre className="overflow-x-auto rounded-md border border-line bg-bg p-3 text-xs leading-relaxed text-ink">
        <code className="font-mono">{code}</code>
      </pre>
      <p className="mt-1.5 rounded-md border border-points/30 bg-points/10 px-3 py-2 text-xs text-ink">
        {explain}
      </p>
    </div>
  );
}
