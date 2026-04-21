"""
VroVault - Main Vault Window
"""
import tkinter as tk
import customtkinter as ctk
from typing import Optional, Dict, Any, List
import threading

import ui.theme as theme
from ui.components import (
    VroButton, VroLabel, VroCard, SearchBar, SidebarItem,
    CredentialCard, NotificationBanner,
)
from ui.credential_form import CredentialFormDialog
from ui.password_gen import PasswordGenDialog
from ui.notes_panel import NotesPanel
from ui.stats_panel import StatsPanel
from utils.clipboard import copy_secure, clear_now
from utils.audit import score_password, audit_credentials
from utils.autolock import AutoLockTimer
from core.profiles import Profile, ProfileManager
from core.database import VaultDB


PANIC_KEY = "<Control-Shift-Delete>"


class MainWindow(ctk.CTkFrame):
    """
    Root frame shown after successful authentication.
    Layout: sidebar (left) | topbar + content (right).
    """

    def __init__(self, master, vault: VaultDB, profile: Profile,
                 pm: ProfileManager, on_logout, **kwargs):
        t = theme.current()
        kwargs.setdefault("fg_color", t["bg_root"])
        super().__init__(master, **kwargs)

        self._vault      = vault
        self._profile    = profile
        self._pm         = pm
        self._on_logout  = on_logout

        self._active_cat_id: Optional[int] = None  # None = All
        self._active_section = "vault"             # vault | notes | stats
        self._discrete_mode  = False
        self._search_query   = ""

        # Auto-lock
        lock_secs = profile.auto_lock_mins * 60
        self._autolock = AutoLockTimer(timeout_seconds=lock_secs,
                                       on_lock=self._trigger_lock)
        self._autolock.start()

        self._build()
        self._load_sidebar()
        self._show_vault()

        # Bind panic key and activity tracking to the real Tk root window.
        # CTkFrame prohibits bind_all(), so we use winfo_toplevel() which
        # returns the underlying tkinter.Tk instance (no restrictions).
        root = master.winfo_toplevel()
        root.bind(PANIC_KEY,  lambda _: self._panic(), add="+")
        root.bind("<Motion>", lambda _: self._autolock.reset(), add="+")
        root.bind("<Key>",    lambda _: self._autolock.reset(), add="+")
        root.bind("<Button>", lambda _: self._autolock.reset(), add="+")

    # ─── Build skeleton ───────────────────────────────────────────────────────

    def _build(self) -> None:
        t = theme.current()
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # ── Sidebar ──
        self._sidebar = ctk.CTkFrame(
            self, fg_color=t["bg_sidebar"], width=230, corner_radius=0,
        )
        self._sidebar.grid(row=0, column=0, sticky="nsew")
        self._sidebar.grid_propagate(False)
        self._sidebar.rowconfigure(2, weight=1)

        # Sidebar logo
        logo_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent", height=64)
        logo_frame.grid(row=0, column=0, sticky="ew")
        logo_frame.grid_propagate(False)
        ctk.CTkLabel(
            logo_frame, text="🔐 VroVault",
            font=theme.font("heading"), text_color=t["fg_primary"],
        ).pack(side="left", padx=16, pady=18)

        # Profile badge
        prof_frame = ctk.CTkFrame(
            self._sidebar, fg_color=t["bg_card"],
            corner_radius=theme.RADIUS, height=52,
        )
        prof_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        prof_frame.grid_propagate(False)
        ctk.CTkLabel(
            prof_frame, text=self._profile.icon,
            font=("Segoe UI Emoji", 20),
        ).pack(side="left", padx=10, pady=12)
        ctk.CTkLabel(
            prof_frame, text=self._profile.name,
            font=theme.font("small"), text_color=t["fg_primary"],
        ).pack(side="left")
        VroButton(
            prof_frame, text="🔓", variant="ghost", width=30, height=30,
            command=self._logout,
        ).pack(side="right", padx=6)

        # Nav items container (scrollable for many categories)
        self._nav_scroll = ctk.CTkScrollableFrame(
            self._sidebar, fg_color="transparent",
        )
        self._nav_scroll.grid(row=2, column=0, sticky="nsew", padx=4, pady=4)
        self._nav_scroll.columnconfigure(0, weight=1)

        # Bottom actions
        bot = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        bot.grid(row=3, column=0, sticky="ew", padx=10, pady=10)
        bot.columnconfigure(0, weight=1)

        btns = [
            ("📝  Notas", "ghost", self._show_notes),
            ("📊  Estadísticas", "ghost", self._show_stats),
            ("🔑  Generador", "ghost", self._open_generator),
            ("🕶️  Modo discreto", "ghost", self._toggle_discrete),
        ]
        for i, (txt, var, cmd) in enumerate(btns):
            VroButton(bot, text=txt, variant=var, command=cmd,
                      anchor="w").grid(row=i, column=0, sticky="ew", pady=1)

        # Theme toggle + panic
        bot2 = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        bot2.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 12))
        bot2.columnconfigure((0, 1), weight=1)
        VroButton(bot2, text="🌙/☀️", variant="ghost",
                  command=self._toggle_theme).grid(row=0, column=0, sticky="ew", padx=2)
        VroButton(bot2, text="⚠️ Pánico", variant="danger",
                  command=self._panic).grid(row=0, column=1, sticky="ew", padx=2)

        # ── Main content area ──
        self._content_area = ctk.CTkFrame(self, fg_color=t["bg_root"], corner_radius=0)
        self._content_area.grid(row=0, column=1, sticky="nsew")
        self._content_area.columnconfigure(0, weight=1)
        self._content_area.rowconfigure(1, weight=1)

        # Top bar
        topbar = ctk.CTkFrame(
            self._content_area, fg_color=t["bg_topbar"],
            height=56, corner_radius=0,
        )
        topbar.grid(row=0, column=0, sticky="ew")
        topbar.grid_propagate(False)
        topbar.columnconfigure(0, weight=1)

        self._search = SearchBar(topbar, on_search=self._on_search)
        self._search.grid(row=0, column=0, sticky="ew", padx=12, pady=10)

        VroButton(topbar, text="➕  Nueva", variant="primary",
                  command=self._open_add_form).grid(row=0, column=1, padx=(0, 12), pady=10)

        # Content placeholder
        self._panel_frame = ctk.CTkFrame(
            self._content_area, fg_color="transparent", corner_radius=0,
        )
        self._panel_frame.grid(row=1, column=0, sticky="nsew")
        self._panel_frame.columnconfigure(0, weight=1)
        self._panel_frame.rowconfigure(0, weight=1)

        # Notification banner (overlay)
        self._banner = NotificationBanner(self)

    # ─── Sidebar nav ─────────────────────────────────────────────────────────

    def _load_sidebar(self) -> None:
        for w in self._nav_scroll.winfo_children():
            w.destroy()

        categories = self._vault.list_categories()
        all_creds  = self._vault.list_credentials()

        # Count per category
        count_map: Dict[int, int] = {}
        for c in all_creds:
            cid = c.get("category_id", 0)
            count_map[cid] = count_map.get(cid, 0) + 1

        # "All credentials" item
        self._nav_all = SidebarItem(
            self._nav_scroll, icon="🔐", label="Todas",
            on_click=lambda: self._select_category(None),
            count=len(all_creds),
        )
        self._nav_all.grid(row=0, column=0, sticky="ew", pady=1)

        # Favourites
        fav_count = sum(1 for c in all_creds if c.get("is_favorite"))
        self._nav_fav = SidebarItem(
            self._nav_scroll, icon="⭐", label="Favoritos",
            on_click=lambda: self._select_favorites(),
            count=fav_count,
        )
        self._nav_fav.grid(row=1, column=0, sticky="ew", pady=1)

        # Separator label
        ctk.CTkLabel(
            self._nav_scroll, text="CATEGORÍAS",
            font=theme.font("tiny"), text_color=theme.current()["fg_muted"],
            anchor="w",
        ).grid(row=2, column=0, sticky="ew", padx=12, pady=(10, 2))

        # Category items
        self._sidebar_items: List[SidebarItem] = []
        for i, cat in enumerate(categories):
            item = SidebarItem(
                self._nav_scroll, icon=cat["icon"], label=cat["name"],
                on_click=lambda cid=cat["id"]: self._select_category(cid),
                count=count_map.get(cat["id"], 0),
            )
            item.grid(row=i + 3, column=0, sticky="ew", pady=1)
            item._cat_id = cat["id"]
            self._sidebar_items.append(item)

        # "Add category" button
        VroButton(
            self._nav_scroll, text="➕  Nueva categoría", variant="ghost",
            command=self._add_category, anchor="w",
        ).grid(row=len(categories) + 3, column=0, sticky="ew", padx=4, pady=(8, 0))

        self._update_sidebar_active()

    def _select_category(self, cat_id: Optional[int]) -> None:
        self._active_cat_id    = cat_id
        self._active_section   = "vault"
        self._search.clear()
        self._show_vault()
        self._update_sidebar_active()

    def _select_favorites(self) -> None:
        self._active_cat_id    = "fav"   # type: ignore
        self._active_section   = "vault"
        self._search.clear()
        self._show_vault()
        self._update_sidebar_active()

    def _update_sidebar_active(self) -> None:
        is_all = self._active_cat_id is None
        is_fav = self._active_cat_id == "fav"
        self._nav_all.set_active(is_all and self._active_section == "vault")
        self._nav_fav.set_active(is_fav)
        for item in self._sidebar_items:
            item.set_active(
                item._cat_id == self._active_cat_id
                and self._active_section == "vault"
            )

    # ─── Panel switching ─────────────────────────────────────────────────────

    def _clear_panel(self) -> None:
        for w in self._panel_frame.winfo_children():
            w.destroy()

    def _show_vault(self) -> None:
        self._active_section = "vault"
        self._clear_panel()
        self._render_credential_list()

    def _show_notes(self) -> None:
        self._active_section = "notes"
        self._clear_panel()
        self._update_sidebar_active()
        panel = NotesPanel(self._panel_frame, vault=self._vault,
                           reset_lock=self._autolock.reset)
        panel.grid(row=0, column=0, sticky="nsew")

    def _show_stats(self) -> None:
        self._active_section = "stats"
        self._clear_panel()
        self._update_sidebar_active()
        panel = StatsPanel(self._panel_frame, vault=self._vault,
                           reset_lock=self._autolock.reset)
        panel.grid(row=0, column=0, sticky="nsew")

    # ─── Credential list ─────────────────────────────────────────────────────

    def _render_credential_list(self) -> None:
        t = theme.current()
        frame = self._panel_frame

        # Get credentials
        q = self._search_query.strip()
        if q:
            creds = self._vault.search_credentials(q)
        elif self._active_cat_id == "fav":
            creds = [c for c in self._vault.list_credentials() if c.get("is_favorite")]
        elif self._active_cat_id is not None:
            creds = self._vault.list_credentials(category_id=self._active_cat_id)
        else:
            creds = self._vault.list_credentials()

        # Audit for strength colours
        audit  = audit_credentials(creds)
        sc_map = audit.get("per_credential", {})

        scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        scroll.columnconfigure(0, weight=1)

        if not creds:
            empty = ctk.CTkFrame(scroll, fg_color="transparent")
            empty.grid(row=0, column=0, pady=60)
            ctk.CTkLabel(
                empty, text="🔒",
                font=("Segoe UI Emoji", 48), text_color=t["fg_muted"],
            ).pack()
            ctk.CTkLabel(
                empty,
                text="No hay credenciales aquí.\nPulsa ➕ Nueva para agregar.",
                font=theme.font("body"), text_color=t["fg_muted"], justify="center",
            ).pack(pady=8)
            return

        for idx, cred in enumerate(creds):
            sc    = sc_map.get(cred["id"], {})
            color = sc.get("color", t["fg_muted"])
            cid   = cred["id"]

            card = CredentialCard(
                scroll, cred=cred, strength_color=color,
                on_copy=lambda c=cred: self._copy_password(c),
                on_edit=lambda c=cred: self._open_edit_form(c),
                on_delete=lambda c=cred: self._delete_credential(c),
                on_favorite=lambda c=cred: self._toggle_favorite(c),
            )
            card.grid(row=idx, column=0, sticky="ew", pady=4)

    def _on_search(self, query: str) -> None:
        self._search_query = query
        self._autolock.reset()
        if self._active_section == "vault":
            self._clear_panel()
            self._render_credential_list()

    # ─── Credential CRUD ─────────────────────────────────────────────────────

    def _open_add_form(self) -> None:
        self._autolock.reset()
        cats = self._vault.list_categories()
        def _save(data: Dict[str, Any]):
            self._vault.add_credential(**data)
            self._refresh_vault()
            self._banner.show("✓ Credencial guardada", "success")
        CredentialFormDialog(
            self, categories=cats, on_save=_save,
            default_category_id=self._active_cat_id
            if isinstance(self._active_cat_id, int) else None,
        )

    def _open_edit_form(self, cred: Dict[str, Any]) -> None:
        self._autolock.reset()
        cats = self._vault.list_categories()
        def _save(data: Dict[str, Any]):
            self._vault.update_credential(cred["id"], **data)
            self._refresh_vault()
            self._banner.show("✓ Cambios guardados", "success")
        CredentialFormDialog(self, categories=cats, on_save=_save, existing=cred)

    def _delete_credential(self, cred: Dict[str, Any]) -> None:
        self._autolock.reset()
        dlg = _ConfirmDialog(
            self,
            title="Eliminar credencial",
            message=f"¿Eliminar '{cred.get('service', '')}' permanentemente?",
            on_confirm=lambda: self._do_delete(cred["id"]),
        )

    def _do_delete(self, cred_id: int) -> None:
        self._vault.delete_credential(cred_id)
        self._refresh_vault()
        self._banner.show("🗑 Credencial eliminada", "warning")

    def _copy_password(self, cred: Dict[str, Any]) -> None:
        self._autolock.reset()
        pw = cred.get("password", "")
        if copy_secure(pw, clear_after_seconds=30):
            svc = cred.get("service", "")
            self._banner.show(f"📋 Contraseña de {svc} copiada (30s)", "success")

    def _toggle_favorite(self, cred: Dict[str, Any]) -> None:
        self._autolock.reset()
        new_state = self._vault.toggle_favorite(cred["id"])
        msg = "⭐ Añadido a favoritos" if new_state else "☆ Eliminado de favoritos"
        self._banner.show(msg, "info")
        self._refresh_vault()

    def _refresh_vault(self) -> None:
        self._load_sidebar()
        if self._active_section == "vault":
            self._clear_panel()
            self._render_credential_list()

    # ─── Categories ──────────────────────────────────────────────────────────

    def _add_category(self) -> None:
        self._autolock.reset()
        _AddCategoryDialog(self, on_create=lambda name, icon: self._do_add_category(name, icon))

    def _do_add_category(self, name: str, icon: str) -> None:
        self._vault.add_category(name, icon)
        self._load_sidebar()

    # ─── Misc actions ─────────────────────────────────────────────────────────

    def _open_generator(self) -> None:
        self._autolock.reset()
        PasswordGenDialog(self)

    def _toggle_discrete(self) -> None:
        self._discrete_mode = not self._discrete_mode
        title = self.winfo_toplevel().title()
        if self._discrete_mode:
            self.winfo_toplevel().title("Sistema")
            self._banner.show("🕶️ Modo discreto activado", "info")
        else:
            self.winfo_toplevel().title("VroVault")
            self._banner.show("Modo discreto desactivado", "info")

    def _toggle_theme(self) -> None:
        root = self.winfo_toplevel()
        theme.toggle(root)
        self._banner.show("Tema cambiado", "info")

    def _panic(self) -> None:
        """Immediate lock + clear clipboard."""
        clear_now()
        self._autolock.stop()
        self._trigger_lock()

    def _trigger_lock(self) -> None:
        self._autolock.stop()
        self._vault.close()
        root = self.winfo_toplevel()
        root.after(0, lambda: self._on_logout())

    def _logout(self) -> None:
        self._autolock.stop()
        clear_now()
        self._vault.close()
        self._on_logout()

    def destroy(self) -> None:
        self._autolock.stop()
        super().destroy()


