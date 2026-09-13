import type { LearnerCtx } from "@/lessons/types";

/* Role-flavored copy for Mission 1. Same pattern as the backend's
   web/copy.py analogy_for(): a "default" plus a few role overrides, correct
   concept underneath either way. Placeholder wording - the real
   personalization backend (see project memory) replaces this later without
   changing the lesson shape. */

export function introLine(ctx: LearnerCtx): string {
  return `This is ${ctx.datasetName}. Before we fix anything, let's make sure we actually know what we're looking at.`;
}

/* Short on purpose - a fact, not a paragraph. Shown as its own callout. */
export function rowColumnFact(): string {
  return "One row = one record. One column = one fact about it, tracked the same way every time.";
}

/* A second, separate callout: the same idea, in the learner's own terms. */
export function roleExampleFact(ctx: LearnerCtx): string {
  switch (norm(ctx.role)) {
    case "sales":
      return "For you: one row per deal, one column per thing you'd note about it - amount, rep, date.";
    case "hr":
      return "For you: one row per employee, one column per fact you'd track - role, tenure, department.";
    case "operations":
      return "For you: one row per order, one column per detail - quantity, status, date.";
    case "student":
      return "For you: one row per observation, one column per variable, like a lab notebook.";
    default:
      return "Every row follows the same columns, so you can compare them fairly.";
  }
}

function norm(role: string | null): string {
  return (role ?? "").toLowerCase();
}
