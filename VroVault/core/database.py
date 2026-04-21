"""
VroVault - Database Layer
=========================
Encrypted SQLite storage. All sensitive fields are encrypted in Python
before being passed to SQLite, so even raw file access yields only ciphertext.
"""

import sqlite3
import json
import base64
import os
import shutil
import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from core.crypto import encrypt_str, decrypt_str, KEY_LEN


# ─── Schema version ──────────────────────────────────────────────────────────
SCHEMA_VERSION = 2


def _get_db_path(data_dir: Path, profile_id: str) -> Path:
    return data_dir / f"vault_{profile_id}.db"


def _get_backup_dir(data_dir: Path) -> Path:
    d = data_dir / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ─── Connection factory ───────────────────────────────────────────────────────

def open_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Harden SQLite: WAL mode for crash safety, memory-mapped I/O off
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA synchronous=FULL;")
    return conn


# ─── Schema initialisation ────────────────────────────────────────────────────

def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS categories (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name_enc   TEXT NOT NULL,
            icon       TEXT NOT NULL DEFAULT '🔑',
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_custom  INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS credentials (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id  INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
            service_enc  TEXT NOT NULL,
            username_enc TEXT NOT NULL,
            password_enc TEXT NOT NULL,
            url_enc      TEXT,
            notes_enc    TEXT,
            is_favorite  INTEGER NOT NULL DEFAULT 0,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS history (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            credential_id INTEGER NOT NULL,
            field         TEXT NOT NULL,
            old_val_enc   TEXT,
            changed_at    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS secure_notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title_enc  TEXT NOT NULL,
            body_enc   TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_cred_category ON credentials(category_id);
    """)
    conn.commit()


# ─── VaultDB class ────────────────────────────────────────────────────────────

class VaultDB:
    """
    High-level interface to an encrypted profile vault.
    All string fields are encrypted with the session key before storage.
    """

    def __init__(self, db_path: Path, key: bytes):
        if len(key) != KEY_LEN:
            raise ValueError("Invalid key length.")
        self.db_path = db_path
        self._key    = key
        self.conn    = open_db(db_path)
        init_schema(self.conn)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _enc(self, value: str) -> str:
        return encrypt_str(value, self._key) if value else ""

    def _dec(self, blob: str) -> str:
        return decrypt_str(blob, self._key) if blob else ""

    def _now(self) -> str:
        return datetime.datetime.utcnow().isoformat()

    # ── Categories ────────────────────────────────────────────────────────────

    def seed_default_categories(self) -> None:
        """Insert default categories if table is empty."""
        count = self.conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if count > 0:
            return
        defaults = [
            ("🌐 Ecosistemas",         "🌐", 0),
            ("🎮 Gaming",               "🎮", 1),
            ("📱 Social & Comunidad",   "📱", 2),
            ("📺 Entretenimiento",      "📺", 3),
            ("🤖 IA & Trabajo",         "🤖", 4),
            ("🎓 Educación",            "🎓", 5),
            ("💳 Finanzas & Shopping",  "💳", 6),
            ("🛠️ Sistemas & Admin",     "🛠️", 7),
            ("🏠 Hogar",                "🏠", 8),
        ]
        for name, icon, order in defaults:
            self.conn.execute(
                "INSERT INTO categories (name_enc, icon, sort_order, is_custom) VALUES (?,?,?,0)",
                (self._enc(name), icon, order),
            )
        self.conn.commit()

    def list_categories(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT id, name_enc, icon, sort_order, is_custom FROM categories ORDER BY sort_order"
        ).fetchall()
        result = []
        for r in rows:
            try:
                name = self._dec(r["name_enc"])
            except Exception:
                name = "???"
            result.append({
                "id": r["id"], "name": name, "icon": r["icon"],
                "sort_order": r["sort_order"], "is_custom": bool(r["is_custom"]),
            })
        return result

    def add_category(self, name: str, icon: str = "🔑") -> int:
        cur = self.conn.execute(
            "SELECT COALESCE(MAX(sort_order),0)+1 FROM categories"
        )
        order = cur.fetchone()[0]
        res = self.conn.execute(
            "INSERT INTO categories (name_enc, icon, sort_order, is_custom) VALUES (?,?,?,1)",
            (self._enc(name), icon, order),
        )
        self.conn.commit()
        return res.lastrowid

    def rename_category(self, cat_id: int, new_name: str) -> None:
        self.conn.execute(
            "UPDATE categories SET name_enc=? WHERE id=?",
            (self._enc(new_name), cat_id),
        )
        self.conn.commit()

    def delete_category(self, cat_id: int) -> None:
        self.conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        self.conn.commit()

    def reorder_category(self, cat_id: int, new_order: int) -> None:
        self.conn.execute(
            "UPDATE categories SET sort_order=? WHERE id=?", (new_order, cat_id)
        )
        self.conn.commit()

    # ── Credentials ───────────────────────────────────────────────────────────

    def _row_to_cred(self, r) -> Dict[str, Any]:
        try:
            return {
                "id":          r["id"],
                "category_id": r["category_id"],
                "service":     self._dec(r["service_enc"]),
                "username":    self._dec(r["username_enc"]),
                "password":    self._dec(r["password_enc"]),
                "url":         self._dec(r["url_enc"])   if r["url_enc"]   else "",
                "notes":       self._dec(r["notes_enc"]) if r["notes_enc"] else "",
                "is_favorite": bool(r["is_favorite"]),
                "created_at":  r["created_at"],
                "updated_at":  r["updated_at"],
            }
        except Exception as e:
            return {"id": r["id"], "service": "[decryption error]", "_error": str(e)}

    def list_credentials(self, category_id: Optional[int] = None) -> List[Dict[str, Any]]:
        if category_id is not None:
            rows = self.conn.execute(
                "SELECT * FROM credentials WHERE category_id=? ORDER BY updated_at DESC",
                (category_id,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM credentials ORDER BY updated_at DESC"
            ).fetchall()
        return [self._row_to_cred(r) for r in rows]

    def search_credentials(self, query: str) -> List[Dict[str, Any]]:
        """Decrypt all and filter in Python (search is post-decryption)."""
        all_creds = self.list_credentials()
        q = query.lower().strip()
        if not q:
            return all_creds
        return [
            c for c in all_creds
            if q in c.get("service", "").lower()
            or q in c.get("username", "").lower()
            or q in c.get("url", "").lower()
            or q in c.get("notes", "").lower()
        ]

    def add_credential(
        self,
        category_id: int,
        service: str,
        username: str,
        password: str,
        url: str = "",
        notes: str = "",
    ) -> int:
        now = self._now()
        res = self.conn.execute(
            """INSERT INTO credentials
               (category_id, service_enc, username_enc, password_enc, url_enc, notes_enc,
                is_favorite, created_at, updated_at)
               VALUES (?,?,?,?,?,?,0,?,?)""",
            (
                category_id,
                self._enc(service),
                self._enc(username),
                self._enc(password),
                self._enc(url),
                self._enc(notes),
                now, now,
            ),
        )
        self.conn.commit()
        return res.lastrowid

    def update_credential(self, cred_id: int, **fields) -> None:
        """Update any combination of service/username/password/url/notes/category_id."""
        old = self.get_credential(cred_id)
        if old is None:
            raise ValueError(f"Credential {cred_id} not found.")

        # Log history for password changes
        if "password" in fields and fields["password"] != old["password"]:
            self.conn.execute(
                "INSERT INTO history (credential_id, field, old_val_enc, changed_at) VALUES (?,?,?,?)",
                (cred_id, "password", self._enc(old["password"]), self._now()),
            )

        mapping = {
            "service":     "service_enc",
            "username":    "username_enc",
            "password":    "password_enc",
            "url":         "url_enc",
            "notes":       "notes_enc",
            "category_id": "category_id",
            "is_favorite": "is_favorite",
        }
        sets, vals = [], []
        for field, col in mapping.items():
            if field in fields:
                val = fields[field]
                if field in ("category_id", "is_favorite"):
                    sets.append(f"{col}=?")
                    vals.append(int(val))
                else:
                    sets.append(f"{col}=?")
                    vals.append(self._enc(str(val)))

        if not sets:
            return
        sets.append("updated_at=?")
        vals.append(self._now())
        vals.append(cred_id)
        self.conn.execute(f"UPDATE credentials SET {', '.join(sets)} WHERE id=?", vals)
        self.conn.commit()

    def get_credential(self, cred_id: int) -> Optional[Dict[str, Any]]:
        r = self.conn.execute(
            "SELECT * FROM credentials WHERE id=?", (cred_id,)
        ).fetchone()
        return self._row_to_cred(r) if r else None

    def delete_credential(self, cred_id: int) -> None:
        self.conn.execute("DELETE FROM credentials WHERE id=?", (cred_id,))
        self.conn.commit()

    def toggle_favorite(self, cred_id: int) -> bool:
        r = self.conn.execute(
            "SELECT is_favorite FROM credentials WHERE id=?", (cred_id,)
        ).fetchone()
        if r is None:
            return False
        new_val = 0 if r["is_favorite"] else 1
        self.conn.execute(
            "UPDATE credentials SET is_favorite=? WHERE id=?", (new_val, cred_id)
        )
        self.conn.commit()
        return bool(new_val)

    # ── Credential history ────────────────────────────────────────────────────

    def get_history(self, cred_id: int) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT field, old_val_enc, changed_at FROM history WHERE credential_id=? ORDER BY changed_at DESC",
            (cred_id,),
        ).fetchall()
        result = []
        for r in rows:
            try:
                old_val = self._dec(r["old_val_enc"])
            except Exception:
                old_val = "[error]"
            result.append({"field": r["field"], "old_value": old_val, "changed_at": r["changed_at"]})
        return result

    # ── Secure Notes ──────────────────────────────────────────────────────────

    def list_notes(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT id, title_enc, body_enc, created_at, updated_at FROM secure_notes ORDER BY updated_at DESC"
        ).fetchall()
        result = []
        for r in rows:
            try:
                title = self._dec(r["title_enc"])
                body  = self._dec(r["body_enc"])
            except Exception:
                title, body = "[error]", ""
            result.append({
                "id": r["id"], "title": title, "body": body,
                "created_at": r["created_at"], "updated_at": r["updated_at"],
            })
        return result

    def add_note(self, title: str, body: str) -> int:
        now = self._now()
        res = self.conn.execute(
            "INSERT INTO secure_notes (title_enc, body_enc, created_at, updated_at) VALUES (?,?,?,?)",
            (self._enc(title), self._enc(body), now, now),
        )
        self.conn.commit()
        return res.lastrowid

    def update_note(self, note_id: int, title: str, body: str) -> None:
        self.conn.execute(
            "UPDATE secure_notes SET title_enc=?, body_enc=?, updated_at=? WHERE id=?",
            (self._enc(title), self._enc(body), self._now(), note_id),
        )
        self.conn.commit()

    def delete_note(self, note_id: int) -> None:
        self.conn.execute("DELETE FROM secure_notes WHERE id=?", (note_id,))
        self.conn.commit()

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        total  = self.conn.execute("SELECT COUNT(*) FROM credentials").fetchone()[0]
        favs   = self.conn.execute("SELECT COUNT(*) FROM credentials WHERE is_favorite=1").fetchone()[0]
        notes  = self.conn.execute("SELECT COUNT(*) FROM secure_notes").fetchone()[0]
        cats   = self.conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        return {"total_credentials": total, "favorites": favs,
                "secure_notes": notes, "categories": cats}

    # ── Export / Import ───────────────────────────────────────────────────────

    def export_encrypted(self, export_key: bytes) -> bytes:
        """Export all decrypted data as JSON, then re-encrypt with export_key."""
        from core.crypto import encrypt
        data = {
            "categories":    self.list_categories(),
            "credentials":   self.list_credentials(),
            "secure_notes":  self.list_notes(),
        }
        json_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
        return encrypt(json_bytes, export_key)

    def import_encrypted(self, blob: bytes, export_key: bytes) -> Dict[str, int]:
        """Import from encrypted export blob. Returns counts of imported items."""
        from core.crypto import decrypt
        json_bytes = decrypt(blob, export_key)
        data       = json.loads(json_bytes.decode("utf-8"))

        imported = {"categories": 0, "credentials": 0, "notes": 0}

        # Map old category IDs to new ones
        cat_map = {}
        for cat in data.get("categories", []):
            new_id = self.add_category(cat["name"], cat.get("icon", "🔑"))
            cat_map[cat["id"]] = new_id
            imported["categories"] += 1

        for cred in data.get("credentials", []):
            old_cat = cred.get("category_id", 1)
            new_cat = cat_map.get(old_cat, 1)
            self.add_credential(
                new_cat,
                cred.get("service", ""),
                cred.get("username", ""),
                cred.get("password", ""),
                cred.get("url", ""),
                cred.get("notes", ""),
            )
            imported["credentials"] += 1

        for note in data.get("secure_notes", []):
            self.add_note(note.get("title", ""), note.get("body", ""))
            imported["notes"] += 1

        return imported

    # ── Backup ────────────────────────────────────────────────────────────────

    def create_backup(self, data_dir: Path) -> Path:
        """Create a timestamped copy of the encrypted DB file."""
        ts     = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_path = _get_backup_dir(data_dir) / f"{self.db_path.stem}_{ts}.db"
        shutil.copy2(str(self.db_path), str(backup_path))
        return backup_path

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
        # Zero key from memory (best effort)
        self._key = bytes(KEY_LEN)
