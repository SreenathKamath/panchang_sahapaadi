"""
Panchang RAG Chatbot (CLI)
---------------------------
Terminal chat interface over the Saraswat Panchang data. All retrieval/LLM logic
lives in panchang_core.py -- this file is just the interactive loop and how it
renders each result, so it stays in sync with the web API in api/main.py, which
shares the same core.

Setup:
    pip install sentence-transformers numpy openai python-dateutil

    Get a free OpenRouter key: https://openrouter.ai/keys
    export OPENROUTER_API_KEY="your-key-here"      (Mac/Linux)
    set OPENROUTER_API_KEY=your-key-here            (Windows)

Run:
    python panchang_chatbot.py
"""

from panchang_core import ChatState, answer_query


def main():
    state = ChatState()
    print(f"Panchang chatbot ready with {len(state.month_names)} month(s) loaded: "
          f"{state.loaded_months_label} ({state.loaded_range}). Type 'exit' to quit.\n")

    while True:
        query = input("You: ").strip()
        if query.lower() in ("exit", "quit"):
            break
        if not query:
            continue

        result = answer_query(state, query)

        if result["status"] == "ambiguous":
            print(f"Bot: That date/weekday exists in more than one loaded month "
                  f"({', '.join(result['ambiguous_months'])}) -- which one did you mean?\n")

        elif result["status"] == "date_not_covered":
            print(f"Bot: {result['resolved_date']} isn't covered by the currently loaded "
                  f"panchang data ({result['loaded_range']}, covering {result['loaded_months']}).\n")

        elif result["status"] == "not_found":
            print("Bot: I couldn't find anything in this panchang confidently "
                  "matching that -- could you rephrase, or mention a specific date?\n")

        else:  # "answered"
            print(f"Bot: {result['reply']}\n")
            if result["match_source"] != "direct lookup":
                # Helpful for debugging retrieval quality during your demo
                matched_dates = [
                    d["gregorian_date"] or f"{d.get('malayalam_month')} overview"
                    for d in result["matches"]
                ]
                print(f"   (matched via {result['match_source']}: {matched_dates})\n")


if __name__ == "__main__":
    main()
