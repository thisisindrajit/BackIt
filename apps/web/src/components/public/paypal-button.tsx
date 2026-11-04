"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

type Session = { start: (opts: { presentationMode: "popup" }, order: Promise<{ orderId: string }>) => Promise<void> };
type Sdk = {
  createPayPalOneTimePaymentSession: (handlers: {
    onApprove: (data: { orderId: string }) => Promise<void>;
    onCancel?: () => void;
    onError?: (e: unknown) => void;
  }) => Session;
};
declare global {
  interface Window {
    paypal?: { createInstance: (opts: { clientId: string; components: string[]; pageType?: string }) => Promise<Sdk> };
  }
}

const SDK_URL = "https://www.sandbox.paypal.com/web-sdk/v6/core";

function loadSdk() {
  if (window.paypal) return Promise.resolve();
  return new Promise<void>((resolve, reject) => {
    const s = document.createElement("script");
    s.src = SDK_URL;
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Couldn't load PayPal. Check your connection and try again."));
    document.head.appendChild(s);
  });
}

export function PayPalButton({ clientId, paypalOrderId, approveUrl, onApprove, disabled }: { clientId: string; paypalOrderId: string; approveUrl: string | null; onApprove: () => Promise<void>; disabled?: boolean }) {
  const session = useRef<Session | null>(null);
  const [ready, setReady] = useState(false);
  const approveRef = useRef(onApprove);
  useEffect(() => {
    approveRef.current = onApprove;
  });

  useEffect(() => {
    let alive = true;
    loadSdk()
      .then(() => window.paypal!.createInstance({ clientId, components: ["paypal-payments"], pageType: "checkout" }))
      .then((sdk) => {
        if (!alive) return;
        session.current = sdk.createPayPalOneTimePaymentSession({
          onApprove: () => approveRef.current(),
          onCancel: () => toast("Payment cancelled. Your spot is still held for now."),
          onError: () => toast.error("PayPal couldn't complete the payment. Try again."),
        });
        setReady(true);
      })
      .catch((e: Error) => toast.error(e.message));
    return () => {
      alive = false;
    };
  }, [clientId]);

  // Popup keeps the buyer on BackIt. PayPal refuses to render inside a frame, so if the popup
  // can't open we send the buyer to PayPal's page, which returns to /checkout/[id]/return.
  async function pay() {
    const redirect = () => {
      if (approveUrl) window.location.assign(approveUrl);
      else toast.error("PayPal couldn't open. Allow pop-ups for backit.club and try again.");
    };
    if (!session.current) return redirect();
    try {
      await session.current.start({ presentationMode: "popup" }, Promise.resolve({ orderId: paypalOrderId }));
    } catch {
      redirect();
    }
  }

  return (
    <Button
      size="lg"
      disabled={(!ready && !approveUrl) || disabled}
      onClick={pay}
    >
      {!ready ? <Spinner data-icon="inline-start" /> : null}
      Pay with PayPal
    </Button>
  );
}
