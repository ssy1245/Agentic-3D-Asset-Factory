"""Run this exported package script inside Blender, not the application's Python."""

import json
from pathlib import Path

import bpy

# Blender may set __file__ to a virtual <scene.blend>/<text-name> path.
# A real saved text path is preferred; never treat the .blend file as a directory.
text = getattr(bpy.context.space_data, "text", None)
candidates = []
for script_file in (getattr(text, "filepath", ""), globals().get("__file__", "")):
    if not script_file:
        continue
    path = Path(bpy.path.abspath(script_file)).resolve()
    if path.is_file():
        candidates.append(path.parent)
    elif path.parent.suffix.lower() == ".blend":
        candidates.append(path.parent.parent)
if bpy.data.filepath:
    candidates.append(Path(bpy.data.filepath).resolve().parent)
root = next((folder for folder in candidates if (folder / "manifest.json").is_file()), None)
if root is None:
    raise RuntimeError(
        "Cannot find manifest.json. Unzip the complete package, then use Text > Open "
        "to open import_blender.py from that folder (do not paste it into a new text block). "
        "Alternatively save the current .blend in the unzipped package folder."
    )
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
collection = bpy.data.collections.new(manifest.get("project_name", "Asset Factory imports"))
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
        obj.name = source.stem + "_" + obj.name
        for owner in list(obj.users_collection):
            owner.objects.unlink(obj)
        collection.objects.link(obj)
# Do not overwrite an existing exported scene.
output_name = manifest.get("output_name", "imported")
if not isinstance(output_name, str) or not output_name or output_name in {".", ".."} or any(c in output_name for c in '<>:"/\\|?*') or any(ord(c) < 32 for c in output_name):
    raise RuntimeError("Unsupported output name in manifest.")
output = root / f"{output_name}.blend"
number = 1
while output.exists():
    output = root / f"{output_name}-{number}.blend"
    number += 1
bpy.ops.wm.save_as_mainfile(filepath=str(output))
