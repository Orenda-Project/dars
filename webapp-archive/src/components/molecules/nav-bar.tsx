import { Logo } from "@/components/atoms/logo";

const NAV_LINKS = [
  { label: "Docs", href: "/docs" },
  { label: "API", href: "/docs" },
  { label: "Pricing", href: "#" },
];

export function NavBar() {
  return (
    <nav className="flex justify-between items-center px-14 py-[22px] border-b border-dars-rule-dark sticky top-0 bg-dars-ink/[0.96] backdrop-blur-sm z-[100] sm:px-6">
      <Logo variant="light" />
      <div className="flex gap-8 items-center text-[13px] text-dars-muted-light sm:gap-4">
        {NAV_LINKS.map(({ label, href }) => (
          <a
            key={label}
            href={href}
            className="text-inherit no-underline hover:text-dars-parchment transition-colors hidden sm:block"
          >
            {label}
          </a>
        ))}
        <a
          href="/login"
          className="bg-dars-terra text-dars-parchment px-[18px] py-2 rounded-md text-[13px] font-semibold no-underline hover:opacity-90 transition-opacity"
        >
          Get access
        </a>
      </div>
    </nav>
  );
}
