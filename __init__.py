bl_info = {
    "name": "Attribute Viewer",
    "author": "Gurpreet Singh",
    "blender": (3, 0, 0),
    "category": "Node",
    "location": "Node Editor",
    "version": (0, 0, 1),
}

import bpy
import rna_keymap_ui

import os

def append_node_group(name, path):
    with bpy.data.libraries.load(path, link=True) as (data_from, data_to):
        nt = data_from.node_groups
        data_to.node_groups.append(nt[nt.index(name)])


class AV_OT_viewer(bpy.types.Operator):
    bl_idname = "av.viewer"
    bl_label = "Viewer"

    prop: bpy.props.StringProperty(default='')

    @classmethod
    def poll(cls, context):
        return hasattr(context.space_data, "edit_tree") and context.space_data.tree_type == "GeometryNodeTree" and context.space_data.node_tree.nodes.active

    def get_group_out(self, ntree):
        group_out = [node for node in ntree.nodes if node.type == 'GROUP_OUTPUT']
        if not group_out:
            return ntree.nodes.new(type="NodeGroupOutput")
        return group_out[0]

    def clear_tmp_viewer_sockets(self, ntree):
        for sock in ntree.outputs:
            if sock.name == "tmp_viewer":
                ntree.outputs.remove(sock)

    def reset_viewer(self, context):
        self.viewer.label = self.viewer.name = "Viewer"
        self.viewer.hide = True

        preferences = context.preferences.addons[__package__].preferences
        self.viewer.use_custom_color = preferences.custom_color
        self.viewer.color = preferences.color

        group_out = self.get_group_out(self.node_tree)
        self.viewer.location = group_out.location
        self.viewer.location[1] += 40

        active = self.node_tree.nodes.active
        if hasattr(active, "node_tree"):
            if active == self.viewer:
                return
            else:
                self.clear_tmp_viewer_sockets(active.node_tree)

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
        mods = [mod for mod in context.object.modifiers if hasattr(mod, 'node_group') and mod.node_group.name == self.node_tree.name]
        return mods[-1]

    def execute(self, context):
        self.node_tree = context.space_data.node_tree
        self.edit_tree = context.space_data.edit_tree
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

        self.reset_viewer(context)

        mod = self.find_mod(context)
        self.prop = list(dict(mod.id_properties_ensure()))[-1]
        mod[self.prop] = "tmp_viewer"

        self.add_viewer_material()

        active_node = self.node_tree.nodes.active
        if active_node == self.viewer:
            return {'FINISHED'}

        if self.edit_tree is not self.node_tree:
            group_out = self.get_group_out(self.edit_tree)
            active = self.edit_tree.nodes.active
            if not active.outputs:
                return {'FINISHED'}

            if active.outputs[0].type == "GEOMETRY":
                return {'FINISHED'}


            sock = self.edit_tree.outputs.new(type="NodeSocketColor", name="tmp_viewer")
            self.edit_tree.links.new(active.outputs[0], group_out.inputs[-2])

            self.node_tree.links.new(self.node_tree.nodes.active.outputs[-1], self.viewer.inputs[1])
            return {'FINISHED'}

        visible_sockets = [_out for _out in active_node.outputs if _out.enabled]

        if not visible_sockets:
            return {'FINISHED'}

        if active_node.outputs[0].type == 'GEOMETRY':
            self.node_tree.links.new(active_node.outputs[0], self.viewer.inputs[0])

            if active_node.type == 'GROUP_INPUT':
                return {'FINISHED'}

            if len(visible_sockets) > 1:
                visible_sockets.remove(active_node.outputs[0])
            else:
                return {'FINISHED'}

        if not self.viewer.inputs['tmp_viewer'].is_linked:
            if visible_sockets:
                self.node_tree.links.new(visible_sockets[0], self.viewer.inputs[1])
        else:
            link = self.viewer.inputs['tmp_viewer'].links[0]
            _from_sock = link.from_socket
            node = _from_sock.node
            self.node_tree.links.remove(link)
            if not (node == active_node):
                self.node_tree.links.new(visible_sockets[0], self.viewer.inputs[1])
            else:
                try:
                    index = visible_sockets.index(_from_sock)
                except ValueError as err:
                    index = 0
                self.node_tree.links.new(visible_sockets[(index + 1) % len(visible_sockets)], self.viewer.inputs[1])

        return {'FINISHED'}


class AV_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    custom_color: bpy.props.BoolProperty(default=False)
    color: bpy.props.FloatVectorProperty(size=3, subtype='COLOR', default=(0.8, 0.2, 0.2), min=0.0, max=1.0)

    def draw(self, context):
        layout = self.layout

        col = layout.column()
        row = col.row(align=True)
        row.prop(self, 'custom_color', text="Enable custom color for viewer")
        row = col.row(align=True)
        row.prop(self, 'color', text="Color")

        col = layout.column()
        col.label(text="Edit Keymap:")
        kc = context.window_manager.keyconfigs.addon
        for km, kmi in addon_keymaps:
            km = km.active()
            col.context_pointer_set("keymap", km)
            rna_keymap_ui.draw_kmi([], kc, km, kmi, col, 0)


addon_keymaps = []

def register():
    bpy.utils.register_class(AV_OT_viewer)
    bpy.utils.register_class(AV_AddonPreferences)

    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name="Node Editor", space_type='NODE_EDITOR')

    kmi = km.keymap_items.new("av.viewer", 'V', 'PRESS')
    kmi.active = True
    addon_keymaps.append((km, kmi))

def unregister():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    bpy.utils.unregister_class(AV_AddonPreferences)
    bpy.utils.unregister_class(AV_OT_viewer)
