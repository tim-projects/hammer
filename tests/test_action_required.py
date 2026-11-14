import json
from types import SimpleNamespace

import pytest

from tasks_ai.cli_io import action_required, error


def _cli(**kwargs):
    defaults = {"as_json": False, "quiet": False, "output_messages": []}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_action_required_json_schema_and_exit_status(capsys):
    with pytest.raises(SystemExit) as exc:
        action_required(
            _cli(as_json=True),
            "Complete verification proof for task 419.",
            hint="Run the required review.",
        )

    response = json.loads(capsys.readouterr().out)
    assert exc.value.code == 1
    assert response == {
        "success": False,
        "status": "action_required",
        "error": "Complete verification proof for task 419.",
        "messages": [],
        "hint": "Run the required review.",
    }


def test_action_required_terminal_wording(capsys):
    with pytest.raises(SystemExit) as exc:
        action_required(
            _cli(),
            "Complete verification proof for task 419.",
            hint="WHAT: Review every patch.",
        )

    output = capsys.readouterr().out
    assert exc.value.code == 1
    assert output.startswith("NEXT STEP:")
    assert "WHAT: Review every patch." in output
    assert "Error:" not in output


def test_genuine_error_remains_a_normal_error(capsys):
    with pytest.raises(SystemExit) as exc:
        error(_cli(as_json=True), "Integrity mismatch.")

    response = json.loads(capsys.readouterr().out)
    assert exc.value.code == 1
    assert response == {
        "success": False,
        "error": "Integrity mismatch.",
        "messages": [],
    }
    assert "status" not in response
