"""Unit tests for admin session authentication."""

# tests/unit/test_admin_auth.py
import sys
from types import ModuleType
from unittest.mock import MagicMock


def _load_auth() -> ModuleType:
    """Import admin.auth with a stubbed streamlit."""
    st_stub = MagicMock()
    sys.modules.setdefault("streamlit", st_stub)
    if "admin.auth" in sys.modules:
        del sys.modules["admin.auth"]
    import admin.auth  # noqa: PLC0415

    return admin.auth


class TestIsAuthenticated:
    """Tests for is_authenticated()."""

    def test_returns_false_when_session_key_absent(self) -> None:
        """is_authenticated() is False when 'authenticated' not in session."""
        auth = _load_auth()
        auth.st.session_state.get.return_value = False

        assert auth.is_authenticated() is False

    def test_returns_true_when_session_key_set(self) -> None:
        """is_authenticated() is True when session holds authenticated=True."""
        auth = _load_auth()
        auth.st.session_state.get.return_value = True

        assert auth.is_authenticated() is True


class TestLoginPage:
    """Tests for login_page()."""

    def test_sets_authenticated_on_correct_password(self, monkeypatch) -> None:
        """login_page() sets authenticated=True when password matches env var."""
        auth = _load_auth()

        monkeypatch.setenv("ADMIN_PASSWORD", "s3cr3t")
        auth.st.text_input.return_value = "s3cr3t"
        auth.st.button.return_value = True
        session: dict = {}
        auth.st.session_state.__setitem__ = lambda _, k, v: session.update({k: v})
        auth.st.session_state.__getitem__ = lambda _, k: session[k]

        auth.login_page()

        assert session.get("authenticated") is True

    def test_leaves_unauthenticated_on_wrong_password(self, monkeypatch) -> None:
        """login_page() does not set authenticated when password is wrong."""
        auth = _load_auth()

        monkeypatch.setenv("ADMIN_PASSWORD", "s3cr3t")
        auth.st.text_input.return_value = "wrong"
        auth.st.button.return_value = True
        session: dict = {}
        auth.st.session_state.__setitem__ = lambda _, k, v: session.update({k: v})

        auth.login_page()

        assert session.get("authenticated") is None
        auth.st.error.assert_called_once()
