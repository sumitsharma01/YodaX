"""Prospective challenger for online-v1, evaluated independently before promotion."""
import math

VERSION = 'online-v2-shadow'
MIN_OUTCOMES = 20
WINDOW = 20


def initial_state():
    return dict(weights=[0.4, 0.3, 0.3], bias=0.0, count=0, recent=[])


def issue(previous, raw, scale, state):
    correction = max(-2 * scale, min(2 * scale, state['bias']))
    experts = [raw, previous, max(0.01, raw + previous * correction)]
    ensemble = sum(weight * price for weight, price in zip(state['weights'], experts))
    recent = state['recent']
    enough = len(recent) >= MIN_OUTCOMES
    # Compare a continuous shadow ensemble with the same no-change observations.
    # The gate cannot learn from outcomes that have not settled yet.
    beats_baseline = enough and sum(r['ensemble_error'] for r in recent) < 0.95 * sum(r['baseline_error'] for r in recent)
    return dict(version=VERSION, experts=experts, weights=list(state['weights']),
        predicted=ensemble if beats_baseline else previous, ensemble=ensemble,
        scale=scale, prior_count=state['count'],
        decision='adaptive' if beats_baseline else 'no_change',
        reason='recent_error_below_baseline' if beats_baseline else
            ('collecting_outcomes' if not enough else 'baseline_performs_better'))


def update(state, prediction, actual, previous):
    scale = prediction['scale']
    actual_return = actual / previous - 1
    losses = []
    for price in prediction['experts']:
        predicted_return = price / previous - 1
        loss = ((predicted_return - actual_return) / scale) ** 2
        # Penalise an opposite-direction call on a material move, without rewarding abstention as a correct direction.
        if predicted_return * actual_return < 0 and abs(actual_return) >= scale * 0.25:
            loss += 0.5
        losses.append(min(loss, 25))
    weights = [weight * math.exp(-0.2 * loss) for weight, loss in zip(state['weights'], losses)]
    total = sum(weights)
    weights = [0.97 * weight / total + 0.01 for weight in weights]
    residual = (actual - prediction['experts'][0]) / previous
    bounded_residual = max(-2 * scale, min(2 * scale, residual))
    recent = state['recent'] + [dict(
        ensemble_error=abs(prediction['ensemble'] / previous - actual / previous),
        baseline_error=abs(actual_return))]
    return dict(weights=weights, bias=0.7 * state['bias'] + 0.3 * bounded_residual,
                count=state['count'] + 1, recent=recent[-WINDOW:])
