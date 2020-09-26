bl_info = {
    "name": "Rig quick map",
    'version': (1, 0, 0),
    "blender": (2, 83, 5),
    'author': 'Naru',
    'description': 'A tool to do quick rig map',
    "category": "Rigging",
    'wiki_url': 'https://github.com/Arisego/BlenderQuickMap',
    'tracker_url': 'https://github.com/Arisego/BlenderQuickMap/issues',
}


from . import RetargetCell


def register():
    print("QuickMap register")
    RetargetCell.register()

def unregister():
    print("QuickMap unregister")
    RetargetCell.unregister()