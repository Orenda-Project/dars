interface IllusProps {
  size?: number;
}

export function IllusOpenBook({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <path
        d="M14 4C11 4 6 6 5 9L5 24C6 22 11 21 14 21C17 21 22 22 23 24L23 9C22 6 17 4 14 4Z"
        stroke="#2c2420"
        strokeWidth="1.3"
      />
      <line x1="14" y1="4" x2="14" y2="21" stroke="#2c2420" strokeWidth="1.3" />
      <line x1="7" y1="12" x2="13" y2="13" stroke="#2c2420" strokeWidth="1" strokeLinecap="round" opacity="0.45" />
      <line x1="7" y1="15" x2="13" y2="16" stroke="#2c2420" strokeWidth="1" strokeLinecap="round" opacity="0.45" />
      <line x1="15" y1="13" x2="21" y2="12" stroke="#bf4e30" strokeWidth="1" strokeLinecap="round" opacity="0.7" />
      <line x1="15" y1="16" x2="21" y2="15" stroke="#bf4e30" strokeWidth="1" strokeLinecap="round" opacity="0.7" />
    </svg>
  );
}
