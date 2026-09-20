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
        "doctor", "idea", "script", "make", "render", "batch", "upload"
    }