# ─── Helper dialogs ───────────────────────────────────────────────────────────

class _ConfirmDialog(ctk.CTkToplevel):
    def __init__(self, parent, title: str, message: str, on_confirm):
        super().__init__(parent)
        t = theme.current()
        self.title(title)
        self.geometry("380x180")
        self.resizable(False, False)
        self.configure(fg_color=t["bg_modal"])
        self.update_idletasks()
        self.after(150, self._activate)

        ctk.CTkLabel(self, text=message, font=theme.font("body"),
                     text_color=t["fg_primary"], wraplength=340).pack(pady=30, padx=20)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack()
        VroButton(btn_row, text="Cancelar", variant="secondary",
                  command=self.destroy).pack(side="left", padx=8)
        VroButton(btn_row, text="Eliminar", variant="danger",
                  command=lambda: [self.destroy(), on_confirm()]).pack(side="left", padx=8)

        self._center(parent)

    def _activate(self) -> None:
        try:
            self.grab_set()
            self.focus_set()
        except Exception:
            pass

    def _center(self, parent) -> None:
        self.after(10, lambda: self.geometry(
            f"+{parent.winfo_rootx() + (parent.winfo_width() - 380) // 2}"
            f"+{parent.winfo_rooty() + (parent.winfo_height() - 180) // 2}"
        ))


