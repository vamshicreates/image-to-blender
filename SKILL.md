---
name: image-to-blender
description: >-
  Cross-platform (Windows, macOS, Linux) AI Agent Skill to reconstruct and build
  3D scenes, props, environments, and animations in Blender from any reference
  image or prompt. Includes zero-touch MCP + Blender Add-on auto-installer,
  direct TCP socket bridge (works without restarting the IDE), and a 5-stage
  visual closed-loop workflow. Activate whenever the user provides a reference
  image or asks to create, model, build, render, or set up Blender.
---

# Image-to-Blender (`image-to-blender`)

A cross-platform (**Windows, macOS, and Linux**) AI Agent Skill that turns any reference image (concept art, product photo, isometric room, architectural interior, stylized prop, or 3D icon) into a complete, well-lit 3D Blender scene using **MCP for Blender** (`mcp-for-blender`) + a built-in **Direct Socket CLI Bridge (`scripts/blender_cli.py`)** and a **5-Stage Multimodal Closed-Loop Pipeline**.

---

## Cross-Platform Execution Notes (Windows & macOS/Linux)

- **Python Command:**
  - **Windows (PowerShell / CMD):** Use `python` (or `py -3`).
  - **macOS / Linux:** Use `python3`.
- **Skill Directory Resolution:**
  - Determine `<SKILL_DIR>` as either `.agents/skills/image-to-blender` (workspace) or `~/.gemini/config/skills/image-to-blender` (global).

---

## Stage 0: Zero-Touch Auto-Setup & Connection Check (Run First)

Whether the user asks to *"set up Blender"* or immediately drops a reference image and says *"build this in Blender"*, **always verify the connection first**:

1. **If `mcp_blender_*` tools are already active in your toolset**:
   - Call `get_scene_info` to confirm Blender's socket server (`localhost:9876`) is responding.
2. **If `mcp_blender_*` tools are NOT loaded yet (first run after cloning, before IDE restart) OR if `get_scene_info` fails to connect**:
   - Run the zero-touch installer & launcher script (use `python` on Windows, `python3` on macOS/Linux):
     ```bash
     python3 <SKILL_DIR>/scripts/setup_blender_mcp.py
     ```
   - **What `setup_blender_mcp.py` does automatically (Zero manual clicks required):**
     1. Finds the existing Blender installation on Windows (`C:\Program Files\Blender Foundation\Blender *\blender.exe`), macOS (`/Applications/Blender.app`), or Linux (`blender`).
     2. Installs `uv` / `uvx` if missing and resolves its absolute binary path.
     3. Copies the bundled [`assets/blender_mcp.py`](assets/blender_mcp.py) add-on into Blender's `scripts/addons/` directory and runs headless Blender once (`addon_utils.enable('blender_mcp', default_set=True); bpy.ops.wm.save_userpref()`) to permanently enable the add-on and its auto-start socket server (`localhost:9876`).
     4. Registers `"blender"` inside `~/.gemini/config/mcp_config.json`.
     5. Launches Blender GUI in the background, waits for port `9876` to listen, and enables **Poly Haven** integration automatically.
3. **Dual-Mode Execution (Native MCP or Direct CLI Bridge)**:
   - If native MCP tools (`execute_blender_code`, `get_viewport_screenshot`, `get_scene_info`) are loaded in the session, you may use them directly.
   - **If native MCP tools are not loaded yet (no IDE restart needed!)**, execute every step seamlessly using [`scripts/blender_cli.py`](scripts/blender_cli.py):
     ```bash
     # Check status & auto-launch Blender if closed
     python3 <SKILL_DIR>/scripts/blender_cli.py status

     # Inspect scene or specific object
     python3 <SKILL_DIR>/scripts/blender_cli.py scene-info
     python3 <SKILL_DIR>/scripts/blender_cli.py object-info Main_Camera

     # Execute a .py script in Blender (auto-injects scripts/bpy_helpers.py into sys.path!)
     python3 <SKILL_DIR>/scripts/blender_cli.py exec -f /path/to/step_script.py

     # Capture live 3D viewport screenshot to PNG for visual inspection via view_file
     python3 <SKILL_DIR>/scripts/blender_cli.py screenshot ./blender_preview.png --max-size 1200

     # Search & download free Poly Haven HDRIs, PBR textures, and 3D models
     python3 <SKILL_DIR>/scripts/blender_cli.py polyhaven-search hdris --categories studio
     python3 <SKILL_DIR>/scripts/blender_cli.py polyhaven-download studio_small_09 hdris --resolution 1k
     ```

---

## The 5-Stage Image-to-Blender Pipeline

Never dump a single giant, blind Python script of raw cubes and spheres. Follow these 5 stages in order:

### Stage 1: Reference Deconstruction & 3-Lane Routing
Inspect the user's reference image carefully with `view_file` and present a concise **3D Scene Blueprint**:

1. **Camera & Perspective Spec**:
   - **Projection**: Perspective (`PERSP`) vs. Orthographic / Isometric (`ORTHO`).
   - **Focal Length Estimate**: Wide (`24mm–35mm` for interiors/landscapes), Standard (`50mm`), Telephoto/Product (`85mm–135mm` for hero props/portraits).
   - **Camera Angle**: Elevation angle, horizon placement, and aspect ratio (`16:9`, `1:1`, `4:5`, `9:16`).
2. **Lighting & Atmosphere Spec**:
   - Key light direction, softness (area size), color temperature (warm/cool), fill/rim ratio, background/cyclorama color, and HDRI/fog needs.
