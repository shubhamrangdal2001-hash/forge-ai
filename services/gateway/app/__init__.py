"""Gateway package bootstrap."""

from pathlib import Path
import sys


def _add_local_orchestrator_to_path() -> None:
    services_dir = Path(__file__).resolve().parents[2]
    orchestrator_dir = services_dir / "orchestrator"
    orchestrator_path = str(orchestrator_dir)
    if orchestrator_dir.exists() and orchestrator_path not in sys.path:
        sys.path.insert(0, orchestrator_path)


_add_local_orchestrator_to_path()
