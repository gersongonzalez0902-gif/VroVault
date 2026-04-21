"""
VroVault - Reusable UI Components
====================================
Custom widgets built on top of CustomTkinter with VroVault theming.
"""

import tkinter as tk
import customtkinter as ctk
from typing import Callable, Optional

import ui.theme as theme


# ── Helpers ──────────────────────────────────────────────────────────────────

def _bind_hover(widget, normal_color: str, hover_color: str,
                attr: str = "fg_color") -> None:
    """Attach enter/leave bindings for a simple colour-swap hover effect."""
    widget.bind("<Enter>", lambda _: widget.configure(**{attr: hover_color}), add="+")
    widget.bind("<Leave>", lambda _: widget.configure(**{attr: normal_color}), add="+")


# ── VroCard ───────────────────────────────────────────────────────────────────

class VroCard(ctk.CTkFrame):
    """A rounded card widget with optional hover highlight."""

    def __init__(self, master, hover: bool = True, **kwargs):
        t = theme.current()
        kwargs.setdefault("fg_color",      t["bg_card"])
        kwargs.setdefault("corner_radius", theme.RADIUS)
        kwargs.setdefault("border_width",  1)
        kwargs.setdefault("border_color",  t["border"])
        super().__init__(master, **kwargs)

        if hover:
            _bind_hover(self, t["bg_card"], t["bg_card_hover"])


# ── VroButton ─────────────────────────────────────────────────────────────────

class VroButton(ctk.CTkButton):
    """Primary accent button."""

    def __init__(self, master, text: str = "", command=None,
                 variant: str = "primary", **kwargs):
        t = theme.current()

        if variant == "primary":
            kwargs.setdefault("fg_color",        t["accent"])
            kwargs.setdefault("hover_color",      t["accent_hover"])
            kwargs.setdefault("text_color",       t["fg_on_accent"])
        elif variant == "secondary":
            kwargs.setdefault("fg_color",         t["bg_card"])
            kwargs.setdefault("hover_color",      t["bg_card_hover"])
            kwargs.setdefault("text_color",       t["fg_primary"])
            kwargs.setdefault("border_width",     1)
            kwargs.setdefault("border_color",     t["border"])
        elif variant == "danger":
            kwargs.setdefault("fg_color",         t["danger"])
            kwargs.setdefault("hover_color",      "#b91c1c")
            kwargs.setdefault("text_color",       "#ffffff")
        elif variant == "ghost":
            kwargs.setdefault("fg_color",         "transparent")
            kwargs.setdefault("hover_color",      t["bg_card_hover"])
            kwargs.setdefault("text_color",       t["fg_secondary"])
            kwargs.setdefault("border_width",     0)

        kwargs.setdefault("corner_radius", theme.RADIUS_SM)
        kwargs.setdefault("font",          theme.font("body"))
        kwargs.setdefault("height",        36)
        super().__init__(master, text=text, command=command, **kwargs)


# ── VroEntry ──────────────────────────────────────────────────────────────────

class VroEntry(ctk.CTkEntry):
    """Styled entry field."""

    def __init__(self, master, placeholder: str = "", show: str = "", **kwargs):
        t = theme.current()
        kwargs.setdefault("fg_color",          t["bg_input"])
        kwargs.setdefault("border_color",      t["border"])
        kwargs.setdefault("text_color",        t["fg_primary"])
        kwargs.setdefault("placeholder_text_color", t["fg_muted"])
        kwargs.setdefault("corner_radius",     theme.RADIUS_SM)
        kwargs.setdefault("font",              theme.font("body"))
        kwargs.setdefault("height",            38)
        kwargs.setdefault("border_width",      1)
        super().__init__(master, placeholder_text=placeholder, show=show, **kwargs)

        def _focus_in(_):
            self.configure(border_color=t["border_focus"])

        def _focus_out(_):
            self.configure(border_color=t["border"])

        self.bind("<FocusIn>",  _focus_in)
        self.bind("<FocusOut>", _focus_out)


# ── VroLabel ──────────────────────────────────────────────────────────────────

class VroLabel(ctk.CTkLabel):
    def __init__(self, master, text: str = "", style: str = "body", **kwargs):
        t = theme.current()
        color_map = {
            "title":   t["fg_primary"],
            "heading": t["fg_primary"],
            "body":    t["fg_primary"],
            "muted":   t["fg_secondary"],
            "tiny":    t["fg_muted"],
            "accent":  t["accent"],
            "success": t["success"],
            "danger":  t["danger"],
            "warning": t["warning"],
        }
        kwargs.setdefault("text_color", color_map.get(style, t["fg_primary"]))
        kwargs.setdefault("font",       theme.font(style if style in theme.FONTS else "body"))
        super().__init__(master, text=text, **kwargs)


