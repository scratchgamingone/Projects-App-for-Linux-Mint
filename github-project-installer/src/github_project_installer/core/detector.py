"""
Project framework and dependency detector.
Scans repository trees to discover build systems, configuration files, and installation commands.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List


def detect_project(repo_path: str) -> Dict[str, Any]:
    """
    Analyzes the files in repo_path and returns detected project metadata,
    frameworks, configuration files, and suggested install/run commands.
    """
    root = Path(repo_path)
    if not root.is_dir():
        return {
            "type": "Unknown",
            "configs": [],
            "install_commands": [],
            "run_commands": [],
            "summary": "Repository path does not exist.",
        }

    detected_configs: List[Dict[str, str]] = []
    install_commands: List[str] = []
    run_commands: List[str] = []
    ecosystems: List[str] = []

    # Helper to check relative path existence
    def has_file(fname: str) -> bool:
        return (root / fname).is_file()

    # 1. Python Detection
    if has_file("requirements.txt") or has_file("pyproject.toml") or has_file("setup.py") or has_file("Pipfile"):
        ecosystems.append("Python")
        if has_file("requirements.txt"):
            detected_configs.append({"file": "requirements.txt", "type": "Python Dependencies"})
            install_commands.append("pip install -r requirements.txt")
        if has_file("pyproject.toml"):
            detected_configs.append({"file": "pyproject.toml", "type": "PEP 517 / Poetry / Flit"})
            install_commands.append("pip install -e .")
        if has_file("setup.py"):
            detected_configs.append({"file": "setup.py", "type": "Setuptools"})
            install_commands.append("pip install -e .")
        if has_file("Pipfile"):
            detected_configs.append({"file": "Pipfile", "type": "Pipenv"})
            install_commands.append("pipenv install")

        for entry in ["main.py", "app.py", "cli.py", "run.py"]:
            if has_file(entry):
                run_commands.append(f"python3 {entry}")
                break

    # 2. Node.js / JavaScript / TypeScript Detection
    if has_file("package.json"):
        ecosystems.append("Node.js / JavaScript")
        detected_configs.append({"file": "package.json", "type": "npm / Node Package"})
        
        # Check package manager locks
        if has_file("pnpm-lock.yaml"):
            install_commands.append("pnpm install")
        elif has_file("yarn.lock"):
            install_commands.append("yarn install")
        elif has_file("bun.lockb"):
            install_commands.append("bun install")
        else:
            install_commands.append("npm install")

        # Parse package.json scripts
        try:
            with open(root / "package.json", "r", encoding="utf-8") as f:
                pkg_data = json.load(f)
                scripts = pkg_data.get("scripts", {})
                if "dev" in scripts:
                    run_commands.append("npm run dev")
                elif "start" in scripts:
                    run_commands.append("npm start")
                elif "build" in scripts:
                    run_commands.append("npm run build")
        except Exception:
            pass

    # 3. Rust Detection
    if has_file("Cargo.toml"):
        ecosystems.append("Rust")
        detected_configs.append({"file": "Cargo.toml", "type": "Cargo Crate"})
        install_commands.append("cargo build --release")
        run_commands.append("cargo run")

    # 4. Go Detection
    if has_file("go.mod"):
        ecosystems.append("Go")
        detected_configs.append({"file": "go.mod", "type": "Go Module"})
        install_commands.append("go mod download")
        run_commands.append("go run .")

    # 5. C / C++ Detection
    if has_file("CMakeLists.txt"):
        ecosystems.append("C/C++ (CMake)")
        detected_configs.append({"file": "CMakeLists.txt", "type": "CMake Build"})
        install_commands.append("cmake -B build && cmake --build build")
    elif has_file("Makefile"):
        ecosystems.append("Makefile / C/C++")
        detected_configs.append({"file": "Makefile", "type": "Make Build"})
        install_commands.append("make")

    # 6. Shell scripts (install.sh / setup.sh)
    for sh in ["install.sh", "setup.sh", "build.sh", "run.sh"]:
        if has_file(sh):
            detected_configs.append({"file": sh, "type": "Shell Script"})
            if sh in ["install.sh", "setup.sh"]:
                install_commands.append(f"./{sh}")
            elif sh in ["run.sh"]:
                run_commands.append(f"./{sh}")

    # 7. Debian packaging
    if (root / "debian" / "control").is_file():
        ecosystems.append("Debian Package")
        detected_configs.append({"file": "debian/control", "type": "Debian Package Control"})
        install_commands.append("dpkg-buildpackage -b -us -uc")

    # 8. Docker
    if has_file("Dockerfile") or has_file("docker-compose.yml") or has_file("compose.yaml"):
        if has_file("docker-compose.yml") or has_file("compose.yaml"):
            comp_file = "docker-compose.yml" if has_file("docker-compose.yml") else "compose.yaml"
            detected_configs.append({"file": comp_file, "type": "Docker Compose"})
            run_commands.append("docker compose up -d")
        if has_file("Dockerfile"):
            detected_configs.append({"file": "Dockerfile", "type": "Docker Container"})

    # Determine primary label
    primary_type = " / ".join(ecosystems) if ecosystems else "Generic Repository"

    # Summary string
    summary = f"Detected {primary_type} with {len(detected_configs)} configuration/build files."

    return {
        "type": primary_type,
        "ecosystems": ecosystems,
        "configs": detected_configs,
        "install_commands": install_commands,
        "run_commands": run_commands,
        "summary": summary,
    }
