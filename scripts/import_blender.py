"""Run this exported package script inside Blender, not the application's Python."""

import json
from pathlib import Path

import bpy

# Text editor scripts may not define __file__.
script_file = globals().get("__file__")
if not script_file:
    text = getattr(bpy.context.space_data, "text", None)
    script_file = getattr(text, "filepath", "")
if not script_file:
    raise RuntimeError("Open the saved import_blender.py file from the unzipped package first.")
root = Path(bpy.path.abspath(script_file)).resolve().parent
manifest = json.loads((root / "manifest.json").read_text())
collection = bpy.data.collections.new("Asset Factory imports")
bpy.context.scene.collection.children.link(collection)
for model in manifest["models"]:
    source = (root / model["path"]).resolve()
    if not source.is_relative_to(root):
        raise RuntimeError("Model path must remain inside the exported package.")
    before = set(bpy.data.objects)
    if source.suffix.lower() == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(source))
    else:
        bpy.ops.import_scene.gltf(filepath=str(source))
    for obj in set(bpy.data.objects) - before:
        obj.name = model["part"] + "_" + obj.name
        for owner in list(obj.users_collection):
            owner.objects.unlink(obj)
        collection.objects.link(obj)
# Do not overwrite an existing exported scene.
output = root / "imported.blend"
number = 1
while output.exists():
    output = root / f"imported-{number}.blend"
    number += 1
bpy.ops.wm.save_as_mainfile(filepath=str(output))
