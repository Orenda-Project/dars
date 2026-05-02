import { redirect } from "next/navigation";

export default function ImportRedirect() {
  redirect("/dashboard/admin/books?tab=import");
}
