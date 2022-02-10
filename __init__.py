bl_info = {
    "name": "Attribute Viewer",
    "author": "Gurpreet Singh",
    "blender": (3, 0, 0),
    "category": "Node",
    "location": "Node Editor",
    "version": (0, 0, 1),
}

import bpy

import os

def append_node_group(name, path):
    with bpy.data.libraries.load(path) as (data_from, data_to):
        nt = data_from.node_groups
        data_to.node_groups.append(nt[nt.index(name)])


class AV_OT_viewer(bpy.types.Operator):
    bl_idname = "av.viewer"
    bl_label = "Viewer"

    prop: bpy.props.StringProperty(default='')

    @classmethod
    def poll(cls, context):
        return hasattr(context.space_data, "edit_tree") and context.space_data.tree_type == "GeometryNodeTree" and context.space_data.node_tree.nodes.active

    def get_group_out(self):
        group_out = [node for node in self.node_tree.nodes if node.type == 'GROUP_OUTPUT']
        return group_out[0]

    def set_defaults(self):
        self.viewer.label = self.viewer.name = "Viewer"
        self.viewer.hide = True

        group_out = self.get_group_out()
        self.viewer.location = group_out.location
        self.viewer.location[1] += 40

        if group_out.inputs[-2].name != "tmp_viewer":
            for _input in self.node_tree.outputs:
                if _input.name == "tmp_viewer":
                    self.node_tree.outputs.remove(self.node_tree.outputs["tmp_viewer"])

            self.node_tree.links.new(self.viewer.outputs[0], group_out.inputs[0])
            self.node_tree.links.new(self.viewer.outputs["tmp_viewer"], group_out.inputs[-1])
        else:
            self.node_tree.links.new(self.viewer.outputs[0], group_out.inputs[0])
            self.node_tree.links.new(self.viewer.outputs["tmp_viewer"], group_out.inputs["tmp_viewer"])

    def add_viewer_material(self):
        mat = bpy.data.materials.get(".GeoNodeViewerMat")
        if not mat:
            mat = bpy.data.materials.new(name=".GeoNodeViewerMat")
            mat.use_nodes = True
            attr_node = mat.node_tree.nodes.new(type="ShaderNodeAttribute")
            attr_node.attribute_name = "tmp_viewer"
            mat.node_tree.links.new(attr_node.outputs[0], mat.node_tree.nodes["Material Output"].inputs[0])

        self.viewer.node_tree.nodes["mat"].inputs["Material"].default_value = mat

    def find_mod(self, context):
        mods = [mod for mod in context.object.modifiers if mod.node_group.name == self.node_tree.name]
        return mods[-1]

    def execute(self, context):
        self.node_tree = context.space_data.node_tree
        self.viewer =  self.node_tree.nodes.get("Viewer")
        if not self.viewer:
            viewer_group = bpy.data.node_groups.get(".GeoNodeAttribViewer")
            node = self.node_tree.nodes.new(type="GeometryNodeGroup")
            if not viewer_group:
                append_node_group(".GeoNodeAttribViewer", os.path.join(os.path.dirname(__file__), "extern", "node_groups.blend"))
                node.node_tree = bpy.data.node_groups.get(".GeoNodeAttribViewer")
            else:
                node.node_tree = viewer_group
            self.viewer = node

        self.set_defaults()

        mod = self.find_mod(context)
        self.prop = list(dict(mod.id_properties_ensure()))[-1]
        mod[self.prop] = "tmp_viewer"

        self.add_viewer_material()

        active_node = self.node_tree.nodes.active
        visible_outputs = [_out for _out in active_node.outputs if _out.enabled]

        if active_node.outputs[0].type == 'GEOMETRY':
            self.node_tree.links.new(active_node.outputs[0], self.viewer.inputs[0])

            if active_node.type == 'GROUP_INPUT':
                return {'FINISHED'}

            if len(visible_outputs) > 1:
                visible_outputs.remove(active_node.outputs[0])
            else:
                return {'FINISHED'}

        if not self.viewer.inputs['tmp_viewer'].is_linked:
            if visible_outputs:
                self.node_tree.links.new(visible_outputs[0], self.viewer.inputs[1])
        else:
            link = self.viewer.inputs['tmp_viewer'].links[0]
            _from_sock = link.from_socket
            node = _from_sock.node
            self.node_tree.links.remove(link)
            if not (node == active_node):
                self.node_tree.links.new(visible_outputs[0], self.viewer.inputs[1])
            else:
                try:
                    index = visible_outputs.index(_from_sock)
                except ValueError as err:
                    index = 0
                self.node_tree.links.new(visible_outputs[(index + 1) % len(visible_outputs)], self.viewer.inputs[1])

        return {'FINISHED'}

addon_keymaps = []

def register():
    bpy.utils.register_class(AV_OT_viewer)

    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name="Node Editor", space_type='NODE_EDITOR')

    kmi = km.keymap_items.new("av.viewer", 'V', 'PRESS')
    kmi.active = True
    addon_keymaps.append((km, kmi))

def unregister():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    bpy.utils.unregister_class(AV_OT_viewer)
