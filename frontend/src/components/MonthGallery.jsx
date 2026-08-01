import { useEffect, useState } from "react";
import { apiUrl, fetchMonths } from "../api";

// Decorative Malayalam labels for the month names -- not sourced from the JSON (which
// only carries the English transliteration), just the standard well-known script
// forms, added purely for the traditional-calendar feel.
const MALAYALAM_MONTH_LABELS = {
  chingam: "ചിങ്ങം",
  kanni: "കന്നി",
  thulam: "തുലാം",
  vrischikam: "വൃശ്ചികം",
  dhanu: "ധനു",
  makaram: "മകരം",
  kumbham: "കുംഭം",
  meenam: "മീനം",
  medam: "മേടം",
  edavam: "എടവം",
  midhunam: "മിഥുനം",
  karkidakam: "കർക്കിടകം",
};

function Lightbox({ src, alt, onClose }) {
  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
    >
      <button
        onClick={onClose}
        className="absolute right-4 top-4 rounded-full bg-panchang-cream/90 px-3 py-1.5 text-sm font-semibold text-panchang-ink shadow"
      >
        Close ✕
      </button>
      <img
        src={src}
        alt={alt}
        onClick={(e) => e.stopPropagation()}
        className="themed-scroll max-h-full max-w-full cursor-zoom-in overflow-auto rounded-lg shadow-2xl"
      />
    </div>
  );
}

export default function MonthGallery() {
  const [months, setMonths] = useState([]);
  const [error, setError] = useState(null);
  const [lightbox, setLightbox] = useState(null);

  useEffect(() => {
    fetchMonths()
      .then(setMonths)
      .catch((err) => setError(err.message));
  }, []);

  if (error) {
    return (
      <p className="rounded-2xl border border-white/30 bg-white/80 p-4 text-panchang-maroon shadow">
        Couldn't load the month gallery: {error}
      </p>
    );
  }

  return (
    <div>
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {months.map((month) => {
          const key = (month.malayalam_month || "").toLowerCase();
          const malayalamLabel = MALAYALAM_MONTH_LABELS[key];
          const imageSrc = month.image ? apiUrl(`/images/${month.image}`) : null;

          return (
            <div
              key={month.malayalam_month}
              className="overflow-hidden rounded-2xl border border-white/40 bg-white/80 shadow-lg backdrop-blur-md transition hover:-translate-y-1 hover:shadow-2xl"
            >
              <button
                onClick={() => imageSrc && setLightbox({ src: imageSrc, alt: month.malayalam_month })}
                disabled={!imageSrc}
                className="block w-full"
              >
                {imageSrc ? (
                  <img
                    src={imageSrc}
                    alt={`${month.malayalam_month} panchang page`}
                    className="aspect-[3/4] w-full cursor-zoom-in object-cover object-top transition hover:opacity-90"
                  />
                ) : (
                  <div className="flex aspect-[3/4] w-full items-center justify-center bg-panchang-ink/5 text-sm text-panchang-ink/40">
                    Scan not available
                  </div>
                )}
              </button>

              <div className="space-y-1.5 p-4">
                <div className="flex items-baseline justify-between">
                  <h3 className="font-display text-2xl font-semibold text-panchang-ink">
                    {month.malayalam_month}
                  </h3>
                  {malayalamLabel && (
                    <span className="font-malayalam text-lg text-panchang-maroon">{malayalamLabel}</span>
                  )}
                </div>
                <p className="text-sm text-panchang-ink/70">{month.malayalam_month_span}</p>
                <p className="text-sm font-medium text-panchang-ink/80">{month.gregorian_range}</p>
                <p className="text-xs text-panchang-ink/50">
                  Saka {month.saka_varsham} &middot; {month.samvatsaram} samvatsaram
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {lightbox && (
        <Lightbox src={lightbox.src} alt={lightbox.alt} onClose={() => setLightbox(null)} />
      )}
    </div>
  );
}
