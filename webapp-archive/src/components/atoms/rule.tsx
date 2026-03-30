interface RuleProps {
  variant?: "light" | "dark";
  className?: string;
}

export function Rule({ variant = "light", className = "" }: RuleProps) {
  const color = variant === "dark" ? "border-dars-rule-dark" : "border-dars-rule-light";
  return <hr className={`border-t ${color} ${className}`} />;
}
