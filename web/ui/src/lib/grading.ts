import type { Level } from "@/lib/api";

/* Friendly topic names for the study screen headline. */
export const TOPIC_NAMES: Record<string, string> = {
  missing_numeric: "Missing Values",
  missing_categorical: "Missing Values",
  label_inconsistency: "Inconsistent Labels",
  format_error_numeric: "Numbers Stored as Text",
  format_error_date: "Mixed-Up Dates",
};

export function topicName(issueType: string): string {
  return TOPIC_NAMES[issueType] ?? "Data Issue";
}

// Words shared across every option's label/id (impute, fill, value...) would
// otherwise make the first option win by default. Strip them so a match has
// to come from something that actually distinguishes one option from another.
const STOPWORDS = new Set([
  "impute",
  "fill",
  "filled",
  "filling",
  "value",
  "values",
  "column",
  "data",
  "with",
  "the",
  "a",
  "an",
  "to",
  "it",
  "in",
  "on",
  "use",
  "using",
  "by",
]);

function keywordsOf(id: string, label: string): string[] {
  return `${id} ${label}`
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((w) => w.length > 1 && !STOPWORDS.has(w));
}

/* PLACEholder grading: turns what the learner types into one of the level's
   real option ids by scoring keyword overlap, so the actual deterministic
   agent (via /api/levels/:id/guess) is still what decides and scores it -
   this function only interprets free text into that same choice.

   This is the intended swap point for the trained personalization/grading
   backend: replace matchAnswer with a call to that model, keep returning an
   option id (or null when it can't tell), and everything downstream -
   scoring, the reveal, the agent's real fix - stays exactly as it is. */
export function matchAnswer(level: Level, text: string): string | null {
  const t = text.toLowerCase().trim();
  if (!t) return null;

  let best: { id: string; score: number } | null = null;
  for (const opt of level.options) {
    const kws = keywordsOf(opt.id, opt.label);
    const score = kws.filter((w) => t.includes(w)).length;
    if (score > 0 && (!best || score > best.score)) best = { id: opt.id, score };
  }
  if (best) return best.id;

  if (level.guess_kind === "pass_fail") {
    if (/\b(pass|passes|works|fine|good|holds|success)\b/.test(t)) return "pass";
    if (/\b(fail|fails|break|breaks|wrong|error|bad)\b/.test(t)) return "fail";
  }

  return null;
}
