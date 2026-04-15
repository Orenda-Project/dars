"use client";

/**
 * BookLoader — Lottie book pagination animation in Dars brand colors.
 *
 * Usage:
 *   <BookLoader />
 *   <BookLoader size={96} />
 *   <BookLoader label="Loading lesson plans…" />
 */

import Lottie from "lottie-react";
import animationData from "@/public/book-loader.json";

interface BookLoaderProps {
  size?: number;
  label?: string;
  className?: string;
}

export function BookLoader({ size = 90, label = "Loading", className = "" }: BookLoaderProps) {
  return (
    <span
      role="status"
      aria-label={label}
      className={`inline-flex items-center justify-center ${className}`}
      style={{ width: size, height: size }}
    >
      <Lottie
        animationData={animationData}
        loop
        autoplay
        style={{ width: size, height: size }}
        aria-hidden="true"
      />
    </span>
  );
}
