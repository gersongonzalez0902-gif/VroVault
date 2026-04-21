"""
VroVault - Theme Engine
========================
Centralized color tokens, font sizes, and helper functions.
Supports dark / light mode toggling via CustomTkinter.
"""

import customtkinter as ctk
from typing import Literal

# ── Appearance ───────────────────────────────────────────────────────────────

INITIAL_APPEARANCE: Literal["dark", "light"] = "dark"
INITIAL_COLOR_THEME = "blue"   # base ctk theme (we override palette below)

# ── Palette — Dark ───────────────────────────────────────────────────────────

DARK = {
    # Backgrounds
    "bg_root":        "#0f1117",
    "bg_sidebar":     "#151822",
    "bg_card":        "#1c2030",
    "bg_card_hover":  "#222840",
    "bg_input":       "#1a1f2e",
    "bg_modal":       "#161b27",
    "bg_topbar":      "#13171f",

    # Foregrounds
    "fg_primary":     "#f0f2f8",
    "fg_secondary":   "#8892b0",
    "fg_muted":       "#4a5568",
    "fg_on_accent":   "#ffffff",

    # Accent — cobalt blue
    "accent":         "#2563eb",
    "accent_hover":   "#1d4ed8",
    "accent_light":   "#1e3a6e",
    "accent_glow":    "#3b82f6",

    # Semantic colours
    "success":        "#10b981",
    "warning":        "#f59e0b",
    "danger":         "#ef4444",
    "info":           "#06b6d4",

    # Strength colours (matching audit.py)
    "str_0":          "#ef4444",
    "str_1":          "#f97316",
    "str_2":          "#eab308",
    "str_3":          "#22c55e",
    "str_4":          "#16a34a",

    # Borders
    "border":         "#252d40",
    "border_focus":   "#2563eb",

    # Sidebar item states
    "sidebar_active": "#1e2d4a",
    "sidebar_text":   "#8892b0",
    "sidebar_active_text": "#f0f2f8",
}

# ── Palette — Light ──────────────────────────────────────────────────────────

LIGHT = {
    "bg_root":        "#f5f7fa",
    "bg_sidebar":     "#ffffff",
    "bg_card":        "#ffffff",
    "bg_card_hover":  "#eef2ff",
    "bg_input":       "#f1f5f9",
    "bg_modal":       "#ffffff",
    "bg_topbar":      "#ffffff",

    "fg_primary":     "#0f172a",
    "fg_secondary":   "#475569",
    "fg_muted":       "#94a3b8",
    "fg_on_accent":   "#ffffff",

    "accent":         "#2563eb",
    "accent_hover":   "#1d4ed8",
    "accent_light":   "#dbeafe",
    "accent_glow":    "#3b82f6",

    "success":        "#059669",
    "warning":        "#d97706",
    "danger":         "#dc2626",
    "info":           "#0284c7",

    "str_0":          "#dc2626",
    "str_1":          "#ea580c",
    "str_2":          "#ca8a04",
    "str_3":          "#16a34a",
    "str_4":          "#15803d",

    "border":         "#e2e8f0",
    "border_focus":   "#2563eb",

    "sidebar_active": "#dbeafe",
    "sidebar_text":   "#475569",
    "sidebar_active_text": "#1e40af",
}

# ── Fonts ─────────────────────────────────────────────────────────────────────

FONTS = {
    "title":    ("Inter", 22, "bold"),
    "heading":  ("Inter", 16, "bold"),
    "subhead":  ("Inter", 13, "bold"),
    "body":     ("Inter", 13, "normal"),
    "small":    ("Inter", 11, "normal"),
    "tiny":     ("Inter", 10, "normal"),
    "mono":     ("Cascadia Code", 12, "normal"),
    "icon":     ("Segoe UI Emoji", 18, "normal"),
}

# ── Sizes ─────────────────────────────────────────────────────────────────────

RADIUS    = 10   # corner radius (px)
RADIUS_SM = 6
RADIUS_LG = 14
PAD       = 16
PAD_SM    = 8
PAD_LG    = 24

# ── Runtime state ─────────────────────────────────────────────────────────────

_mode: Literal["dark", "light"] = INITIAL_APPEARANCE


def current() -> dict:
    """Return the active palette dict."""
    return DARK if _mode == "dark" else LIGHT


def is_dark() -> bool:
    return _mode == "dark"


def apply(app: ctk.CTk) -> None:
    """Apply the current theme mode to the CTk application."""
    ctk.set_appearance_mode(_mode)
    ctk.set_default_color_theme(INITIAL_COLOR_THEME)


def toggle(app: ctk.CTk) -> Literal["dark", "light"]:
    """Toggle between dark and light mode and return the new mode."""
    global _mode
    _mode = "light" if _mode == "dark" else "dark"
    ctk.set_appearance_mode(_mode)
    return _mode


def set_mode(mode: Literal["dark", "light"], app: ctk.CTk | None = None) -> None:
    global _mode
    _mode = mode
    ctk.set_appearance_mode(_mode)


def c(key: str) -> str:
    """Shorthand — return a color from the active palette."""
    return current().get(key, "#ff00ff")   # magenta = missing key (dev signal)


def font(key: str) -> tuple:
    """Shorthand — return a font tuple."""
    return FONTS.get(key, FONTS["body"])
