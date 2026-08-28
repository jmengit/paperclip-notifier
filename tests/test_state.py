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
    assert state.summary()["delivered"] == 1
    state.close()
