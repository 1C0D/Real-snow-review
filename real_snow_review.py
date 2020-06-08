# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    "name": "Real Snow Review",
    "description": "Generate snow mesh",
    "author": "Wolf <wolf.art3d@gmail.com>, modified by 1COD",
    "version": (1, 2),
    "blender": (2, 83, 0),
    "location": "View 3D > Add Object menu or search bar as an operator",
    "doc_url": "https://github.com/macio97/Real-Snow",
    "tracker_url": "https://github.com/macio97/Real-Snow/issues",
    "support": "COMMUNITY",
    "category": "Object",
    }


import bpy
import bmesh
from mathutils import Vector
import math
import random

from bpy.props import BoolProperty, FloatProperty, IntProperty, PointerProperty
from bpy.types import Operator, Panel, PropertyGroup


def main(self, context, obj, snow_col):

    mesh = bpy.data.meshes.new("Snow")
    bm = bmesh_from_object(context, obj)
    if self.selected_faces:
        down_faces = [face for face in bm.faces if not face.select]
    else:
        down_faces = [face for face in bm.faces if Vector(
        (0, 0, -1.0)).angle(face.normal, 4.0) < (1/self.coverage)]
    bmesh.ops.delete(bm, geom=down_faces, context='FACES_KEEP_BOUNDARY')
    surface_area = sum(face.calc_area() for face in bm.faces)
    bmesh_to_object(bm, mesh)

    snow_object = bpy.data.objects.new("Snow", mesh)
    snow_object.matrix_world = obj.matrix_world
    context.collection.objects.link(snow_object)

    ballobj = add_metaballs(self,context, snow_col)
    snow_object.select_set(True)
    context.view_layer.objects.active = snow_object
    snow = add_particles(self,context, surface_area, snow_object, ballobj)

    add_material(snow)
    # parent with object
    snow.parent = obj
    snow.matrix_parent_inverse = obj.matrix_world.inverted()


class SNOW_OT_Create(Operator):
    bl_idname = "snow.create"
    bl_label = "Create Snow"
    bl_description = "Create snow (need a selection with active object)"
    bl_options = {'REGISTER', 'UNDO'}


    coverage: FloatProperty(
        name = "coverage",
        description = "surface of the object covered by snow",
        default = 0.6,
        step = 1,
        precision = 2,
        soft_min = 0.38,
        soft_max = 0.7
        )

    selected_faces : BoolProperty(
        name = "Selected Faces",
        description = "Add snow only on selected faces",
        default = False
        )

    height : FloatProperty(
        name = "Height",
        description = "Height of the snow",
        default = 0.3,
        step = 1,
        precision = 2,
        soft_min = 0.1,
        soft_max = 1.5
        )

    density : IntProperty(
        name = "density",
        description = "density of the snow",
        default = 85,
        soft_min = 40,
        max = 100,
        subtype = 'FACTOR'
        )

    apply_2_all : BoolProperty(
        name = "apply to all selected",
        description = "",
        default = False,
        )

    @classmethod
    def poll(cls, context):
        #conditions to be run from search console too
        if not context.object in context.selected_objects:
            return False
        if not context.area.type == 'VIEW_3D':
            return False
        if not context.object.mode == 'OBJECT':
            return False

        return True

    def execute(self, context):

        cao=bpy.context.active_object
        snow_col = snow_coll(context.scene)

        if not self.apply_2_all:
            obj=cao
            if obj.type == 'MESH':

                bpy.ops.object.transform_apply(location=False, scale=True, rotation=False)
                main(self, context, obj, snow_col)

        if self.apply_2_all:
            # start UI progress bar
            input_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
            length = len(input_objects)
            wm = context.window_manager
            wm.progress_begin(0, length)
            timer=0

            for obj in context.selected_objects:
                if obj.type == 'MESH':

                    bpy.ops.object.transform_apply(location=False, scale=True, rotation=False)
                    context.view_layer.objects.active = obj
                    main(self, context, obj, snow_col)
                    # timer
                    wm.progress_update(timer)
                    timer += 0.001
            # end progress bar
            wm.progress_end()


        return {'FINISHED'}

def snow_coll(scene):

    if "Snow" in scene.collection.children:
        snow_coll = bpy.data.collections["Snow"]
    else:
        snow_coll = bpy.data.collections.new("Snow")
        scene.collection.children.link(snow_coll)

    return snow_coll

