"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { authClient } from "@/lib/auth-client";
import { clearTokenCache } from "@/hooks/use-api";

function safeNext(value: string | null) {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/app";
}

function GoogleIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden {...props}>
      <path fill="#4285F4" d="M23.52 12.27c0-.85-.08-1.67-.22-2.45H12v4.64h6.46a5.52 5.52 0 0 1-2.4 3.62v3h3.88c2.27-2.09 3.58-5.17 3.58-8.81Z" />
      <path fill="#34A853" d="M12 24c3.24 0 5.96-1.07 7.94-2.9l-3.88-3.01c-1.07.72-2.45 1.15-4.06 1.15-3.13 0-5.78-2.11-6.72-4.95H1.27v3.11A12 12 0 0 0 12 24Z" />
      <path fill="#FBBC05" d="M5.28 14.29A7.2 7.2 0 0 1 4.9 12c0-.8.14-1.57.38-2.29V6.6H1.27a12 12 0 0 0 0 10.8l4.01-3.11Z" />
      <path fill="#EA4335" d="M12 4.77c1.76 0 3.34.61 4.59 1.8l3.44-3.44A11.5 11.5 0 0 0 12 0 12 12 0 0 0 1.27 6.6l4.01 3.11C6.22 6.88 8.87 4.77 12 4.77Z" />
    </svg>
  );
}

export function AuthForm({ mode }: { mode: "sign-in" | "sign-up" }) {
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const isSignUp = mode === "sign-up";
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(
    params.get("error") ? "Google sign-in didn’t finish. Please try again." : null
  );

  async function continueWithGoogle() {
    setPending(true);
    setError(null);
    clearTokenCache();
    const result = await authClient.signIn.social({
      provider: "google",
      callbackURL: next,
      errorCallbackURL: `/${mode}?next=${encodeURIComponent(next)}`,
    });
    if (result?.error) {
      setPending(false);
      setError(result.error.message ?? "We couldn’t reach Google. Please try again.");
    }
  }

  const otherHref = `${isSignUp ? "/sign-in" : "/sign-up"}${params.get("next") ? `?next=${encodeURIComponent(next)}` : ""}`;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-2 text-center">
        <h1 className="text-[2.75rem] leading-[1.05]">
          {isSignUp ? (
            <>
              Create your <em>account</em>
            </>
          ) : (
            <>
              Welcome <em>back</em>
            </>
          )}
        </h1>
        <p className="text-muted-foreground">
          {isSignUp ? "One account to run campaigns and back other builders." : "Sign in to your campaigns and backings."}
        </p>
      </div>
      <div className="flex flex-col gap-5">
        {error ? (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
        <Button type="button" size="lg" variant="outline" onClick={continueWithGoogle} disabled={pending}>
          {pending ? <Spinner data-icon="inline-start" /> : <GoogleIcon data-icon="inline-start" className="size-[18px]" />}
          Sign in with Google
        </Button>
        <p className="text-center text-sm text-muted-foreground">
          {isSignUp ? "Already have an account? " : "New to BackIt? "}
          <Link href={otherHref} className="text-link underline underline-offset-4">
            {isSignUp ? "Sign in" : "Create an account"}
          </Link>
        </p>
        <p className="text-center text-xs text-pretty text-muted-foreground">
          We use your Google name and email. Your name is shown on campaigns you run and back.
        </p>
      </div>
    </div>
  );
}
