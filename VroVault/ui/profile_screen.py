"""
VroVault - Profile Selection Screen
=====================================
The first screen the user sees: pick a profile, create one, or enter
a secret phrase to reveal hidden profiles.
"""

import tkinter as tk
import customtkinter as ctk
from typing import Callable, Optional

import ui.theme as theme
from ui.components import VroButton, VroLabel, VroCard, VroEntry, ModalDialog
from core.profiles import ProfileManager, Profile, ProfileError


PROFILE_ICONS = ["👤", "👩", "👨", "🧑", "🧒", "👶", "🦸", "🧙", "🧝", "🤖",
                  "🐱", "🐶", "🦊", "🦁", "🐼", "🦄", "🚀", "⭐", "🔥", "💎"]


class ProfileScreen(ctk.CTkFrame):
    """
    Full-window profile selection / creation widget.
    Calls `on_profile_selected(profile, key)` when a profile is authenticated.
    """

    def __init__(self, master, pm: ProfileManager,
                 on_profile_selected: Callable[[Profile, bytes], None],
                 **kwargs):
        t = theme.current()
        kwargs.setdefault("fg_color", t["bg_root"])
        super().__init__(master, **kwargs)

        self._pm       = pm
        self._callback = on_profile_selected
        self._show_hidden = False

        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        t = theme.current()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # ── Header ──
        header = ctk.CTkFrame(self, fg_color=t["bg_topbar"], height=64, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        ctk.CTkLabel(
            header, text="🔐  VroVault",
            font=theme.font("title"), text_color=t["fg_primary"],
        ).pack(side="left", padx=24, pady=16)

        ctk.CTkLabel(
            header, text="Gestor de credenciales seguro",
            font=theme.font("small"), text_color=t["fg_secondary"],
        ).pack(side="left", pady=16)

        # Theme toggle
        VroButton(
            header, text="☀️  Modo claro", variant="ghost",
            command=self._toggle_theme,
        ).pack(side="right", padx=16, pady=14)

        # ── Center area ──
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.grid(row=1, column=0, sticky="nsew")
        center.columnconfigure(0, weight=1)
        center.rowconfigure(1, weight=1)

        ctk.CTkLabel(
            center, text="Selecciona un perfil",
            font=theme.font("heading"), text_color=t["fg_primary"],
        ).grid(row=0, column=0, pady=(32, 8))

        # Scrollable profiles area
        self._grid_frame = ctk.CTkScrollableFrame(
            center, fg_color="transparent", scrollbar_button_color=t["border"],
        )
        self._grid_frame.grid(row=1, column=0, sticky="nsew", padx=40, pady=8)
        self._grid_frame.columnconfigure((0, 1, 2, 3), weight=1)

        # Bottom row — buttons
        btn_row = ctk.CTkFrame(center, fg_color="transparent")
        btn_row.grid(row=2, column=0, pady=20)

        VroButton(btn_row, text="➕  Nuevo perfil", variant="primary",
                  command=self._open_create_dialog).pack(side="left", padx=8)
        VroButton(btn_row, text="🔒  Mostrar ocultos", variant="ghost",
                  command=self._open_hidden_dialog).pack(side="left", padx=8)

        self._refresh_grid()

    def _refresh_grid(self) -> None:
        """Re-render the profile cards grid."""
        for w in self._grid_frame.winfo_children():
            w.destroy()

        profiles = self._pm.list_profiles(include_hidden=self._show_hidden)

        if not profiles:
            VroLabel(
                self._grid_frame,
                text="No hay perfiles.\nCrea uno nuevo para comenzar.",
                style="muted",
            ).grid(row=0, column=0, columnspan=4, pady=40)
            return

        for idx, profile in enumerate(profiles):
            row, col = divmod(idx, 4)
            card = _ProfileCard(
                self._grid_frame, profile=profile,
                on_select=lambda p=profile: self._open_login(p),
            )
            card.grid(row=row, column=col, padx=10, pady=10, sticky="ew")

    def _open_login(self, profile: Profile) -> None:
        dlg = _LoginDialog(self, profile, self._pm, self._callback)

    def _open_create_dialog(self) -> None:
        dlg = _CreateProfileDialog(self, self._pm,
                                   on_created=self._refresh_grid)

    def _open_hidden_dialog(self) -> None:
        dlg = _RevealHiddenDialog(self, self._pm,
                                  on_reveal=self._on_reveal_hidden)

    def _on_reveal_hidden(self, phrase: str) -> None:
        """Secret phrase to reveal hidden profiles: 'mostertame'."""
        if phrase.strip().lower() == "mostertame":
            self._show_hidden = True
            self._refresh_grid()

    def _toggle_theme(self) -> None:
        import ui.theme as th
        master = self.winfo_toplevel()
        new_mode = th.toggle(master)
        master.after(50, lambda: self._rebuild_after_theme())

    def _rebuild_after_theme(self) -> None:
        """Soft-rebuild: destroy & recreate children after theme toggle."""
        for w in self.winfo_children():
            w.destroy()
        self._build()


# ── _ProfileCard ─────────────────────────────────────────────────────────────

class _ProfileCard(VroCard):
    def __init__(self, master, profile: Profile, on_select: Callable, **kwargs):
        super().__init__(master, hover=True, **kwargs)
        t = theme.current()

        # configure fixed size
        self.configure(width=150, height=150)

        icon = ctk.CTkLabel(
            self, text=profile.icon, font=("Segoe UI Emoji", 36),
            text_color=t["accent"],
        )
        icon.pack(pady=(20, 4))

        name = ctk.CTkLabel(
            self, text=profile.name, font=theme.font("subhead"),
            text_color=t["fg_primary"],
        )
        name.pack()

        tag = ctk.CTkLabel(
            self, text="🔒 Oculto" if profile.is_hidden else
                       ("🎭 Señuelo" if profile.is_decoy else ""),
            font=theme.font("tiny"), text_color=t["warning"],
        )
        tag.pack()

        for w in (self, icon, name, tag):
            w.bind("<Button-1>", lambda _: on_select(), add="+")


# ── _LoginDialog ─────────────────────────────────────────────────────────────

class _LoginDialog(ModalDialog):
    def __init__(self, parent, profile: Profile, pm: ProfileManager,
                 on_success: Callable):
        self._profile    = profile
        self._pm         = pm
        self._on_success = on_success
        self._attempts   = 0
        super().__init__(parent, title=f"Acceder — {profile.name}", width=420, height=340)

    def _build_body(self, frame: ctk.CTkFrame) -> None:
        t = theme.current()

        ctk.CTkLabel(
            frame, text=self._profile.icon,
            font=("Segoe UI Emoji", 40),
        ).pack(pady=(8, 4))

        ctk.CTkLabel(
            frame, text=self._profile.name,
            font=theme.font("heading"), text_color=t["fg_primary"],
        ).pack()

        ctk.CTkLabel(
            frame, text="Introduce tu contraseña maestra:",
            font=theme.font("small"), text_color=t["fg_secondary"],
        ).pack(pady=(16, 6))

        self._pw_var = tk.StringVar()
        pw_entry = ctk.CTkEntry(
            frame, textvariable=self._pw_var, show="●",
            placeholder_text="Contraseña maestra…",
            fg_color=t["bg_input"], border_color=t["border"],
            text_color=t["fg_primary"], height=38, corner_radius=6,
        )
        pw_entry.pack(fill="x")
        pw_entry.focus_set()
        pw_entry.bind("<Return>", lambda _: self._submit())

        self._err_label = ctk.CTkLabel(
            frame, text="", font=theme.font("small"), text_color=t["danger"],
        )
        self._err_label.pack(pady=6)

        VroButton(frame, text="Desbloquear 🔓", variant="primary",
                  command=self._submit).pack(fill="x", pady=(4, 0))

    def _submit(self) -> None:
        pw = self._pw_var.get()
        if not pw:
            self._show_err("Introduce la contraseña.")
            return
        try:
            key = self._pm.authenticate(self._profile.id, pw)
            if key is None:
                self._attempts += 1
                remaining = self._profile.max_attempts - self._profile.failed_attempts
                self._show_err(f"Contraseña incorrecta. Intentos restantes: {remaining}")
            else:
                self.destroy()
                self._on_success(self._profile, key)
        except ProfileError as e:
            self._show_err(str(e))

    def _show_err(self, msg: str) -> None:
        self._err_label.configure(text=msg)


# ── _CreateProfileDialog ──────────────────────────────────────────────────────

class _CreateProfileDialog(ModalDialog):
    def __init__(self, parent, pm: ProfileManager, on_created: Callable):
        self._pm        = pm
        self._on_created = on_created
        self._icon      = "👤"
        super().__init__(parent, title="Nuevo perfil", width=480, height=520)

    def _build_body(self, frame: ctk.CTkFrame) -> None:
        t = theme.current()
        frame.columnconfigure(0, weight=1)

        VroLabel(frame, text="Nombre del perfil", style="small").grid(
            row=0, column=0, sticky="w", pady=(0, 2))
        self._name_var = tk.StringVar()
        VroEntry(frame, placeholder="Mi perfil", textvariable=self._name_var
                 ).grid(row=1, column=0, sticky="ew")

        VroLabel(frame, text="Icono", style="small").grid(
            row=2, column=0, sticky="w", pady=(12, 2))
        icon_row = ctk.CTkFrame(frame, fg_color="transparent")
        icon_row.grid(row=3, column=0, sticky="ew")
        self._icon_lbl = ctk.CTkLabel(icon_row, text=self._icon,
                                       font=("Segoe UI Emoji", 28))
        self._icon_lbl.pack(side="left", padx=(0, 8))
        VroButton(icon_row, text="Elegir icono", variant="secondary",
                  command=self._pick_icon).pack(side="left")

        VroLabel(frame, text="Contraseña maestra", style="small").grid(
            row=4, column=0, sticky="w", pady=(12, 2))
        self._pw_var = tk.StringVar()
        self._pw_entry = ctk.CTkEntry(
            frame, textvariable=self._pw_var, show="●",
            placeholder_text="Mín. 8 caracteres recomendado",
            fg_color=t["bg_input"], border_color=t["border"],
            text_color=t["fg_primary"], height=38, corner_radius=6,
        )
        self._pw_entry.grid(row=5, column=0, sticky="ew")

        VroLabel(frame, text="Confirmar contraseña", style="small").grid(
            row=6, column=0, sticky="w", pady=(8, 2))
        self._pw2_var = tk.StringVar()
        ctk.CTkEntry(
            frame, textvariable=self._pw2_var, show="●",
            placeholder_text="Repite la contraseña",
            fg_color=t["bg_input"], border_color=t["border"],
            text_color=t["fg_primary"], height=38, corner_radius=6,
        ).grid(row=7, column=0, sticky="ew")

        # Options row
        opts = ctk.CTkFrame(frame, fg_color="transparent")
        opts.grid(row=8, column=0, sticky="ew", pady=(12, 0))
        self._hidden_var  = tk.BooleanVar()
        self._decoy_var   = tk.BooleanVar()
        self._destroy_var = tk.BooleanVar()
        ctk.CTkCheckBox(opts, text="Perfil oculto",     variable=self._hidden_var,
                        font=theme.font("small"), text_color=t["fg_secondary"]).pack(side="left", padx=4)
        ctk.CTkCheckBox(opts, text="Señuelo",           variable=self._decoy_var,
                        font=theme.font("small"), text_color=t["fg_secondary"]).pack(side="left", padx=4)
        ctk.CTkCheckBox(opts, text="Autodestruir",      variable=self._destroy_var,
                        font=theme.font("small"), text_color=t["fg_secondary"]).pack(side="left", padx=4)

        self._err_lbl = ctk.CTkLabel(frame, text="", font=theme.font("small"),
                                      text_color=t["danger"])
        self._err_lbl.grid(row=9, column=0, pady=6)

        VroButton(frame, text="Crear perfil ✓", variant="primary",
                  command=self._create).grid(row=10, column=0, sticky="ew")

    def _pick_icon(self) -> None:
        dlg = _IconPickerDialog(self, on_pick=self._set_icon)

    def _set_icon(self, icon: str) -> None:
        self._icon = icon
        self._icon_lbl.configure(text=icon)

    def _create(self) -> None:
        name = self._name_var.get().strip()
        pw   = self._pw_var.get()
        pw2  = self._pw2_var.get()

        if not name:
            self._err_lbl.configure(text="El nombre no puede estar vacío.")
            return
        if len(pw) < 6:
            self._err_lbl.configure(text="La contraseña debe tener mín. 6 caracteres.")
            return
        if pw != pw2:
            self._err_lbl.configure(text="Las contraseñas no coinciden.")
            return

        try:
            self._pm.create_profile(
                name=name, master_password=pw, icon=self._icon,
                is_hidden=self._hidden_var.get(),
                is_decoy=self._decoy_var.get(),
                destroy_on_max=self._destroy_var.get(),
            )
            self.destroy()
            self._on_created()
        except ProfileError as e:
            self._err_lbl.configure(text=str(e))


# ── _IconPickerDialog ─────────────────────────────────────────────────────────

class _IconPickerDialog(ModalDialog):
    def __init__(self, parent, on_pick: Callable[[str], None]):
        self._on_pick = on_pick
        super().__init__(parent, title="Elige un icono", width=340, height=260)

    def _build_body(self, frame: ctk.CTkFrame) -> None:
        t = theme.current()
        frame.columnconfigure(list(range(5)), weight=1)
        for idx, icon in enumerate(PROFILE_ICONS):
            row, col = divmod(idx, 5)
            btn = ctk.CTkButton(
                frame, text=icon, width=48, height=48,
                font=("Segoe UI Emoji", 24),
                fg_color=t["bg_card"], hover_color=t["accent_light"],
                text_color=t["fg_primary"], corner_radius=8,
                command=lambda i=icon: self._pick(i),
            )
            btn.grid(row=row, column=col, padx=4, pady=4)

    def _pick(self, icon: str) -> None:
        self._on_pick(icon)
        self.destroy()


# ── _RevealHiddenDialog ───────────────────────────────────────────────────────

class _RevealHiddenDialog(ModalDialog):
    def __init__(self, parent, pm: ProfileManager, on_reveal: Callable):
        self._on_reveal = on_reveal
        super().__init__(parent, title="Revelar perfiles ocultos", width=380, height=220)

    def _build_body(self, frame: ctk.CTkFrame) -> None:
        t = theme.current()
        ctk.CTkLabel(
            frame,
            text="Introduce la frase secreta\npara revelar perfiles ocultos:",
            font=theme.font("small"), text_color=t["fg_secondary"],
            justify="center",
        ).pack(pady=(0, 12))

        self._phrase_var = tk.StringVar()
        entry = ctk.CTkEntry(
            frame, textvariable=self._phrase_var, show="●",
            placeholder_text="Frase secreta…",
            fg_color=t["bg_input"], border_color=t["border"],
            text_color=t["fg_primary"], height=38, corner_radius=6,
        )
        entry.pack(fill="x")
        entry.focus_set()
        entry.bind("<Return>", lambda _: self._submit())

        VroButton(frame, text="Revelar", variant="primary",
                  command=self._submit).pack(fill="x", pady=(12, 0))

    def _submit(self) -> None:
        self._on_reveal(self._phrase_var.get())
        self.destroy()
