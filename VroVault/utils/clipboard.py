"""
VroVault - Clipboard Manager
=============================
Secure clipboard copy with automatic clearing after a configurable delay.
Uses pyperclip. Falls back gracefully if clipboard is unavailable (headless).
"""

import threading
import time
import logging
from typing import Optional

try:
    import pyperclip
    _CLIPBOARD_AVAILABLE = True
except Exception:
    _CLIPBOARD_AVAILABLE = False

logger = logging.getLogger(__name__)

_clear_timer: Optional[threading.Timer] = None
_clear_lock  = threading.Lock()


def copy_secure(text: str, clear_after_seconds: int = 30) -> bool:
    """
    Copy text to the system clipboard and schedule automatic clearing.

    Args:
        text: The string to copy (e.g. a password).
        clear_after_seconds: Seconds after which the clipboard is cleared.
            Set to 0 to disable auto-clear.

    Returns:
        True if the copy succeeded, False otherwise.
    """
    global _clear_timer

    if not _CLIPBOARD_AVAILABLE:
        logger.warning("Clipboard not available — pyperclip missing or no display.")
        return False

    try:
        pyperclip.copy(text)
    except Exception as exc:
        logger.error("Clipboard copy failed: %s", exc)
        return False

    if clear_after_seconds > 0:
        with _clear_lock:
            if _clear_timer is not None:
                _clear_timer.cancel()
            _clear_timer = threading.Timer(clear_after_seconds, _auto_clear, args=(text,))
            _clear_timer.daemon = True
            _clear_timer.start()

    return True


def _auto_clear(original_text: str) -> None:
    """
    Clear the clipboard only if it still contains the sensitive value we put there.
    This prevents clearing something the user intentionally copied afterwards.
    """
    if not _CLIPBOARD_AVAILABLE:
        return
    try:
        current = pyperclip.paste()
        if current == original_text:
            pyperclip.copy("")
            logger.debug("Clipboard cleared automatically.")
    except Exception as exc:
        logger.debug("Auto-clear failed: %s", exc)


def clear_now() -> None:
    """Immediately clear the clipboard and cancel any pending timer."""
    global _clear_timer
    with _clear_lock:
        if _clear_timer is not None:
            _clear_timer.cancel()
            _clear_timer = None
    if _CLIPBOARD_AVAILABLE:
        try:
            pyperclip.copy("")
        except Exception:
            pass


def cancel_pending_clear() -> None:
    """Cancel a scheduled auto-clear without clearing the clipboard."""
    global _clear_timer
    with _clear_lock:
        if _clear_timer is not None:
            _clear_timer.cancel()
            _clear_timer = None
