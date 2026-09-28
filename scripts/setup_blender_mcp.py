#!/usr/bin/env python3
"""
Cross-Platform Zero-Touch Installer for `image-to-blender` (Windows, macOS, Linux).

What this script automates on any laptop with Blender installed:
1. Locates the installed Blender executable across Windows, macOS, and Linux.
2. Ensures `uv` / `uvx` is installed and resolves its absolute binary path.
3. Installs `blender_mcp.py` into Blender's user add-ons directory.
4. Runs headless Blender once to permanently enable `blender_mcp` in User Preferences
   (so `blendermcp_auto_start_server=True` automatically starts port 9876 whenever Blender opens).
5. Registers `"blender"` inside Antigravity's `~/.gemini/config/mcp_config.json`
   (preserving all existing MCP servers and creating a `.backup`).
6. Optionally launches Blender GUI and verifies the live TCP connection on `localhost:9876`.
"""

import argparse
import glob
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
BUNDLED_ADDON = SKILL_ROOT / "assets" / "blender_mcp.py"


def find_blender_executable() -> str | None:
    """Locate the Blender binary across macOS, Windows, and Linux."""
    env_bin = os.environ.get("BLENDER_PATH") or os.environ.get("BLENDER_BIN")
    if env_bin and Path(env_bin).exists():
        return str(Path(env_bin).resolve())

    system = platform.system()
    candidates = []

    if system == "Darwin":
        candidates.extend([
            "/Applications/Blender.app/Contents/MacOS/Blender",
            str(Path.home() / "Applications/Blender.app/Contents/MacOS/Blender"),
        ])
        candidates.extend(sorted(glob.glob("/Applications/Blender*/Contents/MacOS/Blender"), reverse=True))
        candidates.extend(sorted(glob.glob(str(Path.home() / "Applications/Blender*/Contents/MacOS/Blender")), reverse=True))
        # Spotlight fallback
        try:
            out = subprocess.check_output(
                ["mdfind", "kMDItemCFBundleIdentifier == 'org.blenderfoundation.blender'"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            for line in out.splitlines():
                bin_path = Path(line.strip()) / "Contents/MacOS/Blender"
                if bin_path.exists():
                    candidates.append(str(bin_path))
        except Exception:
            pass

    elif system == "Windows":
        prog_files = [
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            os.environ.get("LOCALAPPDATA", ""),
        ]
        for base in prog_files:
            if not base:
                continue
            pattern = os.path.join(base, "Blender Foundation", "Blender*", "blender.exe")
            candidates.extend(sorted(glob.glob(pattern), reverse=True))
        # Steam path fallback on Windows
        steam_pattern = r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe"
        if os.path.exists(steam_pattern):
            candidates.append(steam_pattern)

    else:  # Linux
        candidates.extend([
            "/snap/bin/blender",
            "/usr/bin/blender",
            "/usr/local/bin/blender",
            str(Path.home() / ".local/bin/blender"),
        ])

    for c in candidates:
        if c and os.path.isfile(c):
            return c

    which_blender = shutil.which("blender") or shutil.which("Blender")
    return which_blender


def find_or_install_uvx() -> str:
    """Locate `uvx` or install `uv` automatically if missing."""
    system = platform.system()
    exe_name = "uvx.exe" if system == "Windows" else "uvx"

    search_dirs = [
        str(Path.home() / ".local" / "bin"),
        str(Path.home() / ".cargo" / "bin"),
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
    ]
    for d in search_dirs:
        candidate = Path(d) / exe_name
        if candidate.is_file():
            return str(candidate)

    found = shutil.which("uvx")
    if found:
        return str(Path(found).resolve())

    print("[setup] `uvx` not found. Installing `uv` automatically...")
    try:
        if system == "Windows":
            subprocess.run(
                ["powershell", "-ExecutionPolicy", "ByPass", "-c", "irm https://astral.sh/uv/install.ps1 | iex"],
                check=True,
            )
        elif system == "Darwin" and shutil.which("brew"):
            subprocess.run(["brew", "install", "uv"], check=True)
        else:
            subprocess.run("curl -LsSf https://astral.sh/uv/install.sh | sh", shell=True, check=True)
    except Exception as exc:
        print(f"[setup] Warning: automatic uv install returned: {exc}")

    for d in search_dirs:
        candidate = Path(d) / exe_name
        if candidate.is_file():
            return str(candidate)

    found = shutil.which("uvx")
    return str(Path(found).resolve()) if found else "uvx"


def install_and_enable_blender_addon(blender_bin: str, uvx_bin: str) -> dict:
    """
    1. Queries Blender for its exact user `scripts/addons` directory.
    2. Copies bundled `blender_mcp.py` (and runs `uvx mcp-for-blender install-addon`).
    3. Enables `blender_mcp` in Blender User Preferences and saves `userpref.blend`.
    """
    result = {"addons_dir": None, "addon_installed": False, "addon_enabled": False}

    # Try uvx install-addon first (non-fatal if offline or uvx still bootstrapping)
    try:
        subprocess.run(
            [uvx_bin, "mcp-for-blender", "install-addon"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            check=False,
        )
    except Exception:
        pass

    # Query Blender for user addons path, copy bundled addon if needed, and enable it in preferences
    expr = (
        "import bpy, addon_utils, shutil, os; "
        "addons_dir = bpy.utils.user_resource('SCRIPTS', path='addons', create=True); "
        "print('BLENDER_ADDONS_DIR=' + str(addons_dir)); "
        f"src = r'''{str(BUNDLED_ADDON)}'''; "
        "dst = os.path.join(addons_dir, 'blender_mcp.py'); "
        "shutil.copy2(src, dst) if os.path.exists(src) else None; "
        "addon_utils.modules_refresh(); "
        "addon_utils.enable('blender_mcp', default_set=True, persistent=True); "
        "bpy.ops.wm.save_userpref(); "
        "print('BLENDER_ADDON_ENABLED=1')"
    )
    try:
        proc = subprocess.run(
            [blender_bin, "-b", "--python-expr", expr],
            capture_output=True,
            text=True,
            timeout=45,
        )
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        for line in out.splitlines():
            if line.startswith("BLENDER_ADDONS_DIR="):
                result["addons_dir"] = line.split("=", 1)[1].strip()
                result["addon_installed"] = True
            if "BLENDER_ADDON_ENABLED=1" in line:
                result["addon_enabled"] = True
    except Exception as exc:
        result["error"] = str(exc)

    return result


def update_antigravity_mcp_config(uvx_bin: str, port: int = 9876) -> str:
    """Safely add `blender` to `~/.gemini/config/mcp_config.json`."""
    config_dir = Path.home() / ".gemini" / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "mcp_config.json"

    data = {"mcpServers": {}}
    if config_file.exists():
        try:
            shutil.copy2(config_file, config_dir / "mcp_config.json.backup")
            data = json.loads(config_file.read_text(encoding="utf-8"))
            if not isinstance(data.get("mcpServers"), dict):
                data["mcpServers"] = {}
        except Exception:
            data = {"mcpServers": {}}

    data["mcpServers"]["blender"] = {
        "command": uvx_bin,
        "args": ["mcp-for-blender"],
        "env": {
            "BLENDER_HOST": "localhost",
            "BLENDER_PORT": str(port),
            "DISABLE_TELEMETRY": "true",
        },
    }

    config_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return str(config_file)


def is_port_open(host: str = "localhost", port: int = 9876) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def send_socket_command(cmd_type: str, params: dict = None, host: str = "localhost", port: int = 9876) -> dict:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(10.0)
        s.connect((host, port))
        payload = json.dumps({"type": cmd_type, "params": params or {}}).encode("utf-8")
        s.sendall(payload)
        chunks = []
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            try:
                return json.loads(b"".join(chunks).decode("utf-8"))
            except json.JSONDecodeError:
                continue
    return {"status": "error", "message": "Empty response"}


def launch_blender_and_wait(blender_bin: str, port: int = 9876, timeout_sec: int = 15) -> bool:
    """Launch Blender GUI if port 9876 isn't listening yet, and enable Poly Haven."""
    if not is_port_open("localhost", port):
        startup_expr = (
            "import bpy, addon_utils; "
            "addon_utils.enable('blender_mcp', default_set=True); "
            "bpy.context.scene.blendermcp_use_polyhaven = True"
        )
        kwargs = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
        }
        if platform.system() == "Windows":
            kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True

        subprocess.Popen([blender_bin, "--python-expr", startup_expr], **kwargs)

        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if is_port_open("localhost", port):
                break
            time.sleep(0.5)

    if is_port_open("localhost", port):
        try:
            send_socket_command(
                "execute_code",
                {"code": "import bpy; bpy.context.scene.blendermcp_use_polyhaven = True"},
                port=port,
            )
        except Exception:
            pass
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description="Zero-touch setup for Image-to-Blender MCP + Skill")
    parser.add_argument("--no-launch", action="store_true", help="Do not launch Blender GUI after setup")
    parser.add_argument("--port", type=int, default=9876, help="Blender MCP socket port (default: 9876)")
    args = parser.parse_args()

    blender_bin = find_blender_executable()
    uvx_bin = find_or_install_uvx()
    mcp_config_path = update_antigravity_mcp_config(uvx_bin, port=args.port)

    summary = {
        "os": platform.system(),
        "blender_executable": blender_bin,
        "uvx_executable": uvx_bin,
        "mcp_config_updated": mcp_config_path,
        "addon_setup": None,
        "server_listening": False,
    }

    if not blender_bin:
        summary["status"] = "BLENDER_NOT_FOUND"
        summary["message"] = (
            "MCP config updated, but Blender executable was not found in standard paths. "
            "Install Blender from https://www.blender.org/download/ or set BLENDER_PATH."
        )
        print(json.dumps(summary, indent=2))
        sys.exit(0)

    summary["addon_setup"] = install_and_enable_blender_addon(blender_bin, uvx_bin)

    if not args.no_launch:
        summary["server_listening"] = launch_blender_and_wait(blender_bin, port=args.port)
    else:
        summary["server_listening"] = is_port_open("localhost", args.port)

    summary["status"] = "READY" if summary["server_listening"] else "INSTALLED_OPEN_BLENDER"
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
