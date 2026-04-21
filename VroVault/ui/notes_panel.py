"""
VroVault - Secure Notes Panel
================================
Panel embedded in the main window for managing encrypted secure notes.
"""

import tkinter as tk
import customtkinter as ctk
from typing import Callable, Optional, Dict, Any, List

import ui.theme as theme
from ui.components import VroButton, VroLabel, VroCard, VroEntry, ModalDialog


class NotesPanel(ctk.CTkFrame):
    """
    Notes panel: list on the left, editor on the right.
    Receives a `vault` (VaultDB) reference and a `reset_lock` callable.
    """

    def __init__(self, master, vault, reset_lock: Callable, **kwargs):
        t = theme.current()
        kwargs.setdefault("fg_color", t["bg_root"])
        super().__init__(master, **kwargs)

        self._vault      = vault
        self._reset_lock = reset_lock
        self._active_id: Optional[int] = None

        self._build()
        self._load_notes()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        t = theme.current()
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # ── Left panel: list ──
        left = ctk.CTkFrame(self, fg_color=t["bg_sidebar"], width=260, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_propagate(False)
        left.rowconfigure(1, weight=1)

        # Header + new button
        top = ctk.CTkFrame(left, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        top.columnconfigure(0, weight=1)

        VroLabel(top, text="📝  Notas seguras", style="heading").grid(
            row=0, column=0, sticky="w")

        VroButton(top, text="➕", variant="primary", width=36, height=32,
                  command=self._new_note).grid(row=0, column=1)

        # Scrollable note list
        self._note_list = ctk.CTkScrollableFrame(
            left, fg_color="transparent",
        )
        self._note_list.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 8))
        self._note_list.columnconfigure(0, weight=1)

        # ── Right panel: editor ──
        right = ctk.CTkFrame(self, fg_color=t["bg_root"], corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        # Editor header
        edit_top = ctk.CTkFrame(right, fg_color=t["bg_topbar"], height=52, corner_radius=0)
        edit_top.grid(row=0, column=0, sticky="ew")
        edit_top.grid_propagate(False)
        edit_top.columnconfigure(0, weight=1)

        self._title_var = tk.StringVar()
        self._title_entry = ctk.CTkEntry(
            edit_top, textvariable=self._title_var,
            placeholder_text="Título de la nota…",
            fg_color="transparent", border_width=0,
            text_color=t["fg_primary"], font=theme.font("heading"),
            height=50,
        )
        self._title_entry.grid(row=0, column=0, sticky="ew", padx=12)

        btn_right = ctk.CTkFrame(edit_top, fg_color="transparent")
        btn_right.grid(row=0, column=1, padx=8)

        self._save_btn = VroButton(btn_right, text="💾  Guardar", variant="primary",
                                    width=110, command=self._save_note)
        self._save_btn.pack(side="left", padx=2)

        self._del_btn = VroButton(btn_right, text="🗑", variant="danger",
                                   width=38, command=self._delete_note)
        self._del_btn.pack(side="left", padx=2)

        # Editor body
        self._body_text = ctk.CTkTextbox(
            right,
            fg_color=t["bg_root"],
            text_color=t["fg_primary"],
            font=("Cascadia Code", 13),
            border_width=0,
            corner_radius=0,
            wrap="word",
        )
        self._body_text.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)

        self._set_editor_state(False)

    # ── Notes CRUD ────────────────────────────────────────────────────────────

    def _load_notes(self) -> None:
        for w in self._note_list.winfo_children():
            w.destroy()

        notes = self._vault.list_notes()
        if not notes:
            VroLabel(self._note_list, text="Sin notas.\nPulsa ➕ para crear una.",
                     style="muted").grid(row=0, column=0, pady=20)
            return

        for idx, note in enumerate(notes):
            card = _NoteListItem(
                self._note_list, note=note,
                on_select=lambda n=note: self._open_note(n),
                is_active=(note["id"] == self._active_id),
            )
            card.grid(row=idx, column=0, sticky="ew", pady=2)

    def _open_note(self, note: Dict[str, Any]) -> None:
        self._reset_lock()
        self._active_id = note["id"]
        self._title_var.set(note["title"])
        self._body_text.delete("1.0", "end")
        self._body_text.insert("1.0", note["body"])
        self._set_editor_state(True)
        self._load_notes()  # refresh active highlight

    def _new_note(self) -> None:
        self._reset_lock()
        self._active_id = None
        self._title_var.set("")
        self._body_text.delete("1.0", "end")
        self._set_editor_state(True)
        self._title_entry.focus_set()

    def _save_note(self) -> None:
        self._reset_lock()
        title = self._title_var.get().strip()
        body  = self._body_text.get("1.0", "end-1c").strip()
        if not title:
            return
        if self._active_id is None:
            nid = self._vault.add_note(title, body)
            self._active_id = nid
        else:
            self._vault.update_note(self._active_id, title, body)
        self._load_notes()

    def _delete_note(self) -> None:
        if self._active_id is None:
            return
        self._reset_lock()
        self._vault.delete_note(self._active_id)
        self._active_id = None
        self._title_var.set("")
        self._body_text.delete("1.0", "end")
        self._set_editor_state(False)
        self._load_notes()

    def _set_editor_state(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self._title_entry.configure(state=state)
        self._body_text.configure(state=state)
        self._save_btn.configure(state="normal" if enabled else "disabled")
        self._del_btn.configure(
            state="normal" if (enabled and self._active_id) else "disabled"
        )

    def refresh(self) -> None:
        self._load_notes()


# ── _NoteListItem ─────────────────────────────────────────────────────────────

class _NoteListItem(ctk.CTkFrame):
    def __init__(self, master, note: Dict[str, Any],
                 on_select: Callable, is_active: bool, **kwargs):
        t = theme.current()
        bg = t["sidebar_active"] if is_active else "transparent"
        kwargs.setdefault("fg_color",      bg)
        kwargs.setdefault("corner_radius", theme.RADIUS_SM)
        super().__init__(master, **kwargs)

        title_color = t["sidebar_active_text"] if is_active else t["fg_primary"]
        date_str    = note.get("updated_at", "")[:10]

        ctk.CTkLabel(
            self, text=note["title"], font=theme.font("small"),
            text_color=title_color, anchor="w",
        ).pack(fill="x", padx=10, pady=(6, 0))

        ctk.CTkLabel(
            self, text=date_str, font=theme.font("tiny"),
            text_color=t["fg_muted"], anchor="w",
        ).pack(fill="x", padx=10, pady=(0, 6))

        self.bind("<Button-1>", lambda _: on_select(), add="+")
        for child in self.winfo_children():
            child.bind("<Button-1>", lambda _: on_select(), add="+")

        if not is_active:
            self.bind("<Enter>", lambda _: self.configure(fg_color=t["bg_card_hover"]), add="+")
            self.bind("<Leave>", lambda _: self.configure(fg_color="transparent"), add="+")
