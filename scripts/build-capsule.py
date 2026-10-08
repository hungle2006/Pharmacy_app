"""Run with Blender: blender --background --python scripts/build-capsule.py.
Creates an editable source scene and a small web-ready GLB. No textures required.
"""
import bpy
import math
from pathlib import Path

root = Path(__file__).resolve().parents[1]
dest = root / 'assets' / 'models'
dest.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

def material(name, color, metallic, roughness):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['Roughness'].default_value = roughness
    return mat

mint = material('Satin jade enamel', (0.12, 0.62, 0.39), 0.32, 0.23)
ivory = material('Pearl ceramic', (0.88, 0.95, 0.90), 0.20, 0.20)
gold = material('Champagne seam', (0.66, 0.82, 0.62), 0.75, 0.22)

def half(name, sign, mat):
    rings = [(0.015, 0.66), (0.92, 0.66)]
    for i in range(1, 21):
        a = i / 20 * math.pi / 2
        rings.append((0.92 + 0.66 * math.sin(a), max(0.0001, 0.66 * math.cos(a))))
    vertices = [(r * math.cos(j / 64 * math.tau), r * math.sin(j / 64 * math.tau), sign * z)
                for z, r in rings for j in range(64)]
    faces = []
    for i in range(len(rings) - 1):
        for j in range(64):
            face = (i * 64 + j, i * 64 + (j + 1) % 64, (i + 1) * 64 + (j + 1) % 64, (i + 1) * 64 + j)
            faces.append(face if sign > 0 else face[::-1])
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    for face in mesh.polygons:
        face.use_smooth = True
    return obj

half('Jade cap', 1, mint)
half('Pearl body', -1, ivory)
bpy.ops.mesh.primitive_torus_add(major_segments=64, minor_segments=8, major_radius=0.658, minor_radius=0.018)
bpy.context.object.name = 'Precision join'
bpy.context.object.data.materials.append(gold)
for p in bpy.context.object.data.polygons:
    p.use_smooth = True

bpy.ops.wm.save_as_mainfile(filepath=str(dest / 'pharmabiz-capsule.blend'))
bpy.ops.export_scene.gltf(filepath=str(dest / 'pharmabiz-capsule.glb'), export_format='GLB', export_animations=False)
print('Exported Blender capsule:', bpy.app.version_string)

# CPU-rendered transparent fallback uses the same Blender model and materials.
from mathutils import Vector
capsule_objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
pivot = bpy.data.objects.new('Poster pose', None)
bpy.context.collection.objects.link(pivot)
for obj in capsule_objects:
    obj.parent = pivot
pivot.rotation_euler = (0, math.radians(-34), 0)
bpy.ops.object.camera_add(location=(0, -8, 3))
camera = bpy.context.object
camera.name = 'Studio camera'
camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 4.4
bpy.context.scene.camera = camera
for name, position, power, size in [('Key',(-3,-4,5),650,4),('Softbox',(4,-2,2),420,3),('Rim',(2,3,4),800,3)]:
    bpy.ops.object.light_add(type='AREA', location=position)
    lamp = bpy.context.object
    lamp.name = name
    lamp.data.energy = power
    lamp.data.shape = 'DISK'
    lamp.data.size = size
    lamp.rotation_euler = (-lamp.location).to_track_quat('-Z', 'Y').to_euler()
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 32
scene.cycles.use_denoising = True
scene.render.threads_mode = 'FIXED'
scene.render.threads = 4
scene.render.resolution_x = scene.render.resolution_y = 800
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.filepath = str(dest / 'capsule-poster.png')
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.3
bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(dest / 'pharmabiz-capsule.blend'))
