import type { Metadata } from "next";
import { Wordmark } from "@/components/backit/wordmark";
import { Checkout } from "@/components/public/checkout";

export const metadata: Metadata = { title: "Checkout" };

export default async function CheckoutPage({ params }: PageProps<"/checkout/[orderId]">) {
  const { orderId } = await params;
  return (
    <div className="flex min-h-svh flex-col">
      <header className="border-b">
        <div className="mx-auto flex h-14 w-full max-w-xl items-center px-4 sm:px-6">
          <Wordmark />
        </div>
      </header>
      <main className="mx-auto flex w-full max-w-xl flex-col gap-6 px-4 py-10 sm:px-6">
        <Checkout orderId={orderId} />
      </main>
    </div>
  );
}