class _AddCategoryDialog(ctk.CTkToplevel):
    ICONS = ["📁", "🌐", "🎮", "📱", "📺", "🤖", "🎓", "💳", "🛠️", "🏠",
             "🔑", "⭐", "🔥", "💼", "🎵", "🎬", "🚀", "🏦", "📡", "🗄️"]

    def __init__(self, parent, on_create):
        super().__init__(parent)
        t = theme.current()
        self._on_create = on_create
        self._icon = "📁"
        self.title("Nueva categoría")
        self.geometry("380x280")
        self.resizable(False, False)
        self.configure(fg_color=t["bg_modal"])
        self.update_idletasks()
        self.after(150, self._activate)

    def _activate(self) -> None:
        try:
            self.grab_set()
            self.focus_set()
        except Exception:
            pass

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        frame.columnconfigure(0, weight=1)

        VroLabel(frame, text="Nombre", style="small").grid(row=0, column=0, sticky="w")
        self._name_var = tk.StringVar()
        from ui.components import VroEntry
        VroEntry(frame, placeholder="Nombre de categoría",
                 textvariable=self._name_var).grid(row=1, column=0, sticky="ew")

        VroLabel(frame, text="Icono", style="small").grid(
            row=2, column=0, sticky="w", pady=(10, 2))

        icon_scroll = ctk.CTkScrollableFrame(frame, height=80, fg_color="transparent")
        icon_scroll.grid(row=3, column=0, sticky="ew")
        for i, ic in enumerate(self.ICONS):
            ctk.CTkButton(
                icon_scroll, text=ic, width=36, height=36,
                font=("Segoe UI Emoji", 18),
                fg_color=t["bg_card"], hover_color=t["accent_light"],
                text_color=t["fg_primary"], corner_radius=6,
                command=lambda x=ic: self._set_icon(x),
            ).grid(row=0, column=i, padx=2)

        self._icon_lbl = ctk.CTkLabel(frame, text=self._icon,
                                       font=("Segoe UI Emoji", 24))
        self._icon_lbl.grid(row=4, column=0, pady=6)

        from ui.components import VroButton as VB
        VB(frame, text="Crear categoría", variant="primary",
           command=self._create).grid(row=5, column=0, sticky="ew")

        self._center(parent)

    def _set_icon(self, icon: str) -> None:
        self._icon = icon
        self._icon_lbl.configure(text=icon)

    def _create(self) -> None:
        name = self._name_var.get().strip()
        if name:
            self.destroy()
            self._on_create(name, self._icon)

    def _center(self, parent) -> None:
        self.after(10, lambda: self.geometry(
            f"+{parent.winfo_rootx() + (parent.winfo_width() - 380) // 2}"
            f"+{parent.winfo_rooty() + (parent.winfo_height() - 280) // 2}"
        ))