# ── StrengthBar ───────────────────────────────────────────────────────────────

class StrengthBar(ctk.CTkFrame):
    """
    4-segment password strength indicator.
    Call update(score, label, color) after scoring.
    """

    SEGMENTS = 4

    def __init__(self, master, **kwargs):
        t = theme.current()
        kwargs.setdefault("fg_color", "transparent")
        kwargs.setdefault("height",   6)
        super().__init__(master, **kwargs)

        self._bars = []
        for i in range(self.SEGMENTS):
            seg = ctk.CTkFrame(
                self, height=6, corner_radius=3,
                fg_color=t["border"],
            )
            seg.grid(row=0, column=i, padx=2, sticky="ew")
            self.grid_columnconfigure(i, weight=1)
            self._bars.append(seg)

        self._label = ctk.CTkLabel(
            self, text="", font=theme.font("tiny"),
            text_color=t["fg_muted"],
        )
        self._label.grid(row=1, column=0, columnspan=self.SEGMENTS,
                         sticky="w", pady=(2, 0))

    def update_strength(self, score: int, label: str, color: str) -> None:
        t = theme.current()
        for i, bar in enumerate(self._bars):
            bar.configure(fg_color=color if i < score else t["border"])
        self._label.configure(text=label, text_color=color)


# ── SearchBar ─────────────────────────────────────────────────────────────────

class SearchBar(ctk.CTkFrame):
    """Search input with live callback and clear button."""

    def __init__(self, master, on_search: Callable[[str], None], **kwargs):
        t = theme.current()
        kwargs.setdefault("fg_color", t["bg_topbar"])
        kwargs.setdefault("corner_radius", theme.RADIUS_SM)
        super().__init__(master, **kwargs)

        self._var = tk.StringVar()
        self._var.trace_add("write", lambda *_: on_search(self._var.get()))

        self._entry = VroEntry(
            self,
            placeholder="🔍  Buscar credenciales…",
            textvariable=self._var,
        )
        self._entry.pack(fill="x", expand=True, padx=0, pady=0)

    def get(self) -> str:
        return self._var.get()

    def clear(self) -> None:
        self._var.set("")

    def focus(self) -> None:
        self._entry.focus_set()


# ── PasswordField ─────────────────────────────────────────────────────────────

class PasswordField(ctk.CTkFrame):
    """
    A password entry with a toggle-visibility eye button and optional
    timed reveal: after `reveal_seconds` the field auto-hides again.
    """

    def __init__(self, master, placeholder: str = "Contraseña",
                 reveal_seconds: int = 5, **kwargs):
        t = theme.current()
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)

        self._reveal_seconds = reveal_seconds
        self._visible = False
        self._after_id = None

        self._var = tk.StringVar()
        self._entry = VroEntry(
            self,
            placeholder=placeholder,
            show="●",
            textvariable=self._var,
        )
        self._entry.pack(side="left", fill="x", expand=True)

        self._toggle_btn = ctk.CTkButton(
            self, text="👁", width=38, height=38,
            fg_color=t["bg_input"], hover_color=t["bg_card_hover"],
            text_color=t["fg_secondary"], corner_radius=theme.RADIUS_SM,
            command=self._toggle,
        )
        self._toggle_btn.pack(side="left", padx=(4, 0))

    def _toggle(self) -> None:
        if self._after_id is not None:
            self._entry.after_cancel(self._after_id)
            self._after_id = None

        self._visible = not self._visible
        self._entry.configure(show="" if self._visible else "●")
        self._toggle_btn.configure(text="🙈" if self._visible else "👁")

        if self._visible and self._reveal_seconds > 0:
            self._after_id = self._entry.after(
                self._reveal_seconds * 1000, self._auto_hide
            )

    def _auto_hide(self) -> None:
        self._visible = False
        self._entry.configure(show="●")
        self._toggle_btn.configure(text="👁")
        self._after_id = None

    def get(self) -> str:
        return self._var.get()

    def set(self, value: str) -> None:
        self._var.set(value)

    def clear(self) -> None:
        self._var.set("")


# ── NotificationBanner ────────────────────────────────────────────────────────

