import { useState } from "react";
import { TopBar } from "@/components/TopBar";
import { Button } from "@/components/ui/Button";

/* Demo-only gate, not real authentication - there's no user database behind
   this, so the "admin" credential is intentionally public rather than
   secret. It exists to give a returning/demo user a fast path that skips
   the onboarding quiz, not to protect anything. */
export const DEMO_EMAIL = "admin@vybe.com";
export const DEMO_PASSWORD = "admin123";

export function Login({ onBack, onSuccess }: { onBack: () => void; onSuccess: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (email.trim().toLowerCase() === DEMO_EMAIL && password === DEMO_PASSWORD) {
      setError(null);
      onSuccess();
    } else {
      setError("That doesn't match. Use the demo credentials below.");
    }
  };

  return (
    <div className="min-h-screen bg-bg">
      <TopBar right="Back to start" />

      <div className="flex min-h-[calc(100vh-88px)] flex-col items-center justify-center px-8">
        <form
          onSubmit={submit}
          className="w-full max-w-[380px] border border-white/10 bg-white/[0.025] p-8"
        >
          <h1 className="text-3xl text-ink">Log in</h1>
          <p className="mt-2 text-sm text-ink-soft">
            Skip the questions, go straight to your data.
          </p>

          <label className="mt-7 block text-xs font-semibold uppercase tracking-wide text-ink-soft">
            Email
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-2 w-full border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm text-ink outline-none focus-visible:border-hero"
            placeholder="you@example.com"
          />

          <label className="mt-5 block text-xs font-semibold uppercase tracking-wide text-ink-soft">
            Password
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-2 w-full border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm text-ink outline-none focus-visible:border-hero"
            placeholder="&bull;&bull;&bull;&bull;&bull;&bull;&bull;&bull;"
          />

          {error && <p className="mt-3 text-sm text-fail">{error}</p>}

          <div className="mt-7">
            <Button glow type="submit" className="w-full justify-center">
              Log in <span aria-hidden>&rarr;</span>
            </Button>
          </div>

          <div className="mt-6 border border-white/10 bg-white/[0.03] px-4 py-3 text-xs text-ink-soft">
            <span className="font-semibold text-ink">Demo access</span> - this is a
            prototype, not a real account system.
            <br />
            {DEMO_EMAIL} / {DEMO_PASSWORD}
          </div>

          <button
            type="button"
            onClick={onBack}
            className="mt-5 text-sm font-semibold text-ink-soft hover:text-ink"
          >
            &larr; Back
          </button>
        </form>
      </div>
    </div>
  );
}
