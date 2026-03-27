// src/components/landing/illustrations.tsx

interface IllusProps {
  size?: number;
}

export function IllusQuill({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none">
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

export function IllusBooks({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none">
      <rect x="4" y="18" width="20" height="6" rx="1" stroke="#2c2420" strokeWidth="1.3" />
      <rect x="5" y="13" width="18" height="5" rx="1" stroke="#2c2420" strokeWidth="1.3" />
      <rect x="7" y="9" width="14" height="4" rx="1" stroke="#2c2420" strokeWidth="1.3" />
      <line x1="8" y1="18" x2="8" y2="24" stroke="#bf4e30" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="11" y1="13" x2="11" y2="18" stroke="#bf4e30" strokeWidth="1.8" strokeLinecap="round" opacity="0.5" />
      <line x1="14" y1="9" x2="14" y2="13" stroke="#bf4e30" strokeWidth="1.8" strokeLinecap="round" opacity="0.28" />
    </svg>
  );
}

export function IllusOpenBook({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none">
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

export function IllusKey({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none">
      <circle cx="11" cy="12" r="6" stroke="#2c2420" strokeWidth="1.3" />
      <circle cx="11" cy="12" r="2.5" stroke="#bf4e30" strokeWidth="1.3" />
      <path d="M16 17L24 25" stroke="#2c2420" strokeWidth="1.3" strokeLinecap="round" />
      <line x1="21" y1="22" x2="24" y2="19" stroke="#2c2420" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  );
}

export function IllusCompass({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none">
      <circle cx="14" cy="14" r="8" stroke="#2c2420" strokeWidth="1.3" strokeDasharray="2 2" />
      <path d="M12 17L14 11L16 17" stroke="#bf4e30" strokeWidth="1.3" fill="none" />
      <line x1="12.5" y1="15.5" x2="15.5" y2="15.5" stroke="#bf4e30" strokeWidth="1.3" strokeLinecap="round" />
      <line x1="6" y1="24" x2="22" y2="6" stroke="#2c2420" strokeWidth="1.1" strokeLinecap="round" opacity="0.25" />
      <circle cx="14" cy="14" r="1.5" fill="#2c2420" />
    </svg>
  );
}

export function IllusComponents({ size = 28 }: IllusProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none">
      <rect x="2" y="16" width="10" height="9" rx="1.5" stroke="#2c2420" strokeWidth="1.3" />
      <rect x="16" y="16" width="10" height="9" rx="1.5" stroke="#2c2420" strokeWidth="1.3" />
      <rect x="9" y="4" width="10" height="9" rx="1.5" stroke="#bf4e30" strokeWidth="1.3" />
      <line x1="7" y1="16" x2="14" y2="13" stroke="#2c2420" strokeWidth="1" strokeLinecap="round" opacity="0.4" />
      <line x1="21" y1="16" x2="14" y2="13" stroke="#2c2420" strokeWidth="1" strokeLinecap="round" opacity="0.4" />
    </svg>
  );
}
