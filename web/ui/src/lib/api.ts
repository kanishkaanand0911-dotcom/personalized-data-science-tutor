/* Client for the FastAPI layer in web/api.py. Every decision shown here comes
   from the backend; this file only calls it and types the shapes. */

const SID_KEY = "da_sid";
const LEARNER_ID_KEY = "vybe_learner_id";

export function getSessionId(): string {
  return sessionStorage.getItem(SID_KEY) ?? "";
}

function setSessionId(id: string) {
  sessionStorage.setItem(SID_KEY, id);
}

export function clearSession() {
  sessionStorage.removeItem(SID_KEY);
}

/* A stable id for this browser, independent of the backend session above
   (which is in-memory and resets whenever the server restarts, or a fresh
   /api/session is created). This is what lets the ADK tutor's own memory -
   profile, XP, badges - actually persist across visits instead of starting
   from zero every time; see web/chat.py's ask_adk(). Kept in localStorage,
   not sessionStorage, specifically so it survives a closed tab/browser. */
export function getOrCreateLearnerId(): string {
  let id = localStorage.getItem(LEARNER_ID_KEY);
  if (!id) {
    id = crypto.randomUUID ? crypto.randomUUID() : `learner_${Date.now()}_${Math.random().toString(16).slice(2)}`;
    localStorage.setItem(LEARNER_ID_KEY, id);
  }
  return id;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const sid = getSessionId();
  if (sid) headers.set("X-Session-Id", sid);
  const res = await fetch(`/api${path}`, { ...init, headers });
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    /* no body */
  }
  if (!res.ok) {
    const hasError = data && typeof data === "object" && "error" in data;
    const msg = hasError ? String((data as { error: unknown }).error) : `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return data as T;
}

export type Profile = { role: string | null; experience: string | null; goal?: string | null };

export type DatasetSummary = {
  name: string;
  rows: number;
  cols: number;
  columns: string[];
  preview: Record<string, unknown>[];
  missing: Record<string, number>;
};

export type RoadmapNode = { key: string; title: string; detail: string };
export type Roadmap = { dataset_name: string; nodes: RoadmapNode[] };

export type LevelOption = { id: string; label: string; blurb: string };
export type Level = {
  id: number;
  column: string;
  issue_type: string;
  severity: string;
  title: string;
  analogy: string;
  question: string;
  options: LevelOption[];
  guess_kind: "which_strategy" | "pass_fail";
};

export type Attempt = {
  strategy: string;
  label: string;
  passed: boolean;
  reason: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
};

export type GuessResult = {
  correct: boolean;
  points_awarded: number;
  points_total: number;
  your_choice: string;
  locked: boolean;
  agent_choice: string;
  agent_choice_label: string;
  resolved: boolean;
  attempts: Attempt[];
  next_level: number | null;
};

export type VerifyCheck = {
  key: string;
  label: string;
  passed: boolean;
  reason: string;
  preview: Record<string, unknown> | null;
};
export type Verify = {
  overall_passed: boolean;
  checks: VerifyCheck[];
  columns_used: Record<string, string | null>;
};

export type ChartBar = { label: string; value: number };
export type TrendPoint = { label: string; value: number };
export type VisualizeData = {
  numeric_charts: { column: string; bars: ChartBar[] }[];
  category_charts: { column: string; bars: ChartBar[] }[];
  trend_chart: { column: string; date_column: string; points: TrendPoint[] } | null;
};

export type ModelAttempt = {
  model: string;
  label: string;
  passed: boolean;
  reason: string;
  cv_r2: number | null;
  test_rmse: number | null;
};
export type ModelResult = {
  available: boolean;
  reason?: string;
  target?: string;
  observation?: {
    n_samples: number;
    n_features: number;
    linearity_signal: string;
    max_abs_correlation: number;
  };
  start_reason?: string;
  attempts: ModelAttempt[];
  chosen: { model: string; label: string; cv_r2: number; explanation: string } | null;
};

export type Results = {
  points_total: number;
  levels_total: number;
  levels_correct: number;
  columns_changed: string[];
  cleaned_preview: Record<string, unknown>[];
  cleaned_columns: string[];
  downstream_passed: boolean;
  model: ModelResult;
  lesson: string;
};

export type TutorProgress = {
  xp: number;
  level: number;
  badges: string[];
  streak_days?: number;
};

export type QuizQuestion = { id: string; prompt: string; options: string[] };
export type QuizResult = {
  results: Record<string, boolean>;
  correct_answers: Record<string, string>;
  points_awarded: number;
  points_total: number;
};

export type CodeReveal = {
  available: boolean;
  label: string | null;
  code: string | null;
  explain: string | null;
};

export type DatasetLoadResponse = {
  dataset: DatasetSummary;
  roadmap: Roadmap;
  levels: Level[];
};

// ----------------------------------------------------------------- mentor

export type LearningMode = "guided" | "assisted" | "independent";
export type MentorAction = "explain" | "hint" | "why_wrong" | "example" | "explain_output" | "next_step";

export type MentorLessonContext = {
  id?: string;
  title?: string;
  objective?: string;
  difficulty?: string;
  step?: "learn" | "predict" | "apply" | "explain";
};

export type MentorDatasetContext = {
  name?: string;
  columns?: string[];
  shape?: { rows?: number; cols?: number };
  sample_rows?: Record<string, unknown>[];
  summary?: Record<string, unknown>;
  current_version?: "raw" | "cleaned" | "model_ready";
};

export type MentorRequest = {
  user_message: string;
  current_lesson?: MentorLessonContext;
  dataset?: MentorDatasetContext;
  current_code?: string;
  last_output?: string;
  last_error?: string;
  attempt_count?: number;
  hints_used?: number;
  learning_mode?: LearningMode;
  mastery_level?: number;
  previous_mistakes?: string[];
  recent_actions?: string[];
  action?: MentorAction;
};

export type MentorResponse = { reply: string; grounded: boolean; mode: LearningMode };

export const api = {
  async startSession(profile: Profile): Promise<string> {
    const { session_id } = await request<{ session_id: string }>("/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profile),
    });
    setSessionId(session_id);
    return session_id;
  },

  async loadSample(): Promise<DatasetLoadResponse> {
    const fd = new FormData();
    fd.append("use_sample", "true");
    return request("/dataset", { method: "POST", body: fd });
  },

  async loadFile(file: File): Promise<DatasetLoadResponse> {
    const fd = new FormData();
    fd.append("file", file);
    return request("/dataset", { method: "POST", body: fd });
  },

  markRead(levelId: number): Promise<{ awarded: boolean; points_total: number }> {
    return request(`/levels/${levelId}/read`, { method: "POST" });
  },

  guess(levelId: number, choiceId: string): Promise<GuessResult> {
    return request(`/levels/${levelId}/guess`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ choice_id: choiceId }),
    });
  },

  chat(message: string, levelId?: number): Promise<{ reply: string; grounded: boolean; progress: TutorProgress | null }> {
    return request("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, level_id: levelId ?? null, learner_id: getOrCreateLearnerId() }),
    });
  },

  callouts(levelId: number): Promise<{ callouts: string[]; grounded: boolean }> {
    return request(`/levels/${levelId}/callouts`);
  },

  quiz(levelId: number): Promise<{ questions: QuizQuestion[] }> {
    return request(`/levels/${levelId}/quiz`);
  },

  submitQuiz(levelId: number, answers: Record<string, string>): Promise<QuizResult> {
    return request(`/levels/${levelId}/quiz`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers }),
    });
  },

  levelCode(levelId: number): Promise<CodeReveal> {
    return request(`/levels/${levelId}/code`);
  },

  modelCode(): Promise<CodeReveal> {
    return request("/model/code");
  },

  modelQuiz(): Promise<{ questions: QuizQuestion[] }> {
    return request("/model/quiz");
  },

  submitModelQuiz(answers: Record<string, string>): Promise<QuizResult> {
    return request("/model/quiz", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers }),
    });
  },

  verify(): Promise<Verify> {
    return request("/verify");
  },

  visualize(): Promise<VisualizeData> {
    return request("/visualize");
  },

  model(): Promise<ModelResult> {
    return request("/model");
  },

  results(): Promise<Results> {
    return request("/results");
  },

  mentor(body: MentorRequest): Promise<MentorResponse> {
    return request("/mentor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...body, learner_id: getOrCreateLearnerId() }),
    });
  },
};
