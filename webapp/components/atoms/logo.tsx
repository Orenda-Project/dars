"use client";

import { useState } from "react";

interface LogoProps {
  variant?: "light" | "dark";
  size?: "sm" | "md" | "lg";
}

export function Logo({ variant = "dark", size = "md" }: LogoProps) {
  const [hovered, setHovered] = useState(false);

  const ink = variant === "light" ? "#faf7f2" : "#1c1410";
  const terra = "#bf4e30";
  const inkFaint =
    variant === "light" ? "rgba(250,247,242,0.07)" : "rgba(28,20,16,0.04)";
  const bgPill =
    variant === "light" ? "rgba(250,247,242,0.08)" : "rgba(28,20,16,0.06)";

  const bookW = 60;
  const bookH = 52;
  const totalW = size === "sm" ? 110 : size === "lg" ? 205 : 158;
  const scale = size === "sm" ? 0.65 : size === "lg" ? 1.35 : 1;

  const px = Math.round(totalW * scale);
  const ph = Math.round(bookH * scale);
  const textSlide = totalW - bookW;

  return (
    <div
      style={{ width: px, height: ph, position: "relative", cursor: "pointer", overflow: "visible" }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      aria-label="Dars"
      role="img"
    >
      {/* ── LAYER 0: background pill ── */}
      <svg
        width={px} height={ph}
        viewBox={`0 0 ${totalW} ${bookH}`}
        fill="none"
        style={{ position: "absolute", inset: 0, zIndex: 0 }}
      >
        <rect
          x="1" y="4" width={totalW - 2} height={bookH - 8} rx="6"
          fill={bgPill}
          style={{ transition: "opacity 0.35s ease", opacity: hovered ? 1 : 0 }}
        />
      </svg>

      {/* ── LAYER 1: text (behind book) ── */}
      <svg
        width={px} height={ph}
        viewBox={`0 0 ${totalW} ${bookH}`}
        fill="none"
        style={{ position: "absolute", inset: 0, zIndex: 1 }}
      >
        <defs>
          <clipPath id="dars-text-clip">
            <rect x={bookW + 2} y="0" width={totalW} height={bookH} />
          </clipPath>
        </defs>
        <g clipPath="url(#dars-text-clip)">
          <g
            style={{
              transition: hovered
                ? "transform 0.45s cubic-bezier(.34,1.2,.64,1)"
                : "transform 0.45s cubic-bezier(.34,1.2,.64,1), opacity 0s 0.45s",
              transform: hovered ? "translateX(0px)" : `translateX(-${textSlide}px)`,
              opacity: hovered ? 1 : 0,
            }}
          >
            <line
              x1={bookW + 4} y1="13" x2={bookW + 4} y2="41"
              stroke={ink} strokeWidth="0.7" strokeLinecap="round" opacity="0.15"
            />
            <text
              x={bookW + 10} y="34"
              fontFamily="var(--font-cormorant), 'Cormorant Garamond', Georgia, serif"
              fontSize="22" fontWeight="700" letterSpacing="3"
              fill={terra} opacity="0.10" dx="0.5" dy="0.5"
            >DARS</text>
            <text
              x={bookW + 10} y="34"
              fontFamily="var(--font-cormorant), 'Cormorant Garamond', Georgia, serif"
              fontSize="22" fontWeight="700" letterSpacing="3"
              fill={ink}
            >DARS</text>
          </g>
        </g>
      </svg>

      {/* ── LAYER 2: book (on top) ── */}
      <svg
        width={px} height={ph}
        viewBox={`0 0 ${totalW} ${bookH}`}
        fill="none"
        style={{ position: "absolute", inset: 0, zIndex: 2 }}
      >
        <style>{`
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
          .bl  { animation: book-left    3.5s cubic-bezier(.45,.05,.55,.95) 0s infinite; transform-origin: 30px 26px; }
          .br  { animation: book-right   3.5s cubic-bezier(.45,.05,.55,.95) 0s infinite; transform-origin: 30px 26px; }
          .ba  { animation: book-arch    3.5s cubic-bezier(.45,.05,.55,.95) 0s infinite; transform-origin: 30px 10px; }
          .bd  { animation: book-dot     3.5s cubic-bezier(.45,.05,.55,.95) 0s infinite; transform-origin: 30px 45px; }
          .bll { animation: page-lines-l 3.5s cubic-bezier(.45,.05,.55,.95) 0s infinite; }
          .blr { animation: page-lines-r 3.5s cubic-bezier(.45,.05,.55,.95) 0s infinite; }
          .book-group { transition: transform 0.45s cubic-bezier(.34,1.2,.64,1); }
        `}</style>

        <g
          className="book-group"
          style={{
            transform: hovered
              ? "translateX(0px)"
              : `translateX(${(totalW - bookW) / 2}px)`,
          }}
        >
          <g className="bl">
            <path
              d="M30 43 C25 41.5 16 40.5 7 41.5 Q5 41.8 5 39.5 L5 12 Q5 10 7 10.3 C16 9.3 25 10 30 12.5 Z"
              fill={inkFaint} stroke={ink} strokeWidth="1.6" strokeLinejoin="round"
            />
          </g>

          <g className="br">
            <path
              d="M30 43 C35 41.5 44 40.5 53 41.5 Q55 41.8 55 39.5 L55 12 Q55 10 53 10.3 C44 9.3 35 10 30 12.5 Z"
              fill={inkFaint} stroke={ink} strokeWidth="1.6" strokeLinejoin="round"
            />
          </g>

          <line x1="30" y1="12.5" x2="30" y2="43" stroke={ink} strokeWidth="1.8" strokeLinecap="round" />

          <g className="bll">
            <line x1="11" y1="19" x2="26" y2="19.8" stroke={terra} strokeWidth="1.3" strokeLinecap="round" />
            <line x1="11" y1="25" x2="25" y2="25.7" stroke={terra} strokeWidth="0.9" strokeLinecap="round" opacity="0.5" />
            <line x1="11" y1="30.5" x2="23" y2="31.1" stroke={terra} strokeWidth="0.7" strokeLinecap="round" opacity="0.25" />
          </g>

          <g className="blr">
            <line x1="34" y1="19.8" x2="49" y2="19" stroke={terra} strokeWidth="1.3" strokeLinecap="round" />
            <line x1="35" y1="25.7" x2="49" y2="25" stroke={terra} strokeWidth="0.9" strokeLinecap="round" opacity="0.5" />
            <line x1="37" y1="31.1" x2="49" y2="30.5" stroke={terra} strokeWidth="0.7" strokeLinecap="round" opacity="0.25" />
          </g>

          <g className="ba">
            <path d="M23 13 Q30 8 37 13" stroke={ink} strokeWidth="1.1" strokeLinecap="round" fill="none" opacity="0.35" />
          </g>

          <g className="bd">
            <circle cx="30" cy="46" r="2.2" fill={terra} />
          </g>
        </g>
      </svg>
    </div>
  );
}
