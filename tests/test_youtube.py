import pytest

from shorts.models import Beat, Script
from shorts.youtube import MAX_TAG_CHARS, MAX_TITLE, build_metadata


@pytest.fixture
def script():
    return Script(
        title="Do 5 squats a day and your legs will double in size",
        hook="THEY LIED",
        beats=[Beat(text="line", visual="v")],
        description="Here is what happens.",
        tags=["shorts", "fitness", "squats"],
        disclaimer="Satire. Not fitness advice.",
    )


def test_title_gets_the_shorts_suffix(script, config):
    body = build_metadata(script, config)
    assert body["snippet"]["title"].endswith("#shorts")


def test_long_titles_are_truncated_to_the_api_limit(script, config):
    script.title = "x" * 300
    title = build_metadata(script, config)["snippet"]["title"]
    assert len(title) <= MAX_TITLE
    assert title.endswith("#shorts")


def test_tag_list_respects_the_combined_character_budget(script, config):
    script.tags = [f"tag{i:03d}averylongtagname" for i in range(80)]
    tags = build_metadata(script, config)["snippet"]["tags"]
    assert sum(len(t) + 1 for t in tags) <= MAX_TAG_CHARS


def test_description_carries_disclaimer_and_footer(script, config):
    description = build_metadata(script, config)["snippet"]["description"]
    assert "Satire. Not fitness advice." in description
    assert "#shorts" in description


def test_privacy_defaults_to_private(script, config):
    assert build_metadata(script, config)["status"]["privacyStatus"] == "private"


def test_privacy_is_configurable(script, config):
    cfg = config.merged_with({"upload": {"privacy": "unlisted"}})
    assert build_metadata(script, cfg)["status"]["privacyStatus"] == "unlisted"


def test_upload_refuses_while_disabled(script, config, tmp_path):
    from shorts.models import RenderResult
    from shorts.youtube import upload

    result = RenderResult(tmp_path / "v.mp4", None, script, 20.0, tmp_path)
    with pytest.raises(RuntimeError, match="upload.enabled is false"):
        upload(result, config)


def test_dry_run_uploads_nothing(script, config, tmp_path, capsys):
    from shorts.models import RenderResult
    from shorts.youtube import upload

    cfg = config.merged_with({"upload": {"enabled": True}})
    result = RenderResult(tmp_path / "v.mp4", None, script, 20.0, tmp_path)
    assert upload(result, cfg, dry_run=True) is None
    assert "#shorts" in capsys.readouterr().out
