"""SENTINEL — AI-powered contextual security auditing platform."""

try:
    from importlib.metadata import version as _pkg_version

    __version__ = _pkg_version("sentinel")
except Exception:
    from pathlib import Path as _Path

    _vf = _Path(__file__).parent.parent / "VERSION"
    __version__ = _vf.read_text().strip() if _vf.exists() else "0.0.0"
