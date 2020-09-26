from bpy_extras.io_utils import ExportHelper, ImportHelper
import json
import bpy

from bpy.types import (Operator,
                       Panel,
                       PropertyGroup,
                       UIList)

from bpy.props import (IntProperty,
                       BoolProperty,
                       StringProperty,
                       CollectionProperty,
                       PointerProperty)

# Constrain Name
l_Source_Location_Name = "naru_source_location"
l_Source_Rotation_Name = "naru_source_rotation"


# Class to be regist
classes = ()


# Collection Operate
def make_collection(collection_name):
    if collection_name in bpy.data.collections:  # Does the collection already exist?
        return bpy.data.collections[collection_name]
    else:
        new_collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(
            new_collection)  # Add the new collection under a parent
        return new_collection


# ListBox
# Show list of retarget cell
class QM_UL_ControlCell(UIList):
    """
    List box for retarget cells, this is the list in side panel
    """
    # Constants (flags)
    # Be careful not to shadow FILTER_ITEM!
    VGROUP_EMPTY = 1 << 0

    # Custom properties, saved with .blend file.
    use_filter_name_reverse: bpy.props.BoolProperty(name="Reverse Name", default=False, options=set(),
                                                    description="Reverse name filtering")

    use_order_name: bpy.props.BoolProperty(name="Name", default=False, options=set(),
                                           description="Sort groups by their name (case-insensitive)")

    use_filter_linked: bpy.props.BoolProperty(name="Linked", default=False, options=set(),
                                              description="Filter linked only")

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row()

        subrow = row.row(align=True)
        subrow.prop(item, "source_name", text="", emboss=False)

        subrow = subrow.row(align=True)
        if len(item.target_name) > 0:
            subrow.prop(item, "source_follow_location", text="",
                        toggle=True, icon="CON_LOCLIKE")
            subrow.prop(item, "source_follow_rotation", text="",
                        toggle=True, icon="CON_ROTLIKE")

    def invoke(self, context, event):
        pass

    def draw_filter(self, context, layout):
        # Nothing much to say here, it's usual UI code...
        row = layout.row()

        subrow = row.row(align=True)
        subrow.prop(self, "filter_name", text="")
        icon = 'ZOOM_OUT' if self.use_filter_name_reverse else 'ZOOM_IN'
        subrow.prop(self, "use_filter_name_reverse", text="", icon=icon)

        icon = 'LINKED' if self.use_filter_linked else 'UNLINKED'
        subrow.prop(self, "use_filter_linked", text="", icon=icon)

        subrow = layout.row(align=True)
        subrow.label(text="Order by:")
        subrow.prop(self, "use_order_name", toggle=True)

    # Filter
    # 1. we use [source_name] not [name]
    # 2. provide filter for targeted cell
    def filter_items(self, context, data, propname):
        statelist = getattr(data, propname)
        helper_funcs = bpy.types.UI_UL_list

        # Default return values.
        flt_flags = []
        flt_neworder = []

        # Filtering by name
        if self.filter_name:
            flt_flags = helper_funcs.filter_items_by_name(self.filter_name, self.bitflag_filter_item, statelist, "source_name",
                                                          reverse=self.use_filter_name_reverse)
        if not flt_flags:
            flt_flags = [self.bitflag_filter_item] * len(statelist)

        # Filtering cell with target
        if self.use_filter_linked:
            for i, item in enumerate(statelist):
                if len(item.target_name) == 0:
                    flt_flags[i] &= ~self.bitflag_filter_item

        # Reorder by name
        if self.use_order_name:
            flt_neworder = helper_funcs.sort_items_by_name(
                statelist, "source_name")

        return flt_flags, flt_neworder


classes += (QM_UL_ControlCell,)


