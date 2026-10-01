from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent


def main() -> int:
    docker = shutil.which("docker")
    if not docker:
        print(
            "error: Docker is required to run the backend stack automatically.",
            file=sys.stderr,
        )
        return 1

    version = subprocess.run(
        [docker, "compose", "version"],
        cwd=BACKEND_DIR,
        check=False,
    )
    if version.returncode != 0:
        print(
            "error: the Docker Compose plugin is required ('docker compose').",
            file=sys.stderr,
        )
        return version.returncode

    try:
        subprocess.run(
            [docker, "compose", "up", "--build"],
            cwd=BACKEND_DIR,
            check=True,
        )
    except KeyboardInterrupt:
        print("\nStopping backend stack...", flush=True)
        subprocess.run(
            [docker, "compose", "down"],
            cwd=BACKEND_DIR,
            check=False,
        )
        return 0
    except subprocess.CalledProcessError as exc:
        print(
            f"error: backend stack exited with status {exc.returncode}",
            file=sys.stderr,
        )
        return exc.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
