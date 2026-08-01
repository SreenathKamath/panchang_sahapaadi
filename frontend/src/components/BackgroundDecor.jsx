// Purely decorative, fixed behind all page content (pointer-events-none so it never
// intercepts clicks/taps). A few soft blurred color orbs plus faint floating Hindu
// motifs (Om, a diya/lamp, a lotus) give the warm gradient backdrop some depth and
// life without competing with the actual content sitting on top in glass cards.

function DiyaIcon({ className }) {
  return (
    <svg viewBox="0 0 64 64" className={className} fill="currentColor" aria-hidden="true">
      <path d="M32 6c6 9 8 14.5 8 19a8 8 0 1 1-16 0c0-4.5 2-10 8-19Z" opacity="0.95" />
      <path d="M8 40c0 3.5 3.5 7 9.5 9.5C22.5 51.5 27 52.5 32 52.5s9.5-1 14.5-3C52.5 47 56 43.5 56 40H8Z" opacity="0.85" />
      <ellipse cx="32" cy="40" rx="24" ry="5" opacity="0.6" />
    </svg>
  );
}

function LotusIcon({ className }) {
  return (
    <svg viewBox="0 0 100 100" className={className} fill="currentColor" aria-hidden="true">
      {Array.from({ length: 8 }).map((_, i) => (
        <ellipse
          key={i}
          cx="50"
          cy="32"
          rx="11"
          ry="26"
          opacity="0.8"
          transform={`rotate(${i * 45} 50 50)`}
        />
      ))}
      <circle cx="50" cy="50" r="7" opacity="0.95" />
    </svg>
  );
}

function OmSymbol({ className }) {
  return (
    <span className={`font-devanagari select-none leading-none ${className}`} aria-hidden="true">
      ॐ
    </span>
  );
}

function Orb({ className, style }) {
  return <div className={`absolute rounded-full blur-3xl ${className}`} style={style} />;
}

export default function BackgroundDecor() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <Orb
        className="animate-float-slow -left-24 -top-24 h-96 w-96 bg-panchang-orange/40"
      />
      <Orb
        className="animate-float-slower right-[-10%] top-1/4 h-[28rem] w-[28rem] bg-panchang-gold/25"
      />
      <Orb
        className="animate-float-slow bottom-[-15%] left-1/4 h-96 w-96 bg-panchang-maroon-light/30"
      />

      <OmSymbol className="animate-float-slower absolute right-[6%] top-[8%] text-[9rem] text-panchang-gold-light/15 sm:text-[12rem]" />
      <LotusIcon className="animate-float-slow absolute bottom-[8%] left-[4%] h-32 w-32 text-panchang-orange-light/15 sm:h-44 sm:w-44" />
      <DiyaIcon className="animate-float-slower absolute left-[8%] top-[15%] h-20 w-20 text-panchang-gold-light/15 sm:h-28 sm:w-28" />
    </div>
  );
}

export { DiyaIcon, LotusIcon, OmSymbol };
