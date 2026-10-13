# Testing

Testing moved from the cheapest, most controlled layer to the most realistic one. Most bugs were found and fixed before any paid voice call.

| Layer | How | Cost | What it catches |
|---|---|---|---|
| 1. Workflow | Run each n8n tool workflow with mock inputs | Free | SQL logic, rules, edge cases, output wording |
| 2. Router | `curl` requests shaped like Vapi's tool calls | Free | Secret header, routing, argument parsing, call-ID lockout |
| 3. Chat agent | n8n chat agent with the same prompt and tools | Free | Conversation logic, tool choice, prompt conflicts |
| 4. Voice | Vapi calls, scripted, then with a real person | Paid | Speech recognition, timing, interruptions, real behavior |

After every test that changes data, `nova-bank/reset_tests.sh` restores the database.

## Router test example

```bash
curl -s -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "x-vapi-secret: $SECRET" \
  -d '{"message":{"type":"tool-calls","toolCallList":[{"id":"t1","type":"function","function":{"name":"verify_identity","arguments":{"customer_id":"10001","security_answer":"wrong"}}}],"call":{"id":"lock-test"}}}'
```

Run three times, then once with the correct answer: the fourth call returns `LOCKED`.

## Voice test scenarios

| Scenario | Checks | Result |
|---|---|---|
| Balance and branch hours | Verification, policy search, spoken amounts, call ending | Passed after fixes (amount misreads, duplicate filler messages) |
| Full fraud call | Find charges → block the card that was used → urgent ticket → replacement with free express | Passed: correct card blocked, ticket before replacement, every step confirmed separately |
| Charged twice | Find the one true duplicate among five same-store charges, dispute the second | Passed |
| Keypad entry by phone | Typed customer ID | Passed after raising the keypad timeout |
| Real person, unscripted | Mumbled details, slow typing, emotional moments, off-topic questions | Revealed a lockout bug and background-noise issue (fixed) |

## Findings and fixes

### Prompt and tool consistency
- **Looping on tools that didn't exist.** The prompt mentioned tools not built yet; the model kept trying to call them until it hit the iteration limit. Fix: the prompt describes only real tools.
- **Conflicting instructions.** A tool result said "next, offer a replacement" while the prompt said "ticket first". The model followed both and reused one "yes" for two actions. Fix: tool results and prompt give the same order; every action needs its own yes.

### Verification
- **No real attempt limit.** The model can't reliably count failed attempts across a messy conversation. Fix: attempts stored per call ID in `verification_attempts`; lock after three, enforced in SQL.
- **"Yep" used as the security answer.** Fix: confirm the ID with "Is that right?" alone, then ask for the answer separately.
- **Six-digit IDs read back as valid.** Models miscount digits. Fix: the tool rejects non-5-digit IDs without counting an attempt.
- **Real-user lockout.** "grape" was transcribed as "wait"; the agent reused "wait" for every retry and locked the caller out. Fix: always ask for the answer again after a failure, and ask to spell it if needed.

### Data and money
- **Wrong card blocked during fraud.** With no card specified, the tool picked the only active card, not the one used for the charges. Fix: transactions report the card used; the agent passes it explicitly.
- **Misread balances.** The model converted numbers to words itself and slipped on cents. Fix: tools provide the spoken words first, with the number in brackets.
- **False duplicates.** The model called two fees a month apart "duplicates". Fix: duplicate detection in code; the agent may only report listed duplicates.

### Voice
- **Interruptions while the caller paused.** Fix: smart endpointing, longer wait before speaking, two words needed to interrupt the agent.
- **Grouped or dropped digits from speech-to-text.** Fix: join digit groups before counting, offer keypad entry after the second try.
- **Background chatter.** The platform's default office sound made a caller think others were listening. Fix: background sound off.
- **Unsafe end-call phrase.** "bye" would match inside words like "nearby" and hang up mid-sentence. Fix: phrase reduced to "goodbye", plus the End Call tool.
