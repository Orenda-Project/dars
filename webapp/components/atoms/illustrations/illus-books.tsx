interface IllusProps {
  size?: number;
}

export function IllusBooks({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <rect x="4" y="7" width="7" height="14" rx="1" stroke="#2c2420" strokeWidth="1.3" />
      <rect x="12" y="5" width="7" height="16" rx="1" stroke="#2c2420" strokeWidth="1.3" />
      <rect x="20" y="8" width="5" height="13" rx="1" stroke="#2c2420" strokeWidth="1.3" />
      <line x1="4" y1="21" x2="25" y2="21" stroke="#bf4e30" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
