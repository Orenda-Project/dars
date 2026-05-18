/**
 * F4.3 — /teacher-app/ root → redirect to /teacher-app/today.
 */
import { redirect } from "next/navigation";

export default function TeacherAppRoot() {
  redirect("/teacher-app/today");
}
