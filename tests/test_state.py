from pathlib import Path

from paperclip_notifier.state import State


def test_checkpoint_and_outbox_survive_restart(tmp_path: Path):
    state = State(tmp_path)
    event = {"event_id": "e1", "occurred_at": "2026-08-27T00:00:00Z"}
    state.checkpoint_batch("source", [("e1", event["occurred_at"], event, ["webhook"])])
    assert len(state.pending()) == 1
    state.close()
    state = State(tmp_path)
    assert len(state.pending()) == 1
    state.checkpoint_batch("source", [("e1", event["occurred_at"], event, ["webhook"])])
    assert len(state.pending()) == 1
    state.deliver_success("e1", "webhook")


def test_summary_can_be_read_from_health_thread(tmp_path: Path):
    state = State(tmp_path)
    state.checkpoint_batch("source", [("e1", "2026-08-27T00:00:00Z", {"event_id": "e1"}, ["webhook"])])
    result = {}

    import threading

    thread = threading.Thread(target=lambda: result.update(state.summary()))
    thread.start()
    thread.join()
    assert result == {"pending": 1}
    state.close()
