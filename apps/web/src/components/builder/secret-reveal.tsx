"use client";

import { CheckIcon, CopyIcon } from "lucide-react";
import { useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from "@/components/ui/input-group";

export function CopyField({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <InputGroup>
      <InputGroupInput readOnly value={value} aria-label={label} className="font-mono text-xs" onFocus={(e) => e.currentTarget.select()} />
      <InputGroupAddon align="inline-end">
        <InputGroupButton
          size="icon-xs"
          aria-label={copied ? "Copied" : `Copy ${label.toLowerCase()}`}
          onClick={async () => {
            await navigator.clipboard.writeText(value);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          }}
        >
          {copied ? <CheckIcon /> : <CopyIcon />}
        </InputGroupButton>
      </InputGroupAddon>
    </InputGroup>
  );
}

export function SecretReveal({ secret }: { secret: string }) {
  return (
    <div className="flex flex-col gap-3">
      <CopyField value={secret} label="Webhook secret" />
      <Alert className="border-transparent bg-accent text-accent-foreground">
        <AlertTitle>You won’t see this again</AlertTitle>
        <AlertDescription className="text-accent-foreground/80">
          Store it in your product’s environment, for the demo product that’s <code className="font-mono">BACKIT_WEBHOOK_SECRET</code>. Lost it? Rotate it from the Setup tab.
        </AlertDescription>
      </Alert>
    </div>
  );
}