# Generate constrain from [Follower B] to [Target bone]
def AddTargetLink(InFollower, InArmature, InTargetBone):
    print("(AddTargetLink) Follower: " + str(InFollower))
    print("(AddTargetLink) Target: " + str(InTargetBone))

    # location sontrain
    ts_Name = "naru_follow_location"
    if ts_Name in InFollower.constraints:
        print("Target exists")
        ts_CopyLocation = InFollower.constraints[ts_Name]
        pass
    else:
        print("New Constrain: Location")
        ts_CopyLocation = InFollower.constraints.new('COPY_LOCATION')
        ts_CopyLocation.name = ts_Name

    ts_CopyLocation.target = InArmature
    ts_CopyLocation.subtarget = InTargetBone

    # rotation constrain
    ts_Name = "naru_follow_rotation"
    if ts_Name in InFollower.constraints:
        print("Target exists")
        ts_CopyRotation = InFollower.constraints[ts_Name]
        pass
    else:
        print("New Constrain: Rotation")
        ts_CopyRotation = InFollower.constraints.new('COPY_ROTATION')
        ts_CopyRotation.name = ts_Name

    ts_CopyRotation.target = InArmature
    ts_CopyRotation.subtarget = InTargetBone


# Target changes
# Trigged while target bone changes in single cell
#   1. Will Call RefreshSourceLink() to try generate [Follower A] and [Follower B] if not generated yet
#   2. Call AddTargetLink to connect [follower B] to [Target bone]
def OnTargetChange(self, value):
    """Target changed in single QM_Map_Control"""
    context = bpy.context
    obj = context.active_object
    scn = context.scene

    # Try pick out source armature
    if obj and obj.type == 'ARMATURE':
        qm_state = obj.quickmap_state
    elif scn.quickmap_armature:
        obj = scn.quickmap_armature
        if obj.type == 'ARMATURE':
            qm_state = obj.quickmap_state
        else:
            print("OnTargetChange: no armature 01")
            return
    else:
        print("OnTargetChange: no armature 02")
        return

    item = self

    # Step1: Try create followers if not exist
    ts_SrcBone = obj.pose.bones[item.source_name]
    TryInitLink(ts_SrcBone, item)
    RefreshSourceLink(ts_SrcBone, item)

    # Step2: Try link follower to target bone
    ts_FollowTarget = item.follow_target
    AddTargetLink(ts_FollowTarget, qm_state.map_target, item.target_name)


# Source follow type changed
# Will call RefreshSourceLink
def OnSourceFollowTypeChange(self, value):
    """
    Refresh link type from [Source bone] to [Follower A]
    """

    print("OnSourceFollowTypeChange")
    print(self)
    print(value)

    context = bpy.context
    obj = context.active_object
    scn = context.scene

    # Try find source armature
    if obj and obj.type == 'ARMATURE':
        pass
    elif scn.quickmap_armature:
        obj = scn.quickmap_armature
        if obj.type == 'ARMATURE':
            pass
        else:
            print("OnSourceFollowTypeChange: no armature 01")
            return
    else:
        print("OnSourceFollowTypeChange: no armature 02")
        return

    #item = qm_state.quickmap_celllist[qm_state.quickmap_celllist_index]
    item = self

    print("Change source follow type: " + item.source_name)
    ts_SrcBone = obj.pose.bones[item.source_name]
    RefreshSourceLink(ts_SrcBone, item)


class QM_Map_Control(bpy.types.PropertyGroup):
    """Single data for link"""

    follow_target: PointerProperty(type=bpy.types.Object)
    """
    [Follower B] Parent of source_follow, will follow bone in target animation
    """

    source_follow: PointerProperty(type=bpy.types.Object)
    """
    [Follower A] Source bone will follow this
    """

    # Switch: Whether source bone follow [Follower A] with location
    source_follow_location: BoolProperty(
        update=OnSourceFollowTypeChange, default=True)

    # Switch: Whether source bone follow [Follower A] with rotation
    source_follow_rotation: BoolProperty(
        update=OnSourceFollowTypeChange, default=True)

    # relate rotaion between [Follower A] and [Follower B]
    # [Follower B] is parent of [Follower A]
    relate_a_b_rotation: bpy.props.FloatVectorProperty(
        size=3, update=OnTargetChange, description="Rotation between follower A and follower B", subtype='EULER')

    # relate location between [Follower A] and [Follower B]
    # [Follower B] is parent of [Follower A]
    relate_a_b_location: bpy.props.FloatVectorProperty(
        size=3, update=OnTargetChange, description="Rotation between follower A and follower B", subtype='TRANSLATION')

    source_name: StringProperty()
    """
    Name of source bone
    """

    target_name: StringProperty(update=OnTargetChange)
    """
    Name of target bone
    """


