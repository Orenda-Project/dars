interface LogoProps {
  variant?: "light" | "dark";
  size?: "sm" | "md" | "lg";
  animated?: boolean;
}

export function Logo({
  variant = "dark",
  size = "md",
  animated = false,
}: LogoProps) {
  const ink = variant === "light" ? "#faf7f2" : "#1c1410";
  const terra = "#bf4e30";
  const inkFaint =
    variant === "light" ? "rgba(250,247,242,0.07)" : "rgba(28,20,16,0.04)";

  const scale = size === "sm" ? 0.6 : size === "lg" ? 1.4 : 1;
  const w = Math.round(136 * scale);
  const h = Math.round(48 * scale);

  return (
    <svg
      width={w}
      height={h}
      viewBox="0 0 136 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Dars"
      role="img"
    >
      <style>{`
        @keyframes dl-draw {
          from { stroke-dashoffset: 1 }
          to   { stroke-dashoffset: 0 }
        }
        @keyframes dl-fade {
          from { opacity: 0; transform: translateY(2px) }
          to   { opacity: 1; transform: translateY(0) }
        }
        @keyframes dl-pop {
          0%   { transform: scale(0); opacity: 0 }
          70%  { transform: scale(1.3); opacity: 1 }
          100% { transform: scale(1); opacity: 1 }
        }
        @keyframes book-left {
          0%, 100% { transform: scaleX(1) translateX(0); }
          45%      { transform: scaleX(1.08) translateX(-1.5px); }
        }
        @keyframes book-right {
          0%, 100% { transform: scaleX(1) translateX(0); }
          45%      { transform: scaleX(1.08) translateX(1.5px); }
        }
        @keyframes book-arch {
          0%, 100% { transform: scaleX(1) translateY(0); }
          45%      { transform: scaleX(1.12) translateY(-1px); }
        }
        @keyframes book-dot {
          0%, 100% { transform: scale(1); }
          45%      { transform: scale(1.2); }
        }
        @keyframes page-lines-l {
          0%, 100% { transform: translateX(0); }
          45%      { transform: translateX(-0.8px); }
        }
        @keyframes page-lines-r {
          0%, 100% { transform: translateX(0); }
          45%      { transform: translateX(0.8px); }
        }

        .dl { stroke-dasharray: 1; stroke-dashoffset: ${animated ? 1 : 0}; }
        ${animated ? `
        .dl-1 { animation: dl-draw .5s cubic-bezier(.4,0,.2,1) 0s forwards }
        .dl-2 { animation: dl-draw .5s cubic-bezier(.4,0,.2,1) .08s forwards }
        .dl-3 { animation: dl-draw .35s cubic-bezier(.4,0,.2,1) .28s forwards }
        .dl-4 { animation: dl-draw .3s cubic-bezier(.4,0,.2,1) .40s forwards }
        .dl-5 { animation: dl-draw .3s cubic-bezier(.4,0,.2,1) .45s forwards }
        .dl-6 { animation: dl-draw .25s cubic-bezier(.4,0,.2,1) .55s forwards }
        .dl-dot-enter { animation: dl-pop .3s cubic-bezier(.4,0,.2,1) .72s both; }
        .dl-txt { animation: dl-fade .35s ease-out .62s both }
        ` : `
        .dl-dot-enter {}
        .dl-txt {}
        `}

        .bl {
          animation: book-left 3.5s cubic-bezier(.45,.05,.55,.95) ${animated ? "1s" : "0s"} infinite;
          transform-origin: 24px 24px;
        }
        .br {
          animation: book-right 3.5s cubic-bezier(.45,.05,.55,.95) ${animated ? "1s" : "0s"} infinite;
          transform-origin: 24px 24px;
        }
        .ba {
          animation: book-arch 3.5s cubic-bezier(.45,.05,.55,.95) ${animated ? "1s" : "0s"} infinite;
          transform-origin: 24px 10px;
        }
        .bd {
          animation: book-dot 3.5s cubic-bezier(.45,.05,.55,.95) ${animated ? "1s" : "0s"} infinite;
          transform-origin: 24px 39px;
        }
        .bll {
          animation: page-lines-l 3.5s cubic-bezier(.45,.05,.55,.95) ${animated ? "1s" : "0s"} infinite;
        }
        .blr {
          animation: page-lines-r 3.5s cubic-bezier(.45,.05,.55,.95) ${animated ? "1s" : "0s"} infinite;
        }

        .wm-en {
          font-family: var(--font-cormorant), 'Cormorant Garamond', Georgia, serif;
          font-size: 22px;
          font-weight: 700;
          letter-spacing: 3px;
        }
        .wm-ur {
          font-family: var(--font-nastaliq), 'Noto Nastaliq Urdu', serif;
          font-size: 12px;
          font-weight: 700;
          direction: rtl;
        }
      `}</style>

      {/* ── BOOK MARK (centered at x=24) ────────────── */}

      <g className="bl">
        <path
          d="M24 37 C20 35.8 12 35 5 36 Q3 36.3 3 34 L3 11 Q3 9 5 9.3 C12 8.5 20 9 24 11 Z"
          fill={inkFaint}
          stroke={ink}
          strokeWidth="1.5"
          strokeLinejoin="round"
          className={animated ? "dl dl-1" : ""}
          pathLength="1"
        />
      </g>

      <g className="br">
        <path
          d="M24 37 C28 35.8 36 35 43 36 Q45 36.3 45 34 L45 11 Q45 9 43 9.3 C36 8.5 28 9 24 11 Z"
          fill={inkFaint}
          stroke={ink}
          strokeWidth="1.5"
          strokeLinejoin="round"
          className={animated ? "dl dl-2" : ""}
          pathLength="1"
        />
      </g>

      <line
        x1="24" y1="11" x2="24" y2="37"
        stroke={ink} strokeWidth="1.6" strokeLinecap="round"
        className={animated ? "dl dl-3" : ""} pathLength="1"
      />

      <g className="bll">
        <line x1="8" y1="17" x2="20" y2="17.5" stroke={terra} strokeWidth="1.2" strokeLinecap="round" className={animated ? "dl dl-4" : ""} pathLength="1" />
        <line x1="8" y1="21.5" x2="19" y2="22" stroke={terra} strokeWidth="0.8" strokeLinecap="round" opacity="0.5" className={animated ? "dl dl-4" : ""} pathLength="1" />
        <line x1="8" y1="25.5" x2="17" y2="26" stroke={terra} strokeWidth="0.6" strokeLinecap="round" opacity="0.25" className={animated ? "dl dl-4" : ""} pathLength="1" />
      </g>

      <g className="blr">
        <line x1="28" y1="17.5" x2="40" y2="17" stroke={terra} strokeWidth="1.2" strokeLinecap="round" className={animated ? "dl dl-5" : ""} pathLength="1" />
        <line x1="29" y1="22" x2="40" y2="21.5" stroke={terra} strokeWidth="0.8" strokeLinecap="round" opacity="0.5" className={animated ? "dl dl-5" : ""} pathLength="1" />
        <line x1="31" y1="26" x2="40" y2="25.5" stroke={terra} strokeWidth="0.6" strokeLinecap="round" opacity="0.25" className={animated ? "dl dl-5" : ""} pathLength="1" />
      </g>

      <g className="ba">
        <path
          d="M18 11.5 Q24 7 30 11.5"
          stroke={ink} strokeWidth="1" strokeLinecap="round" fill="none" opacity="0.35"
          className={animated ? "dl dl-6" : ""} pathLength="1"
        />
      </g>

      <g className="bd">
        <circle cx="24" cy="39" r="1.8" fill={terra} className={animated ? "dl-dot-enter" : ""} />
      </g>

      {/* ── WORDMARK — vertically centered with book ── */}
      <g className={animated ? "dl-txt" : ""}>
        {/* Separator line — tight to the left of "Dars" */}
        <line
          x1="58" y1="14" x2="58" y2="36"
          stroke={ink} strokeWidth="0.7" strokeLinecap="round" opacity="0.15"
        />
        <text x="64" y="32" className="wm-en" fill={terra} opacity="0.10" dx="0.5" dy="0.5">DARS</text>
        <text x="64" y="32" className="wm-en" fill={ink}>DARS</text>
      </g>
    </svg>
  );
}
