import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { sendChatQuery } from "../api";
import { DiyaIcon } from "./BackgroundDecor";

const STARTER_QUESTIONS = [
  "What's today's panchang?",
  "When is the next Ekadashi?",
  "What is malayalam date 5 of Chingam?",
  "Who is the contact for Kottayam?",
];

// The LLM consistently formats replies with markdown (bold labels, bullet lists,
// headings -- seen in every test reply) -- rendering that as literal text left visible
// "**asterisks**" in the UI, so bot messages go through ReactMarkdown while user
// messages (their own raw typed text) stay plain.
const MARKDOWN_COMPONENTS = {
  p: ({ children }) => <p className="mb-1.5 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="mb-1.5 list-inside list-disc space-y-0.5 last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="mb-1.5 list-inside list-decimal space-y-0.5 last:mb-0">{children}</ol>,
  // remark wraps list-item text in a block-level <p> (GFM "loose list" rule), which
  // breaks list-inside -- the bullet marker ends up alone on its own line above the
  // paragraph instead of next to the text. Forcing that inner <p> inline fixes it.
  li: ({ children }) => <li className="[&>p]:m-0 [&>p]:inline">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-panchang-orange-dark">{children}</strong>,
  h1: ({ children }) => <p className="mb-1 font-display text-base font-semibold">{children}</p>,
  h2: ({ children }) => <p className="mb-1 font-display text-base font-semibold">{children}</p>,
  h3: ({ children }) => <p className="mb-1 font-semibold">{children}</p>,
};

function Bubble({ role, children }) {
  const isUser = role === "user";
  return (
    <div className={`flex animate-fade-up ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-md ${
          isUser
            ? "whitespace-pre-wrap rounded-br-sm bg-gradient-to-br from-panchang-orange to-panchang-orange-dark text-white"
            : "rounded-bl-sm border border-white/60 bg-white/90 text-panchang-ink backdrop-blur-sm"
        }`}
      >
        {isUser || typeof children !== "string" ? (
          children
        ) : (
          <ReactMarkdown components={MARKDOWN_COMPONENTS}>{children}</ReactMarkdown>
        )}
      </div>
    </div>
  );
}

export default function ChatBot() {
  const [messages, setMessages] = useState([
    {
      role: "bot",
      content:
        "Namaskaram! Ask me anything about this year's panchang -- a date, a festival, today's tithi, or a committee contact.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [slowHint, setSlowHint] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  // The free-tier LLM (openai/gpt-oss-20b:free) can take 30-45+ seconds to reply --
  // observed directly during testing, not a worst case. A bare bouncing-dots
  // indicator that long reads as "broken", so a reassuring hint kicks in after a few
  // seconds rather than immediately (most direct-lookup answers come back in under a
  // second and shouldn't show it at all).
  useEffect(() => {
    if (!loading) {
      setSlowHint(false);
      return;
    }
    const timer = setTimeout(() => setSlowHint(true), 4000);
    return () => clearTimeout(timer);
  }, [loading]);

  async function ask(query) {
    const trimmed = query.trim();
    if (!trimmed || loading) return;

    setMessages((m) => [...m, { role: "user", content: trimmed }]);
    setInput("");
    setLoading(true);

    try {
      const result = await sendChatQuery(trimmed);
      setMessages((m) => [...m, { role: "bot", ...renderResult(result, trimmed) }]);
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: "bot", content: `Something went wrong reaching the panchang service: ${err.message}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function renderResult(result, originalQuery) {
    if (result.status === "ambiguous") {
      return {
        content: "That date/weekday falls in more than one loaded month -- which one did you mean?",
        quickReplies: result.ambiguous_months.map((month) => ({
          label: month,
          query: `${originalQuery} in ${month}`,
        })),
      };
    }
    if (result.status === "date_not_covered") {
      return {
        content: `${result.resolved_date} isn't covered by the currently loaded panchang data (${result.loaded_range}, covering ${result.loaded_months}).`,
      };
    }
    if (result.status === "not_found") {
      return {
        content:
          "I couldn't find anything in this panchang confidently matching that -- could you rephrase, or mention a specific date?",
      };
    }
    return {
      content: result.reply,
      caption:
        result.match_source && result.match_source !== "direct lookup"
          ? `matched via ${result.match_source}`
          : null,
    };
  }

  function handleSubmit(e) {
    e.preventDefault();
    ask(input);
  }

  return (
    <div className="flex h-[72vh] max-h-[760px] min-h-[460px] flex-col overflow-hidden rounded-3xl border border-white/30 bg-white/15 shadow-[0_8px_40px_rgba(0,0,0,0.35)] backdrop-blur-2xl">
      <div className="flex items-center gap-3 border-b border-white/20 bg-white/10 px-5 py-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-panchang-orange to-panchang-orange-dark shadow-[0_0_14px_rgba(242,102,13,0.6)]">
          <DiyaIcon className="h-6 w-6 text-white" />
        </div>
        <div>
          <p className="font-display text-lg font-semibold text-panchang-cream">Ask Panchang</p>
          <p className="text-xs text-panchang-cream/60">Your community calendar companion</p>
        </div>
      </div>

      <div ref={scrollRef} className="themed-scroll flex-1 space-y-3 overflow-y-auto p-4 sm:p-6">
        {messages.map((msg, i) => (
          <div key={i} className="space-y-1">
            <Bubble role={msg.role}>{msg.content}</Bubble>
            {msg.caption && (
              <p className="px-2 text-xs italic text-panchang-cream/50">{msg.caption}</p>
            )}
            {msg.quickReplies && (
              <div className="flex flex-wrap gap-2 px-2 pt-1">
                {msg.quickReplies.map((qr) => (
                  <button
                    key={qr.label}
                    onClick={() => ask(qr.query)}
                    className="rounded-full border border-panchang-gold-light/50 bg-white/20 px-3 py-1 text-xs font-medium text-panchang-cream transition hover:bg-white/30"
                  >
                    {qr.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="space-y-1">
            <Bubble role="bot">
              <span className="inline-flex items-center gap-1">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-panchang-orange [animation-delay:-0.3s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-panchang-orange [animation-delay:-0.15s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-panchang-orange" />
              </span>
            </Bubble>
            {slowHint && (
              <p className="px-2 text-xs italic text-panchang-cream/50">
                Still thinking -- the free AI model can take up to a minute to reply.
              </p>
            )}
          </div>
        )}
      </div>

      {messages.length <= 1 && (
        <div className="flex flex-wrap gap-2 border-t border-white/20 px-4 py-3 sm:px-6">
          {STARTER_QUESTIONS.map((q) => (
            <button
              key={q}
              onClick={() => ask(q)}
              className="rounded-full border border-white/30 bg-white/10 px-3 py-1.5 text-xs font-medium text-panchang-cream transition hover:border-panchang-gold-light hover:bg-white/20"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex items-center gap-2 border-t border-white/20 bg-white/10 p-3 sm:p-4">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about a date, festival, or contact..."
          className="flex-1 rounded-full border border-white/30 bg-white/90 px-4 py-2.5 text-sm text-panchang-ink outline-none placeholder:text-panchang-ink/40 focus:border-panchang-orange"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-full bg-gradient-to-br from-panchang-orange to-panchang-orange-dark px-5 py-2.5 text-sm font-semibold text-white shadow-[0_4px_14px_rgba(242,102,13,0.5)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
        >
          Send
        </button>
      </form>
    </div>
  );
}