classes += (QM_Map_Control,)


# Will try create [Follower A] and [Folloer B]
# [Source Bone] => [Follower A] => [Folloer B] => [Target Animation]
def TryInitLink(InBone, InItem):
    """
    Try create followers if not exists.

    Parameters
    ----------
    InBone : Bone
        Bone in the source armature

    InItem : QM_Map_Control
        Map data

    """
    ts_CollectionName = "qm_test"
    ts_Collection = make_collection(ts_CollectionName)

    ts_Bone = InBone  # Source bone
    ts_BoneName = ts_Bone.name

    # FollowTarget|[Folloer B]
    if not InItem.follow_target:
        ts_FollowTargetName = ts_BoneName + "_T"
        ts_FollowTarget = bpy.data.objects.new(ts_FollowTargetName, None)

        # due to the new mechanism of "collection"
        ts_Collection.objects.link(ts_FollowTarget)

        # empty_draw was replaced by empty_display
        ts_FollowTarget.empty_display_size = 0.05
        ts_FollowTarget.empty_display_type = 'CUBE'

        InItem.follow_target = ts_FollowTarget

    # SourceFollow|[Follower A]
    if not InItem.source_follow:
        ts_SourceFollowName = ts_BoneName + "_S"
        ts_SourceFollow = bpy.data.objects.new(ts_SourceFollowName, None)

        # due to the new mechanism of "collection"
        ts_Collection.objects.link(ts_SourceFollow)

        # empty_draw was replaced by empty_display
        ts_SourceFollow.empty_display_size = 0.05
        ts_SourceFollow.empty_display_type = 'ARROWS'

        InItem.source_follow = ts_SourceFollow

    # Parent [Follower A] to [Follower B]
    if InItem.follow_target and InItem.source_follow:
        InItem.source_follow.parent = InItem.follow_target
        InItem.source_follow.rotation_euler = InItem.relate_a_b_rotation
        InItem.source_follow.location = InItem.relate_a_b_location


# Refresh constrain link from [Source Bone] to [Follower A]
# Will create constrain if not exist
def RefreshSourceLink(InBone, InItem):
    if not InItem.source_follow:
        print("RefreshSourceLink: Item no source follow")
        return

    # If target is none, just set influence to 0, constrains are still keeeped in place
    ts_HasTarget = len(InItem.target_name) > 0

    # [Source Bone] to [Follower A]: Location Constrain
    if l_Source_Location_Name in InBone.constraints:
        print("- Location exsits")
        ts_CopyLocation = InBone.constraints[l_Source_Location_Name]
        pass
    else:
        ts_CopyLocation = InBone.constraints.new('COPY_LOCATION')
        ts_CopyLocation.target = InItem.source_follow
        ts_CopyLocation.name = l_Source_Location_Name

    if InItem.source_follow_location and ts_HasTarget:
        ts_CopyLocation.influence = 1.0
    else:
        ts_CopyLocation.influence = 0.0

    # [Source Bone] to [Follower A]: Rotation Constrain
    if l_Source_Rotation_Name in InBone.constraints:
        print("- Rotation exists")
        ts_CopyRotation = InBone.constraints[l_Source_Rotation_Name]
        pass
    else:
        ts_CopyRotation = InBone.constraints.new('COPY_ROTATION')
        ts_CopyRotation.target = InItem.source_follow
        ts_CopyRotation.name = l_Source_Rotation_Name

    if InItem.source_follow_rotation and ts_HasTarget:
        ts_CopyRotation.influence = 1.0
    else:
        ts_CopyRotation.influence = 0.0


# Operator
# Generate source bone list from selected armature
class QM_OT_GenerateMap(Operator):
    """Generate controls for current armature"""
    bl_idname = "qm.generate_control"
    bl_label = "Generate Control"
    bl_description = "Generate controls for current armature"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return bpy.context.mode == 'OBJECT' and obj and obj.type == 'ARMATURE'

    def execute(self, context):
        obj = context.active_object
        obj.quickmap_state.quickmap_celllist.clear()
        for ts_Bone in obj.pose.bones:
            item = obj.quickmap_state.quickmap_celllist.add()
            item.source_name = ts_Bone.name

        return{'FINISHED'}


