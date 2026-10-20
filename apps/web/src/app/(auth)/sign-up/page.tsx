import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthForm } from "@/components/backit/auth-form";

export const metadata: Metadata = { title: "Create account" };

export default function Page() {
  return (
    <Suspense>
      <AuthForm mode="sign-up" />
    </Suspense>
  );
}
