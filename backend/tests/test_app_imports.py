import importlib

MODULES = [
    "app.main",
    "app.core.config",
    "app.core.logging",
    "app.api.health",
]


def test_core_modules_import_cleanly() -> None:
    for module_name in MODULES:
        importlib.import_module(module_name)
