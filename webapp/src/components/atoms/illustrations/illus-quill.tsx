interface IllusProps {
  size?: number;
}

export function IllusQuill({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <path
        d="M21 4C21 4 25 8 22 14L11 23L7 24L8 20L19 11C20 8 21 4 21 4Z"
        stroke="#2c2420"
        strokeWidth="1.3"
        strokeLinejoin="round"
      />
      <path d="M19 11L21 13" stroke="#2c2420" strokeWidth="1.3" strokeLinecap="round" />
      <line x1="7" y1="24" x2="11" y2="24" stroke="#bf4e30" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M17 7C19 6 21 5 22 5" stroke="#2c2420" strokeWidth="0.9" strokeLinecap="round" opacity="0.35" />
    </svg>
  );
}