classes += (QM_OT_GenerateMap,)


# Operator
# Bake control into animation, all constrains in source bone will be removed
class QM_QT_BakeControl(Operator):
    """Bake control to animation"""
    bl_idname = "qm.bake_control"
    bl_label = "Bake Control"
    bl_description = "Bake control to animation"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        obj = scene.quickmap_armature
        return bpy.context.mode == 'OBJECT' and obj and obj.type == 'ARMATURE'

    def execute(self, context):
        td_FrameEnd = bpy.context.scene.frame_end
        print("Start bake: " + str(td_FrameEnd))

        if 0 == td_FrameEnd:
            return{"CANCEL"}

        scene = context.scene
        arm = scene.quickmap_armature

        # ensure that only the armature is selected in Object mode
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        arm.select_set(True)
        scene.view_layers[0].objects.active = arm

        # enter pose mode and bake
        bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.pose.select_all(action='SELECT')
        bpy.ops.nla.bake(frame_start=0, frame_end=td_FrameEnd, step=1, only_selected=True,
                         visual_keying=True, clear_constraints=True, clear_parents=False,
                         use_current_action=True, bake_types={'POSE'})
        return{'FINISHED'}


classes += (QM_QT_BakeControl,)


# Operator
# Refresh control link, trigger OnTargetChange for every source bone that has target setted
# Used for link repair after Bake Animation
class QM_QT_RefreshControl(Operator):
    """Refresh control link"""
    bl_idname = "qm.refresh_link"
    bl_label = "Refresh Control"
    bl_description = "Refresh all the link"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        obj = scene.quickmap_armature
        return bpy.context.mode == 'OBJECT' and obj and obj.type == 'ARMATURE'

    def execute(self, context):
        td_FrameEnd = bpy.context.scene.frame_end
        print("Start bake: " + str(td_FrameEnd))

        if 0 == td_FrameEnd:
            return{"CANCEL"}

        scene = context.scene
        arm = scene.quickmap_armature

        for ts_State in arm.quickmap_state.quickmap_celllist:
            if len(ts_State.target_name) == 0:
                continue

            print("Relink: " + ts_State.source_name +
                  " -> " + ts_State.target_name)
            OnTargetChange(ts_State, context)

        return{'FINISHED'}


classes += (QM_QT_RefreshControl,)


"""
Read write config from file
"""


# Save list config to file
class OP_BF_SaveToFile(bpy.types.Operator, ExportHelper):
    bl_idname = 'qm.bf_save'
    bl_label = 'Save Config'
    filename_ext = '.qm.bf'

    filter_glob: bpy.props.StringProperty(
        default='*.qm.bf',
        options={'HIDDEN'},
        maxlen=255
    )

    def execute(self, context):

        obj = context.active_object
        scn = context.scene

        if obj and obj.type == 'ARMATURE':
            qm_state = obj.quickmap_state
        elif scn.quickmap_armature:
            obj = scn.quickmap_armature
            if obj.type == 'ARMATURE':
                qm_state = obj.quickmap_state
            else:
                print(text="Select an armature to work t1")
                return {'CANCELLED'}
        else:
            print(text="Select an armature to work t2")
            return {'CANCELLED'}

        with open(self.filepath, 'w') as f:
            tlist_QmStates = {}
            for ts_State in qm_state.quickmap_celllist:
                if len(ts_State.target_name) == 0:
                    continue

                tdic_State = {}
                tdic_State["target_name"] = ts_State.target_name
                tdic_State["source_follow_location"] = ts_State.source_follow_location
                tdic_State["source_follow_rotation"] = ts_State.source_follow_rotation
                tdic_State["relate_a_b_rotation"] = [ts_State.relate_a_b_rotation[0],
                                                     ts_State.relate_a_b_rotation[1], ts_State.relate_a_b_rotation[2]]                
                tdic_State["relate_a_b_location"] = [ts_State.relate_a_b_location[0],
                                                     ts_State.relate_a_b_location[1], ts_State.relate_a_b_location[2]]
                tlist_QmStates[ts_State.source_name] = tdic_State

            ts_DumpedJson = json.dumps(tlist_QmStates)
            print(ts_DumpedJson)
            f.write(ts_DumpedJson)

        return {'FINISHED'}


