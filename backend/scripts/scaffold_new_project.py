"""
Simple scaffolding script to create a new project from this backend
boilerplate.

Usage (from the backend directory):

    uv run python scripts/scaffold_new_project.py

The script will:
- prompt for a target directory and project name
- copy the current backend tree into that directory
- remove the existing .git directory if present
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def prompt(text: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or (default or "")


def main() -> None:
    here = Path(__file__).resolve().parents[1]
    default_target = here.parent / "my-new-backend"

    print(f"Backend boilerplate root: {here}")

    target_dir = Path(prompt("Target directory for new project", str(default_target)))
    project_name = prompt("Project name", "FastAPI Backend Project")

    if target_dir.exists() and any(target_dir.iterdir()):
        raise SystemExit(f"Target directory {target_dir} is not empty; aborting.")

    print(f"Creating new project at {target_dir} ...")
    shutil.copytree(here, target_dir, dirs_exist_ok=False)

    # Remove VCS metadata if copied.
    git_dir = target_dir / ".git"
    if git_dir.exists():
        shutil.rmtree(git_dir)

    # Update README title if present.
    readme_path = target_dir / "README.md"
    if readme_path.exists():
        content = readme_path.read_text(encoding="utf-8")
        content = content.replace("FastAPI Tutorial T1 Backend", project_name)
        readme_path.write_text(content, encoding="utf-8")

    print("Done.")
    print("Next steps:")
    print(f"  1) cd {target_dir}")
    print("  2) Initialize git: git init && git add . && git commit -m \"Initial commit\"")
    print("  3) Create and configure your .env from .env.example")


if __name__ == "__main__":
    main()

