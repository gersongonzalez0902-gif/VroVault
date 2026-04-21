"""
VroVault - Auto-Lock Timer
===========================
Monitors inactivity and fires a callback to lock the vault.
Thread-safe and restartable.
"""

import threading
import time
import logging

logger = logging.getLogger(__name__)


class AutoLockTimer:
    """
    Fires `on_lock()` if no activity is registered within `timeout_seconds`.

    Usage:
        timer = AutoLockTimer(timeout_seconds=300, on_lock=my_lock_fn)
        timer.start()
        ...
        timer.reset()   # call on any user interaction
        timer.stop()    # call on clean shutdown
    """

    def __init__(self, timeout_seconds: int, on_lock):
        self._timeout  = max(30, timeout_seconds)
        self._on_lock  = on_lock
        self._lock     = threading.Lock()
        self._last_act = time.monotonic()
        self._running  = False
        self._thread: threading.Thread | None = None

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running  = True
            self._last_act = time.monotonic()
            self._thread   = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        logger.debug("AutoLockTimer started (timeout=%ds).", self._timeout)

    def stop(self) -> None:
        with self._lock:
            self._running = False
        logger.debug("AutoLockTimer stopped.")

    def reset(self) -> None:
        """Call this on every meaningful user interaction."""
        with self._lock:
            self._last_act = time.monotonic()

    def set_timeout(self, seconds: int) -> None:
        with self._lock:
            self._timeout = max(30, seconds)
            self._last_act = time.monotonic()

    @property
    def remaining_seconds(self) -> int:
        with self._lock:
            elapsed = time.monotonic() - self._last_act
            return max(0, int(self._timeout - elapsed))

    # ── Internal loop ─────────────────────────────────────────────────────────

    def _loop(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break
                elapsed = time.monotonic() - self._last_act
                should_lock = elapsed >= self._timeout

            if should_lock:
                logger.info("AutoLock triggered after %ds of inactivity.", int(elapsed))
                try:
                    self._on_lock()
                except Exception as exc:
                    logger.error("AutoLock callback raised: %s", exc)
                # Stop — the callback is responsible for restarting if needed
                with self._lock:
                    self._running = False
                break

            time.sleep(1)
