// The RedLine mark: three lines of a terms page, the middle one pinned and
// watched (the red line ending in a node). Same drawing as the favicon.
export function Mark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" className="mark">
      <rect width="64" height="64" rx="15" fill="#0b0b0d" />
      <rect x=".5" y=".5" width="63" height="63" rx="14.5" fill="none" stroke="#fff" strokeOpacity=".14" />
      <g strokeLinecap="round" strokeWidth="6" fill="none">
        <path d="M16 20h26" stroke="#f4f4f5" />
        <path d="M16 32h34" stroke="#d92d32" />
        <path d="M16 44h16" stroke="#f4f4f5" strokeOpacity=".45" />
      </g>
      <circle cx="50" cy="32" r="5.5" fill="#d92d32" />
      <circle cx="50" cy="32" r="2.2" fill="#0b0b0d" />
    </svg>
  );
}

export function Logo() {
  return (
    <span className="logo">
      <Mark size={28} />
      RedLine
    </span>
  );
}
