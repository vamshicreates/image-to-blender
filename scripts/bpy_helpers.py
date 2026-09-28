"""
Reusable Blender Python (bpy) helpers for the `image-to-blender` skill.
Includes Live Foreground Viewport Redraw (`live_viewport_update`) and automatic
Material Preview / Camera View switching so the user watches every 3D object,
modifier, material, and light appear live on screen on both macOS and Windows.
Compatible with Blender 3.6, 4.0, 4.1, 4.2, 4.3, 4.4, and 5.x.
"""

import bpy
import math
import time
from mathutils import Vector


def live_viewport_update(pause_sec: float = 0.18, shading_mode: str = None, frame_all: bool = False):
    """
    Force Blender's 3D Viewport to redraw immediately in the foreground so the user
    watches objects, modifiers, materials, and lights appear step-by-step in real time.
    """
    try:
        bpy.context.view_layer.update()
    except Exception:
        pass

    if not bpy.app.background:
        try:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == "VIEW_3D":
                        for space in area.spaces:
                            if space.type == "VIEW_3D" and shading_mode:
                                try:
                                    space.shading.type = shading_mode
                                except Exception:
                                    pass
                        if frame_all:
                            region = next((r for r in area.regions if r.type == "WINDOW"), None)
                            if region:
                                with bpy.context.temp_override(window=window, area=area, region=region):
                                    try:
                                        bpy.ops.view3d.view_all(center=False)
                                    except Exception:
                                        pass
                        area.tag_redraw()
            bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
        except Exception:
            pass

        if pause_sec > 0:
            time.sleep(pause_sec)


def set_viewport_to_camera(shading_mode: str = "MATERIAL"):
    """Switch the active 3D Viewport to look through the active Scene Camera with Material or Rendered shading."""
    if bpy.app.background:
        return
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "VIEW_3D":
                    for space in area.spaces:
                        if space.type == "VIEW_3D":
                            if shading_mode:
                                try:
                                    space.shading.type = shading_mode
                                except Exception:
                                    pass
                            if space.region_3d:
                                space.region_3d.view_perspective = "CAMERA"
                    area.tag_redraw()
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
    except Exception:
        pass


def ensure_collection(name: str, parent=None):
    """Get or create a collection and link it to the scene or parent collection."""
    if name in bpy.data.collections:
        col = bpy.data.collections[name]
    else:
        col = bpy.data.collections.new(name)
        target_parent = parent or bpy.context.scene.collection
        target_parent.children.link(col)
    return col


def move_to_collection(obj, col_name: str):
    """Move an object exclusively into the named collection and redraw viewport."""
    col = ensure_collection(col_name)
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)
    live_viewport_update(0.10)


def get_world_bounds(obj):
    """
    Return (min_vec, max_vec, dimensions, center) in world space,
    accounting for modifiers and object transforms.
    """
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    corners = [eval_obj.matrix_world @ Vector(corner) for corner in eval_obj.bound_box]
    xs = [c.x for c in corners]
    ys = [c.y for c in corners]
    zs = [c.z for c in corners]
    min_v = Vector((min(xs), min(ys), min(zs)))
    max_v = Vector((max(xs), max(ys), max(zs)))
    dims = max_v - min_v
    center = (min_v + max_v) * 0.5
    return min_v, max_v, dims, center


def normalize_to_size(obj, target_max_dim: float = 1.0):
    """Uniformly scale an object so its largest world dimension equals target_max_dim."""
    _, _, dims, _ = get_world_bounds(obj)
    current_max = max(dims.x, dims.y, dims.z)
    if current_max > 1e-6:
        factor = target_max_dim / current_max
        obj.scale = (obj.scale.x * factor, obj.scale.y * factor, obj.scale.z * factor)
        live_viewport_update(0.12)
    return obj


def place_on_z(obj, target_z: float = 0.0, x: float = None, y: float = None):
    """Snap an object's bottom-most world Z coordinate to target_z (prevents floating/clipping)."""
    min_v, _, _, center = get_world_bounds(obj)
    dz = target_z - min_v.z
    obj.location.z += dz
    if x is not None:
        obj.location.x += (x - center.x)
    if y is not None:
        obj.location.y += (y - center.y)
    live_viewport_update(0.15)
    return obj


