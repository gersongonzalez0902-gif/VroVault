"""
VroVault - Profile Manager
===========================
Manages user profiles stored in profiles.json (metadata only, never secrets).
Each profile has its own encrypted SQLite vault.
"""

import json
import os
import time
import secrets
import base64
from pathlib import Path
from typing import List, Optional, Dict, Any

from core.crypto import (
    derive_key, generate_salt, create_verification_token, verify_key,
    hash_pin, verify_pin, KEY_LEN, SALT_LEN,
)
from core.database import VaultDB, _get_db_path


PROFILES_FILE = "profiles.json"
MAX_ATTEMPTS  = 5
LOCKOUT_DELAY = 2.0   # seconds multiplied by attempt number


class ProfileError(Exception):
    pass


class Profile:
    def __init__(self, data: Dict[str, Any]):
        self.id             : str           = data["id"]
        self.name           : str           = data["name"]
        self.icon           : str           = data.get("icon", "👤")
        self.salt_b64       : str           = data["salt"]           # base64
        self.verify_token   : str           = data["verify_token"]
        self.is_hidden      : bool          = data.get("is_hidden", False)
        self.is_decoy       : bool          = data.get("is_decoy", False)
        self.pin_salt_b64   : Optional[str] = data.get("pin_salt")
        self.pin_hash       : Optional[str] = data.get("pin_hash")
        self.auto_lock_mins : int           = data.get("auto_lock_mins", 5)
        self.max_attempts   : int           = data.get("max_attempts", MAX_ATTEMPTS)
        self.failed_attempts: int           = data.get("failed_attempts", 0)
        self.locked_until   : float         = data.get("locked_until", 0.0)
        self.created_at     : str           = data.get("created_at", "")
        self.destroy_on_max : bool          = data.get("destroy_on_max", False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":              self.id,
            "name":            self.name,
            "icon":            self.icon,
            "salt":            self.salt_b64,
            "verify_token":    self.verify_token,
            "is_hidden":       self.is_hidden,
            "is_decoy":        self.is_decoy,
            "pin_salt":        self.pin_salt_b64,
            "pin_hash":        self.pin_hash,
            "auto_lock_mins":  self.auto_lock_mins,
            "max_attempts":    self.max_attempts,
            "failed_attempts": self.failed_attempts,
            "locked_until":    self.locked_until,
            "created_at":      self.created_at,
            "destroy_on_max":  self.destroy_on_max,
        }


