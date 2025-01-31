import bpy
import numpy as np
import os
import glob

class Anton_OT_Visualizer(bpy.types.Operator):
    bl_idname = 'anton.visualize'
    bl_label = 'Render'
    bl_description = 'Visualizes generated outcome'

    def execute(self, context):
        """Visualizes the generated outcome with metaballs which are implicit surfaces, meaning that they are not explicitly defined
        by vertices. Metaballs are instantiated at the centroid of each element with a density value above the specified threshold.

        :ivar density_out: Density threshold
        :vartype density_out: ``float``
        :ivar cdists: Distance to each element's centroid from origin
        :vartype cdists: *numpy.array* of ``float``
        :ivar coms: Center of mass of each **slice**
        :vartype coms: *numpy.array* of ``float``

        :return: ``FINISHED`` if successful, ``CANCELLED`` otherwise

        \\
        """
        scene = context.scene

        if scene.anton.optimized:
            last_modified = max(glob.glob(os.path.join(scene.anton.workspace_path, scene.anton.filename, 'output', '*/')), key=os.path.getmtime)
            viz_file = os.path.join(last_modified, 'fem', "{:05d}.tcb.zip".format(scene.anton.viz_iteration - 1))
            density_file = os.path.join(scene.anton.workspace_path, scene.anton.filename, '{:05d}.densities.txt'.format(scene.anton.viz_iteration - 1))
            stl_file = os.path.join(scene.anton.workspace_path, scene.anton.filename, '{}_{:05d}.stl'.format(scene.anton.filename, scene.anton.viz_iteration))

            os.system("ti run convert_fem_solve {} {}".format(viz_file, density_file))

            if os.path.isfile(density_file):
                self.marchthecubes(inp_path=density_file, output_path=stl_file, resolution=scene.anton.res, density_thresh=scene.anton.density_out)

                bpy.ops.import_mesh.stl(filepath=stl_file, global_scale=1)
                bpy.ops.object.modifier_add(type='CORRECTIVE_SMOOTH')
                bpy.context.object.modifiers["CorrectiveSmooth"].factor = 1
                bpy.context.object.modifiers["CorrectiveSmooth"].iterations = 1
                bpy.context.object.modifiers["CorrectiveSmooth"].scale = 0

                self.report({'INFO'}, 'Imported iteration: {}'.format(scene.anton.viz_iteration))
                return {'FINISHED'}
            else:
                return {'CANCELLED'}
        else:
            self.report({'ERROR'}, 'Generate results before visualization!')
            return {'CANCELLED'}

    @staticmethod
    def marchthecubes(inp_path, output_path, resolution=100, density_thresh=0.1):
        from skimage import measure
        import re

        section_pattern = re.compile(r'base_coordinates: \[(?P<X>[.eE\+\-\d]*), (?P<Y>[.eE\+\-\d]*), (?P<Z>[.eE\+\-\d]*)\]')
        coord_pattern = re.compile(r'\[(?P<X>[.eE\+\-\d]*),(?P<Y>[.eE\+\-\d]*),(?P<Z>[.eE\+\-\d]*)\]:\s(?P<DENSITY>[.eE\+\-\d]*)')

        verts = []
        densities = []

        with open(inp_path, 'r') as f:
            base_coord = np.array([0, 0, 0], dtype=int)
            line = f.readline()

            while(line):
                section_match = section_pattern.search(line)
                coord_match = coord_pattern.search(line)
                if section_match:
                    base_coord = np.array(list(map(int, [section_match.group('X'), section_match.group('Y'), section_match.group('Z')]))) - 8

                if coord_match:
                    _coord = base_coord + np.array(list(map(int, [coord_match.group('X'), coord_match.group('Y'), coord_match.group('Z')])))
                    if float(coord_match.group('DENSITY')) >= density_thresh:
                        verts.append(_coord)
                        densities.append(float(coord_match.group('DENSITY')))

                line = f.readline()

        pts = np.array(verts, dtype=int)
        lower_bound = np.floor(np.min(pts, axis=0)) - 2
        upper_bound = np.ceil(np.max(pts, axis=0)) + 2

        grid, _, _ = np.mgrid[lower_bound[0]:upper_bound[0]:1,
                                lower_bound[1]:upper_bound[1]:1,
                                lower_bound[2]:upper_bound[2]:1]

        data_indices = np.array(np.ceil((pts - lower_bound)/1), dtype=int)
        data = 0.0 * grid
        # mask??

        for _index in data_indices:
            try:
                data[_index[0]][_index[1]][_index[2]] = 1
            except:
                pass
            
        vertices, faces, normals, _ = measure.marching_cubes(data)
        vertices = vertices + lower_bound + 0.5
        vertices = 10 * vertices/resolution - 5

        with open(output_path, 'w') as f:
            f.write('solid\n')
            for i, tri in enumerate(faces):
                normal = normals[tri[0]] + normals[tri[1]] + normals[tri[2]]
                f.write('facet normal {} {} {}\n'.format(
                                                        normal[0],
                                                        normal[1],
                                                        normal[2]))

                f.write('outer loop\n')
                for vertex_id in tri:
                    f.write('vertex {} {} {}\n'.format(
                                                        vertices[vertex_id][0],
                                                        vertices[vertex_id][1],
                                                        vertices[vertex_id][2]))

                f.write('endloop\n')
                f.write('endfacet\n')

            f.write('endsolid\n')
