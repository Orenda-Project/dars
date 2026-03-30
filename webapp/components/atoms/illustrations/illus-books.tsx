interface IllusProps {
  size?: number;
}

export function IllusBooks({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <rect x="4" y="18" width="20" height="6" rx="1" stroke="#2c2420" strokeWidth="1.3" />
      <rect x="5" y="13" width="18" height="5" rx="1" stroke="#2c2420" strokeWidth="1.3" />
      <rect x="7" y="9" width="14" height="4" rx="1" stroke="#2c2420" strokeWidth="1.3" />
      <line x1="8" y1="18" x2="8" y2="24" stroke="#bf4e30" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="11" y1="13" x2="11" y2="18" stroke="#bf4e30" strokeWidth="1.8" strokeLinecap="round" opacity="0.5" />
      <line x1="14" y1="9" x2="14" y2="13" stroke="#bf4e30" strokeWidth="1.8" strokeLinecap="round" opacity="0.28" />
    </svg>
  );
}
