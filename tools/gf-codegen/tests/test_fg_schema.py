from gf_codegen.compose.fg_schema import (
    normalize_function_groups,
    validate_exec_function_groups,
)


def test_normalize_infers_mode_from_states():
    fgs = normalize_function_groups(
        [{"id": "DriveParkFG", "initial": "DrivingActive", "states": ["DrivingActive", "ParkingActive"]}]
    )
    assert fgs[0]["kind"] == "mode"
    assert "ParkingActive" in fgs[0]["states"]


def test_validate_rejects_bad_active_in():
    data = {
        "function_groups": [
            {"id": "MachineFG", "kind": "machine", "initial": "Running"},
            {
                "id": "DriveParkFG",
                "kind": "mode",
                "initial": "DrivingActive",
                "states": ["DrivingActive", "ParkingActive"],
            },
        ],
        "processes": [
            {
                "name": "planning.driving",
                "function_group": "DriveParkFG",
                "active_in": ["NotAState"],
            }
        ],
    }
    errs, _ = validate_exec_function_groups(data)
    assert any("NotAState" in e for e in errs)


def test_validate_rejects_active_in_on_machine():
    data = {
        "function_groups": [{"id": "MachineFG", "kind": "machine", "initial": "Running"}],
        "processes": [
            {"name": "perception.fcm", "function_group": "MachineFG", "active_in": ["Running"]}
        ],
    }
    errs, _ = validate_exec_function_groups(data)
    assert any("active_in not allowed" in e for e in errs)
