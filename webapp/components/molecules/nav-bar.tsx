import { Logo } from "@/components/atoms/logo";

export function NavBar() {
  return (
    <nav className="border-b border-dars-rule-dark sticky top-0 bg-dars-ink/[0.96] backdrop-blur-sm z-[100]">
      <div className="w-full max-w-7xl mx-auto px-14 py-[22px] flex justify-between items-center sm:px-6">
        <Logo variant="light" />
        <a
          href="/dashboard/login"
          className="bg-dars-terra text-dars-parchment px-[18px] py-2 rounded-md text-[13px] font-semibold no-underline hover:opacity-90 transition-opacity"
        >
          Log in
        </a>
      </div>
    </nav>
  );
}
