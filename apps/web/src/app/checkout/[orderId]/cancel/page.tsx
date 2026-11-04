import { redirect } from "next/navigation";

export default async function CheckoutCancel({ params }: PageProps<"/checkout/[orderId]/cancel">) {
  const { orderId } = await params;
  redirect(`/checkout/${orderId}`);
}
