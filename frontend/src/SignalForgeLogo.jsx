import React from 'react'

/**
 * SignalForge Brand Logo Symbol
 *
 * Vector implementation matching the reference fintech trading identity:
 * - Circular blue/cyan gradient ring
 * - Deep navy/near-black inner background
 * - Green (bullish) and red (bearish) candlestick bars
 * - Strong straight blue/cyan upward arrow from lower-left to upper-right
 * - Optimized for crisp display at 24px–44px
 */
export function SignalForgeLogo({ size = 36, className = '', ...props }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 44 44"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`signalforge-logo ${className}`.trim()}
      aria-hidden="true"
      {...props}
    >
      <defs>
        {/* Outer Circular Ring Gradient */}
        <linearGradient
          id="sfLogoRingGrad"
          x1="0%"
          y1="100%"
          x2="100%"
          y2="0%"
        >
          <stop offset="0%" stopColor="#0284c7" />
          <stop offset="45%" stopColor="#168cff" />
          <stop offset="100%" stopColor="#00e5ff" />
        </linearGradient>

        {/* Inner Background Gradient */}
        <linearGradient
          id="sfLogoBgGrad"
          x1="0%"
          y1="0%"
          x2="100%"
          y2="100%"
        >
          <stop offset="0%" stopColor="#0a1628" />
          <stop offset="100%" stopColor="#020813" />
        </linearGradient>

        {/* Strong Straight Upward Arrow Gradient */}
        <linearGradient
          id="sfLogoArrowGrad"
          x1="0%"
          y1="100%"
          x2="100%"
          y2="0%"
        >
          <stop offset="0%" stopColor="#0284c7" />
          <stop offset="55%" stopColor="#168cff" />
          <stop offset="100%" stopColor="#00f0ff" />
        </linearGradient>
      </defs>

      {/* Dark Circular Background + Blue/Cyan Gradient Ring */}
      <circle
        cx="22"
        cy="22"
        r="19.5"
        fill="url(#sfLogoBgGrad)"
        stroke="url(#sfLogoRingGrad)"
        strokeWidth="2.2"
      />

      {/* Subtle Grid Baseline */}
      <line
        x1="8"
        y1="22"
        x2="36"
        y2="22"
        stroke="#38bdf8"
        strokeWidth="0.8"
        strokeDasharray="2 2"
        strokeOpacity="0.22"
      />

      {/* Candlestick #1: Green Bullish (Left) */}
      <line
        x1="12"
        y1="22"
        x2="12"
        y2="33"
        stroke="#00d9a3"
        strokeWidth="1"
        strokeLinecap="round"
      />
      <rect
        x="10.5"
        y="24.5"
        width="3"
        height="6"
        rx="0.6"
        fill="#00d9a3"
      />

      {/* Candlestick #2: Red Bearish (Mid-Left Pullback) */}
      <line
        x1="18"
        y1="19"
        x2="18"
        y2="31"
        stroke="#f43f5e"
        strokeWidth="1"
        strokeLinecap="round"
      />
      <rect
        x="16.5"
        y="22"
        width="3"
        height="6.5"
        rx="0.6"
        fill="#f43f5e"
      />

      {/* Candlestick #3: Green Bullish (Mid-Right Rally) */}
      <line
        x1="24"
        y1="14"
        x2="24"
        y2="27"
        stroke="#00d9a3"
        strokeWidth="1"
        strokeLinecap="round"
      />
      <rect
        x="22.5"
        y="16.5"
        width="3"
        height="7.5"
        rx="0.6"
        fill="#00d9a3"
      />

      {/* Candlestick #4: Green Bullish (Right Continuation High) */}
      <line
        x1="30"
        y1="9.5"
        x2="30"
        y2="22"
        stroke="#00d9a3"
        strokeWidth="1"
        strokeLinecap="round"
      />
      <rect
        x="28.5"
        y="12"
        width="3"
        height="7"
        rx="0.6"
        fill="#00d9a3"
      />

      {/* Strong Straight Blue/Cyan Upward Arrow */}
      {/* 1. Dark outline/separation for visual punch across candlesticks */}
      <line
        x1="9"
        y1="35"
        x2="30.5"
        y2="13.5"
        stroke="#020813"
        strokeWidth="4.6"
        strokeLinecap="round"
        opacity="0.65"
      />
      {/* 2. Arrow Shaft */}
      <line
        x1="9"
        y1="35"
        x2="30.5"
        y2="13.5"
        stroke="url(#sfLogoArrowGrad)"
        strokeWidth="2.8"
        strokeLinecap="round"
      />
      {/* 3. Sharp Arrowhead */}
      <path
        d="M 35.5 8.5 L 27.5 9.5 L 30 14 L 34.5 16.5 Z"
        stroke="#020813"
        strokeWidth="1.2"
        strokeLinejoin="round"
        fill="url(#sfLogoArrowGrad)"
      />
    </svg>
  )
}

export default SignalForgeLogo