class ProfileManager:
    def __init__(self, data_dir: Path):
        self.data_dir    = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._file       = data_dir / PROFILES_FILE
        self._profiles   : Dict[str, Profile] = {}
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._file.exists():
            self._profiles = {}
            return
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._profiles = {p["id"]: Profile(p) for p in data.get("profiles", [])}
        except Exception as e:
            raise ProfileError(f"Cannot load profiles: {e}")

    def _save(self) -> None:
        tmp = self._file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                {"version": 1, "profiles": [p.to_dict() for p in self._profiles.values()]},
                f, indent=2, ensure_ascii=False,
            )
        os.replace(tmp, self._file)   # atomic rename

    # ── Profile listing ───────────────────────────────────────────────────────

    def list_profiles(self, include_hidden: bool = False) -> List[Profile]:
        profiles = list(self._profiles.values())
        if not include_hidden:
            profiles = [p for p in profiles if not p.is_hidden]
        return profiles

    def get_profile(self, profile_id: str) -> Optional[Profile]:
        return self._profiles.get(profile_id)

    # ── Create ────────────────────────────────────────────────────────────────

    def create_profile(
        self,
        name: str,
        master_password: str,
        icon: str = "👤",
        is_hidden: bool = False,
        is_decoy: bool = False,
        auto_lock_mins: int = 5,
        destroy_on_max: bool = False,
    ) -> Profile:
        import datetime

        if not name.strip():
            raise ProfileError("Profile name cannot be empty.")
        if len(master_password) < 6:
            raise ProfileError("Master password must be at least 6 characters.")

        profile_id = secrets.token_hex(16)
        salt       = generate_salt()
        key        = derive_key(master_password, salt)
        token      = create_verification_token(key)

        profile = Profile({
            "id":              profile_id,
            "name":            name.strip(),
            "icon":            icon,
            "salt":            base64.b64encode(salt).decode("ascii"),
            "verify_token":    token,
            "is_hidden":       is_hidden,
            "is_decoy":        is_decoy,
            "pin_salt":        None,
            "pin_hash":        None,
            "auto_lock_mins":  auto_lock_mins,
            "max_attempts":    MAX_ATTEMPTS,
            "failed_attempts": 0,
            "locked_until":    0.0,
            "created_at":      datetime.datetime.utcnow().isoformat(),
            "destroy_on_max":  destroy_on_max,
        })

        # Initialise empty vault DB
        db_path = _get_db_path(self.data_dir, profile_id)
        vault   = VaultDB(db_path, key)
        vault.seed_default_categories()
        vault.close()

        self._profiles[profile_id] = profile
        self._save()
        return profile

    # ── Authentication ────────────────────────────────────────────────────────

    def authenticate(self, profile_id: str, master_password: str) -> Optional[bytes]:
        """
        Validates master password.
        Returns the derived key on success, None on failure.
        Tracks failed attempts and lockout.
        """
        profile = self._profiles.get(profile_id)
        if profile is None:
            raise ProfileError("Profile not found.")

        # Check lockout
        now = time.time()
        if profile.locked_until > now:
            remaining = int(profile.locked_until - now)
            raise ProfileError(f"Profile locked. Try again in {remaining}s.")

        salt = base64.b64decode(profile.salt_b64.encode("ascii"))
        key  = derive_key(master_password, salt)

        if verify_key(key, profile.verify_token):
            # Success — reset failed counter
            profile.failed_attempts = 0
            profile.locked_until    = 0.0
            self._save()
            return key
        else:
            # Failure
            profile.failed_attempts += 1
            attempt = profile.failed_attempts
            # Progressive delay: 2s, 4s, 6s…
            delay = LOCKOUT_DELAY * attempt
            profile.locked_until = time.time() + delay

            if attempt >= profile.max_attempts and profile.destroy_on_max:
                self._destroy_profile(profile_id)
                raise ProfileError("Maximum attempts reached. Profile destroyed.")
            elif attempt >= profile.max_attempts:
                profile.locked_until = time.time() + 300  # 5 min hard lockout
                self._save()
                raise ProfileError("Maximum attempts reached. Profile locked for 5 minutes.")

            self._save()
            return None

    def _destroy_profile(self, profile_id: str) -> None:
        """Permanently delete a profile and its vault (self-destruct)."""
        db_path = _get_db_path(self.data_dir, profile_id)
        if db_path.exists():
            # Overwrite with random bytes before deletion
            size = db_path.stat().st_size
            with open(db_path, "wb") as f:
                f.write(secrets.token_bytes(size))
            db_path.unlink()
        self._profiles.pop(profile_id, None)
        self._save()

    # ── PIN ───────────────────────────────────────────────────────────────────

    def set_pin(self, profile_id: str, pin: str) -> None:
        profile = self._profiles.get(profile_id)
        if not profile:
            raise ProfileError("Profile not found.")
        if not pin.isdigit() or len(pin) < 4:
            raise ProfileError("PIN must be at least 4 digits.")
        from core.crypto import generate_salt as _gs
        salt = _gs()
        profile.pin_salt_b64 = base64.b64encode(salt).decode("ascii")
        profile.pin_hash     = hash_pin(pin, salt)
        self._save()

    def verify_pin_for_profile(self, profile_id: str, pin: str) -> bool:
        profile = self._profiles.get(profile_id)
        if not profile or not profile.pin_hash or not profile.pin_salt_b64:
            return False
        salt = base64.b64decode(profile.pin_salt_b64.encode("ascii"))
        return verify_pin(pin, salt, profile.pin_hash)

    def remove_pin(self, profile_id: str) -> None:
        profile = self._profiles.get(profile_id)
        if profile:
            profile.pin_salt_b64 = None
            profile.pin_hash     = None
            self._save()

    # ── Edit / Delete ─────────────────────────────────────────────────────────

    def rename_profile(self, profile_id: str, new_name: str) -> None:
        profile = self._profiles.get(profile_id)
        if not profile:
            raise ProfileError("Profile not found.")
        profile.name = new_name.strip()
        self._save()

    def set_profile_icon(self, profile_id: str, icon: str) -> None:
        profile = self._profiles.get(profile_id)
        if profile:
            profile.icon = icon
            self._save()

    def set_auto_lock(self, profile_id: str, minutes: int) -> None:
        profile = self._profiles.get(profile_id)
        if profile:
            profile.auto_lock_mins = max(1, minutes)
            self._save()

    def delete_profile(self, profile_id: str, master_password: str) -> None:
        """Delete profile — requires master password confirmation."""
        key = self.authenticate(profile_id, master_password)
        if key is None:
            raise ProfileError("Incorrect master password.")
        self._destroy_profile(profile_id)

    def toggle_hidden(self, profile_id: str) -> bool:
        profile = self._profiles.get(profile_id)
        if profile:
            profile.is_hidden = not profile.is_hidden
            self._save()
            return profile.is_hidden
        return False

    # ── Vault opener ─────────────────────────────────────────────────────────

    def open_vault(self, profile_id: str, key: bytes) -> VaultDB:
        db_path = _get_db_path(self.data_dir, profile_id)
        return VaultDB(db_path, key)
