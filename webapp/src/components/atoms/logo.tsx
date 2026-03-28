interface LogoProps {
  variant?: "light" | "dark";
  size?: "sm" | "md";
}

export function Logo({ variant = "dark", size = "md" }: LogoProps) {
  const nameColor = variant === "light" ? "text-dars-parchment" : "text-dars-ink";
  const urduColor = "text-dars-terra";
  const textSize = size === "sm" ? "text-base" : "text-lg";

  return (
    <div className={`font-serif font-bold flex items-baseline gap-2 ${textSize} ${nameColor}`}>
      Dars{" "}
      <span className={`${urduColor} font-normal text-sm`}>درس</span>
    </div>
  );
}
