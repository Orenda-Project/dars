interface IllusProps {
  size?: number;
}

export function IllusOpenBook({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <path d="M14 8C14 8 10 7 6 8V20C10 19 14 20 14 20V8Z" stroke="#2c2420" strokeWidth="1.3" strokeLinejoin="round" />
      <path d="M14 8C14 8 18 7 22 8V20C18 19 14 20 14 20V8Z" stroke="#2c2420" strokeWidth="1.3" strokeLinejoin="round" />
      <line x1="14" y1="8" x2="14" y2="20" stroke="#bf4e30" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}
