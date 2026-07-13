         BUYER TYPES ONE SENTENCE
        "PART-1003 is 6 weeks late"
                    │
                    ▼
        ┌───────────────────────────┐
        │    PYDANTIC AI          │  ← the manager
        │   hands the LLM a menu:   │
        │   "you may call ONE thing:│
        │    analyze_lead_time_     │
        │    change(sku, weeks)"    │
        └───────────┬───────────────┘
                    │  sends menu + sentence over the internet
                    ▼
        ┌───────────────────────────┐
        │    THE LLM (OpenAI)     │  ←  YOUR API KEY IS USED **HERE**
        │   reads English,          │     (and ONLY here)
        │   picks from the menu     │
        └───────────┬───────────────┘
                    │
                    │  replies NOT in English, but as a ticket:
                    │  sku="PART-1003", new_lead_time=6
                    ▼
        ┌───────────────────────────┐
        │    PYDANTIC AI CHECKS   │  is PART-1003 real? is 6 ≥ 1?
        │    fake? → bounce back  │   good? → send to the kitchen
        └───────────┬───────────────┘
                    │
                    ▼
   ╔═══════════════════════════════════════╗
   ║    THE SOLVER (your Python)         ║  ← ALL THE MATH HAPPENS HERE
   ║   CP-SAT + parts.csv + budget          ║     NO AI. NO API KEY.
   ║   → cost $988,179                      ║     The LLM is just WAITING.
   ║   → binding: budget                    ║
   ╚═══════════════┬═══════════════════════╝
                    │
                    │  the NUMBERS go back to the LLM
                    ▼
        ┌───────────────────────────┐
        │    THE LLM (OpenAI)     │  ←  API KEY USED AGAIN (2nd time)
        │   reads the numbers,      │
        │   writes English          │
        └───────────┬───────────────┘
                    │
                    ▼
   "The delay costs $988k. Cash is your bottleneck —
    +$1,000/week would recover $19,391."
                    │
                    ▼
               BUYER READS IT


   📹 LANGFUSE watched this ENTIRE tree and recorded it.
      It didn't touch anything. It just filmed it.
