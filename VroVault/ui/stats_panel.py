"""
VroVault - Statistics & Audit Panel
=====================================
Displays vault stats, password strength distribution,
duplicate detection, and weak password list.
"""

import tkinter as tk
import customtkinter as ctk
from typing import Callable, Dict, Any, List

import ui.theme as theme
from ui.components import VroCard, VroLabel, VroButton
from utils.audit import audit_credentials, STRENGTH_LABELS, STRENGTH_COLORS


class StatsPanel(ctk.CTkFrame):
    """
    Statistics and security audit panel.
    Receives `vault` (VaultDB) and `reset_lock` callable.
    """

    def __init__(self, master, vault, reset_lock: Callable, **kwargs):
        t = theme.current()
        kwargs.setdefault("fg_color", t["bg_root"])
        super().__init__(master, **kwargs)

        self._vault      = vault
        self._reset_lock = reset_lock

        self._build()
        self.refresh()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        t = theme.current()
        self.columnconfigure(0, weight=1)

        # ── Top header ──
        header = ctk.CTkFrame(self, fg_color=t["bg_topbar"], height=52, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.columnconfigure(0, weight=1)

        VroLabel(header, text="📊  Estadísticas y Auditoría", style="heading").grid(
            row=0, column=0, padx=16, pady=14, sticky="w")

        VroButton(header, text="🔄  Actualizar", variant="ghost",
                  command=self.refresh).grid(row=0, column=1, padx=12)

        # ── Scrollable content ──
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
        )
        self._scroll.grid(row=1, column=0, sticky="nsew", padx=16, pady=16)
        self._scroll.columnconfigure((0, 1, 2, 3), weight=1)
        self.rowconfigure(1, weight=1)

    # ── Refresh (re-renders entire content) ───────────────────────────────────

    def refresh(self) -> None:
        self._reset_lock()
        for w in self._scroll.winfo_children():
            w.destroy()

        t = theme.current()
        db_stats  = self._vault.get_stats()
        all_creds = self._vault.list_credentials()
        audit     = audit_credentials(all_creds)

        row = 0

        # ── Summary cards row ──
        cards_data = [
            ("🔐", str(db_stats["total_credentials"]), "Credenciales", t["accent"]),
            ("⭐", str(db_stats["favorites"]),         "Favoritos",    t["warning"]),
            ("📝", str(db_stats["secure_notes"]),      "Notas seguras",t["info"]),
            ("📁", str(db_stats["categories"]),        "Categorías",   t["success"]),
        ]
        for col, (icon, value, label, color) in enumerate(cards_data):
            self._summary_card(self._scroll, icon, value, label, color).grid(
                row=row, column=col, padx=6, pady=6, sticky="ew")
        row += 1

        # ── Average security score ──
        avg   = audit["average_score"]
        avg_pct = int(avg / 4 * 100)
        avg_color = STRENGTH_COLORS[int(min(avg, 3.9))]

        avg_card = VroCard(self._scroll, hover=False)
        avg_card.grid(row=row, column=0, columnspan=4, sticky="ew", padx=6, pady=6)
        avg_card.columnconfigure(0, weight=1)

        VroLabel(avg_card, text="🛡️  Nivel de seguridad promedio del vault",
                 style="subhead").grid(row=0, column=0, padx=14, pady=(12, 6), sticky="w")

        bar_frame = ctk.CTkFrame(avg_card, fg_color="transparent")
        bar_frame.grid(row=1, column=0, padx=14, pady=(0, 12), sticky="ew")
        bar_frame.columnconfigure(0, weight=1)

        pbar = ctk.CTkProgressBar(
            bar_frame, height=12, corner_radius=6,
            progress_color=avg_color,
            fg_color=t["border"],
        )
        pbar.set(avg / 4)
        pbar.grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(
            bar_frame,
            text=f"{avg_pct}%  —  {STRENGTH_LABELS[int(min(avg, 3.9))]}",
            font=theme.font("small"), text_color=avg_color,
        ).grid(row=0, column=1, padx=(10, 0))

        row += 1

        # ── Strength distribution ──
        dist_card = VroCard(self._scroll, hover=False)
        dist_card.grid(row=row, column=0, columnspan=4, sticky="ew", padx=6, pady=6)
        dist_card.columnconfigure(list(range(len(STRENGTH_LABELS))), weight=1)

        VroLabel(dist_card, text="📈  Distribución de fortaleza",
                 style="subhead").grid(row=0, column=0, columnspan=5,
                                       padx=14, pady=(12, 8), sticky="w")

        dist = audit["strength_dist"]
        total = max(db_stats["total_credentials"], 1)
        for i, (label, color) in enumerate(zip(STRENGTH_LABELS, STRENGTH_COLORS)):
            count = dist.get(label, 0)
            pct   = count / total

            col_frame = ctk.CTkFrame(dist_card, fg_color="transparent")
            col_frame.grid(row=1, column=i, padx=10, pady=(0, 14), sticky="ew")

            ctk.CTkLabel(col_frame, text=str(count), font=theme.font("heading"),
                         text_color=color).pack()
            ctk.CTkLabel(col_frame, text=label, font=theme.font("tiny"),
                         text_color=t["fg_muted"]).pack()

            pbar2 = ctk.CTkProgressBar(col_frame, height=6, width=80,
                                        corner_radius=3, progress_color=color,
                                        fg_color=t["border"])
            pbar2.set(pct)
            pbar2.pack(pady=(4, 0))

        row += 1

        # ── Duplicate passwords ──
        dups = audit["duplicates"]
        if dups:
            dup_card = VroCard(self._scroll, hover=False)
            dup_card.grid(row=row, column=0, columnspan=4, sticky="ew", padx=6, pady=6)
            dup_card.columnconfigure(0, weight=1)

            VroLabel(dup_card,
                     text=f"⚠️  Contraseñas duplicadas ({len(dups)} grupos)",
                     style="subhead").grid(row=0, column=0, padx=14, pady=(12, 6), sticky="w")

            for didx, group in enumerate(dups):
                services = ", ".join(c.get("service", "?") for c in group)
                ctk.CTkLabel(
                    dup_card,
                    text=f"  • {services}",
                    font=theme.font("small"), text_color=t["warning"],
                    anchor="w",
                ).grid(row=didx + 1, column=0, padx=14, sticky="w")

            ctk.CTkFrame(dup_card, fg_color="transparent", height=12).grid(
                row=len(dups) + 1, column=0)
            row += 1

        # ── Weak passwords list ──
        weak = audit["weak"]
        if weak:
            weak_card = VroCard(self._scroll, hover=False)
            weak_card.grid(row=row, column=0, columnspan=4, sticky="ew", padx=6, pady=6)
            weak_card.columnconfigure(0, weight=1)

            VroLabel(weak_card,
                     text=f"🔴  Contraseñas débiles ({len(weak)})",
                     style="subhead").grid(row=0, column=0, padx=14, pady=(12, 6), sticky="w")

            for widx, cred in enumerate(weak):
                svc  = cred.get("service", "?")
                user = cred.get("username", "")
                sc   = audit["per_credential"].get(cred["id"], {})
                lbl  = sc.get("label", "")
                color = sc.get("color", t["danger"])

                row_f = ctk.CTkFrame(weak_card, fg_color="transparent")
                row_f.grid(row=widx + 1, column=0, padx=14, sticky="ew")

                ctk.CTkLabel(
                    row_f, text=f"🔐 {svc}  ({user})",
                    font=theme.font("small"), text_color=t["fg_secondary"], anchor="w",
                ).pack(side="left")

                ctk.CTkLabel(
                    row_f, text=lbl, font=theme.font("tiny"),
                    text_color=color, anchor="e",
                ).pack(side="right")

            ctk.CTkFrame(weak_card, fg_color="transparent", height=12).grid(
                row=len(weak) + 1, column=0)
            row += 1

        if not weak and not dups:
            ok_card = VroCard(self._scroll, hover=False)
            ok_card.grid(row=row, column=0, columnspan=4, sticky="ew", padx=6, pady=6)
            ctk.CTkLabel(
                ok_card,
                text="✅  Excelente — no se detectaron contraseñas débiles ni duplicadas.",
                font=theme.font("body"), text_color=t["success"],
            ).pack(padx=14, pady=16)

    # ── Summary card helper ────────────────────────────────────────────────────

    def _summary_card(self, parent, icon: str, value: str,
                      label: str, color: str) -> VroCard:
        t = theme.current()
        card = VroCard(parent, hover=False)

        ctk.CTkLabel(card, text=icon, font=("Segoe UI Emoji", 28),
                     text_color=color).pack(pady=(14, 2))
        ctk.CTkLabel(card, text=value, font=theme.font("title"),
                     text_color=t["fg_primary"]).pack()
        ctk.CTkLabel(card, text=label, font=theme.font("tiny"),
                     text_color=t["fg_muted"]).pack(pady=(0, 14))
        return card
