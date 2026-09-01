"""ASTRA Sentinel V1 terminal entry point."""
from astra_sentinel import build_default_runtime
from astra_sentinel.cli import run_cli


if __name__ == "__main__":
    dispatcher, _audit = build_default_runtime()
    run_cli(dispatcher)
