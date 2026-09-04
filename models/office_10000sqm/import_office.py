"""Import the exact web GLB into editable Blender objects and save a .blend.
Usage: blender --background --python models/office_10000sqm/import_office.py -- --input .generated/office_10000sqm/solstice-14.glb --output .generated/office_10000sqm/solstice-14.blend
Run in a NEW Blender process; this script clears the scene in that process.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
import bpy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    source = args.input.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if source.suffix.lower() != '.glb':
        raise ValueError('Expected the exported .glb file')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(source))
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    groups = {}
    for n in range(15):
        name = '00 Site' if n == 0 else f'{n:02d} Floor {n}'
        collection = bpy.data.collections.new(name)
        scene.collection.children.link(collection)
        groups[n] = collection
    count = 0
    for obj in list(scene.objects):
        if obj.type != 'MESH':
            continue
        floor = int(obj.get('floor', 0))
        target = groups.get(floor, groups[0])
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)
        target.objects.link(obj)
        obj['design_status'] = 'Concept only; not for construction'
        if 'canopy' in obj.name.lower() or 'shrub' in obj.name.lower():
            for polygon in obj.data.polygons:
                polygon.use_smooth = True
        count += 1
    scene['project'] = 'SOLSTICE 14'
    scene['gross_area_m2'] = 10000
    scene['occupied_storeys'] = 14
    scene['energy_simulated'] = False
    scene['area_basis'] = 'Includes 144 m2 covered sky terraces; not statutory GFA or net lettable area'
    light_data = bpy.data.lights.new('Concept sun', type='SUN')
    light_data.energy = 3.0
    light_data.angle = 0.10
    light = bpy.data.objects.new('Concept sun', light_data)
    scene.collection.objects.link(light)
    light.rotation_euler = (0.55, -0.50, -0.35)
    scene.world.color = (0.35, 0.35, 0.35)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    print(f'Saved {count} metric mesh objects to {output}')


if __name__ == '__main__':
    main()
