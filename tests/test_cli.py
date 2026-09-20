import pytest

from shorts.cli import build_parser, main


def test_doctor_reports_cleanly(capsys):
    assert main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "ffmpeg" in out and "caption font" in out


def test_idea_prints_the_requested_count(capsys):
    assert main(["idea", "-n", "3", "--seed", "1"]) == 0
    assert capsys.readouterr().out.count("•") == 3


def test_idea_json_output_is_parseable(capsys):
    import json

    assert main(["idea", "-n", "2", "--seed", "1", "--json"]) == 0
    for line in capsys.readouterr().out.strip().splitlines():
        assert json.loads(line)["claim"]


def test_show_prompt_makes_no_model_call(capsys):
    assert main(["script", "--show-prompt", "--seed", "2"]) == 0
    out = capsys.readouterr().out
    assert "=== SYSTEM ===" in out and "=== USER ===" in out


def test_script_writes_json_to_disk(tmp_path):
    from shorts.models import Script

    out = tmp_path / "s.json"
    assert main(["script", "--seed", "3", "-o", str(out)]) == 0
    assert Script.load(out).beats


def test_set_overrides_reach_the_config(capsys):
    assert main(["doctor", "--set", "visual.layout=full"]) == 0
    assert "layout: full" in capsys.readouterr().out


def test_errors_are_reported_without_a_traceback(capsys):
    assert main(["doctor", "--set", "providers.image=bogus", "--config", "/nope.yaml"]) == 1
    assert "error:" in capsys.readouterr().err


def test_upload_rejects_a_directory_without_artifacts(tmp_path, capsys):
    assert main(["upload", str(tmp_path)]) == 1
    assert "script.json" in capsys.readouterr().err


def test_every_subcommand_is_wired():
    parser = build_parser()
    actions = [a for a in parser._actions if a.dest == "command"]
    assert set(actions[0].choices) == {
        "doctor", "idea", "script", "make", "render", "batch", "upload",
        "pitch", "fetch-broll", "auth",
    }


# --- phone-oriented commands ---------------------------------------------

def test_pitch_writes_scripts_without_rendering(tmp_path):
    from shorts.models import Script

    assert main(["pitch", "-n", "3", "--seed", "4", "--out-dir", str(tmp_path)]) == 0
    written = sorted(tmp_path.glob("*.json"))
    assert len(written) == 3
    assert all(Script.load(p).beats for p in written)
    assert not list(tmp_path.glob("*.mp4"))   # nothing rendered


def test_pitch_markdown_is_readable_on_a_phone(tmp_path):
    summary = tmp_path / "pitch.md"
    assert main(["pitch", "-n", "2", "--seed", "5",
                 "--out-dir", str(tmp_path), "--markdown", str(summary)]) == 0
    text = summary.read_text()
    assert text.count("###") == 2
    assert "> " in text          # beats quoted, so they scan as script lines
    assert "`01.json" not in text.replace(str(tmp_path), "")  # paths are real


def test_expand_scripts_accepts_files_dirs_and_globs(tmp_path):
    from shorts.cli import _expand_scripts

    (tmp_path / "01.json").write_text("{}")
    (tmp_path / "02.json").write_text("{}")
    (tmp_path / "notes.txt").write_text("ignore me")

    assert len(_expand_scripts([tmp_path])) == 2
    assert len(_expand_scripts([tmp_path / "01.json"])) == 1
    assert len(_expand_scripts([tmp_path / "notes.txt"])) == 0


def test_render_reports_when_nothing_matches(tmp_path, capsys):
    assert main(["render", str(tmp_path)]) == 1
    assert "no script.json found" in capsys.readouterr().err


def test_fetch_broll_on_the_shipped_template_is_a_noop(capsys):
    assert main(["fetch-broll"]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_auth_explains_the_missing_client_secret(capsys, monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "/nonexistent/client_secret.json")
    assert main(["auth", "--redirect-url", "https://localhost/?code=x"]) == 1
    assert "Google Cloud Console" in capsys.readouterr().err


def test_auth_rejects_a_url_without_a_code(tmp_path, capsys, monkeypatch):
    import json

    secret = tmp_path / "client_secret.json"
    secret.write_text(json.dumps({"web": {
        "client_id": "id", "client_secret": "secret",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }}))
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", str(secret))
    assert main(["auth", "--redirect-url", "https://localhost/"]) == 1
    assert "no ?code=" in capsys.readouterr().err