3. **Object Inventory & 3-Lane Hybrid Routing**:
   Assign every distinct element in the reference image to the appropriate construction lane:
   - **Lane A — Procedural / Hard-Surface / Architectural (`bpy` + BMesh + Modifiers + Curves)**:
     Walls, floors, cycloramas, tables, shelves, isometric rooms, bottles/glassware (Spin/Screw modifier), cables/tubes (Bezier curves + bevel depth), rounded hard-surface gadgets (Bevel + Subdivision + Boolean), typography, and geometric motion graphics.
   - **Lane B — Real-World Assets, PBR Materials & HDRIs (`Poly Haven` / `Sketchfab` / `Poly Pizza`)**:
     Use Poly Haven (`polyhaven-search` / `polyhaven-download`) for studio/outdoor HDRIs, photorealistic wood/marble/concrete/fabric PBR textures, and complex furniture/foliage props.
   - **Lane C — Organic / Sculpted Hero Meshes (`Hyper3D Rodin` / `Tripo3D` / `Hunyuan3D` or Subdivision/Metaball Modeling)**:
     If external 3D generation API keys are configured in Blender, route organic characters/sculptures to Image-to-3D generation; otherwise construct clean subdivision-surface / metaball / skin-modifier geometry in `bpy`.

---

### Stage 2: Scene Setup, Camera Lock & Reference Plane
Run a setup script in Blender (using `bpy_helpers` which is auto-imported via `blender_cli.py exec`):

```python
import bpy
from bpy_helpers import ensure_collection, setup_camera_with_target

# Clean default Cube/Light if starting fresh
for name in ("Cube", "Light", "Camera"):
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)

for col_name in ("00_Reference", "01_Camera_Lights", "02_Environment", "03_Hero_Objects", "04_Props"):
    ensure_collection(col_name)

setup_camera_with_target(
    location=(0.0, -4.2, 2.0),
    target=(0.0, 0.0, 0.75),
    focal_length=50.0,
    res_x=1920,
    res_y=1080,
    ref_image_path=r"/absolute/path/to/reference_image.png",
)
```

---

### Stage 3: Greybox Blockout & Spatial Grounding Verification
Before adding fine details, block out major volumes and **verify physical grounding**:
1. **Never Guess Z-Heights Blindly**: Every object must rest physically on the floor (`Z = 0`) or on top of its parent support surface.
2. Use the world-space bounding-box helpers from [`scripts/bpy_helpers.py`](scripts/bpy_helpers.py):
   - `normalize_to_size(obj, target_max_dim=1.2)` — Normalizes imported or procedural meshes to exact real-world meter dimensions.
   - `place_on_z(obj, target_z=0.0, x=0.0, y=0.0)` — Snaps the lowest world-space vertex (`min_z`) to the floor.
   - `place_on_top(obj, support_obj, offset_x=0.0, offset_y=0.0)` — Places `obj` directly resting on the top surface (`max_z`) of `support_obj`.
3. **Checkpoint 1**: Capture a viewport screenshot (`blender_cli.py screenshot`) and view it with `view_file` to verify camera framing and blockout proportions before detailing.

---

### Stage 4: Detailed Modeling, Materials & Lighting
1. **Geometry Quality Rules**:
   - Never leave sharp, un-beveled default primitives! Call `add_bevel_and_smooth(obj, width=0.01, segments=3, subsurf_levels=1)` from [`bpy_helpers.py`](scripts/bpy_helpers.py) so edges catch realistic specular highlights.
   - Use **BMesh**, **Extrusions**, **Inset Faces**, **Curve Profiles**, **Array**, **Mirror**, **Solidify**, and **Boolean** modifiers to build real architectural and product details (panel gaps, chamfers, legs, handles, frames, moldings).
2. **Blender 4.x / 5.x Safe PBR Materials**:
   - Use `create_pbr_material(name, base_color, metallic, roughness, transmission, ior, emission_color, emission_strength)` from [`bpy_helpers.py`](scripts/bpy_helpers.py) which handles both Blender 3.x and Blender 4.x/5.x Principled BSDF socket names (`"Specular IOR Level"`, `"Transmission Weight"`, `"Emission Color"`).
3. **Lighting & Color Management**:
   - Build a motivated 3-point lighting setup (Key Area Light, Fill Area Light, Rim Light) + Poly Haven HDRI or procedural World sky.
   - Configure `AgX` (or `Filmic` fallback) view transform for high dynamic range rolloff.

---

### Stage 5: Multimodal Closed-Loop Critique & Final Render
1. **Visual Audit Loop (Minimum 2 Passes)**:
   - Render a fast preview (`bpy.ops.render.render(write_still=True)`) or capture a viewport screenshot (`blender_cli.py screenshot`) and inspect it with `view_file` alongside the user's reference image.
   - Evaluate 5 strict criteria:
     1. **Silhouette & Proportions**: Do object aspect ratios and relative sizes match the reference?
     2. **Contact & Grounding**: Are all objects resting on surfaces without floating or clipping?
     3. **Camera Framing**: Do horizon line, perspective convergence, and cropping match?
     4. **Color & Surface Feel**: Are roughness, metallic reflections, and colors accurate?
     5. **Light & Shadow Direction**: Do cast shadows point the same way with matching softness?
2. **Self-Correction**: Apply targeted fixes in Blender for any discrepancies, then re-verify with a fresh screenshot/render.
3. **Final Output**: Save the `.blend` file (`bpy.ops.wm.save_as_mainfile(...)`) and render the final high-resolution image to the workspace so the user has both the live interactive Blender scene and the rendered still.
