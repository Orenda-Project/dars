interface IllusProps {
  size?: number;
}

export function IllusCompass({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <circle cx="14" cy="14" r="8" stroke="#2c2420" strokeWidth="1.3" strokeDasharray="2 2" />
      <path d="M12 17L14 11L16 17" stroke="#bf4e30" strokeWidth="1.3" fill="none" />
      <line x1="12.5" y1="15.5" x2="15.5" y2="15.5" stroke="#bf4e30" strokeWidth="1.3" strokeLinecap="round" />
      <line x1="6" y1="24" x2="22" y2="6" stroke="#2c2420" strokeWidth="1.1" strokeLinecap="round" opacity="0.25" />
      <circle cx="14" cy="14" r="1.5" fill="#2c2420" />
    </svg>
  );
}
