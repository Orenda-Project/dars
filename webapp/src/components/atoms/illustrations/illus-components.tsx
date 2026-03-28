interface IllusProps {
  size?: number;
}

export function IllusComponents({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <rect x="2" y="16" width="10" height="9" rx="1.5" stroke="#2c2420" strokeWidth="1.3" />
      <rect x="16" y="16" width="10" height="9" rx="1.5" stroke="#2c2420" strokeWidth="1.3" />
      <rect x="9" y="4" width="10" height="9" rx="1.5" stroke="#bf4e30" strokeWidth="1.3" />
      <line x1="7" y1="16" x2="14" y2="13" stroke="#2c2420" strokeWidth="1" strokeLinecap="round" opacity="0.4" />
      <line x1="21" y1="16" x2="14" y2="13" stroke="#2c2420" strokeWidth="1" strokeLinecap="round" opacity="0.4" />
    </svg>
  );
}
