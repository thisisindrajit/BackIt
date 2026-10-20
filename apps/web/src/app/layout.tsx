import type { Metadata } from "next";
import localFont from "next/font/local";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";

// Timeless Serif is primary (headings, money, story); Timeless Sans is secondary (interface).
// Both variable files carry a STYL axis: Serif 0 = display, 100 = text; Sans 100 = Sans.
const timelessSerif = localFont({
  src: [
    { path: "../fonts/TimelessSerifVF.ttf", style: "normal", weight: "200 700" },
    { path: "../fonts/TimelessSerifItalicVF.ttf", style: "italic", weight: "300 700" },
  ],
  variable: "--font-timeless-serif",
  display: "swap",
});

const timelessSans = localFont({
  src: [{ path: "../fonts/TimelessSansVF.ttf", style: "normal", weight: "300 800" }],
  variable: "--font-timeless-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "BackIt", template: "%s · BackIt" },
  description:
    "Turn your first fans into your best salespeople. Early fans buy at a founding price and earn a reward for every friend who buys.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${timelessSerif.variable} ${timelessSans.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <TooltipProvider>{children}</TooltipProvider>
        <Toaster position="bottom-right" />
      </body>
    </html>
  );
}
