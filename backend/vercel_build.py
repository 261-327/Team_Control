"""Production release step; the Django preset installs dependencies and collects static."""

import os
import subprocess
import sys
from pathlib import Path

from config.vercel_hosting import validate_environment


def main():
    # Fail before Django imports or DB access. Preview never touches the production DB.
    validate_environment(os.environ)
    subprocess.run(
        [sys.executable, "manage.py", "migrate", "--noinput"],
        cwd=Path(__file__).resolve().parent,
        check=True,
    )


if __name__ == "__main__":
    main()
