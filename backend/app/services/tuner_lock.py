"""
Tuner Lock Service - Prevents multiple clients from controlling the tuner simultaneously.

The RTL-SDR dongle is a single hardware resource that can only tune to one frequency.
This service provides session-based locking to prevent conflicts when multiple clients
(frontend, Music Assistant, etc.) try to control the tuner at the same time.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Optional


logger = logging.getLogger(__name__)


class TunerMode(str, Enum):
    """Current tuner mode."""
    IDLE = "idle"
    FM = "fm"
    DAB = "dab"


@dataclass
class TunerSession:
    """Represents an active tuner session."""
    session_id: str
    client_id: str
    mode: TunerMode
    started_at: float
    last_activity: float

    @property
    def age_seconds(self) -> float:
        """How long the session has been active."""
        return time.time() - self.started_at

    @property
    def idle_seconds(self) -> float:
        """How long since last activity."""
        return time.time() - self.last_activity


class TunerLockService:
    """
    Manages exclusive access to the RTL-SDR tuner.

    Features:
    - Session-based locking with client identification
    - Automatic session timeout after inactivity
    - Force takeover option for emergency situations
    - Status reporting for debugging
    """

    # Session timeout after 5 minutes of inactivity
    SESSION_TIMEOUT_SECONDS = 300

    def __init__(self):
        self._session: Optional[TunerSession] = None
        self._lock = asyncio.Lock()

    @property
    def current_session(self) -> Optional[TunerSession]:
        """Get current session (may be expired)."""
        return self._session

    @property
    def is_locked(self) -> bool:
        """Check if tuner is currently locked by an active session."""
        if self._session is None:
            return False
        # Check if session has timed out
        if self._session.idle_seconds > self.SESSION_TIMEOUT_SECONDS:
            return False
        return True

    def get_status(self) -> dict:
        """Get current lock status for debugging."""
        if self._session is None:
            return {
                "locked": False,
                "mode": TunerMode.IDLE.value,
                "session": None,
            }

        is_expired = self._session.idle_seconds > self.SESSION_TIMEOUT_SECONDS
        return {
            "locked": not is_expired,
            "mode": self._session.mode.value,
            "session": {
                "session_id": self._session.session_id,
                "client_id": self._session.client_id,
                "started_at": self._session.started_at,
                "last_activity": self._session.last_activity,
                "age_seconds": self._session.age_seconds,
                "idle_seconds": self._session.idle_seconds,
                "expired": is_expired,
            },
        }

    async def acquire(
        self,
        client_id: str,
        mode: TunerMode,
        force: bool = False,
    ) -> tuple[bool, str]:
        """
        Attempt to acquire the tuner lock.

        Args:
            client_id: Identifier for the client (e.g., "frontend", "music-assistant")
            mode: Tuner mode to set (FM or DAB)
            force: If True, forcibly take over from another client

        Returns:
            Tuple of (success, session_id or error message)
        """
        async with self._lock:
            now = time.time()

            # Check if there's an existing session
            if self._session is not None:
                # Same client - extend session
                if self._session.client_id == client_id:
                    self._session.last_activity = now
                    self._session.mode = mode
                    logger.debug(f"Extended session for {client_id}")
                    return True, self._session.session_id

                # Different client - check if expired
                if self._session.idle_seconds > self.SESSION_TIMEOUT_SECONDS:
                    logger.info(f"Session expired for {self._session.client_id}, allowing {client_id}")
                    # Fall through to create new session
                elif force:
                    logger.warning(f"Force takeover by {client_id} from {self._session.client_id}")
                    # Fall through to create new session
                else:
                    # Session is active and belongs to another client
                    error = (
                        f"Tuner is in use by {self._session.client_id} "
                        f"(idle {int(self._session.idle_seconds)}s). "
                        f"Use force=true to take over."
                    )
                    logger.info(f"Lock denied for {client_id}: {error}")
                    return False, error

            # Create new session
            session_id = str(uuid.uuid4())[:8]
            self._session = TunerSession(
                session_id=session_id,
                client_id=client_id,
                mode=mode,
                started_at=now,
                last_activity=now,
            )
            logger.info(f"Session {session_id} acquired by {client_id} for {mode.value}")
            return True, session_id

    async def release(self, client_id: str, session_id: Optional[str] = None) -> bool:
        """
        Release the tuner lock.

        Args:
            client_id: Client releasing the lock
            session_id: Optional session ID for verification

        Returns:
            True if released, False if not owned by this client
        """
        async with self._lock:
            if self._session is None:
                return True  # Already released

            # Verify ownership
            if self._session.client_id != client_id:
                logger.warning(f"Release denied: {client_id} doesn't own the session")
                return False

            if session_id and self._session.session_id != session_id:
                logger.warning(f"Release denied: session ID mismatch")
                return False

            logger.info(f"Session {self._session.session_id} released by {client_id}")
            self._session = None
            return True

    async def touch(self, client_id: str) -> bool:
        """
        Update last activity timestamp for keep-alive.

        Args:
            client_id: Client touching the session

        Returns:
            True if successful, False if not owned
        """
        async with self._lock:
            if self._session is None:
                return False

            if self._session.client_id != client_id:
                return False

            self._session.last_activity = time.time()
            return True

    async def verify(self, client_id: str, session_id: Optional[str] = None) -> bool:
        """
        Verify that a client owns the current session.

        Args:
            client_id: Client to verify
            session_id: Optional session ID to verify

        Returns:
            True if client owns an active session
        """
        if self._session is None:
            return False

        if self._session.client_id != client_id:
            return False

        if session_id and self._session.session_id != session_id:
            return False

        # Check expiration
        if self._session.idle_seconds > self.SESSION_TIMEOUT_SECONDS:
            return False

        return True