def bmesh_from_object(context,obj):

    if obj.modifiers:
        depsgraph = context.evaluated_depsgraph_get()
        obj_eval = obj.evaluated_get(depsgraph)
        me = obj_eval.to_mesh()
        bm = bmesh.new()
        bm.from_mesh(me)
        obj_eval.to_mesh_clear()
    else:
        me = obj.data
        bm = bmesh.new()
        bm.from_mesh(me)

    return bm

def bmesh_to_object(bm, mesh):
    bm.to_mesh(mesh)
    bm.free()

def add_metaballs(self, context, snow_col) -> bpy.types.Object:
    ball_name = "SnowBall"
    ball = bpy.data.metaballs.new(ball_name)
    ballobj = bpy.data.objects.new(ball_name, ball)
    snow_col.objects.link(ballobj)

    # these settings have proven to work on a large amount of scenarios
    ball.resolution = 0.7*self.height+0.3
    ball.threshold = 1.3
    element = ball.elements.new()
    element.radius = 1.5
    element.stiffness = 0.75
    ballobj.scale = [0.09, 0.09, 0.09]

    return ballobj

def add_particles(self, context, surface_area, snow_object, ballobj):
    # approximate the number of particles to be emitted
    number = int(surface_area*50*(self.height**-2)*((self.density/100)**2))
    bpy.ops.object.particle_system_add()
    particles = snow_object.particle_systems[0]
    psettings = particles.settings
    psettings.type = 'HAIR'
    psettings.render_type = 'OBJECT'
    # generate random number for seed
    random_seed = random.randint(0, 1000)
    particles.seed = random_seed
    # set particles object
    psettings.particle_size = self.height
    psettings.instance_object = ballobj
    psettings.count = number
    # convert particles to mesh
    bpy.ops.object.select_all(action='DESELECT')
    context.view_layer.objects.active = ballobj
    ballobj.select_set(True)
    bpy.ops.object.convert(target='MESH')
    snow = bpy.context.active_object
    snow.scale = [0.09, 0.09, 0.09]
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')
    bpy.ops.object.select_all(action='DESELECT')
    snow_object.select_set(True)
    bpy.ops.object.delete()
    snow.select_set(True)

    return snow

