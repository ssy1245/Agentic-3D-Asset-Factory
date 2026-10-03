"""Build a standalone scene in Blender's isolated background process."""
import json
import sys
from pathlib import Path

import bpy

manifest = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
collection = bpy.data.collections.new(manifest["project_name"])
bpy.context.scene.collection.children.link(collection)
for model in manifest["models"]:
    source = Path(model["path"])
    before = set(bpy.data.objects)
    if source.suffix.lower() == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(source))
    else:
        bpy.ops.import_scene.gltf(filepath=str(source))
    for obj in set(bpy.data.objects) - before:
        obj.name = manifest["project_name"] + "_" + model["part"] + "_" + obj.name
        for owner in list(obj.users_collection):
            owner.objects.unlink(obj)
        collection.objects.link(obj)
# Make the .blend portable, including imported textures.
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=manifest["output"], compress=False)
