# Project constraints

- All generated 3D models must request quad meshes (`quad=true`). Never fall back to triangle generation.
- Head targets 5,000 faces; Body & outfit and Hair target 20,000 faces. Generate geometry before materials.
- Standard component generation uses four separate approved images in Tripo order front, left, back, right. Do not silently use only Front.
- Preserve original FBX as the authoritative export. Triangulated GLB is a derived browser preview, not the original quad topology.
- Preserve generated images/models and project history when rewinding workflow. Do not commit generated assets or secrets.
- Head reference ends on the neck shaft before outward shoulder transition. Body retains shoulders plus a short upward neck-shaft allowance for joining; do not add a full duplicate neck.
