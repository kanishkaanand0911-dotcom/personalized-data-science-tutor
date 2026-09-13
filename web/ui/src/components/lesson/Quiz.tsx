import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Tag } from "@/components/ui/Tag";
import { Fade } from "@/components/ui/Fade";
import type { QuizQuestion, QuizResult } from "@/lib/api";

/* A quick, low-stakes recap after a level's (or the modeling phase's)
   reveal: multiple-choice questions built from the real outcome that was
   just shown, never a second chance to change the original guess/answer.
   fetchQuestions/submitAnswers are injected so this same component serves
   both a level's quiz (api.quiz/api.submitQuiz) and the modeling quiz
   (api.modelQuiz/api.submitModelQuiz) - the scoring and UI are identical
   either way. onDone hands back the running point total so the caller can
   stay in sync without a second fetch. */
export function Quiz({
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
  const [questions, setQuestions] = useState<QuizQuestion[] | null>(null);
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [result, setResult] = useState<QuizResult | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setQuestions(null);
    setSelected({});
    setResult(null);
    fetchQuestions().then((res) => setQuestions(res.questions));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetKey]);

  if (!questions) {
    return (
      <div className="mt-6 space-y-3">
        <div className="h-20 animate-pulse rounded-md border border-line bg-surface" />
        <div className="h-20 animate-pulse rounded-md border border-line bg-surface" />
      </div>
    );
  }

  const allAnswered = questions.every((q) => selected[q.id]);

  const submit = async () => {
    setBusy(true);
    try {
      setResult(await submitAnswers(selected));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Fade k={`quiz-${resetKey}`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-soft">Quick recap</p>
      <div className="mt-3 space-y-4">
        {questions.map((q) => (
          <div key={q.id}>
            <p className="text-sm font-semibold text-ink">{q.prompt}</p>
            <div className="mt-2 flex flex-col gap-2">
              {q.options.map((opt) => {
                const picked = selected[q.id] === opt;
                const graded = result != null;
                const isCorrect = graded && result.correct_answers[q.id] === opt;
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
                    disabled={graded}
                    onClick={() => setSelected((s) => ({ ...s, [q.id]: opt }))}
                    className={`rounded-md border px-3 py-2 text-left text-sm transition-colors ${tone}`}
                  >
                    {opt}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {!result ? (
        <div className="mt-5">
          <Button variant="flat" disabled={!allAnswered || busy} onClick={submit}>
            Check answers
          </Button>
        </div>
      ) : (
        <div className="mt-5 flex items-center gap-3">
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
