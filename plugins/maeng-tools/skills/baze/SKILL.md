---
name: baze
description: Use when the user asks for Gemini 4 Argon, Solar, another non-Claude and non-GPT model, or the school's BAZE gateway by name, for writing, polishing or Korean material - "argon으로", "argon한테", "제미나이로", "솔라로", "BAZE로". Sends one prompt to the named model and prints the answer. Only on request, never automatically, and never with eta content. Claude and GPT stay on the user's subscriptions.
---

# baze (school API gateway)

The university gives the user a BAZE key with 5,000 credits a month. This skill makes one chat call through it. Claude Code and Codex keep their own settings: never set `ANTHROPIC_BASE_URL`, `OPENAI_BASE_URL` or a key in a shell profile for this.

## Rules

- **On request only.** Call it when the user names a model or BAZE. Do not route work here on your own.
- **Data.** Never send eta content: the eta decision covers OpenAI, not BAZE. `ask.py` refuses from the eta checkout or when the text mentions eta or Endix. Requests pass through the school's account and the gateway's operator. `ask.py` masks recognizable secret formats; `<private>` vault spans are yours to leave out.
- **Key.** Keychain item `baze-api-key`. Never print it or ask for it in the chat.
- **Credits.** Argon costs 2 credits per 1K input tokens and 10 per 1K output, so a call with 2K in and 1K out is 14 credits. Prefer a short excerpt to a whole document.

## Use

```bash
python3 <this skill>/scripts/ask.py "<prompt>"
python3 <this skill>/scripts/ask.py --file draft.md --system "<instructions>" "<prompt>"
python3 <this skill>/scripts/ask.py --model solar-pro4 "<prompt>"
```

The answer goes to stdout; model and tokens go to stderr. Nothing retries, because a call can spend credit.

| Model | For |
|---|---|
| `gemini-4-argon` (default) | writing, polishing, Korean material when quality matters |
| `solar-pro4` | cheap Korean work, about a seventh of Argon's input price; a comparison partner for Argon |
| `gemini-3.8-flash` | long Korean material on a budget |

Other ids: `curl -H "Authorization: Bearer $(security find-generic-password -s baze-api-key -w)" https://api.baze.co/v1/gateway/models/?type=llm`.

Show the user the model's answer as it came back, and say which model wrote it.
