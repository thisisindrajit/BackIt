import { redirect } from "next/navigation";

export default async function CheckoutReturn({ params }: PageProps<"/checkout/[orderId]/return">) {
  const { orderId } = await params;
  redirect(`/checkout/${orderId}?approved=1`);
}
