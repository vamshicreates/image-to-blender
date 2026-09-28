# Image-to-Blender (`image-to-blender`)

A cross-platform (**Windows, macOS, and Linux**) AI Agent Skill that connects **Antigravity / Claude Code / Cursor** directly to **Blender** and turns any reference image into a complete, well-lit 3D Blender scene using a **5-Stage Multimodal Closed-Loop Workflow**.

Built for **zero manual setup** on any laptop that already has Blender installed.

---

## ✨ What This Skill Does Automatically

1. **Zero-Touch Auto-Installer (`scripts/setup_blender_mcp.py`)**:
   - **Auto-detects Blender** across Windows (`C:\Program Files\Blender Foundation\Blender *\blender.exe`), macOS (`/Applications/Blender.app`), and Linux (`blender`).
   - **Auto-installs `uv` / `uvx`** if missing and resolves its exact binary path (preventing GUI `spawn uvx ENOENT` errors).
   - **Installs & Permanently Enables the Blender MCP Add-on (`assets/blender_mcp.py`)** via headless Blender (`addon_utils.enable('blender_mcp', default_set=True); bpy.ops.wm.save_userpref()`) — **you never have to open Edit → Preferences → Add-ons or click "Start MCP Server"**.
   - **Auto-configures `~/.gemini/config/mcp_config.json`** (preserving existing MCP servers and creating a backup).
   - **Auto-launches Blender** with the socket server listening on `localhost:9876` and enables **Poly Haven** asset integration out of the box.

2. **Direct Zero-Restart CLI Bridge (`scripts/blender_cli.py`)**:
   - Works **immediately inside your current chat session** without waiting to restart Antigravity/Claude.
   - Executes `bpy` scripts, queries scene/object bounding boxes, downloads free Poly Haven HDRIs/textures/models, and captures offscreen GPU viewport screenshots (`get_viewport_screenshot`).

3. **5-Stage Reference-to-3D Pipeline (`SKILL.md` + `scripts/bpy_helpers.py`)**:
   - **Stage 1 — Reference Deconstruction & 3-Lane Routing**: Extracts camera focal length, perspective/isometric projection, lighting mood, and routes objects across Procedural `bpy`/Modifiers (Lane A), Poly Haven/Sketchfab PBR Assets (Lane B), or AI Image-to-3D Meshes (Lane C).
   - **Stage 2 — Camera Lock & Reference Overlay**: Locks camera framing with a `Track To` constraint and attaches the reference image as a semi-transparent Camera Background Image.
   - **Stage 3 — Greybox Blockout & Ground-Snapping**: Uses world-space bounding-box math (`place_on_z`, `place_on_top`, `normalize_to_size`) so objects rest physically on floors and tables without floating or clipping.
   - **Stage 4 — Detailed Modeling, PBR Shaders & Lighting**: Applies bevels, subdivision surfaces, Blender 3.x/4.x/5.x compatible Principled BSDF materials, and motivated 3-point + HDRI lighting.
   - **Stage 5 — Multimodal Visual Self-Correction Loop**: Captures live viewport screenshots/renders, compares them side-by-side against the reference image, and iteratively refines until proportions, grounding, materials, and lighting match.

---

## 📂 Repository Structure

```text
image-to-blender/
├── SKILL.md                        # Main 5-Stage Agent Skill instruction file
├── README.md                       # Quickstart & documentation
├── LICENSE                         # MIT License
├── assets/
│   └── blender_mcp.py              # Bundled MCP for Blender add-on (auto-start enabled)
└── scripts/
    ├── setup_blender_mcp.py        # Cross-platform zero-touch installer & Blender launcher
    ├── blender_cli.py              # Direct TCP socket CLI bridge (works without IDE restart)
    └── bpy_helpers.py              # Reusable Blender 3.x/4.x/5.x bounding-box, camera & PBR helpers
```

---

## 🚀 How to Install & Use (For Your Friend's Laptop)

> **Prerequisite:** [Blender](https://www.blender.org/download/) (3.0 or newer) installed on the laptop. Everything else is handled automatically.

### Option 1: Zero-Touch via Antigravity Chat (Recommended)
Just paste this prompt into Antigravity:
> *"Install the skill from `https://github.com/vamshicreates/image-to-blender` into `.agents/skills/image-to-blender` and run its setup script."*

### Option 2: 1-Line Terminal Install (macOS / Linux / Windows Git Bash)
```bash
git clone https://github.com/vamshicreates/image-to-blender.git .agents/skills/image-to-blender && python3 .agents/skills/image-to-blender/scripts/setup_blender_mcp.py
```
*(On Windows PowerShell, replace `python3` with `python`).*

---

## 🎨 Usage

Once installed, simply **drop any reference image into chat** and say:
> *"Create this in Blender."*

The agent will automatically launch Blender (if not already open), analyze your reference image, construct the 3D scene, inspect live viewport screenshots to self-correct proportions/lighting, and save both the `.blend` file and final render.
