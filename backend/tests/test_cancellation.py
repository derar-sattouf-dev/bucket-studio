"""Cooperative cancellation (app.core.cancellation) and the registries built on it."""

import pytest

from app.core import image_worker
from app.core.cancellation import Cancelled, CancelToken
from app.core.image_worker import TaskStatus


def test_a_fresh_token_passes_its_checkpoints():
    token = CancelToken()
    assert token.cancelled is False
    token.check()


def test_cancel_raises_at_the_next_checkpoint_with_the_reason():
    token = CancelToken()
    token.cancel("Aborted by user")
    assert token.cancelled is True
    with pytest.raises(Cancelled, match="Aborted by user"):
        token.check()


def test_cancel_is_idempotent_and_the_first_reason_wins():
    token = CancelToken()
    token.cancel("first")
    token.cancel("second")
    assert token.reason == "first"


def test_cancelling_a_parent_cancels_its_children_but_not_the_other_way_round():
    job = CancelToken()
    first, second = CancelToken(job), CancelToken(job)

    first.cancel("Skipped")
    assert (first.cancelled, second.cancelled, job.cancelled) == (True, False, False)
    second.check()

    job.cancel("Job stopped by user")
    assert second.cancelled is True
    assert second.reason == "Job stopped by user"
    assert first.reason == "Skipped"  # its own cancellation came first
    with pytest.raises(Cancelled, match="Job stopped by user"):
        second.check()


def test_cancellation_reaches_grandchildren():
    root = CancelToken()
    leaf = CancelToken(CancelToken(root))
    root.cancel("stop")
    assert leaf.cancelled and leaf.reason == "stop"


def test_image_tasks_are_claimed_once_and_aborted_through_their_token():
    key = "images/cancel/unit.jpg"
    parent = CancelToken()
    task = image_worker.register_task(key, parent=parent)
    try:
        assert task is not None and image_worker.is_processing(key)
        assert image_worker.register_task(key) is None  # already claimed

        assert image_worker.request_abort(key) is True
        assert task.token.cancelled and not parent.cancelled
        with pytest.raises(Cancelled, match="Aborted by user"):
            task.token.check()
    finally:
        image_worker.finish_task(key, TaskStatus.ABORTED, "Aborted by user")

    assert not image_worker.is_processing(key)
    assert image_worker.request_abort(key) is False  # nothing in flight any more
    assert image_worker.get_statuses([key, "images/cancel/unknown.jpg"]) == {
        key: TaskStatus.ABORTED,
        "images/cancel/unknown.jpg": TaskStatus.DONE,
    }
    with pytest.raises(ValueError):
        image_worker.finish_task(key, TaskStatus.PROCESSING)