classes += (OP_BF_SaveToFile,)


# Load list config from file
class OP_BF_LoadFromFile(bpy.types.Operator, ImportHelper):
    bl_idname = 'qm.bf_load'
    bl_label = 'Load Config'

    filter_glob: bpy.props.StringProperty(
        default='*.qm.bf',
        options={'HIDDEN'},
        maxlen=255
    )

    def execute(self, context):

        obj = context.active_object
        scn = context.scene

        if obj and obj.type == 'ARMATURE':
            qm_state = obj.quickmap_state
        elif scn.quickmap_armature:
            obj = scn.quickmap_armature
            if obj.type == 'ARMATURE':
                qm_state = obj.quickmap_state
            else:
                print(text="Select an armature to work t1")
                return {'CANCELLED'}
        else:
            print(text="Select an armature to work t2")
            return {'CANCELLED'}

        # Read file
        with open(self.filepath, 'r') as f:
            ts_LoadedList = json.load(f)
            print("Loaded")
            print(ts_LoadedList)

        ts_ReadLen = len(ts_LoadedList)
        if 0 == ts_ReadLen:
            print("Nothing readed: " + self.filepath)
            return {'CANCELLED'}

        # deserialize json to state map
        for ts_State in qm_state.quickmap_celllist:
            ts_StateSrcName = ts_State.source_name
            if ts_StateSrcName in ts_LoadedList:
                ts_CurLoad = ts_LoadedList[ts_StateSrcName]
                ts_State.target_name = ts_CurLoad["target_name"]
                ts_State.source_follow_location = ts_CurLoad["source_follow_location"]
                ts_State.source_follow_rotation = ts_CurLoad["source_follow_rotation"]
                ts_State.relate_a_b_rotation[0] = ts_CurLoad["relate_a_b_rotation"][0]
                ts_State.relate_a_b_rotation[1] = ts_CurLoad["relate_a_b_rotation"][1]
                ts_State.relate_a_b_rotation[2] = ts_CurLoad["relate_a_b_rotation"][2]

                ts_State.relate_a_b_location[0] = ts_CurLoad["relate_a_b_location"][0]
                ts_State.relate_a_b_location[1] = ts_CurLoad["relate_a_b_location"][1]
                ts_State.relate_a_b_location[2] = ts_CurLoad["relate_a_b_location"][2]

                print("Read in config: " + ts_StateSrcName +
                      " -> " + ts_State.target_name)
                OnTargetChange(ts_State, context)

        # bpy.ops.naru.bf_clearlist()
        # print(len(ts_LoadedList))
        # for ts_ItemKey in ts_LoadedList:
        #     print(ts_ItemKey)
        #     print(ts_LoadedList[ts_ItemKey])

        # bpy.context.scene.naru_bonelist_index = len(
        #     bpy.context.scene.naru_bonelist)-1
        # bpy.context.area.tag_redraw()
        return {'FINISHED'}


classes += (OP_BF_LoadFromFile,)


# Draw read/write button to UI
def _Draw_SaveLoad(layout):
    row = layout.row()
    row.operator('qm.bf_load', icon='FILEBROWSER')
    row.operator('qm.bf_save', icon='FILE_TICK')


