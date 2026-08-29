import React from 'react';

/**
 * TeleTipsLogo — Full Horizontal Brand Logo
 * Features:
 * - First 'T': Integrated cyan spark/star symbol
 * - Middle connection ('leT'): Data stream code indicators (//...)
 * - Second 'T': Upward directional cyan routing arrow
 * - Letter 'p': Hexagonal node symbol with circuit connection
 */
export const TeleTipsLogo = ({
  className = "h-8 w-auto",
  glow = true,
  textColor = "currentColor",
  accentColor = "#06B6D4",
  ...props
}) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 720 180"
      fill="none"
      className={`${className} ${glow ? 'filter drop-shadow-[0_0_8px_rgba(6,182,212,0.45)] hover:drop-shadow-[0_0_15px_rgba(6,182,212,0.7)] transition-all duration-300' : ''}`}
      {...props}
    >
      <defs>
        {/* Glow Filters */}
        <filter id="tt-glow-cyan" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="5" result="blur1" />
          <feMerge>
            <feMergeNode in="blur1" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>

        <linearGradient id="tt-cyanGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#22D3EE" />
          <stop offset="100%" stopColor="#06B6D4" />
        </linearGradient>

        <linearGradient id="tt-textGrad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#FFFFFF" />
          <stop offset="100%" stopColor="#F8FAFC" />
        </linearGradient>
      </defs>

      <g id="teletips-brand-typography">
        {/* Letter 1: 'T' with cyan 4-point star spark */}
        <g transform="translate(10, 20)">
          <rect x="0" y="20" width="80" height="20" rx="3" fill="url(#tt-textGrad)" />
          <rect x="30" y="40" width="20" height="80" rx="3" fill="url(#tt-textGrad)" />
          <g filter="url(#tt-glow-cyan)">
            <path d="M40 30 Q40 50 20 50 Q40 50 40 70 Q40 50 60 50 Q40 50 40 30 Z" fill="#00F0FF" />
          </g>
          <path d="M40 36 Q40 50 26 50 Q40 50 40 64 Q40 50 54 50 Q40 50 40 36 Z" fill="#FFFFFF" />
        </g>

        {/* Letter 2: 'e' with data stream / code indicators */}
        <g transform="translate(105, 20)">
          <path
            d="M45 42 C20 42 5 60 5 85 C5 110 20 128 50 128 C68 128 80 118 85 105 L66 100 C63 108 56 112 48 112 C34 112 25 102 24 88 L88 88 C88 86 88 82 88 78 C88 56 70 42 45 42 Z M25 74 C27 62 35 56 46 56 C57 56 65 62 67 74 L25 74 Z"
            fill="url(#tt-textGrad)"
          />
          {/* Data stream code lines (//...) */}
          <g filter="url(#tt-glow-cyan)">
            <rect x="35" y="80" width="18" height="3.5" rx="1.75" fill="#00F0FF" />
            <rect x="42" y="86" width="30" height="3.5" rx="1.75" fill="#00F0FF" />
            <circle cx="28" cy="81.5" r="2" fill="#00F0FF" />
            <circle cx="35" cy="87.5" r="2" fill="#00F0FF" />
            <line x1="18" y1="84" x2="24" y2="76" stroke="#00F0FF" strokeWidth="2.5" strokeLinecap="round" />
            <line x1="24" y1="84" x2="30" y2="76" stroke="#00F0FF" strokeWidth="2.5" strokeLinecap="round" />
          </g>
        </g>

        {/* Letter 3: 'l' */}
        <g transform="translate(205, 20)">
          <rect x="5" y="20" width="20" height="120" rx="3" fill="url(#tt-textGrad)" />
        </g>

        {/* Letter 4: 'e' */}
        <g transform="translate(240, 20)">
          <path
            d="M45 42 C20 42 5 60 5 85 C5 110 20 128 50 128 C68 128 80 118 85 105 L66 100 C63 108 56 112 48 112 C34 112 25 102 24 88 L88 88 C88 86 88 82 88 78 C88 56 70 42 45 42 Z M25 74 C27 62 35 56 46 56 C57 56 65 62 67 74 L25 74 Z"
            fill="url(#tt-textGrad)"
          />
        </g>

        {/* Letter 5: 'T' with Particle Dots & Upward Cyan Rocket Arrow */}
        <g transform="translate(340, 20)">
          <rect x="0" y="20" width="90" height="20" rx="3" fill="url(#tt-textGrad)" />
          {/* Particle dots */}
          <circle cx="60" cy="26" r="2" fill="#475569" />
          <circle cx="70" cy="24" r="2.5" fill="#475569" />
          <circle cx="80" cy="27" r="1.8" fill="#475569" />
          <circle cx="66" cy="12" r="2" fill="#00F0FF" filter="url(#tt-glow-cyan)" />
          <circle cx="80" cy="8" r="2.5" fill="#00F0FF" filter="url(#tt-glow-cyan)" />
          <circle cx="92" cy="18" r="2" fill="#00F0FF" filter="url(#tt-glow-cyan)" />

          {/* Stem of T */}
          <path d="M35 40 L35 140 L55 140 L55 40 Z" fill="url(#tt-textGrad)" />

          {/* Glowing Upward Routing Arrow */}
          <g filter="url(#tt-glow-cyan)">
            <polygon points="45,50 18,88 36,88 36,138 54,138 54,88 72,88" fill="url(#tt-cyanGrad)" />
          </g>
          <polygon points="45,54 23,86 38,86 38,136 52,136 52,86 67,86" fill="#E0F2FE" />
        </g>

        {/* Letter 6: 'i' with Cyan Hexagon */}
        <g transform="translate(445, 20)">
          <rect x="10" y="55" width="20" height="85" rx="3" fill="url(#tt-textGrad)" />
          {/* Cyan Hexagon Dot */}
          <g filter="url(#tt-glow-cyan)">
            <polygon points="20,16 32,23 32,37 20,44 8,37 8,23" fill="#00F0FF" />
          </g>
          <polygon points="20,19 29,24 29,36 20,41 11,36 11,24" fill="#FFFFFF" />
        </g>

        {/* Letter 7: 'p' with Circuit Node Connection */}
        <g transform="translate(490, 20)">
          <path
            d="M10 55 L30 55 L30 68 C36 58 48 52 62 52 C84 52 98 70 98 94 C98 118 84 136 62 136 C48 136 36 130 30 120 L30 170 L10 170 Z M30 94 C30 110 39 120 54 120 C68 120 78 110 78 94 C78 78 68 68 54 68 C39 68 30 78 30 94 Z"
            fill="url(#tt-textGrad)"
          />
          {/* Circuit branch and Hexagon node */}
          <g filter="url(#tt-glow-cyan)">
            <line x1="-15" y1="94" x2="10" y2="94" stroke="#00F0FF" strokeWidth="3" strokeLinecap="round" />
            <polygon points="54,80 66,87 66,101 54,108 42,101 42,87" fill="#00F0FF" />
            <polygon points="54,83 63,88 63,100 54,105 45,100 45,88" fill="#0F172A" />
          </g>
        </g>

        {/* Letter 8: 's' */}
        <g transform="translate(600, 20)">
          <path
            d="M50 42 C72 42 85 55 85 72 L65 72 C65 63 58 58 49 58 C38 58 31 63 31 70 C31 77 38 81 53 85 C75 90 87 97 87 112 C87 128 73 138 48 138 C25 138 10 126 10 108 L30 108 C30 118 38 123 50 123 C62 123 68 118 68 111 C68 103 60 99 45 95 C25 90 12 83 12 68 C12 51 27 42 50 42 Z"
            fill="url(#tt-textGrad)"
          />
        </g>
      </g>
    </svg>
  );
};

export default TeleTipsLogo;
