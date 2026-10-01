# Evaluation: generator `extractive`

43 questions (35 answerable, 8 not answerable from the corpus), top-k = 5

| Metric | Value |
|---|---|
| hit_at_k | 1.0 |
| mrr | 0.9214 |
| citation_precision | 0.7727 |
| faithfulness | 1.0 |
| key_fact_recall | 0.8667 |
| correct_abstention | 0.875 |
| false_abstention | 0.0571 |
| latency_ms | 50.4605 |

**Gate: PASSED** 

## Abstention threshold sweep

| threshold | correct abstention | false abstention |
|---|---|---|
| 0.3 | 0.62 | 0.0 |
| 0.4 | 0.75 | 0.03 |
| 0.5 | 0.88 | 0.06 |
| 0.6 | 0.88 | 0.14 |
| 0.7 | 0.88 | 0.23 |

## Questions that need attention

| id | issue | answer (shortened) |
|---|---|---|
| q01 | key facts 0% | Die von den Krankenhäusern erbrachten und in Rechnung gestellten Leistungen sind von den Krankenkassen innerhalb von fün |
| q03 | key facts 0% | Nach Abschluss einer Prüfung nach § 275 Absatz 1 Nummer 1 des Fünften Buches Sozialgesetzbuch erfolgen keine weiteren Pr |
| q11 | false abstention | Dazu finde ich in den hinterlegten Rechtsgrundlagen keine Antwort. |
| q19 | key facts 33% | (4) Mit einem Versorgungsvertrag nach Absatz 1 wird das Krankenhaus für die Dauer des Vertrages zur Krankenhausbehandlun |
| q20 | false abstention | Dazu finde ich in den hinterlegten Rechtsgrundlagen keine Antwort. |
| u05 | answered out-of-scope question | (3b) Hat in den Fällen des Absatzes 3 die Krankenkasse den Leistungsantrag des Versicherten ohne vorherige Prüfung durch |
