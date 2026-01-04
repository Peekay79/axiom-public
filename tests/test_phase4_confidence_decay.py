import datetime as dt


def test_confidence_decay_reduces_over_time(monkeypatch):
    from pods.memory.decay_policy import decay

    # Half-life default is 90 days (AXIOM_DECAY_HALFLIFE_DAYS). Legacy AXIOM_DECAY_HALF_LIFE maps with deprecation.
    # Keep environment default; assert monotonic decrease with age
    original = 0.8
    age_0 = dt.timedelta(days=0)
    age_30 = dt.timedelta(days=30)
    age_60 = dt.timedelta(days=60)

    now = decay(original, age_0)
    later = decay(original, age_30)
    later2 = decay(original, age_60)

    assert 0.0 <= later <= now
    assert 0.0 <= later2 <= later