class NotificationBanner(ctk.CTkFrame):
    """
    Temporary toast-style notification that auto-dismisses.
    Kind: "success" | "danger" | "warning" | "info"
    """

    def __init__(self, master, **kwargs):
        t = theme.current()
        kwargs.setdefault("fg_color", t["bg_card"])
        kwargs.setdefault("corner_radius", theme.RADIUS_SM)
        super().__init__(master, **kwargs)

        self._label = ctk.CTkLabel(
            self, text="", font=theme.font("small"),
            text_color=t["fg_primary"],
        )
        self._label.pack(padx=12, pady=6)
        self._after_id = None
        self.place_forget()

    def show(self, message: str, kind: str = "success", duration_ms: int = 3000) -> None:
        t = theme.current()
        colors = {
            "success": t["success"],
            "danger":  t["danger"],
            "warning": t["warning"],
            "info":    t["info"],
        }
        color = colors.get(kind, t["info"])
        self.configure(fg_color=color)
        self._label.configure(text=message, text_color="#ffffff")

        if self._after_id:
            self.after_cancel(self._after_id)
        self.lift()
        self.place(relx=0.5, rely=0.97, anchor="s")
        self._after_id = self.after(duration_ms, self._hide)

    def _hide(self) -> None:
        self.place_forget()
        self._after_id = None


# ── SidebarItem ───────────────────────────────────────────────────────────────

class SidebarItem(ctk.CTkFrame):
    """A single clickable category item in the sidebar."""

    def __init__(self, master, icon: str, label: str,
                 on_click: Callable, count: int = 0, **kwargs):
        t = theme.current()
        kwargs.setdefault("fg_color", "transparent")
        kwargs.setdefault("corner_radius", theme.RADIUS_SM)
        kwargs.setdefault("height", 40)
        super().__init__(master, **kwargs)

        self._on_click = on_click
        self._active   = False
        self._t        = t

        self._icon_lbl = ctk.CTkLabel(
            self, text=icon, font=theme.font("body"), width=28,
            text_color=t["sidebar_text"],
        )
        self._icon_lbl.pack(side="left", padx=(8, 4))

        self._name_lbl = ctk.CTkLabel(
            self, text=label, font=theme.font("body"), anchor="w",
            text_color=t["sidebar_text"],
        )
        self._name_lbl.pack(side="left", fill="x", expand=True)

        if count > 0:
            self._count_lbl = ctk.CTkLabel(
                self, text=str(count), font=theme.font("tiny"),
                fg_color=t["accent_light"], text_color=t["accent_glow"],
                corner_radius=10, width=24, height=18,
            )
            self._count_lbl.pack(side="right", padx=8)

        for w in (self, self._icon_lbl, self._name_lbl):
            w.bind("<Button-1>", lambda _: self._on_click(), add="+")
            w.bind("<Enter>",    lambda _: self._on_enter(), add="+")
            w.bind("<Leave>",    lambda _: self._on_leave(), add="+")

    def set_active(self, active: bool) -> None:
        t = theme.current()
        self._active = active
        color     = t["sidebar_active"]   if active else "transparent"
        txt_color = t["sidebar_active_text"] if active else t["sidebar_text"]
        self.configure(fg_color=color)
        self._icon_lbl.configure(text_color=txt_color)
        self._name_lbl.configure(text_color=txt_color)

    def _on_enter(self) -> None:
        if not self._active:
            self.configure(fg_color=self._t["bg_card_hover"])

    def _on_leave(self) -> None:
        if not self._active:
            self.configure(fg_color="transparent")

    def update_count(self, count: int) -> None:
        pass   # extended separately if needed


# ── CredentialCard ────────────────────────────────────────────────────────────