def place_on_top(obj, support_obj, offset_x: float = 0.0, offset_y: float = 0.0):
    """Place `obj` directly resting on the top surface of `support_obj`."""
    _, support_max, _, support_center = get_world_bounds(support_obj)
    return place_on_z(
        obj,
        target_z=support_max.z,
        x=support_center.x + offset_x,
        y=support_center.y + offset_y,
    )


def add_bevel_and_smooth(obj, width: float = 0.01, segments: int = 3, subsurf_levels: int = 0):
    """Apply realistic edge bevels and smooth shading so primitives never look like raw programmer art."""
    if obj.type != "MESH":
        return obj
    bev = obj.modifiers.new(name="Bevel", type="BEVEL")
    bev.width = width
    bev.segments = segments
    bev.limit_method = "ANGLE"
    bev.angle_limit = math.radians(30)

    if subsurf_levels > 0:
        sub = obj.modifiers.new(name="Subdivision", type="SUBSURF")
        sub.levels = subsurf_levels
        sub.render_levels = subsurf_levels

    bpy.context.view_layer.objects.active = obj
    for poly in obj.data.polygons:
        poly.use_smooth = True
    live_viewport_update(0.15)
    return obj


def create_pbr_material(
    name: str,
    base_color=(0.8, 0.8, 0.8, 1.0),
    metallic: float = 0.0,
    roughness: float = 0.4,
    transmission: float = 0.0,
    ior: float = 1.45,
    emission_color=None,
    emission_strength: float = 0.0,
):
    """Create a Principled BSDF material compatible across Blender 3.x, 4.x, and 5.x."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not bsdf:
        bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")

    if len(base_color) == 3:
        base_color = (*base_color, 1.0)
    bsdf.inputs["Base Color"].default_value = base_color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if "IOR" in bsdf.inputs:
        bsdf.inputs["IOR"].default_value = ior

    for sock_name in ("Transmission Weight", "Transmission"):
        if sock_name in bsdf.inputs:
            bsdf.inputs[sock_name].default_value = transmission
            break

    if emission_color and emission_strength > 0:
        if len(emission_color) == 3:
            emission_color = (*emission_color, 1.0)
        for sock_name in ("Emission Color", "Emission"):
            if sock_name in bsdf.inputs:
                bsdf.inputs[sock_name].default_value = emission_color
                break
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emission_strength

    live_viewport_update(0.10, shading_mode="MATERIAL")
    return mat


def setup_camera_with_target(
    location=(0.0, -4.5, 2.2),
    target=(0.0, 0.0, 0.8),
    focal_length: float = 50.0,
    ortho_scale: float = None,
    res_x: int = 1920,
    res_y: int = 1080,
    ref_image_path: str = None,
    switch_viewport_to_cam: bool = True,
):
    """Create or update the active scene camera with a Track-To target Empty and optional reference image overlay."""
    scene = bpy.context.scene
    scene.render.resolution_x = res_x
    scene.render.resolution_y = res_y

    target_obj = bpy.data.objects.get("Camera_Target")
    if not target_obj:
        target_obj = bpy.data.objects.new("Camera_Target", None)
        ensure_collection("01_Camera_Lights").objects.link(target_obj)
    target_obj.location = Vector(target)

    cam_obj = bpy.data.objects.get("Main_Camera")
    if not cam_obj:
        cam_data = bpy.data.cameras.new("Main_Camera")
        cam_obj = bpy.data.objects.new("Main_Camera", cam_data)
        ensure_collection("01_Camera_Lights").objects.link(cam_obj)
    else:
        cam_data = cam_obj.data

    cam_obj.location = Vector(location)
    if ortho_scale is not None:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = ortho_scale
    else:
        cam_data.type = "PERSP"
        cam_data.lens = focal_length

    track = next((c for c in cam_obj.constraints if c.type == "TRACK_TO"), None)
    if not track:
        track = cam_obj.constraints.new(type="TRACK_TO")
    track.target = target_obj
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"

    if ref_image_path:
        try:
            img = bpy.data.images.load(ref_image_path, check_existing=True)
            cam_data.show_background_images = True
            bg = cam_data.background_images.new() if not cam_data.background_images else cam_data.background_images[0]
            bg.image = img
            bg.alpha = 0.35
            bg.display_depth = "FRONT"
        except Exception as exc:
            print(f"Could not attach reference image: {exc}")

    scene.camera = cam_obj
    if switch_viewport_to_cam:
        set_viewport_to_camera("MATERIAL")
    live_viewport_update(0.20)
    return cam_obj, target_obj
