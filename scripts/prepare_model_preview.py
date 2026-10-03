"""Background Blender worker: inspect original FBX polygons and export preview GLB."""
import json
import sys
from pathlib import Path

import bpy

source, output, metadata = map(Path, sys.argv[sys.argv.index("--") + 1:])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(source))
meshes = [obj.data for obj in bpy.context.scene.objects if obj.type == "MESH"]
if not meshes:
    raise RuntimeError("FBX has no meshes")
sizes = [len(p.vertices) for mesh in meshes for p in mesh.polygons]
stats = {"meshes": len(meshes), "faces": len(sizes), "quad_faces": sizes.count(4), "triangle_faces": sizes.count(3), "other_faces": sum(n not in (3, 4) for n in sizes), "materials": len(bpy.data.materials)}
metadata.write_text(json.dumps(stats))
# GLB triangulates for rendering; the original FBX is never exported over or modified.
bpy.ops.export_scene.gltf(filepath=str(output), export_format="GLB")
