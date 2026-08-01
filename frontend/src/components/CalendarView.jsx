import { useEffect, useState } from "react";
import { fetchMonthDays, fetchMonths } from "../api";

// Sunday-first column order, matching the Malayalam weekday names in the data.
const WEEKDAY_ORDER = [
  "ravivaram",
  "chandravaram",
  "kujavaram",
  "budhavaram",
  "guruvaram",
  "sukravaram",
  "mandavaram",
];
const WEEKDAY_SHORT = ["Ravi", "Chandra", "Kuja", "Budha", "Guru", "Sukra", "Manda"];

function DayDetail({ day, onClose }) {
  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-2xl border border-white/50 bg-panchang-cream/95 p-6 shadow-2xl backdrop-blur-xl"
      >
        <div className="mb-3 flex items-start justify-between">
          <div>
            <h3 className="font-display text-3xl font-semibold text-panchang-ink">
              {day.malayalam_date}
            </h3>
            <p className="text-sm text-panchang-ink/70">
              {day.weekday} &middot; {day.gregorian_date}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-full bg-panchang-ink/10 px-2.5 py-1 text-sm text-panchang-ink"
          >
            ✕
          </button>
        </div>

        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <dt className="text-panchang-ink/50">Tithi</dt>
          <dd className="font-medium text-panchang-ink">{day.tithi ?? "Not recorded"}</dd>
          <dt className="text-panchang-ink/50">Nakshatra</dt>
          <dd className="font-medium text-panchang-ink">{day.nakshatra ?? "Not recorded"}</dd>
          <dt className="text-panchang-ink/50">Rahukalam</dt>
          <dd className="font-medium text-panchang-ink">{day.rahukalam}</dd>
          <dt className="text-panchang-ink/50">Gulikakalam</dt>
          <dd className="font-medium text-panchang-ink">{day.gulikakalam}</dd>
        </dl>

        {day.special_notes.length > 0 && (
          <div className="mt-4 rounded-xl border border-panchang-orange/30 bg-panchang-orange/10 p-3">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-panchang-orange-dark">
              Special notes
            </p>
            <ul className="list-inside list-disc space-y-1 text-sm text-panchang-ink">
              {day.special_notes.map((note, i) => (
                <li key={i}>{note}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

export default function CalendarView() {
  const [months, setMonths] = useState([]);
  const [activeMonth, setActiveMonth] = useState(null);
  const [days, setDays] = useState([]);
  const [selectedDay, setSelectedDay] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchMonths()
      .then((m) => {
        setMonths(m);
        if (m.length > 0) setActiveMonth(m[0].malayalam_month);
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!activeMonth) return;
    fetchMonthDays(activeMonth)
      .then(setDays)
      .catch((err) => setError(err.message));
  }, [activeMonth]);

  if (error) {
    return (
      <p className="rounded-2xl border border-white/30 bg-white/80 p-4 text-panchang-maroon shadow">
        Couldn't load the calendar: {error}
      </p>
    );
  }

  const leadingBlanks = days.length
    ? WEEKDAY_ORDER.indexOf((days[0].weekday || "").toLowerCase())
    : 0;

  return (
    <div>
      <div className="mb-6 flex flex-wrap gap-2">
        {months.map((m) => (
          <button
            key={m.malayalam_month}
            onClick={() => setActiveMonth(m.malayalam_month)}
            className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
              activeMonth === m.malayalam_month
                ? "bg-gradient-to-r from-panchang-orange to-panchang-orange-dark text-white shadow-[0_4px_14px_rgba(242,102,13,0.5)]"
                : "border border-white/40 bg-white/70 text-panchang-ink backdrop-blur-md hover:border-panchang-orange"
            }`}
          >
            {m.malayalam_month}
          </button>
        ))}
      </div>

      <div className="overflow-hidden rounded-2xl border border-white/40 bg-white/80 shadow-lg backdrop-blur-md">
        <div className="grid grid-cols-7 border-b border-panchang-gold/30 bg-gradient-to-r from-panchang-orange-dark via-panchang-maroon to-panchang-orange-dark">
          {WEEKDAY_SHORT.map((label, i) => (
            <div
              key={label}
              className={`p-2 text-center text-xs font-semibold uppercase tracking-wide sm:text-sm ${
                i === 0 ? "text-panchang-gold-light" : "text-white/90"
              }`}
            >
              {label}
            </div>
          ))}
        </div>

        <div className="grid grid-cols-7">
          {Array.from({ length: leadingBlanks }).map((_, i) => (
            <div key={`blank-${i}`} className="aspect-square border-b border-r border-panchang-gold/10" />
          ))}

          {days.map((day) => {
            const isSunday = (day.weekday || "").toLowerCase() === "ravivaram";
            const hasNotes = day.special_notes.length > 0;
            return (
              <button
                key={day.gregorian_date}
                onClick={() => setSelectedDay(day)}
                className={`group relative flex aspect-square flex-col items-center justify-center gap-0.5 border-b border-r border-panchang-gold/10 p-1 transition hover:bg-panchang-orange/10 sm:p-2 ${
                  day.highlighted ? "bg-panchang-maroon/10" : ""
                }`}
              >
                <span
                  className={`text-lg font-semibold sm:text-xl ${
                    isSunday || day.highlighted ? "text-panchang-maroon" : "text-panchang-ink"
                  }`}
                >
                  {day.malayalam_date}
                </span>
                <span className="text-[10px] text-panchang-ink/40 sm:text-xs">
                  {day.gregorian_date.slice(8)}
                </span>
                {hasNotes && (
                  <span className="absolute bottom-1 h-1.5 w-1.5 rounded-full bg-panchang-orange sm:bottom-1.5" />
                )}
              </button>
            );
          })}
        </div>
      </div>

      <p className="mt-3 text-xs text-panchang-cream/70">
        <span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-panchang-orange align-middle" />
        marks a day with a festival or special note &middot; tap any day for full details
      </p>

      {selectedDay && <DayDetail day={selectedDay} onClose={() => setSelectedDay(null)} />}
    </div>
  );
}
