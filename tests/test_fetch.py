import pytest

from shorts.fetch import _parse_line, read_sources


def test_url_only_takes_the_filename_from_the_url():
    assert _parse_line("https://x.test/a/squats-01.mp4") == (
        "https://x.test/a/squats-01.mp4", "squats-01.mp4"
    )


def test_explicit_filename_wins():
    url, name = _parse_line("https://x.test/abc123  squats-01.mp4")
    assert url == "https://x.test/abc123" and name == "squats-01.mp4"


def test_extensionless_names_get_mp4():
    assert _parse_line("https://x.test/clip?id=7")[1].endswith(".mp4")


@pytest.mark.parametrize("hostile", [
    "../../etc/pass wd.mp4",
    "/etc/shadow.mp4",
    "..%2f..%2fsecret.mp4",
    "....//....//x.mp4",
])
def test_hostile_filenames_cannot_escape_the_broll_directory(hostile, tmp_path):
    """The name comes from a URL, so treat it as untrusted."""
    _, name = _parse_line(f"https://x.test/a.mp4  {hostile}")
    resolved = (tmp_path / name).resolve()
    assert resolved.parent == tmp_path.resolve()
    assert name not in (".", "..", "")


def test_percent_encoding_is_decoded():
    assert _parse_line("https://x.test/push%20ups.mp4")[1] == "push-ups.mp4"


@pytest.mark.parametrize("line", ["", "   ", "# a comment", "  # indented comment"])
def test_blank_and_comment_lines_are_skipped(line):
    assert _parse_line(line) is None


def test_trailing_comments_are_stripped():
    url, _ = _parse_line("https://x.test/a.mp4   # my clip")
    assert url == "https://x.test/a.mp4"


def test_shipped_sources_file_is_all_comments(config):
    """The template must not try to fetch anything on a fresh clone."""
    assert read_sources(config) == []


def test_non_http_sources_are_skipped(tmp_path, config):
    from shorts.fetch import fetch_broll

    cfg = config.merged_with({"broll": {"dir": str(tmp_path)}})
    (tmp_path / "sources.txt").write_text("file:///etc/passwd  evil.mp4\n")
    assert fetch_broll(cfg) == []


def test_missing_sources_file_is_not_an_error(tmp_path, config):
    from shorts.fetch import fetch_broll

    cfg = config.merged_with({"broll": {"dir": str(tmp_path / "nope")}})
    assert fetch_broll(cfg) == []


def test_existing_clips_are_not_refetched(tmp_path, config):
    from shorts.fetch import fetch_broll

    cfg = config.merged_with({"broll": {"dir": str(tmp_path)}})
    (tmp_path / "sources.txt").write_text("https://x.invalid/squats.mp4\n")
    clip = tmp_path / "squats.mp4"
    clip.write_bytes(b"already here")

    # An unreachable host would raise if it were actually fetched.
    assert fetch_broll(cfg) == [clip]
    assert clip.read_bytes() == b"already here"
