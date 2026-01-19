"""
Secrets Vault Module for JUGGERNAUT Autonomy System.

This module provides secure storage, retrieval, and automatic rotation
of API keys, tokens, and credentials with comprehensive audit logging.
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

# Configure module logger
logger = logging.getLogger(__name__)

# Constants
DEFAULT_ROTATION_DAYS: int = 30
MIN_ROTATION_DAYS: int = 1
MAX_ROTATION_DAYS: int = 365
SECRET_KEY_LENGTH: int = 32
ENCRYPTION_ITERATIONS: int = 100000
SALT_LENGTH: int = 16
AUDIT_LOG_MAX_ENTRIES: int = 10000
ROTATION_CHECK_INTERVAL_SECONDS: int = 3600


class SecretType(Enum):
    """Enumeration of supported secret types."""
    
    API_KEY = "api_key"
    TOKEN = "token"
    CREDENTIAL = "credential"
    PASSWORD = "password"
    CERTIFICATE = "certificate"
    ENCRYPTION_KEY = "encryption_key"


class AuditAction(Enum):
    """Enumeration of auditable actions on secrets."""
    
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    ROTATE = "rotate"
    EXPIRE = "expire"
    ACCESS_DENIED = "access_denied"


@dataclass
class AuditLogEntry:
    """Represents a single audit log entry for secret operations."""
    
    timestamp: datetime
    action: AuditAction
    secret_name: str
    actor: str
    success: bool
    details: Optional[str] = None
    ip_address: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert audit log entry to dictionary format."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "secret_name": self.secret_name,
            "actor": self.actor,
            "success": self.success,
            "details": self.details,
            "ip_address": self.ip_address,
        }


@dataclass
class SecretMetadata:
    """Metadata associated with a stored secret."""
    
    name: str
    secret_type: SecretType
    created_at: datetime
    last_rotated: datetime
    rotation_interval_days: int
    expires_at: Optional[datetime] = None
    version: int = 1
    tags: Dict[str, str] = field(default_factory=dict)
    rotation_callback: Optional[str] = None
    
    def is_rotation_due(self) -> bool:
        """Check if the secret is due for rotation."""
        next_rotation = self.last_rotated + timedelta(days=self.rotation_interval_days)
        return datetime.now(timezone.utc) >= next_rotation
    
    def is_expired(self) -> bool:
        """Check if the secret has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) >= self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary format."""
        return {
            "name": self.name,
            "secret_type": self.secret_type.value,
            "created_at": self.created_at.isoformat(),
            "last_rotated": self.last_rotated.isoformat(),
            "rotation_interval_days": self.rotation_interval_days,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "version": self.version,
            "tags": self.tags,
            "rotation_callback": self.rotation_callback,
        }


class EncryptionBackend(ABC):
    """Abstract base class for encryption backends."""
    
    @abstractmethod
    def encrypt(self, plaintext: bytes, key: bytes) -> bytes:
        """Encrypt plaintext data."""
        pass
    
    @abstractmethod
    def decrypt(self, ciphertext: bytes, key: bytes) -> bytes:
        """Decrypt ciphertext data."""
        pass


class SimpleEncryptionBackend(EncryptionBackend):
    """Simple XOR-based encryption with key stretching.
    
    WARNING: For production, use cryptography library (Fernet).
    """
    
    def encrypt(self, plaintext: bytes, key: bytes) -> bytes:
        """Encrypt using XOR with key stretching."""
        salt = secrets.token_bytes(SALT_LENGTH)
        stretched_key = self._stretch_key(key, salt)
        encrypted = bytes(
            p ^ k for p, k in zip(plaintext, self._cycle_key(stretched_key, len(plaintext)))
        )
        return salt + encrypted
    
    def decrypt(self, ciphertext: bytes, key: bytes) -> bytes:
        """Decrypt XOR-encrypted data."""
        if len(ciphertext) < SALT_LENGTH:
            raise ValueError("Ciphertext too short")
        salt = ciphertext[:SALT_LENGTH]
        encrypted = ciphertext[SALT_LENGTH:]
        stretched_key = self._stretch_key(key, salt)
        return bytes(
            c ^ k for c, k in zip(encrypted, self._cycle_key(stretched_key, len(encrypted)))
        )
    
    def _stretch_key(self, key: bytes, salt: bytes) -> bytes:
        """Stretch key using PBKDF2-like iteration."""
        result = hmac.new(key, salt, hashlib.sha256).digest()
        for _ in range(ENCRYPTION_ITERATIONS // 1000):
            result = hmac.new(key, result, hashlib.sha256).digest()
        return result
    
    def _cycle_key(self, key: bytes, length: int) -> bytes:
        """Cycle key to match required length."""
        repetitions = (length // len(key)) + 1
        return (key * repetitions)[:length]


class RotationCallbackRegistry:
    """Registry for secret rotation callback functions."""
    
    def __init__(self) -> None:
        """Initialize the callback registry."""
        self._callbacks: Dict[str, Callable[[str, str, str], bool]] = {}
        self._lock = threading.Lock()
    
    def register(self, name: str, callback: Callable[[str, str, str], bool]) -> None:
        """Register a rotation callback."""
        with self._lock:
            self._callbacks[name] = callback
            logger.info("Registered rotation callback: %s", name)
    
    def unregister(self, name: str) -> bool:
        """Unregister a rotation callback."""
        with self._lock:
            if name in self._callbacks:
                del self._callbacks[name]
                logger.info("Unregistered rotation callback: %s", name)
                return True
            return False
    
    def execute(self, name: str, secret_name: str, old_value: str, new_value: str) -> bool:
        """Execute a registered callback."""
        with self._lock:
            if name not in self._callbacks:
                raise KeyError(f"Callback not registered: {name}")
            callback = self._callbacks[name]
        try:
            return callback(secret_name, old_value, new_value)
        except Exception as exc:
            logger.error("Rotation callback %s failed for %s: %s", name, secret_name, exc)
            return False


class AuditLogger:
    """Thread-safe audit logger for secret operations."""
    
    def __init__(self, max_entries: int = AUDIT_LOG_MAX_ENTRIES) -> None:
        """Initialize the audit logger."""
        self._entries: List[AuditLogEntry] = []
        self._max_entries = max_entries
        self._lock = threading.Lock()
    
    def log(
        self,
        action: AuditAction,
        secret_name: str,
        actor: str,
        success: bool,
        details: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """Log an audit event."""
        entry = AuditLogEntry(
            timestamp=datetime.now(timezone.utc),
            action=action,
            secret_name=secret_name,
            actor=actor,
            success=success,
            details=details,
            ip_address=ip_address,
        )
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]
        log_level = logging.INFO if success else logging.WARNING
        logger.log(
            log_level,
            "AUDIT: %s %s by %s - %s%s",
            action.value, secret_name, actor,
            "SUCCESS" if success else "FAILED",
            f" - {details}" if details else "",
        )
    
    def get_entries(
        self,
        secret_name: Optional[str] = None,
        action: Optional[AuditAction] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditLogEntry]:
        """Retrieve audit log entries with optional filtering."""
        with self._lock:
            entries = self._entries.copy()
        if secret_name:
            entries = [e for e in entries if e.secret_name == secret_name]
        if action:
            entries = [e for e in entries if e.action == action]
        if since:
            entries = [e for e in entries if e.timestamp >= since]
        return entries[-limit:]
    
    def export_json(self) -> str:
        """Export all audit logs as JSON."""
        with self._lock:
            entries = [e.to_dict() for e in self._entries]
        return json.dumps(entries, indent=2)


class SecretsVault:
    """Secure vault for storing and managing secrets with automatic rotation."""
    
    def __init__(
        self,
        master_key: Optional[bytes] = None,
        encryption_backend: Optional[EncryptionBackend] = None
    ) -> None:
        """Initialize the secrets vault."""
        self._master_key = master_key or secrets.token_bytes(SECRET_KEY_LENGTH)
        self._encryption = encryption_backend or SimpleEncryptionBackend()
        self._secrets: Dict[str, bytes] = {}
        self._metadata: Dict[str, SecretMetadata] = {}
        self._lock = threading.RLock()
        self._audit = AuditLogger()
        self._callbacks = RotationCallbackRegistry()
        self._rotation_thread: Optional[threading.Thread] = None
        self._stop_rotation = threading.Event()
        logger.info("SecretsVault initialized")
    
    def store_secret(
        self,
        name: str,
        value: str,
        secret_type: SecretType,
        actor: str,
        rotation_interval_days: int = DEFAULT_ROTATION_DAYS,
        expires_at: Optional[datetime] = None,
        tags: Optional[Dict[str, str]] = None,
        rotation_callback: Optional[str] = None
    ) -> bool:
        """Store a secret in the vault."""
        if not MIN_ROTATION_DAYS <= rotation_interval_days <= MAX_ROTATION_DAYS:
            raise ValueError(
                f"Rotation interval must be between {MIN_ROTATION_DAYS} "
                f"and {MAX_ROTATION_DAYS} days"
            )
        try:
            encrypted = self._encryption.encrypt(value.encode("utf-8"), self._master_key)
            now = datetime.now(timezone.utc)
            metadata = SecretMetadata(
                name=name,
                secret_type=secret_type,
                created_at=now,
                last_rotated=now,
                rotation_interval_days=rotation_interval_days,
                expires_at=expires_at,
                version=1,
                tags=tags or {},
                rotation_callback=rotation_callback,
            )
            with self._lock:
                is_update = name in self._secrets
                self._secrets[name] = encrypted
                self._metadata[name] = metadata
            action = AuditAction.UPDATE if is_update else AuditAction.CREATE
            self._audit.log(action, name, actor, True, f"Type: {secret_type.value}")
            return True
        except Exception as exc:
            logger.error("Failed to store secret %s: %s", name, exc)
            self._audit.log(AuditAction.CREATE, name, actor, False, f"Error: {exc}")
            return False
    
    def retrieve_secret(
        self,
        name: str,
        actor: str,
        ip_address: Optional[str] = None
    ) -> Optional[str]:
        """Retrieve a secret from the vault."""
        with self._lock:
            if name not in self._secrets:
                self._audit.log(AuditAction.READ, name, actor, False, "Secret not found", ip_address)
                return None
            metadata = self._metadata[name]
            if metadata.is_expired():
                self._audit.log(AuditAction.READ, name, actor, False, "Secret expired", ip_address)
                return None
            encrypted = self._secrets[name]
        try:
            decrypted = self._encryption.decrypt(encrypted, self._master_key)
            self._audit.log(AuditAction.READ, name, actor, True, f"Version: {metadata.version}", ip_address)
            return decrypted.decode("utf-8")
        except Exception as exc:
            logger.error("Failed to decrypt secret %s: %s", name, exc)
            self._audit.log(AuditAction.READ, name, actor, False, f"Decryption error: {exc}", ip_address)
            return None
    
    def delete_secret(self, name: str, actor: str) -> bool:
        """Delete a secret from the vault."""
        with self._lock:
            if name not in self._secrets:
                self._audit.log(AuditAction.DELETE, name, actor, False, "Secret not found")
                return False
            del self._secrets[name]
            del self._metadata[name]
        self._audit.log(AuditAction.DELETE, name, actor, True)
        return True
    
    def rotate_secret(self, name: str, new_value: str, actor: str) -> bool:
        """Manually rotate a secret to a new value."""
        with self._lock:
            if name not in self._secrets:
                self._audit.log(AuditAction.ROTATE, name, actor, False, "Secret not found")
                return False
            metadata = self._metadata[name]
            old_encrypted = self._secrets[name]
        try:
            old_value = self._encryption.decrypt(old_encrypted, self._master_key).decode("utf-8")
            if metadata.rotation_callback:
                try:
                    success = self._callbacks.execute(metadata.rotation_callback, name, old_value, new_value)
                    if not success:
                        self._audit.log(AuditAction.ROTATE, name, actor, False, "Callback failed")
                        return False
                except KeyError:
                    logger.warning("Rotation callback %s not found for %s", metadata.rotation_callback, name)
            encrypted = self._encryption.encrypt(new_value.encode("utf-8"), self._master_key)
            with self._lock:
                self._secrets[name] = encrypted
                metadata.last_rotated = datetime.now(timezone.utc)
                metadata.version += 1
            self._audit.log(AuditAction.ROTATE, name, actor, True, f"Version: {metadata.version}")
            return True
        except Exception as exc:
            logger.error("Failed to rotate secret %s: %s", name, exc)
            self._audit.log(AuditAction.ROTATE, name, actor, False, f"Error: {exc}")
            return False
    
    def get_metadata(self, name: str) -> Optional[SecretMetadata]:
        """Get metadata for a secret."""
        with self._lock:
            return self._metadata.get(name)
    
    def list_secrets(
        self,
        secret_type: Optional[SecretType] = None,
        tag_filter: Optional[Dict[str, str]] = None
    ) -> List[str]:
        """List all secret names with optional filtering."""
        with self._lock:
            names = list(self._metadata.keys())
            if secret_type:
                names = [n for n in names if self._metadata[n].secret_type == secret_type]
            if tag_filter:
                names = [
                    n for n in names
                    if all(self._metadata[n].tags.get(k) == v for k, v in tag_filter.items())
                ]
        return names
    
    def get_secrets_due_for_rotation(self) -> List[str]:
        """Get list of secrets that are due for rotation."""
        with self._lock:
            return [name for name, meta in self._metadata.items() if meta.is_rotation_due()]
    
    def get_expired_secrets(self) -> List[str]:
        """Get list of expired secrets."""
        with self._lock:
            return [name for name, meta in self._metadata.items() if meta.is_expired()]
    
    def register_rotation_callback(self, name: str, callback: Callable[[str, str, str], bool]) -> None:
        """Register a callback for secret rotation."""
        self._callbacks.register(name, callback)
    
    def start_auto_rotation(self, check_interval: int = ROTATION_CHECK_INTERVAL_SECONDS) -> None:
        """Start background thread for automatic rotation checks."""
        if self._rotation_thread and self._rotation_thread.is_alive():
            logger.warning("Auto-rotation already running")
            return
        self._stop_rotation.clear()
        self._rotation_thread = threading.Thread(
            target=self._rotation_loop,
            args=(check_interval,),
            daemon=True,
            name="SecretsVault-AutoRotation"
        )
        self._rotation_thread.start()
        logger.info("Started auto-rotation thread (interval: %d seconds)", check_interval)
    
    def stop_auto_rotation(self) -> None:
        """Stop the automatic rotation background thread."""
        self._stop_rotation.set()
        if self._rotation_thread:
            self._rotation_thread.join(timeout=5)
            logger.info("Stopped auto-rotation thread")
    
    def _rotation_loop(self, check_interval: int) -> None:
        """Background loop for checking and triggering rotations."""
        while not self._stop_rotation.is_set():
            try:
                for name in self.get_secrets_due_for_rotation():
                    logger.info("Secret %s is due for rotation", name)
                    self._audit.log(AuditAction.EXPIRE, name, "system", True, "Rotation due")
                for name in self.get_expired_secrets():
                    self._audit.log(AuditAction.EXPIRE, name, "system", True, "Secret expired")
            except Exception as exc:
                logger.error("Error in rotation check loop: %s", exc)
            self._stop_rotation.wait(check_interval)
    
    def get_audit_log(
        self,
        secret_name: Optional[str] = None,
        action: Optional[AuditAction] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditLogEntry]:
        """Get audit log entries."""
        return self._audit.get_entries(secret_name, action, since, limit)
    
    def export_audit_log_json(self) -> str:
        """Export audit log as JSON string."""
        return self._audit.export_json()
    
    def get_vault_stats(self) -> Dict[str, Any]:
        """Get statistics about the vault."""
        with self._lock:
            total_secrets = len(self._secrets)
            by_type: Dict[str, int] = {}
            expired_count = 0
            rotation_due_count = 0
            for meta in self._metadata.values():
                type_key = meta.secret_type.value
                by_type[type_key] = by_type.get(type_key, 0) + 1
                if meta.is_expired():
                    expired_count += 1
                if meta.is_rotation_due():
                    rotation_due_count += 1
        return {
            "total_secrets": total_secrets,
            "by_type": by_type,
            "expired": expired_count,
            "rotation_due": rotation_due_count,
            "auto_rotation_active": self._rotation_thread is not None and self._rotation_thread.is_alive(),
        }


def create_vault_from_env(env_prefix: str = "VAULT_") -> SecretsVault:
    """Create a vault instance from environment variables."""
    master_key_hex = os.environ.get(f"{env_prefix}MASTER_KEY")
    master_key = bytes.fromhex(master_key_hex) if master_key_hex else None
    return SecretsVault(master_key=master_key)


_default_vault: Optional[SecretsVault] = None


def get_default_vault() -> SecretsVault:
    """Get or create the default vault instance."""
    global _default_vault
    if _default_vault is None:
        _default_vault = create_vault_from_env()
    return _default_vault
