"""Conventional classification metrics without extra dependencies."""
import math


def confusion(y_true, y_pred):
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    return tp, fp, tn, fn


def binary(y_true, y_pred) -> dict:
    tp, fp, tn, fn = confusion(y_true, y_pred)
    n = tp + fp + tn + fn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        'n': n, 'accuracy': round((tp + tn) / n, 4) if n else 0.0,
        'precision': round(precision, 4), 'recall': round(recall, 4), 'f1': round(f1, 4),
        'fpr': round(fp / (fp + tn), 4) if fp + tn else 0.0,      # legitimate messages wrongly flagged
        'fnr': round(fn / (fn + tp), 4) if fn + tp else 0.0,      # scams missed
        'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn,
    }


def roc_auc(y_true, scores):
    """Probability that a random scam scores higher than a random legitimate message (ties count half)."""
    pos = [s for t, s in zip(y_true, scores) if t == 1]
    neg = [s for t, s in zip(y_true, scores) if t == 0]
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return round(wins / (len(pos) * len(neg)), 4)


def sweep(y_true, scores, thresholds=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95)):
    rows = []
    for t in thresholds:
        m = binary(y_true, [int(s >= t) for s in scores])
        rows.append({'threshold': t, **{k: m[k] for k in ('precision', 'recall', 'f1', 'fp', 'fn')}})
    return rows


def best_threshold(y_true, scores):
    """Threshold with the best F1 (ties: the higher threshold, fewer false alarms). Use on the dev split only."""
    best = max(sweep(y_true, scores, [i / 100 for i in range(5, 100, 5)]), key=lambda r: (r['f1'], r['threshold']))
    return best['threshold']


def latency(ms_list) -> dict:
    if not ms_list:
        return {}
    s = sorted(ms_list)
    p95 = s[min(len(s) - 1, math.ceil(0.95 * len(s)) - 1)]
    return {'mean_ms': round(sum(s) / len(s)), 'p95_ms': round(p95), 'max_ms': round(s[-1])}


def by_group(rows, key, pred_key='pred'):
    """Per-category (or per-language) accuracy plus missed / wrongly flagged counts."""
    out = {}
    for r in rows:
        g = out.setdefault(r[key], {'n': 0, 'correct': 0, 'missed': 0, 'false_alarm': 0})
        g['n'] += 1
        g['correct'] += r['label'] == r[pred_key]
        g['missed'] += r['label'] == 1 and r[pred_key] == 0
        g['false_alarm'] += r['label'] == 0 and r[pred_key] == 1
    for g in out.values():
        g['accuracy'] = round(g['correct'] / g['n'], 3)
    return dict(sorted(out.items()))
