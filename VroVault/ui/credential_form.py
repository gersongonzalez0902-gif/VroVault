"""
VroVault - Credential Form Dialog
====================================
Modal dialog for adding and editing credentials.
Includes inline password generator, strength bar, and URL/notes fields.
"""

import tkinter as tk
import customtkinter as ctk
from typing import Callable, Optional, Dict, Any, List

import ui.theme as theme
from ui.components import (
    VroButton, VroLabel, VroEntry, PasswordField,
    StrengthBar, ModalDialog,
)
from utils.audit import score_password
from core.crypto import generate_secure_password


class CredentialFormDialog(ModalDialog):
    """
    Add / Edit credential dialog.

    On save, calls `on_save(data_dict)` where data_dict keys match
    VaultDB.add_credential / update_credential arguments.
    """

    def __init__(
        self,
        parent,
        categories: List[Dict[str, Any]],
        on_save: Callable[[Dict[str, Any]], None],
        existing: Optional[Dict[str, Any]] = None,
        default_category_id: Optional[int] = None,
    ):
        self._categories    = categories
        self._on_save       = on_save
        self._existing      = existing   # None = new credential
        self._def_cat_id    = default_category_id

        title = "Editar credencial" if existing else "Nueva credencial"
        super().__init__(parent, title=title, width=520, height=580)

    # ── Body ──────────────────────────────────────────────────────────────────

    def _build_body(self, frame: ctk.CTkFrame) -> None:
        t = theme.current()
        frame.columnconfigure(0, weight=1)

        row = 0

        # Category selector
        VroLabel(frame, text="Categoría", style="small").grid(
            row=row, column=0, sticky="w", pady=(0, 2))
        row += 1

        cat_names  = [f"{c['icon']} {c['name']}" for c in self._categories]
        self._cat_map = {f"{c['icon']} {c['name']}": c["id"] for c in self._categories}

        default_cat = cat_names[0] if cat_names else ""
        if self._existing:
            for c in self._categories:
                if c["id"] == self._existing.get("category_id"):
                    default_cat = f"{c['icon']} {c['name']}"
                    break
        elif self._def_cat_id:
            for c in self._categories:
                if c["id"] == self._def_cat_id:
                    default_cat = f"{c['icon']} {c['name']}"
                    break

        self._cat_var = tk.StringVar(value=default_cat)
        ctk.CTkOptionMenu(
            frame,
            variable=self._cat_var,
            values=cat_names,
            fg_color=t["bg_input"],
            button_color=t["accent"],
            button_hover_color=t["accent_hover"],
            text_color=t["fg_primary"],
            dropdown_fg_color=t["bg_card"],
            dropdown_hover_color=t["bg_card_hover"],
            dropdown_text_color=t["fg_primary"],
            corner_radius=theme.RADIUS_SM,
            height=38,
        ).grid(row=row, column=0, sticky="ew")
        row += 1

        # Service
        VroLabel(frame, text="Servicio / Sitio", style="small").grid(
            row=row, column=0, sticky="w", pady=(10, 2))
        row += 1
        self._svc_var = tk.StringVar(value=self._existing.get("service", "") if self._existing else "")
        VroEntry(frame, placeholder="Google, Netflix, Steam…",
                 textvariable=self._svc_var).grid(row=row, column=0, sticky="ew")
        row += 1

        # Username
        VroLabel(frame, text="Usuario / Email", style="small").grid(
            row=row, column=0, sticky="w", pady=(10, 2))
        row += 1
        self._user_var = tk.StringVar(value=self._existing.get("username", "") if self._existing else "")
        VroEntry(frame, placeholder="usuario@email.com",
                 textvariable=self._user_var).grid(row=row, column=0, sticky="ew")
        row += 1

        # Password row
        VroLabel(frame, text="Contraseña", style="small").grid(
            row=row, column=0, sticky="w", pady=(10, 2))
        row += 1

        pw_outer = ctk.CTkFrame(frame, fg_color="transparent")
        pw_outer.grid(row=row, column=0, sticky="ew")
        pw_outer.columnconfigure(0, weight=1)

        self._pw_field = PasswordField(pw_outer, placeholder="Contraseña…", reveal_seconds=5)
        self._pw_field.grid(row=0, column=0, sticky="ew")
        if self._existing:
            self._pw_field.set(self._existing.get("password", ""))

        # Bind strength update on typing
        self._pw_field._var.trace_add("write", lambda *_: self._update_strength())

        gen_btn = VroButton(
            pw_outer, text="⚙️", variant="secondary", width=38, height=38,
            command=self._open_generator,
        )
        gen_btn.grid(row=0, column=1, padx=(4, 0))
        row += 1

        # Strength bar
        self._strength_bar = StrengthBar(frame)
        self._strength_bar.grid(row=row, column=0, sticky="ew", pady=(4, 0))
        row += 1
        self._update_strength()

        # URL
        VroLabel(frame, text="URL (opcional)", style="small").grid(
            row=row, column=0, sticky="w", pady=(10, 2))
        row += 1
        self._url_var = tk.StringVar(value=self._existing.get("url", "") if self._existing else "")
        VroEntry(frame, placeholder="https://…",
                 textvariable=self._url_var).grid(row=row, column=0, sticky="ew")
        row += 1

        # Notes
        VroLabel(frame, text="Notas seguras (opcional)", style="small").grid(
            row=row, column=0, sticky="w", pady=(10, 2))
        row += 1

        self._notes_text = ctk.CTkTextbox(
            frame, height=70, corner_radius=theme.RADIUS_SM,
            fg_color=t["bg_input"], border_color=t["border"],
            border_width=1, text_color=t["fg_primary"],
            font=theme.font("body"),
        )
        self._notes_text.grid(row=row, column=0, sticky="ew")
        if self._existing and self._existing.get("notes"):
            self._notes_text.insert("1.0", self._existing["notes"])
        row += 1

        # Error label
        self._err = ctk.CTkLabel(
            frame, text="", font=theme.font("small"),
            text_color=t["danger"],
        )
        self._err.grid(row=row, column=0, pady=(6, 0))
        row += 1

        # Save button
        label = "Guardar cambios ✓" if self._existing else "Guardar credencial ✓"
        VroButton(frame, text=label, variant="primary",
                  command=self._save).grid(row=row, column=0, sticky="ew", pady=(4, 0))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _update_strength(self) -> None:
        pw  = self._pw_field.get()
        sc  = score_password(pw)
        self._strength_bar.update_strength(sc["score"], sc["label"], sc["color"])

    def _open_generator(self) -> None:
        from ui.password_gen import PasswordGenDialog
        def _apply(pw: str):
            self._pw_field.set(pw)
            self._update_strength()
        PasswordGenDialog(self, on_use=_apply)

    def _save(self) -> None:
        cat_name = self._cat_var.get()
        cat_id   = self._cat_map.get(cat_name)
        service  = self._svc_var.get().strip()
        username = self._user_var.get().strip()
        password = self._pw_field.get()
        url      = self._url_var.get().strip()
        notes    = self._notes_text.get("1.0", "end-1c").strip()

        if not service:
            self._err.configure(text="El nombre del servicio es obligatorio.")
            return
        if not username:
            self._err.configure(text="El usuario/email es obligatorio.")
            return
        if not password:
            self._err.configure(text="La contraseña no puede estar vacía.")
            return
        if cat_id is None:
            self._err.configure(text="Selecciona una categoría válida.")
            return

        data = {
            "category_id": cat_id,
            "service":     service,
            "username":    username,
            "password":    password,
            "url":         url,
            "notes":       notes,
        }
        self.destroy()
        self._on_save(data)
