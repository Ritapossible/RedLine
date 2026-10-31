// Inline icons; stroke follows the text colour.
const S = { width: 20, height: 20, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };

export const ArrowRight = () => (
  <svg {...S} width={18} height={18}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);
export const Pin = () => (
  <svg {...S}>
    <path d="M12 17v5M5 17h14l-2-4V5a2 2 0 0 0-2-2H9a2 2 0 0 0-2 2v8l-2 4Z" />
  </svg>
);
export const Lock = () => (
  <svg {...S}>
    <rect x="4" y="10" width="16" height="11" rx="2.5" />
    <path d="M8 10V7a4 4 0 0 1 8 0v3" />
  </svg>
);
export const Eye = () => (
  <svg {...S}>
    <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);
export const Scale = () => (
  <svg {...S}>
    <path d="M12 3v18M5 21h14M6 7h12M6 7l-3 7a3 3 0 0 0 6 0L6 7Zm12 0-3 7a3 3 0 0 0 6 0l-3-7Z" />
  </svg>
);
export const Return = () => (
  <svg {...S}>
    <path d="M9 14 4 9l5-5" />
    <path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11" />
  </svg>
);
export const Shield = () => (
  <svg {...S}>
    <path d="M12 3 4 6v6c0 5 3.4 8.4 8 9 4.6-.6 8-4 8-9V6l-8-3Z" />
    <path d="m9 12 2 2 4-4" />
  </svg>
);
export const Chain = () => (
  <svg {...S}>
    <path d="M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1" />
    <path d="M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1" />
  </svg>
);
export const Code = () => (
  <svg {...S}>
    <path d="m8 7-5 5 5 5M16 7l5 5-5 5" />
  </svg>
);
export const Spark = () => (
  <svg {...S}>
    <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6" />
  </svg>
);
export const Menu = () => (
  <svg {...S} width={22} height={22}>
    <path d="M4 7h16M4 12h16M4 17h16" />
  </svg>
);
export const Close = () => (
  <svg {...S} width={22} height={22}>
    <path d="M6 6l12 12M18 6 6 18" />
  </svg>
);
export const Check = () => (
  <svg {...S} width={16} height={16}>
    <path d="m5 12 5 5 9-10" />
  </svg>
);
export const ArrowUpRight = () => (
  <svg {...S} width={16} height={16}>
    <path d="M7 17 17 7M8 7h9v9" />
  </svg>
);
