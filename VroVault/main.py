"""
VroVault - Application Entry Point
=====================================
Bootstraps CustomTkinter, applies theme, and orchestrates
the profile screen → vault window lifecycle.
"""

import sys
import logging
import os
from pathlib import Path

import customtkinter as ctk

import ui.theme as theme
from core.profiles import ProfileManager, Profile
from core.database import VaultDB

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("vrovault")

# ── Data directory ────────────────────────────────────────────────────────────

DATA_DIR = Path(os.environ.get("VROVAULT_DATA", Path.home() / ".local" / "share" / "vrovault"))


# ── Application class ─────────────────────────────────────────────────────────

class VroVaultApp(ctk.CTk):
    """Root application window."""

    def __init__(self):
        super().__init__()

        # Apply theme before any widget creation
        theme.set_mode("dark")
        theme.apply(self)

        self.title("VroVault")
        self.geometry("1100x720")
        self.minsize(800, 560)

        t = theme.current()
        self.configure(fg_color=t["bg_root"])

        # Try to set window icon (graceful fail)
        icon_path = Path(__file__).parent / "assets" / "icon.png"
        if icon_path.exists():
            try:
                from PIL import Image, ImageTk
                img = Image.open(icon_path)
                self._icon_img = ImageTk.PhotoImage(img)
                self.iconphoto(True, self._icon_img)
            except Exception:
                pass

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Profile manager
        self._pm: ProfileManager = ProfileManager(DATA_DIR)

        # Active session state
        self._active_vault: VaultDB | None = None
        self._active_profile: Profile | None = None

        # Render the first screen
        self._show_profile_screen()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Screen routing ────────────────────────────────────────────────────────

    def _clear_content(self) -> None:
        for w in self.winfo_children():
            w.destroy()

    def _show_profile_screen(self) -> None:
        self._clear_content()
        from ui.profile_screen import ProfileScreen
        screen = ProfileScreen(
            self,
            pm=self._pm,
            on_profile_selected=self._on_profile_selected,
        )
        screen.grid(row=0, column=0, sticky="nsew")
        logger.info("Profile screen shown.")

    def _on_profile_selected(self, profile: Profile, key: bytes) -> None:
        """Called by ProfileScreen after successful authentication."""
        self._active_profile = profile
        try:
            self._active_vault = self._pm.open_vault(profile.id, key)
            # Seed default categories on first open
            self._active_vault.seed_default_categories()
            # Auto-backup on open (runs in background thread)
            self._schedule_backup()
        except Exception as e:
            logger.error("Failed to open vault: %s", e)
            self._show_profile_screen()
            return

        self._show_main_window()

    def _show_main_window(self) -> None:
        self._clear_content()
        from ui.main_window import MainWindow
        win = MainWindow(
            self,
            vault=self._active_vault,
            profile=self._active_profile,
            pm=self._pm,
            on_logout=self._on_logout,
        )
        win.grid(row=0, column=0, sticky="nsew")
        logger.info("Vault opened for profile '%s'.", self._active_profile.name)

    def _on_logout(self) -> None:
        """Lock / logout — return to profile screen."""
        if self._active_vault:
            try:
                self._active_vault.close()
            except Exception:
                pass
        self._active_vault   = None
        self._active_profile = None
        logger.info("Session locked. Returning to profile screen.")
        self._show_profile_screen()

    # ── Backup ────────────────────────────────────────────────────────────────

    def _schedule_backup(self) -> None:
        import threading

        def _run():
            try:
                if self._active_vault:
                    bp = self._active_vault.create_backup(DATA_DIR)
                    logger.info("Auto-backup created: %s", bp.name)
                    # Keep only last 10 backups
                    _prune_backups(DATA_DIR / "backups", keep=10)
            except Exception as e:
                logger.warning("Auto-backup failed: %s", e)

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    # ── Close ─────────────────────────────────────────────────────────────────

    def _on_close(self) -> None:
        from utils.clipboard import clear_now
        clear_now()
        if self._active_vault:
            try:
                self._active_vault.close()
            except Exception:
                pass
        logger.info("VroVault closed.")
        self.destroy()


# ── Backup pruning ────────────────────────────────────────────────────────────

def _prune_backups(backup_dir: Path, keep: int = 10) -> None:
    if not backup_dir.exists():
        return
    files = sorted(backup_dir.glob("*.db"), key=lambda p: p.stat().st_mtime)
    while len(files) > keep:
        files.pop(0).unlink(missing_ok=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    # Linux: prefer Wayland-compatible font rendering
    if sys.platform.startswith("linux"):
        os.environ.setdefault("GDK_BACKEND", "x11")

    try:
        app = VroVaultApp()
        app.mainloop()
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    except Exception as e:
        logger.critical("Fatal error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
