import { Logo } from "@/components/atoms/logo";

export function LoginTemplate() {
  return (
    <main className="min-h-screen bg-dars-parchment flex flex-col items-center justify-center px-4 py-16">
      <a href="/" className="no-underline mb-10">
        <Logo size="md" />
      </a>
      <span className="font-serif text-[13px] text-dars-terra italic mb-4">Coming soon</span>
      <h1 className="font-serif text-[42px] sm:text-[30px] font-bold text-dars-ink tracking-[-1px] leading-[1.1] mb-4 text-center max-w-md">
        Your dashboard is on its way.
      </h1>
      <p className="text-base text-dars-muted max-w-[360px] text-center leading-[1.65]">
        We&apos;re putting the finishing touches on your workspace. Check back soon.
      </p>
    </main>
  );
}
