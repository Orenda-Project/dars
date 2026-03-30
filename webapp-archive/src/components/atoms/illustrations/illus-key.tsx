interface IllusProps {
  size?: number;
}

export function IllusKey({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <circle cx="11" cy="12" r="6" stroke="#2c2420" strokeWidth="1.3" />
      <circle cx="11" cy="12" r="2.5" stroke="#bf4e30" strokeWidth="1.3" />
      <path d="M16 17L24 25" stroke="#2c2420" strokeWidth="1.3" strokeLinecap="round" />
      <line x1="21" y1="22" x2="24" y2="19" stroke="#2c2420" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  );
}
