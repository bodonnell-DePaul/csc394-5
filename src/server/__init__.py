__all__ = ["app", "create_app"]


def __getattr__(name: str):
    if name in __all__:
        from .main import app, create_app

        if name == "app":
            return app
        if name == "create_app":
            return create_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