def add_material(obj: bpy.types.Object):
    mat_name = "Snow"
    # if material doesn't exist, create it
    if mat_name in bpy.data.materials:
        bpy.data.materials[mat_name].name = mat_name+".001"
    mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    # delete all nodes
    for node in nodes:
        nodes.remove(node)
    # add nodes
    output = nodes.new('ShaderNodeOutputMaterial')
    principled = nodes.new('ShaderNodeBsdfPrincipled')
    vec_math = nodes.new('ShaderNodeVectorMath')
    com_xyz = nodes.new('ShaderNodeCombineXYZ')
    dis = nodes.new('ShaderNodeDisplacement')
    mul1 = nodes.new('ShaderNodeMath')
    add1 = nodes.new('ShaderNodeMath')
    add2 = nodes.new('ShaderNodeMath')
    mul2 = nodes.new('ShaderNodeMath')
    mul3 = nodes.new('ShaderNodeMath')
    ramp1 = nodes.new('ShaderNodeValToRGB')
    ramp2 = nodes.new('ShaderNodeValToRGB')
    ramp3 = nodes.new('ShaderNodeValToRGB')
    vor = nodes.new('ShaderNodeTexVoronoi')
    noise1 = nodes.new('ShaderNodeTexNoise')
    noise2 = nodes.new('ShaderNodeTexNoise')
    noise3 = nodes.new('ShaderNodeTexNoise')
    mapping = nodes.new('ShaderNodeMapping')
    coord = nodes.new('ShaderNodeTexCoord')
    # change location
    output.location = (100, 0)
    principled.location = (-200, 500)
    vec_math.location = (-400, 400)
    com_xyz.location = (-600, 400)
    dis.location = (-200, -100)
    mul1.location = (-400, -100)
    add1.location = (-600, -100)
    add2.location = (-800, -100)
    mul2.location = (-1000, -100)
    mul3.location = (-1000, -300)
    ramp1.location = (-500, 150)
    ramp2.location = (-1300, -300)
    ramp3.location = (-1000, -500)
    vor.location = (-1500, 200)
    noise1.location = (-1500, 0)
    noise2.location = (-1500, -200)
    noise3.location = (-1500, -400)
    mapping.location = (-1700, 0)
    coord.location = (-1900, 0)
    # change node parameters
    principled.distribution = "MULTI_GGX"
    principled.subsurface_method = "RANDOM_WALK"
    principled.inputs[0].default_value[0] = 0.904
    principled.inputs[0].default_value[1] = 0.904
    principled.inputs[0].default_value[2] = 0.904
    principled.inputs[1].default_value = 1
    principled.inputs[2].default_value[0] = 0.36
    principled.inputs[2].default_value[1] = 0.46
    principled.inputs[2].default_value[2] = 0.6
    principled.inputs[3].default_value[0] = 0.904
    principled.inputs[3].default_value[1] = 0.904
    principled.inputs[3].default_value[2] = 0.904
    principled.inputs[5].default_value = 0.224
    principled.inputs[7].default_value = 0.1
    principled.inputs[13].default_value = 0.1
    vec_math.operation = "MULTIPLY"
    vec_math.inputs[1].default_value[0] = 0.5
    vec_math.inputs[1].default_value[1] = 0.5
    vec_math.inputs[1].default_value[2] = 0.5
    com_xyz.inputs[0].default_value = 0.36
    com_xyz.inputs[1].default_value = 0.46
    com_xyz.inputs[2].default_value = 0.6
    dis.inputs[1].default_value = 0.1
    dis.inputs[2].default_value = 0.3
    mul1.operation = "MULTIPLY"
    mul1.inputs[1].default_value = 0.1
    mul2.operation = "MULTIPLY"
    mul2.inputs[1].default_value = 0.6
    mul3.operation = "MULTIPLY"
    mul3.inputs[1].default_value = 0.4
    ramp1.color_ramp.elements[0].position = 0.525
    ramp1.color_ramp.elements[1].position = 0.58
    ramp2.color_ramp.elements[0].position = 0.069
    ramp2.color_ramp.elements[1].position = 0.757
    ramp3.color_ramp.elements[0].position = 0.069
    ramp3.color_ramp.elements[1].position = 0.757
    vor.feature = "N_SPHERE_RADIUS"
    vor.inputs[2].default_value = 30
    noise1.inputs[2].default_value = 12
    noise2.inputs[2].default_value = 2
    noise2.inputs[3].default_value = 4
    noise3.inputs[2].default_value = 1
    noise3.inputs[3].default_value = 4
    mapping.inputs[3].default_value[0] = 12
    mapping.inputs[3].default_value[1] = 12
    mapping.inputs[3].default_value[2] = 12
    # link nodes
    link = mat.node_tree.links
    link.new(principled.outputs[0], output.inputs[0])
    link.new(vec_math.outputs[0], principled.inputs[2])
    link.new(com_xyz.outputs[0], vec_math.inputs[0])
    link.new(dis.outputs[0], output.inputs[2])
    link.new(mul1.outputs[0], dis.inputs[0])
    link.new(add1.outputs[0], mul1.inputs[0])
    link.new(add2.outputs[0], add1.inputs[0])
    link.new(mul2.outputs[0], add2.inputs[0])
    link.new(mul3.outputs[0], add2.inputs[1])
    link.new(ramp1.outputs[0], principled.inputs[12])
    link.new(ramp2.outputs[0], mul3.inputs[0])
    link.new(ramp3.outputs[0], add1.inputs[1])
    link.new(vor.outputs[4], ramp1.inputs[0])
    link.new(noise1.outputs[0], mul2.inputs[0])
    link.new(noise2.outputs[0], ramp2.inputs[0])
    link.new(noise3.outputs[0], ramp3.inputs[0])
    link.new(mapping.outputs[0], vor.inputs[0])
    link.new(mapping.outputs[0], noise1.inputs[0])
    link.new(mapping.outputs[0], noise2.inputs[0])
    link.new(mapping.outputs[0], noise3.inputs[0])
    link.new(coord.outputs[3], mapping.inputs[0])
    # set displacement and add material
    mat.cycles.displacement_method = "DISPLACEMENT"
    obj.data.materials.append(mat)


def add_object_snow_button(self, context):
    pass
    self.layout.operator(
        "snow.create",
        text="Add Snow",
        icon="FREEZE")

# Register
def register():

    bpy.utils.register_class(SNOW_OT_Create)
    bpy.types.VIEW3D_MT_mesh_add.append(add_object_snow_button)

# Unregister
def unregister():

    bpy.utils.unregister_class(SNOW_OT_Create)
    bpy.types.VIEW3D_MT_mesh_add.remove(add_object_snow_button)

if __name__ == "__main__":
    register()

