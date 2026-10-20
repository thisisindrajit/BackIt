import type { Metadata } from "next";
import { DemoProduct } from "@/components/public/demo-product";

export const metadata: Metadata = { title: "Demo product" };

export default function DemoPage() {
  return <DemoProduct />;
}
