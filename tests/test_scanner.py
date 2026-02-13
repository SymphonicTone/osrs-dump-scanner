import time
from scanner import Scanner


def make_result(is_dump: bool):
    return {"is_dump": is_dump}


def test_initial_state_no_alert_when_not_dump():
    scanner = Scanner()

    alert = scanner.process_item(1001, make_result(False))

    assert alert is None


def test_first_dump_triggers_alert():
    scanner = Scanner()

    alert = scanner.process_item(1001, make_result(True))

    assert alert is not None


def test_duplicate_dump_does_not_trigger_alert():
    scanner = Scanner()

    scanner.process_item(1001, make_result(True))
    alert = scanner.process_item(1001, make_result(True))

    assert alert is None


def test_recovery_silently_resets_state():
    scanner = Scanner()

    scanner.process_item(1001, make_result(True))
    alert = scanner.process_item(1001, make_result(False))

    assert alert is None


def test_recovery_then_new_dump_triggers_again():
    scanner = Scanner()

    scanner.process_item(1001, make_result(True))
    scanner.process_item(1001, make_result(False))
    alert = scanner.process_item(1001, make_result(True))

    assert alert is not None


def test_multiple_items_independent():
    scanner = Scanner()

    alert1 = scanner.process_item(1001, make_result(True))
    alert2 = scanner.process_item(2002, make_result(True))

    assert alert1 is not None
    assert alert2 is not None

    assert scanner.process_item(1001, make_result(True)) is None
    assert scanner.process_item(2002, make_result(True)) is None


def test_cleanup_removes_stale_items():
    scanner = Scanner(cleanup_seconds=1)
    result = {"is_dump": True}

    scanner.process_item(1001, result)
    assert 1001 in scanner._state

    time.sleep(1.1)
    scanner.process_item(2002, {"is_dump": False})
    assert 1001 not in scanner._state
