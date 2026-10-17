from threading import Event, Thread

import pytest

from codeguard.claude import PromptCacheWarmup

WAIT_SECONDS = 5


def call_thread(warmup: PromptCacheWarmup, prefix: str, started: Event) -> Thread:
    def call() -> None:
        with warmup.after_first_call(prefix):
            started.set()

    return Thread(target=call)


class TestPromptCacheWarmup:
    def test_later_call_waits_for_the_first_call_with_its_prefix(self):
        warmup = PromptCacheWarmup()
        later_started = Event()
        later = call_thread(warmup, "a.py", later_started)

        with warmup.after_first_call("a.py"):
            later.start()
            assert not later_started.wait(0.2)
        later.join(WAIT_SECONDS)

        assert later_started.is_set()

    def test_call_with_another_prefix_does_not_wait(self):
        warmup = PromptCacheWarmup()
        other_started = Event()
        other = call_thread(warmup, "b.py", other_started)

        with warmup.after_first_call("a.py"):
            other.start()
            assert other_started.wait(WAIT_SECONDS)
        other.join(WAIT_SECONDS)

    def test_failed_first_call_releases_later_calls(self):
        warmup = PromptCacheWarmup()
        later_started = Event()
        later = call_thread(warmup, "a.py", later_started)

        with pytest.raises(RuntimeError), warmup.after_first_call("a.py"):
            later.start()
            raise RuntimeError
        later.join(WAIT_SECONDS)

        assert later_started.is_set()
