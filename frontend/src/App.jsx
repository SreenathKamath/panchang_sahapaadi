import { useState } from "react";
import ChatBot from "./components/ChatBot";
import MonthGallery from "./components/MonthGallery";
import CalendarView from "./components/CalendarView";
import BackgroundDecor, { DiyaIcon } from "./components/BackgroundDecor";

const TABS = [
  { id: "chat", label: "Ask Panchang" },
  { id: "gallery", label: "Monthly Pages" },
  { id: "calendar", label: "Calendar & Festivals" },
];

function App() {
  const [tab, setTab] = useState("chat");

  return (
    <div className="min-h-screen">
      <BackgroundDecor />

      <header className="px-4 py-10 text-center sm:py-14">
        <DiyaIcon className="mx-auto mb-2 h-10 w-10 text-panchang-gold-light drop-shadow-[0_0_12px_rgba(217,164,65,0.6)]" />
        <p className="font-malayalam text-lg text-panchang-gold-light/90 sm:text-xl">
          സാരസ്വത പഞ്ചാംഗം
        </p>
        <h1 className="font-display text-5xl font-bold text-panchang-cream drop-shadow-[0_2px_16px_rgba(0,0,0,0.35)] sm:text-6xl">
          Saraswat Panchang
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-sm text-panchang-cream/80 sm:text-base">
          Your community calendar, made easy to search -- ask a question, browse the
          monthly pages, or look up a festival.
        </p>
      </header>

      <nav className="sticky top-3 z-20 mx-auto mb-2 flex w-fit max-w-[95vw] flex-wrap justify-center gap-1.5 rounded-full border border-white/25 bg-white/15 p-1.5 shadow-lg backdrop-blur-xl">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`rounded-full px-4 py-2 text-sm font-semibold transition sm:text-base ${
              tab === t.id
                ? "bg-gradient-to-r from-panchang-orange to-panchang-orange-dark text-white shadow-[0_4px_16px_rgba(242,102,13,0.5)]"
                : "text-panchang-cream/80 hover:bg-white/10"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        {tab === "chat" && <ChatBot />}
        {tab === "gallery" && <MonthGallery />}
        {tab === "calendar" && <CalendarView />}
      </main>

      <footer className="px-4 py-8 text-center text-xs text-panchang-cream/50">
        Data extracted from the printed Saraswat Panchang, Saka 1948 &middot; 1202 Chingam
        &ndash; Karkidakam
      </footer>
    </div>
  );
}

export default App;
