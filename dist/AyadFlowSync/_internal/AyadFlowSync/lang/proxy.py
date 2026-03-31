#!/usr/bin/env python3
"""lang.proxy — Lazy Lang proxy to avoid circular imports."""


def _get_lang():
    """Lazy import — only resolves when actually called."""
    from .lang import Lang
    return Lang


class LangProxy:
    """Proxy that lazily loads Lang on first method call.
    Use this in modules that can't import Lang directly (circular deps)."""

    @staticmethod
    def t(key, **kw):
        return _get_lang().t(key, **kw)

    @staticmethod
    def get_lang():
        return _get_lang().current

    @staticmethod
    def set_lang(lang):
        _get_lang().set(lang)
