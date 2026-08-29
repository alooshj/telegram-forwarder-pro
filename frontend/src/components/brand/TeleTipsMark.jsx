import React from 'react';

/**
 * TeleTipsMark — Collapsed Brand Mark / Favicon Symbol
 * Styled second 'T' with upward cyan rocket routing arrow and hexagon automation node.
 */
export const TeleTipsMark = ({
  className = "w-8 h-8",
  glow = true,
  ...props
}) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 140 140"
      fill="none"
      className={`${className} ${glow ? 'filter drop-shadow-[0_0_8px_rgba(6,182,212,0.5)]' : ''}`}
      {...props}
    >
      <defs>
        <filter id="mark-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <linearGradient id="mark-cyan" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#22D3EE" />
          <stop offset="100%" stopColor="#06B6D4" />
        </linearGradient>
      </defs>

      {/* Dark Cyber Rounded Tile Background */}
      <rect x="5" y="5" width="130" height="130" rx="28" fill="#0F172A" stroke="rgba(6, 182, 212, 0.3)" strokeWidth="2" />

      <g transform="translate(20, 10)">
        {/* Top bar of 'T' */}
        <rect x="5" y="20" width="90" height="18" rx="4" fill="#FFFFFF" />

        {/* Dynamic Glow Particles on Top Bar */}
        <circle cx="70" cy="14" r="2.5" fill="#00F0FF" filter="url(#mark-glow)" />
        <circle cx="82" cy="10" r="3" fill="#00F0FF" filter="url(#mark-glow)" />

        {/* Stem of 'T' with Upward Directional Arrow */}
        <path d="M38 38 L38 115 L62 115 L62 38 Z" fill="#FFFFFF" />

        {/* Upward Cyan Routing Arrow */}
        <g filter="url(#mark-glow)">
          <polygon points="50,38 24,72 40,72 40,112 60,112 60,72 76,72" fill="url(#mark-cyan)" />
        </g>
        <polygon points="50,42 28,70 42,70 42,110 58,110 58,70 72,70" fill="#E0F2FE" />
      </g>
    </svg>
  );
};

export default TeleTipsMark;