# Side panel, main view of plugin
# As by blender's design, property could not be modifed in ui
class TP_LinkGenerate(bpy.types.Panel):
    bl_idname = "QM_PT_ViewPanel"
    bl_label = "LinkGenerate"
    bl_category = "QuickMap"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        scn = context.scene

        # Work in object mode only to avoid mistacke
        if bpy.context.mode != 'OBJECT':
            layout.label(text="Work in object mode only", icon='ERROR')
            return

        # Draw button for Generate control ist
        box = layout.box()
        box.operator("qm.generate_control")

        # Pick out source armature
        if obj and obj.type == 'ARMATURE':
            qm_state = obj.quickmap_state
        elif scn.quickmap_armature:
            obj = scn.quickmap_armature
            if obj.type == 'ARMATURE':
                qm_state = obj.quickmap_state
            else:
                layout.label(text="Select an armature to work.", icon='ERROR')
                return
        else:
            layout.label(text="Select an armature to work", icon='INFO')
            return

        layout.label(text="Follower: "+obj.name, icon='INFO')
        layout.template_list("QM_UL_ControlCell", "",
                             qm_state, "quickmap_celllist",
                             qm_state, "quickmap_celllist_index"
                             )

        # Stop show target oprators if no control, avoid miss oprate
        if len(qm_state.quickmap_celllist) == 0:
            layout.label(text="Generate control to continue", icon='INFO')
            return

        # Target armature that provide animation
        layout.separator()
        layout.prop(qm_state, 'map_target',
                    text='Target', icon='ARMATURE_DATA')

        box = layout.box()
        if qm_state.map_target == None:
            box.label(text="Target is missing", icon='UNLINKED')
            return

        if qm_state.map_target == obj:
            box.label(text="Target is source", icon='ERROR')
            return

        box.label(text="Target: "+qm_state.map_target.name, icon='LINKED')

        # Show detail control for selected source bone
        tb_FollowerValid = False
        try:
            item = qm_state.quickmap_celllist[qm_state.quickmap_celllist_index]
            tb_FollowerValid = len(item.source_name) > 0
            pass
        except IndexError:
            pass

        if tb_FollowerValid:
            box.label(text="Follower bone: " +
                      item.source_name, icon='COPY_ID')

            box.prop_search(item, 'target_name', qm_state.map_target.pose,
                            'bones', text='', icon='BONE_DATA')

            row = box.row()
            row.enabled = len(item.target_name) > 0
            row.prop(item, "source_follow_location", text="Location",
                     toggle=True, icon="CON_LOCLIKE")
            row.prop(item, "source_follow_rotation", text="Rotation",
                     toggle=True, icon="CON_ROTLIKE")

            box.prop(item, "relate_a_b_rotation", text="Relative Rotation")
            box.prop(item, "relate_a_b_location", text="Relative Location")
        else:
            box.label(text="Choose a follower bone above", icon='PANEL_CLOSE')

        # Draw read/write config from file
        _Draw_SaveLoad(layout)

        # Buttons used for animation bake
        layout.separator()
        box = layout.box()
        box.operator("qm.bake_control")
        box.operator("qm.refresh_link")


classes += (TP_LinkGenerate,)


# OnSelect event handler for control map list
def OnSelect_ControlList(self, value):
    """
    Called while single control in list is selected

    Parameters
    ----------
    self : QmState
        Parent Property 
    value : struct
        Not used
    """

    if bpy.context.mode != 'OBJECT':
        self.report({'INFO'}, "OnSelect_ControlList works in object mode only")
        return

    try:
        item = self.quickmap_celllist[self.quickmap_celllist_index]
        pass
    except IndexError:
        self.report({'INFO'}, "OnSelect_ControlList got invalid index")
        return

    print("Select: " + item.source_name)

    # Cache source armature as we may change selected object
    if bpy.context.active_object and bpy.context.active_object.type == 'ARMATURE':
        bpy.context.scene.quickmap_armature = bpy.context.active_object

    # Select linked follower if possible
    bpy.ops.object.select_all(action='DESELECT')
    ts_FollowTarget = item.follow_target
    if ts_FollowTarget:
        ts_FollowTarget.select_set(state=True)
        bpy.context.view_layer.objects.active = ts_FollowTarget

    ts_SourceFollow = item.source_follow
    if ts_SourceFollow:
        ts_SourceFollow.select_set(state=True)

    return


# Core data for quick map control
# grouped together to avoid Register/UnRegister for every single data
class QMState(bpy.types.PropertyGroup):
    map_target: bpy.props.PointerProperty(
        type=bpy.types.Object,
        name="FollowTarget",
        poll=lambda self, obj: obj.type == 'ARMATURE' and obj != bpy.context.object
    )
    quickmap_celllist: CollectionProperty(type=QM_Map_Control)
    quickmap_celllist_index: IntProperty(update=OnSelect_ControlList)


classes += (QMState,)


"""
Blender class register/unregister
"""


def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

    bpy.types.Object.quickmap_state = bpy.props.PointerProperty(type=QMState)
    bpy.types.Scene.quickmap_armature = bpy.props.PointerProperty(
        name="QuickMap Armature", type=bpy.types.Object)


def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)

    del bpy.types.Object.quickmap_state
    del bpy.types.Scene.quickmap_armature
