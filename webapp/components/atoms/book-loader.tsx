interface BookLoaderProps {
  size?: number;
  label?: string;
  className?: string;
}

export function BookLoader({ size = 48, label = "Loading", className = "" }: BookLoaderProps) {
  return (
    <span
      role="status"
      aria-label={label}
      className={`inline-flex flex-col items-center gap-2 ${className}`}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 48 48"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <style>{`
          @keyframes page-turn {
            0%   { transform-origin: left center; transform: rotateY(0deg);   opacity: 1; }
            40%  { transform-origin: left center; transform: rotateY(-160deg); opacity: 0.7; }
            60%  { transform-origin: left center; transform: rotateY(-160deg); opacity: 0.7; }
            100% { transform-origin: left center; transform: rotateY(0deg);   opacity: 1; }
          }
          .book-page {
            animation: page-turn 1.6s ease-in-out infinite;
          }
        `}</style>

        {/* Book spine */}
        <rect x="22" y="10" width="3" height="28" rx="1" fill="#1c1410" opacity="0.15" />

        {/* Left cover */}
        <rect x="6" y="10" width="17" height="28" rx="1.5" stroke="#1c1410" strokeWidth="1.3" fill="none" />

        {/* Right cover */}
        <rect x="25" y="10" width="17" height="28" rx="1.5" stroke="#1c1410" strokeWidth="1.3" fill="none" />

        {/* Animated page */}
        <rect
          className="book-page"
          x="25" y="12"
          width="15" height="24"
          rx="1"
          fill="#faf7f2"
          stroke="#bf4e30"
          strokeWidth="1"
        />

        {/* Lines on left page */}
        <line x1="9" y1="18" x2="20" y2="18" stroke="#1c1410" strokeWidth="0.8" strokeLinecap="round" opacity="0.25" />
        <line x1="9" y1="22" x2="20" y2="22" stroke="#1c1410" strokeWidth="0.8" strokeLinecap="round" opacity="0.25" />
        <line x1="9" y1="26" x2="20" y2="26" stroke="#1c1410" strokeWidth="0.8" strokeLinecap="round" opacity="0.25" />
        <line x1="9" y1="30" x2="16" y2="30" stroke="#1c1410" strokeWidth="0.8" strokeLinecap="round" opacity="0.25" />
      </svg>
    </span>
  );
}
