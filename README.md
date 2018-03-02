uExport
============

Overview
---------------
uExport is a simple tool to automatically export complex characters from Maya to Unreal Engine 4. It works by marking up the scene with metadata related to what rendermeshes and skeletons compose a 'character'.

When scenes are saved with this markup, you can open any Maya scene and automatically export exactly what content is supposed to be going to UE4, even in a batch process.

Here's a simple test where one uExport node has been created; which is exposed to the user like so:
![alt tag](http://chrisevans3d.com/files/github/uExport_simple.gif)

__Features:__
* Serialize export info into Maya scene
  * exported path
  * user friendly asset name
  * fbx name
  * fbx export settings
  * export skeleton
  * rendermeshes
  * LODs
* UI to create and edit export markup
* Fire arbitrary python scripts assoc with any export (useful for LODs)

Under the Hood
---------------
Under the hood, this data is serialized to disk using this network node:
![alt tag](http://chrisevans3d.com/files/github/uNode.PNG)

Advanced Usage
---------------
You can have multiple uExport nodes in one scene, not only to represent each character, but even in one export file when breaking up characters into multiple exported FBX files on disk:
![alt tag](http://chrisevans3d.com/files/github/uexport01.png)
