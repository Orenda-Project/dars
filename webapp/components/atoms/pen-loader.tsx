/**
 * PenLoader — a calligraphy nib that draws an ink stroke, then fades and repeats.
 * Used as the branded loading indicator throughout the Dars dashboard.
 *
 * Usage:
 *   <PenLoader />                  — default size (48px)
 *   <PenLoader size={64} />        — custom size
 *   <PenLoader label="Loading…" /> — accessible label (default: "Loading")
 */

interface PenLoaderProps {
  size?: number;
  label?: string;
  className?: string;
}

export function PenLoader({ size = 48, label = "Loading", className = "" }: PenLoaderProps) {
  const strokeLen = 120;

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
          @keyframes pen-draw {
            0%   { stroke-dashoffset: ${strokeLen}; opacity: 1; }
            70%  { stroke-dashoffset: 0;            opacity: 1; }
            85%  { stroke-dashoffset: 0;            opacity: 0; }
            100% { stroke-dashoffset: ${strokeLen}; opacity: 0; }
          }
          @keyframes nib-move {
            0%   { transform: translate(5px, 36px) rotate(-145deg); opacity: 1; }
            70%  { transform: translate(37px, 26px) rotate(-145deg); opacity: 1; }
            85%  { transform: translate(37px, 26px) rotate(-145deg); opacity: 0; }
            100% { transform: translate(5px, 36px) rotate(-145deg); opacity: 0; }
          }
          .pen-stroke {
            stroke-dasharray: ${strokeLen};
            stroke-dashoffset: ${strokeLen};
            animation: pen-draw 1.8s cubic-bezier(0.4, 0, 0.2, 1) infinite;
          }
          .pen-nib {
            animation: nib-move 1.8s cubic-bezier(0.4, 0, 0.2, 1) infinite;
          }
        `}</style>

        {/* Ink stroke — a slightly curved path from bottom-left to upper-right */}
        <path
          className="pen-stroke"
          d="M 5 38 Q 20 30 38 28"
          stroke="#bf4e30"
          strokeWidth="2.2"
          strokeLinecap="round"
        />

        {/* Minimal outline pen nib */}
        <g className="pen-nib">
          {/* Outer nib shape — shoulder tapering to a point */}
          <path
            d="M -4.5,0 L 4.5,0 L 0,13 Z"
            fill="none"
            stroke="#1c1410"
            strokeWidth="1.2"
            strokeLinejoin="round"
          />
          {/* Center slit */}
          <line
            x1="0" y1="4"
            x2="0" y2="12"
            stroke="#1c1410"
            strokeWidth="0.8"
            strokeLinecap="round"
            opacity="0.5"
          />
          {/* Ink dot at tip */}
          <circle cx="0" cy="13.5" r="1" fill="#bf4e30" />
        </g>
      </svg>
    </span>
  );
}
