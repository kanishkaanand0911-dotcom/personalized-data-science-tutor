import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Tag } from "@/components/ui/Tag";
import { Fade } from "@/components/ui/Fade";
import type { QuizQuestion, QuizResult } from "@/lib/api";

/* The lighter-weight sibling of Quiz: one question, a real flip card
   instead of a list. Front is just the question - plain, high-contrast,
   nothing to read but the prompt. Tapping it flips to the options (a CSS
   3D rotate, not a fade) where picking one grades instantly, same colors
   and scoring as Quiz. fetchQuestions/submitAnswers are injected the same
   way as Quiz, so this works for both a level's recap and the modeling
   quiz - only the first question from the topic's real question set is
   ever shown here. */
export function Flashcard({
  resetKey,
  fetchQuestions,
  submitAnswers,
  onDone,
}: {
  resetKey: string | number;
  fetchQuestions: () => Promise<{ questions: QuizQuestion[] }>;
  submitAnswers: (answers: Record<string, string>) => Promise<QuizResult>;
  onDone: (pointsTotal: number) => void;
}) {
  const [question, setQuestion] = useState<QuizQuestion | null>(null);
  const [flipped, setFlipped] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<QuizResult | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setQuestion(null);
    setFlipped(false);
    setSelected(null);
    setResult(null);
    fetchQuestions().then((res) => setQuestion(res.questions[0] ?? null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetKey]);

  if (!question) {
    return <div className="mx-auto mt-6 h-56 max-w-sm animate-pulse rounded-md border border-line bg-surface" />;
  }

  const pick = async (opt: string) => {
    if (result || busy) return;
    setSelected(opt);
    setBusy(true);
    try {
      setResult(await submitAnswers({ [question.id]: opt }));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Fade k={`flashcard-${resetKey}`}>
      <p className="text-center text-xs font-semibold uppercase tracking-wide text-ink-soft">Flashcard</p>

      <div className="mx-auto mt-3 max-w-sm [perspective:1200px]">
        <div
          className="relative h-56 w-full transition-transform duration-500 ease-out [transform-style:preserve-3d]"
          style={{ transform: flipped ? "rotateY(180deg)" : "rotateY(0deg)" }}
        >
          {/* Front: just the question, plain and readable - tap anywhere to flip. */}
          <button
            type="button"
            onClick={() => setFlipped(true)}
            disabled={flipped}
            className="absolute inset-0 flex flex-col items-center justify-center gap-4 rounded-md border border-line bg-surface p-6 text-center [backface-visibility:hidden]"
          >
            <p className="text-lg font-semibold leading-snug text-ink">{question.prompt}</p>
            <span className="text-xs font-semibold uppercase tracking-wide text-hero">
              Tap to reveal <span aria-hidden>&rarr;</span>
            </span>
          </button>

          {/* Back: the real options, only visible once flipped. */}
          <div
            className="absolute inset-0 flex flex-col justify-center gap-2 overflow-y-auto rounded-md border border-line bg-surface p-4 [backface-visibility:hidden]"
            style={{ transform: "rotateY(180deg)" }}
          >
            {question.options.map((opt) => {
              const graded = result != null;
              const isCorrect = graded && result.correct_answers[question.id] === opt;
              const picked = selected === opt;
              const tone = !graded
                ? picked
                  ? "border-hero bg-hero/10 text-ink"
                  : "border-line text-ink hover:border-hero/50"
                : isCorrect
                  ? "border-pass bg-pass/10 text-ink"
                  : picked
                    ? "border-fail bg-fail/10 text-ink"
                    : "border-line text-ink-soft";
              return (
                <button
                  key={opt}
                  disabled={graded || busy}
                  onClick={() => pick(opt)}
                  className={`rounded-md border px-3 py-2 text-left text-sm transition-colors ${tone}`}
                >
                  {opt}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {result && (
        <div className="mt-5 flex items-center justify-center gap-3">
          <Tag tone={result.points_awarded > 0 ? "points" : result.points_awarded < 0 ? "fail" : "neutral"}>
            {result.points_awarded > 0 ? "+" : ""}
            {result.points_awarded} points
          </Tag>
          <Button variant="flat" onClick={() => onDone(result.points_total)}>
            Continue <span aria-hidden>&rarr;</span>
          </Button>
        </div>
      )}
    </Fade>
  );
}
