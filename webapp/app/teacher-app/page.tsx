import { redirect } from "next/navigation";

// Entry point for the Teacher Sample App — sends the user to today's schedule.
export default function TeacherAppIndex() {
  redirect("/teacher-app/today");
}
