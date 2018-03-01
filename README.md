uExport
============

uExport is a simple tool to automatically export complex characters from Maya to Unreal Engine 4. It works by marking up the scene with metadata related to what rendermeshes and skeletons compose a 'character'.

Usually, you would have one uExport node, which is exposed to the user like so:
![alt tag](http://chrisevans3d.com/files/github/uExport_simple.gif)

Under the hood, this data is serialized to disk using this network node:
![alt tag](http://chrisevans3d.com/files/github/uNode.PNG)

You can have multiple uExport nodes in one scene, not only to represent each character, but even in one export file when breaking up characters into multiple exported FBX files on disk:
![alt tag](http://chrisevans3d.com/files/github/uexport01.png)
