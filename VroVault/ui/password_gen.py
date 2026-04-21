"""
VroVault - Password Generator Dialog
=======================================
Pro password generator with configurable options,
live strength preview, and one-click apply.
"""

import tkinter as tk
import customtkinter as ctk
from typing import Callable

import ui.theme as theme
from ui.components import VroButton, VroLabel, StrengthBar, ModalDialog
from core.crypto import generate_secure_password
from utils.audit import score_password
from utils.clipboard import copy_secure


class PasswordGenDialog(ModalDialog):
    """
    Standalone password generator.
    `on_use(password)` is called when the user clicks "Usar contraseña".
    If `on_use` is None the dialog only offers copy-to-clipboard.
    """

    def __init__(self, parent, on_use: Callable[[str], None] | None = None):
        self._on_use   = on_use
        self._pw_var   = tk.StringVar()
        super().__init__(parent, title="🔑  Generador de contraseñas", width=480, height=460)
        self._generate()

    # ── Body ──────────────────────────────────────────────────────────────────

    def _build_body(self, frame: ctk.CTkFrame) -> None:
        t = theme.current()
        frame.columnconfigure(0, weight=1)

        # ── Generated password display ──
        pw_display_frame = ctk.CTkFrame(
            frame, fg_color=t["bg_input"], corner_radius=theme.RADIUS_SM,
            border_width=1, border_color=t["border"],
        )
        pw_display_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        pw_display_frame.columnconfigure(0, weight=1)

        self._pw_lbl = ctk.CTkLabel(
            pw_display_frame,
            textvariable=self._pw_var,
            font=("Cascadia Code", 14, "bold"),
            text_color=t["accent_glow"],
            wraplength=340,
        )
        self._pw_lbl.grid(row=0, column=0, padx=12, pady=12, sticky="ew")

        # ── Strength bar ──
        self._strength_bar = StrengthBar(frame)
        self._strength_bar.grid(row=1, column=0, sticky="ew", pady=(0, 16))

        # ── Length slider ──
        VroLabel(frame, text="Longitud de la contraseña", style="small").grid(
            row=2, column=0, sticky="w", pady=(0, 2))

        len_row = ctk.CTkFrame(frame, fg_color="transparent")
        len_row.grid(row=3, column=0, sticky="ew")
        len_row.columnconfigure(0, weight=1)

        self._len_var = tk.IntVar(value=20)
        slider = ctk.CTkSlider(
            len_row,
            from_=8, to=64,
            variable=self._len_var,
            number_of_steps=56,
            progress_color=t["accent"],
            button_color=t["accent"],
            button_hover_color=t["accent_hover"],
            command=lambda _: self._on_option_change(),
        )
        slider.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self._len_lbl = ctk.CTkLabel(
            len_row, textvariable=self._len_var,
            font=theme.font("subhead"), text_color=t["accent"],
            width=30,
        )
        self._len_lbl.grid(row=0, column=1)

        # ── Character class options ──
        opts_frame = ctk.CTkFrame(frame, fg_color="transparent")
        opts_frame.grid(row=4, column=0, sticky="ew", pady=(12, 0))

        self._upper_var  = tk.BooleanVar(value=True)
        self._lower_var  = tk.BooleanVar(value=True)
        self._digit_var  = tk.BooleanVar(value=True)
        self._symbol_var = tk.BooleanVar(value=True)
        self._ambig_var  = tk.BooleanVar(value=False)

        def _chk(parent, text, var, col):
            ctk.CTkCheckBox(
                parent, text=text, variable=var,
                font=theme.font("small"), text_color=t["fg_secondary"],
                command=self._on_option_change,
                checkmark_color=t["fg_on_accent"],
                fg_color=t["accent"], hover_color=t["accent_hover"],
            ).grid(row=0, column=col, padx=6, sticky="w")

        opts_frame.columnconfigure((0, 1, 2, 3, 4), weight=1)
        _chk(opts_frame, "A-Z",       self._upper_var,  0)
        _chk(opts_frame, "a-z",       self._lower_var,  1)
        _chk(opts_frame, "0-9",       self._digit_var,  2)
        _chk(opts_frame, "!@#…",      self._symbol_var, 3)
        _chk(opts_frame, "Sin ambig.", self._ambig_var, 4)

        # ── Action buttons ──
        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.grid(row=5, column=0, sticky="ew", pady=(16, 0))
        btn_row.columnconfigure((0, 1, 2), weight=1)

        VroButton(btn_row, text="🔄  Regenerar", variant="secondary",
                  command=self._generate).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        VroButton(btn_row, text="📋  Copiar", variant="secondary",
                  command=self._copy).grid(row=0, column=1, sticky="ew", padx=4)

        if self._on_use:
            VroButton(btn_row, text="✓  Usar", variant="primary",
                      command=self._use).grid(row=0, column=2, sticky="ew", padx=(4, 0))

        # Feedback label
        self._fb_lbl = ctk.CTkLabel(
            frame, text="", font=theme.font("tiny"), text_color=t["success"],
        )
        self._fb_lbl.grid(row=6, column=0, pady=(8, 0))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _generate(self) -> None:
        try:
            pw = generate_secure_password(
                length=self._len_var.get() if hasattr(self, "_len_var") else 20,
                use_upper=self._upper_var.get()  if hasattr(self, "_upper_var")  else True,
                use_lower=self._lower_var.get()  if hasattr(self, "_lower_var")  else True,
                use_digits=self._digit_var.get() if hasattr(self, "_digit_var")  else True,
                use_symbols=self._symbol_var.get() if hasattr(self, "_symbol_var") else True,
                exclude_ambiguous=self._ambig_var.get() if hasattr(self, "_ambig_var") else False,
            )
        except ValueError as e:
            pw = ""
            if hasattr(self, "_fb_lbl"):
                self._fb_lbl.configure(text=str(e),
                                        text_color=theme.current()["danger"])
            return

        self._pw_var.set(pw)
        self._update_strength(pw)

    def _update_strength(self, pw: str) -> None:
        if hasattr(self, "_strength_bar"):
            sc = score_password(pw)
            self._strength_bar.update_strength(sc["score"], sc["label"], sc["color"])

    def _on_option_change(self) -> None:
        self._generate()

    def _copy(self) -> None:
        pw = self._pw_var.get()
        if pw:
            copy_secure(pw, clear_after_seconds=30)
            if hasattr(self, "_fb_lbl"):
                self._fb_lbl.configure(
                    text="✓ Copiado al portapapeles (se borrará en 30s)",
                    text_color=theme.current()["success"],
                )

    def _use(self) -> None:
        pw = self._pw_var.get()
        if pw and self._on_use:
            self.destroy()
            self._on_use(pw)
