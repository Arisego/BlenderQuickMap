# Blender Quick Map plugin

A simple blender addon helps retarget animation.

## How it work

The method used to retargeting animation in addon is shared by *Maciej Szcześnik* in Unity Connect article "Retargeting animations with Blender 2.80". I made this plugin just to speed up the retargeting steps, so we can make things happen more quickly.

> As unity connect is gone, you may visit this [archived version](https://web.archive.org/web/20200812235638/https://connect.unity.com/p/retargeting-animations-with-blender-2-80) instead. It's an archive of the  [original link](https://connect.unity.com/p/retargeting-animations-with-blender-2-80).

This plugins helps to automatically generating and changing follow chains , and provides save/load to save out retarget map config.

## Concepts

Some concept name differs from the origin article:

* Source Armature: The armature you want to have animation on it
* Target Armature: Animation is on this armature
* Follower A: *Source Bone* will follow this object by constrain
* Follower B: This object is parent of *Follower A*, and will follow *Target Bone*

The follow chain works like this:

1. Animation moves bone in *Taret Armature*
2. *Target Bone* in *Target Armature* will move *Follower B* 
3. *Follower B* then moves *Follower A*
4. *Follower A* then moves *Source Bone* in *Source Armature*

## Usage

You will see a "QuickMap" tab in side panels, try press *N*  in main view if you do not see any side panel.

Follow the tips in panel will help, you can find more detail steps in [wiki page](https://github.com/Arisego/BlenderQuickMap/wiki).
