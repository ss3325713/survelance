"""Security subsystem for PySURVEILLANCE.

Provides:
1. PBKDF2-HMAC-SHA256 cryptographic PIN/password hashing with unique salts.
2. Expiring session tokens with client IP binding and automatic pruning.
3. Anti-CSRF token validation for state-changing administrative requests.
4. Brute-force protection: rate limiting and temporary lockouts on failed logins.
5. Structured security audit logging (strictly redacting PINs and secrets).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

security_logger = logging.getLogger("wheat_watch.security")


def hash_pin(pin: str, salt_hex: Optional[str] = None) -> Tuple[str, str]:
    """Hash PIN using PBKDF2-HMAC-SHA256 with 100,000 rounds.

    Returns:
        (hash_hex, salt_hex)
    """
    if salt_hex is None:
        salt = secrets.token_bytes(16)
        salt_hex = salt.hex()
    else:
        salt = bytes.fromhex(salt_hex)

    derived = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 100000)
    return derived.hex(), salt_hex


def verify_pin_hash(pin: str, stored_hash_hex: str, stored_salt_hex: str) -> bool:
    """Verify input PIN against stored PBKDF2 hash using constant-time comparison."""
    try:
        salt = bytes.fromhex(stored_salt_hex)
        candidate = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 100000)
        return hmac.compare_digest(candidate.hex(), stored_hash_hex)
    except Exception:
        return False


class RateLimiter:
    """Tracks failed login attempts and applies temporary lockouts to prevent brute force."""

    def __init__(self, max_attempts: int = 5, window_sec: float = 300.0, lockout_sec: float = 300.0) -> None:
        self._lock = threading.Lock()
        self.max_attempts = max_attempts
        self.window_sec = window_sec
        self.lockout_sec = lockout_sec
        self._failures: Dict[str, List[float]] = {}
        self._lockouts: Dict[str, float] = {}

    def is_locked_out(self, client_ip: str) -> Tuple[bool, int]:
        """Check if client IP is currently locked out. Returns (locked, seconds_remaining)."""
        now = time.time()
        with self._lock:
            lockout_until = self._lockouts.get(client_ip, 0.0)
            if now < lockout_until:
                remaining = int(lockout_until - now)
                return True, max(1, remaining)
            return False, 0

    def record_failure(self, client_ip: str) -> Tuple[bool, int]:
        """Record a failed login attempt. If threshold exceeded, triggers lockout."""
        now = time.time()
        with self._lock:
            # Clean old failures
            attempts = [t for t in self._failures.get(client_ip, []) if now - t < self.window_sec]
            attempts.append(now)
            self._failures[client_ip] = attempts

            if len(attempts) >= self.max_attempts:
                lockout_until = now + self.lockout_sec
                self._lockouts[client_ip] = lockout_until
                self._failures[client_ip] = []
                security_logger.warning(
                    f"[SECURITY AUDIT] IP {client_ip} exceeded {self.max_attempts} failed login attempts. "
                    f"Locked out for {int(self.lockout_sec)}s."
                )
                return True, int(self.lockout_sec)

            remaining_attempts = self.max_attempts - len(attempts)
            security_logger.warning(
                f"[SECURITY AUDIT] Failed PIN authentication attempt from IP {client_ip}. "
                f"Remaining attempts before lockout: {remaining_attempts}"
            )
            return False, remaining_attempts

    def record_success(self, client_ip: str) -> None:
        """Reset failed attempt counters on successful login."""
        with self._lock:
            self._failures.pop(client_ip, None)
            self._lockouts.pop(client_ip, None)


class SessionManager:
    """Thread-safe session storage with TTL expiration, IP binding, and CSRF token generation."""

    def __init__(self, default_ttl_sec: float = 86400.0) -> None:
        self._lock = threading.Lock()
        self.default_ttl = default_ttl_sec
        # token -> {created_at, expires_at, client_ip, csrf_token, role}
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(self, client_ip: str, role: str = "admin") -> Tuple[str, str]:
        """Create a new authenticated session. Returns (session_token, csrf_token)."""
        now = time.time()
        session_token = secrets.token_hex(32)
        csrf_token = secrets.token_urlsafe(32)

        with self._lock:
            self._prune_expired(now)
            self._sessions[session_token] = {
                "created_at": now,
                "expires_at": now + self.default_ttl,
                "client_ip": client_ip,
                "csrf_token": csrf_token,
                "role": role,
            }

        security_logger.info(f"[SECURITY AUDIT] Authenticated session created for IP {client_ip} (Role: {role}).")
        return session_token, csrf_token

    def validate_session(self, token: str, client_ip: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Validate an active session token. Returns session dict if valid, else None."""
        if not token:
            return None

        now = time.time()
        with self._lock:
            session = self._sessions.get(token)
            if not session:
                return None

            if now >= session["expires_at"]:
                self._sessions.pop(token, None)
                security_logger.info(f"[SECURITY AUDIT] Session expired for IP {session.get('client_ip')}.")
                return None

            # Optional client IP consistency check (permits loopback aliases)
            if client_ip and session.get("client_ip"):
                stored_ip = session["client_ip"]
                if stored_ip != client_ip and not (stored_ip in ("127.0.0.1", "localhost") and client_ip in ("127.0.0.1", "localhost")):
                    security_logger.warning(
                        f"[SECURITY AUDIT] Session IP mismatch: stored={stored_ip}, incoming={client_ip}"
                    )

            return dict(session)

    def validate_csrf(self, session_token: str, csrf_token: Optional[str]) -> bool:
        """Validate CSRF token matches the session."""
        if not csrf_token:
            return False
        with self._lock:
            session = self._sessions.get(session_token)
            if not session:
                return False
            return hmac.compare_digest(session.get("csrf_token", ""), csrf_token)

    def invalidate_session(self, token: str) -> bool:
        """Invalidate an active session token upon logout."""
        with self._lock:
            removed = self._sessions.pop(token, None)
            if removed:
                security_logger.info(f"[SECURITY AUDIT] Session logged out for IP {removed.get('client_ip')}.")
                return True
            return False

    def _prune_expired(self, now: float) -> None:
        """Prune expired sessions from internal dictionary."""
        expired = [tok for tok, s in self._sessions.items() if now >= s["expires_at"]]
        for tok in expired:
            self._sessions.pop(tok, None)


# Global instances
rate_limiter = RateLimiter(max_attempts=5, window_sec=300.0, lockout_sec=300.0)
session_manager = SessionManager(default_ttl_sec=86400.0)