class CredentialCard(VroCard):
    """
    Compact credential row used in the main list.
    Shows service icon, name, username, strength dot, and action buttons.
    """

    def __init__(self, master, cred: dict, strength_color: str,
                 on_copy: Callable, on_edit: Callable,
                 on_delete: Callable, on_favorite: Callable, **kwargs):
        super().__init__(master, **kwargs)
        t = theme.current()

        # Left: icon + text
        icon_char = self._pick_icon(cred.get("service", ""))
        icon = ctk.CTkLabel(
            self, text=icon_char, font=theme.font("heading"),
            width=40, text_color=t["accent"],
        )
        icon.grid(row=0, column=0, rowspan=2, padx=(12, 6), pady=10, sticky="ns")

        svc = ctk.CTkLabel(
            self, text=cred.get("service", ""), font=theme.font("subhead"),
            text_color=t["fg_primary"], anchor="w",
        )
        svc.grid(row=0, column=1, sticky="w", pady=(10, 0))

        user = ctk.CTkLabel(
            self, text=cred.get("username", ""), font=theme.font("small"),
            text_color=t["fg_secondary"], anchor="w",
        )
        user.grid(row=1, column=1, sticky="w", pady=(0, 10))

        self.grid_columnconfigure(1, weight=1)

        # Strength dot
        dot = ctk.CTkFrame(
            self, width=10, height=10, corner_radius=5,
            fg_color=strength_color,
        )
        dot.grid(row=0, column=2, padx=4, pady=10, sticky="ne")

        # Fav star
        fav_icon = "★" if cred.get("is_favorite") else "☆"
        fav_btn = ctk.CTkButton(
            self, text=fav_icon, width=30, height=30,
            fg_color="transparent", hover_color=t["bg_card_hover"],
            text_color=t["warning"] if cred.get("is_favorite") else t["fg_muted"],
            font=theme.font("body"), corner_radius=6,
            command=on_favorite,
        )
        fav_btn.grid(row=0, column=3, rowspan=2, padx=2)

        # Copy btn
        copy_btn = ctk.CTkButton(
            self, text="📋", width=30, height=30,
            fg_color="transparent", hover_color=t["accent_light"],
            text_color=t["accent"], font=theme.font("body"),
            corner_radius=6, command=on_copy,
        )
        copy_btn.grid(row=0, column=4, rowspan=2, padx=2)

        # Edit btn
        edit_btn = ctk.CTkButton(
            self, text="✏️", width=30, height=30,
            fg_color="transparent", hover_color=t["bg_card_hover"],
            text_color=t["fg_secondary"], font=theme.font("body"),
            corner_radius=6, command=on_edit,
        )
        edit_btn.grid(row=0, column=5, rowspan=2, padx=2)

        # Delete btn
        del_btn = ctk.CTkButton(
            self, text="🗑", width=30, height=30,
            fg_color="transparent", hover_color="#3d0f0f",
            text_color=t["danger"], font=theme.font("body"),
            corner_radius=6, command=on_delete,
        )
        del_btn.grid(row=0, column=6, rowspan=2, padx=(2, 10))

    @staticmethod
    def _pick_icon(service: str) -> str:
        name = service.lower()
        MAP = {
            "google": "🌐", "gmail": "📧", "youtube": "▶️",
            "github": "🐙", "git": "🐙",
            "steam": "🎮", "epic": "🎮", "riot": "🎮",
            "discord": "💬", "whatsapp": "💬", "telegram": "💬",
            "netflix": "📺", "spotify": "🎵", "disney": "🎬",
            "amazon": "📦", "paypal": "💳", "bank": "🏦",
            "ssh": "🔑", "server": "🖥️", "db": "🗄️",
            "wifi": "📡", "router": "📡",
            "facebook": "📘", "instagram": "📸", "twitter": "🐦", "x": "🐦",
            "linkedin": "💼", "microsoft": "🪟", "apple": "🍎",
            "openai": "🤖", "claude": "🤖",
        }
        for key, icon in MAP.items():
            if key in name:
                return icon
        return "🔐"


# ── ModalDialog ───────────────────────────────────────────────────────────────

class ModalDialog(ctk.CTkToplevel):
    """
    Base class for modal dialogs.
    Subclasses override _build_body() to add content.
    """

    def __init__(self, parent, title: str = "VroVault", width: int = 480,
                 height: int = 400):
        super().__init__(parent)
        t = theme.current()

        self.title(title)
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)
        self.configure(fg_color=t["bg_modal"])

        # On Wayland the window is not immediately "viewable".
        # We must wait for Tk to fully map the window before calling
        # grab_set(), otherwise we get "grab failed: window not viewable".
        # update_idletasks() flushes pending geometry, then after(150) gives
        # the compositor time to actually display the window.
        self.update_idletasks()
        self.after(150, self._activate_modal)

        # Center relative to parent
        self.after(10, lambda: self._center(parent))

        # Title bar
        header = ctk.CTkFrame(self, fg_color=t["bg_topbar"], corner_radius=0, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text=title, font=theme.font("subhead"),
            text_color=t["fg_primary"],
        ).pack(side="left", padx=16, pady=12)

        ctk.CTkButton(
            header, text="✕", width=32, height=32,
            fg_color="transparent", hover_color=t["danger"],
            text_color=t["fg_secondary"], font=theme.font("body"),
            corner_radius=6, command=self.destroy,
        ).pack(side="right", padx=8, pady=9)

        self._body = ctk.CTkFrame(self, fg_color="transparent")
        self._body.pack(fill="both", expand=True, padx=20, pady=16)

        self._build_body(self._body)

    def _activate_modal(self) -> None:
        """Called after window is fully mapped — safe to grab on Wayland."""
        try:
            self.grab_set()
            self.focus_set()
        except Exception:
            pass  # best-effort on unusual WMs

    def _build_body(self, frame: ctk.CTkFrame) -> None:
        """Override in subclasses."""
        pass

    def _center(self, parent) -> None:
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        sw = self.winfo_width()
        sh = self.winfo_height()
        x  = px + (pw - sw) // 2
        y  = py + (ph - sh) // 2
        self.geometry(f"+{x}+{y}")
