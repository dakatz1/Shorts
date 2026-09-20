from shorts.ideas import ANGLES, OUTCOMES, IdeaGenerator


def test_seeded_generation_is_reproducible():
    a = IdeaGenerator(absurdity=4, seed=99).batch(5)
    b = IdeaGenerator(absurdity=4, seed=99).batch(5)
    assert [i.claim for i in a] == [i.claim for i in b]


def test_absurdity_ceiling_is_respected():
    allowed = {o for o, level, _ in OUTCOMES if level <= 2}
    for idea in IdeaGenerator(absurdity=2, seed=1).batch(12):
        # The claim embeds a formatted outcome, so match on the template stem.
        assert any(o.split("{")[0].strip() in idea.claim for o in allowed)


def test_batch_rotates_exercises():
    ideas = IdeaGenerator(seed=5).batch(8)
    assert len({i.exercise for i in ideas}) == 8


def test_every_angle_is_documented():
    for idea in IdeaGenerator(seed=3).batch(20):
        assert idea.angle in ANGLES


def test_timeframe_is_not_double_stated():
    """Outcomes carrying their own timing must not also get a trailing timeframe."""
    for idea in IdeaGenerator(absurdity=5, seed=7).batch(30):
        assert "permanently in" not in idea.claim
        assert "indefinitely in" not in idea.claim
