# Guardian model evaluation

Every model Guardian uses has a model card and a live, re-runnable evaluation on the analyst page **Model
evaluation** (`/<panel>/evaluation/`). Each run is stored, so earlier results stay visible. The same runs work from
the terminal:

```bash
cd pita
python manage.py run_eval                                   # all evaluations
python manage.py run_eval classifier fused --out results.json
```

The numbers below come from the runs on **6 Nov 2026** against the Testbed GPU machine (`DESKTOP-3CGBSSB`, GTX 1060
6 GB, mode `live`). The full output, including every failure example, is in
[testbed-evidence/2026-11-06_evaluation.json](testbed-evidence/2026-11-06_evaluation.json). Nothing here is
estimated. If a model does not answer, the run is recorded as "Model unavailable".

## Data

All data is **synthetic and written by the team**. It contains no real messages from children and no real phone
numbers. It is in [pita/evaluation/data/](../pita/evaluation/data/).

| Set | Size | Use |
|---|---|---|
| `messages_v1.csv` | 126 messages: 68 scams, 58 legitimate. Split: 42 dev, 84 test | Message classifier, rules, full check |
| `urls_v1.csv` | 50 links: 25 official or common, 25 look-alike, number-address or shortened | Link model and lexical checks |
| `waves_v1.json` | 5 scam waves of 3 to 4 rewordings each, plus 6 unrelated messages (300 pairs) | Embeddings |
| Rendered chat screenshots | 6 chats, 17 messages, drawn in memory with known senders | Screenshot reading |
| Explanation cases | 6 (high and suspicious, child and parent, three age bands) | Explanation checks |
| Generation topics | 2 analyst topics | Family-version generation |

The legitimate messages deliberately include false-positive traps that Ugandan children really see: one-time-code
notices, Mobile Money receipts, telco promotions with short codes, school fee reminders, bank notices and "you won"
messages between friends.

Every message is in English. The set has no Luganda or Runyankole yet, so no claim is made about those languages.

The threshold is tuned on the **dev** split only, and every reported number is on the **test** split.

## Results

### Message checks (84 test messages: 46 scams, 38 legitimate)

| Configuration | Precision | Recall | F1 | False alarms | Missed scams | ROC-AUC | Mean latency |
|---|---|---|---|---|---|---|---|
| DistilBERT classifier alone, threshold 0.5 | 67.2% | 84.8% | 0.750 | 19 of 38 | 7 of 46 | 0.754 | 402 ms |
| Safety rules only (the fallback) | 72.3% | 73.9% | 0.731 | 13 of 38 | 12 of 46 | 0.704 | under 1 ms |
| **Full Guardian check (fused)** | 65.2% | **93.5%** | **0.768** | 23 of 38 | **3 of 46** | 0.716* | 427 ms |

\*For the rule-based and fused checks, ROC-AUC uses the risk level (high, some warning signs, low) as an ordinal
score.

What this shows:
- **Fusion catches almost every scam.** It missed 3 of 46, compared with 7 for the classifier and 12 for the rules.
  For a child-safety tool, a missed scam costs more than a false alarm.
- **False alarms are the main weakness.** Most of them are genuine one-time-code notices, Mobile Money receipts,
  telco promotions and bank notices. Each of these mentions PINs, codes or money, and the classifier was trained on
  English emails, not Ugandan SMS. In a separate re-run on the 38 legitimate test messages, the full check gave 6 "high risk", 17 "some warning signs"
  and 15 "low observed risk", so most false alarms are the milder warning. That re-run isn't stored as an
  evaluation run.
  Across the 84 test messages, the full check gave 25 high-risk, 41 warning-sign and 18 low-risk results.
- **The tuned threshold doesn't help.** The dev split suggests 0.8 for the classifier, but on test it gives F1 0.722
  (16 false alarms, 11 missed), worse than 0.5. Guardian keeps 0.5.
- **Missed by the full check:** a "seed offering" church impersonation, a "send me photos for airtime" grooming
  message with no scam keywords, and a "help me vote, send the code" request.
- **Next improvements:** recognise official sender formats and short codes as legitimate evidence, and fine-tune the
  classifier on Ugandan SMS.

### Links (50 links, analysed as text, never visited)

| Configuration | Precision | Recall | F1 | False alarms | Missed | ROC-AUC |
|---|---|---|---|---|---|---|
| Phishing-URL model, threshold 0.5 | 95.2% | 80.0% | 0.870 | 1 | 5 | 0.955 |
| Phishing-URL model, threshold 0.8 | | | 0.732 | 1 | 10 | |
| Lexical checks (the fallback) | | | 1.000 | 0 | 0 | |

Mean latency: 10.7 ms per link.

**Caveat.** The same team wrote both the lexical checks and this URL list, so the perfect lexical score partly
reflects that overlap. It is not evidence that the checks generalise. In the product, both signals are used
together.

### Scam-wave similarity (all-MiniLM-L6-v2)

On 300 pairs, rewordings of the same scam scored a mean cosine similarity of 0.537. Unrelated pairs scored 0.186,
a separation of 0.351.

| Measure | Result |
|---|---|
| ROC-AUC | 0.981 |
| Best threshold | 0.45 |
| At that threshold | F1 0.808: 4 false matches, 6 missed matches |
| Nearest neighbour from the same wave | 100% |
| Time to embed 25 messages | 1.5 s |

### Qwen3-VL-2B (llama.cpp, GTX 1060)

| Check | Result |
|---|---|
| Screenshot text read correctly (85% character similarity or more) | 17 of 17 (100%), mean 3.5 s per screenshot |
| Sender role correct | **100%** after the fix below (was 64.7%) |
| Child's own messages wrongly analysed | 0 (was 2 before the fix) |
| Explanations passing every check (no "safe" claims, no em dash, 1 to 5 actions, short sentences) | 6 of 6, mean 1.9 s, child reading grade about 3.2 |
| Family versions: valid JSON, all parts present, 3 quiz questions, valid answers, no duplicates | 2 of 2 |
| Family versions passing Guardian's safety screen | 1 of 2 |
| Model writes the `{link}` placeholder itself | 0 of 2. Guardian replaces the invented address with the practice link |
| Practice message keeps the exercise realistic | 1 of 2 |

Mean generation time is 20.9 s per topic.

**Two weaknesses found by this page and fixed on 6 Nov:**
1. In back-and-forth chats, Qwen swapped who sent which message, so the child's own words would have been checked
   and the scammer's skipped. The extraction prompt now asks for each bubble's side (left or right), and the service
   derives the sender from that. Sender accuracy went from 64.7% to 100%.
2. Practice messages carried invented web addresses or said "don't click, it's not real". Guardian now swaps the
   first invented address for the practice link. The safety screen also flags messages that give the exercise away,
   so the analyst fixes them before publishing.

## Limitations

- The datasets are small and written by the team. They show behaviour and weaknesses, not production accuracy.
- Every message is in English, and the screenshots are clean renders rather than real phone captures.
- Scores are uncalibrated model scores, not probabilities.
- The latencies come from one GPU machine with one request at a time.
