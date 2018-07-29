'''
uExport
Christopher Evans, Version 0.1, Feb 2014
@author = Chris Evans
version = 0.85

Add this to a shelf:
import uExport as ue
uExportToolWindow = ue.show()

'''

import os
import re
import time
import stat
import types

from cStringIO import StringIO
import xml.etree.ElementTree as xml
import json
import functools

import maya.cmds as cmds
import maya.OpenMayaUI as openMayaUI
import maya.mel as mel

# legacy support
from Qtpy.Qt import QtWidgets, QtCore

mayaApi = cmds.about(api=True)
if mayaApi >= 201700:
    import shiboken2 as shiboken
    import pyside2uic as pysideuic
else:
    import shiboken
    import pysideuic

def show():
    global uExportToolWindow
    try:
        uExportToolWindow.close()
    except:
        pass

    uExportToolWindow = uExportTool()
    uExportToolWindow.show()
    return uExportToolWindow

def loadUiType(uiFile):
    """
    Pyside lacks the "loadUiType" command, so we have to convert the ui file to py code in-memory first
    and then execute it in a special frame to retrieve the form_class.
    http://tech-artists.org/forum/showthread.php?3035-PySide-in-Maya-2013 (ChrisE)
    """
    parsed = xml.parse(uiFile)
    widget_class = parsed.find('widget').get('class')
    form_class = parsed.find('class').text

    with open(uiFile, 'r') as f:
        o = StringIO()
        frame = {}

        pysideuic.compileUi(f, o, indent=0)
        pyc = compile(o.getvalue(), '<string>', 'exec')
        exec pyc in frame

        #Fetch the base_class and form class based on their type in the xml from designer
        form_class = frame['Ui_%s'%form_class]
        base_class = eval('QtWidgets.%s'%widget_class)
    return form_class, base_class

def getMayaWindow():
    ptr = openMayaUI.MQtUtil.mainWindow()
    if ptr is not None:
        return shiboken.wrapInstance(long(ptr), QtWidgets.QWidget)

try:
    selfDirectory = os.path.dirname(__file__)
    uiFile = selfDirectory + '/uExport.ui'
except:
    uiFile = 'D:\\Build\\usr\\jeremy_ernst\\MayaTools\\General\\Scripts\\epic\\rigging\\uExport\\uExport.ui'
    form_class, base_class = loadUiType(uiFile)

if os.path.isfile(uiFile):
    form_class, base_class = loadUiType(uiFile)
else:
    cmds.error('Cannot find UI file: ' + uiFile)



#these are used by both classes below, this method is usually in the utils lib at Epic
def attrExists(attr):
    if '.' in attr:
        node, att = attr.split('.')
        return cmds.attributeQuery(att, node=node, ex=1)
    else:
        cmds.warning('attrExists: No attr passed in: ' + attr)
        return False

def msgConnect(attribFrom, attribTo, debug=0):
    # TODO needs a mode to dump all current connections (overwrite/force)
    objFrom, attFrom = attribFrom.split('.')
    objTo, attTo = attribTo.split('.')
    if debug: print 'msgConnect>>> Locals:', locals()
    if not attrExists(attribFrom):
        cmds.addAttr(objFrom, longName=attFrom, attributeType='message')
    if not attrExists(attribTo):
        cmds.addAttr(objTo, longName=attTo, attributeType='message')

    # check that both atts, if existing are msg atts
    for a in (attribTo, attribFrom):
        if cmds.getAttr(a, type=1) != 'message':
            cmds.warning('msgConnect: Attr, ' + a + ' is not a message attribute. CONNECTION ABORTED.')
            return False

    try:
        return cmds.connectAttr(attribFrom, attribTo, f=True)
    except Exception as e:
        print e
        return False

def findRelatedSkinCluster(skinObject):
    '''Python implementation of MEL command: http://takkun.nyamuuuu.net/blog/archives/592'''

    skinShape = None
    skinShapeWithPath = None
    hiddenShape = None
    hiddenShapeWithPath = None

    cpTest = cmds.ls( skinObject, typ="controlPoint" )
    if len( cpTest ):
        skinShape = skinObject

    else:
        rels = cmds.listRelatives( skinObject )
        if rels == None: return False
        for r in rels :
            cpTest = cmds.ls( "%s|%s" % ( skinObject, r ), typ="controlPoint" )
            if len( cpTest ) == 0:
                continue

            io = cmds.getAttr( "%s|%s.io" % ( skinObject, r ) )
            if io:
                continue

            visible = cmds.getAttr( "%s|%s.v" % ( skinObject, r ) )
            if not visible:
                hiddenShape = r
                hiddenShapeWithPath = "%s|%s" % ( skinObject, r )
                continue

            skinShape = r
            skinShapeWithPath = "%s|%s" % ( skinObject, r )
            break

    if skinShape:
        if len( skinShape ) == 0:
            if len( hiddenShape ) == 0:
                return None

            else:
                skinShape = hiddenShape
                skinShapeWithPath = hiddenShapeWithPath

    clusters = cmds.ls( typ="skinCluster" )
    for c in clusters:
        geom = cmds.skinCluster( c, q=True, g=True )
        for g in geom:
            if g == skinShape or g == skinShapeWithPath:
                return c

    return None

def getParents(item):
     parents = []
     current_item = item
     current_parent = current_item.parent()

     # Walk up the tree and collect all parent items of this item
     while not current_parent is None:
         parents.append(current_parent)
         current_item = current_parent
         current_parent = current_item.parent()
     return parents

########################################################################
## UEXPORT CLASS
########################################################################

class uExport(object):
    '''
    Just a little basket to store things.
    TODO: Add properties to get/set values
    TODO: add logic to check that meshes exist across LODs
    '''
    def __init__(self, node):

        #update for new LOD attrs instead of just rendermeshes
        if not attrExists(node + '.rendermeshes_LOD0'):
            if attrExists(node + '.rendermesh'):
                if cmds.listConnections(node + '.rendermesh'):
                    lod0meshes = cmds.listConnections(node + '.rendermesh')
                    for mesh in lod0meshes:
                        msgConnect(node + '.rendermeshes_LOD0', mesh + '.uExport')
                    cmds.deleteAttr(node, at='rendermesh')
                else:
                    cmds.addAttr(node, longName='rendermeshes_LOD0', attributeType='message')
            else:
                cmds.addAttr(node, longName='rendermeshes_LOD0', attributeType='message')

            #add the other lod attrs
            cmds.addAttr(node, longName='rendermeshes_LOD1', attributeType='message')
            cmds.addAttr(node, longName='rendermeshes_LOD2', attributeType='message')
            cmds.addAttr(node, longName='rendermeshes_LOD3', attributeType='message')
            cmds.addAttr(node, longName='rendermeshes_LOD4', attributeType='message')

        #TODO: don't assume 4 LODs
        if not attrExists(node + '.export_script_LOD0'):
            cmds.addAttr(node, longName='export_script_LOD0', dt='string')
            cmds.addAttr(node, longName='export_script_LOD1', dt='string')
            cmds.addAttr(node, longName='export_script_LOD2', dt='string')
            cmds.addAttr(node, longName='export_script_LOD3', dt='string')
            cmds.addAttr(node, longName='export_script_LOD4', dt='string')

        if not attrExists(node + '.fbx_name_LOD0'):
            cmds.addAttr(node, longName='fbx_name_LOD0', dt='string')
            cmds.addAttr(node, longName='fbx_name_LOD1', dt='string')
            cmds.addAttr(node, longName='fbx_name_LOD2', dt='string')
            cmds.addAttr(node, longName='fbx_name_LOD3', dt='string')
            cmds.addAttr(node, longName='fbx_name_LOD4', dt='string')

        self.export_root = cmds.listConnections(node + '.export_root')

        self.version = cmds.getAttr(node + '.uexport_ver')
        self.node = node
        self.name = node.split('|')[-1]
        self.asset_name = node
        self.folder_path = None
        self.fbxPropertiesDict = None


        if attrExists(node + '.asset_name'):
            self.asset_name = cmds.getAttr(node + '.asset_name')
        if attrExists(node + '.fbx_name'):
            self.fbx_name = cmds.getAttr(node + '.fbx_name')
        if attrExists(node + '.folder_path'):
            self.folder_path = cmds.getAttr(node + '.folder_path')

        #ART MetaData
        #TO DO: Move to properties
        if attrExists(node + '.joint_mover_template'):
            self.joint_mover_template = cmds.getAttr(node + '.joint_mover_template')
        if attrExists(node + '.skeleton_template'):
            self.skeleton_template = cmds.getAttr(node + '.skeleton_template')
        if attrExists(node + '.pre_script'):
            self.pre_script = cmds.getAttr(node + '.pre_script')
        if attrExists(node + '.post_script'):
            self.post_script = cmds.getAttr(node + '.post_script')
        if attrExists(node + '.export_file'):
            self.export_file = cmds.getAttr(node + '.export_file')
        if attrExists(node + '.anim_file'):
            self.anim_file = cmds.getAttr(node + '.anim_file')
        if attrExists(node + '.skeleton_uasset'):
            self.skeleton_uasset = cmds.getAttr(node + '.skeleton_uasset')
        if attrExists(node + '.skelmesh_uasset'):
            self.skelmesh_uasset = cmds.getAttr(node + '.skelmesh_uasset')
        if attrExists(node + '.physics_uasset'):
            self.physics_uasset = cmds.getAttr(node + '.physics_uasset')
        if attrExists(node + '.thumbnail_large'):
            self.thumbnail_large = cmds.getAttr(node + '.thumbnail_large')
        if attrExists(node + '.thumbnail_small'):
            self.thumbnail_small = cmds.getAttr(node + '.thumbnail_small')

    ## Built in methods
    ########################################################################
    def getLodDicts(self):
        lodDicts = {}
        lodDicts[0] = {'meshes':self.rendermeshes_LOD0, 'export_script':self.export_script_LOD0, 'fbx_name':self.fbx_name_LOD0}
        lodDicts[1] = {'meshes':self.rendermeshes_LOD1, 'export_script':self.export_script_LOD1, 'fbx_name':self.fbx_name_LOD1}
        lodDicts[2] = {'meshes':self.rendermeshes_LOD2, 'export_script':self.export_script_LOD2, 'fbx_name':self.fbx_name_LOD2}
        lodDicts[3] = {'meshes':self.rendermeshes_LOD3, 'export_script':self.export_script_LOD3, 'fbx_name':self.fbx_name_LOD3}
        lodDicts[4] = {'meshes':self.rendermeshes_LOD4, 'export_script':self.export_script_LOD4, 'fbx_name':self.fbx_name_LOD4}
        return lodDicts

    def getShaderDict(self):
        shaderDict = {}
        for mesh in self.rendermeshes_ALL:
            for shader in self.getAssocShaders(mesh):
                if shader not in shaderDict.keys():
                    shaderDict[shader] = [mesh]
                else:
                    shaderDict[shader].append(mesh)
        if shaderDict:
            return shaderDict
        else:
            return False

    def getAssocShaders(self, mesh):
        shapes = cmds.listRelatives(mesh, shapes=1, f=True)
        shadingGrps = cmds.listConnections(shapes,type='shadingEngine')
        shaders = cmds.ls(cmds.listConnections(shadingGrps),materials=1)
        return shaders

    def connectRenderMeshes(self, renderMeshes, LOD=0):
        try:
            cmds.undoInfo(openChunk=True)
            lodAttr = None
            if LOD >=0 or LOD <=4:
                lodAttr = self.node + '.rendermeshes_LOD' + str(LOD)
                conns = cmds.listConnections(lodAttr, plugs=1, destination=1)
                if conns:
                    for conn in cmds.listConnections(lodAttr, plugs=1, destination=1):
                        cmds.disconnectAttr(lodAttr, conn)
            if lodAttr:
                for mesh in renderMeshes:
                    msgConnect(lodAttr, mesh + '.uExport')
            else:
                cmds.error('connectRenderMeshes>>> please specify a LOD integer (0-4) for your meshes')

        except Exception as e:
            print e
        finally:
            cmds.undoInfo(closeChunk=True)

    def getFbxExportPropertiesDict(self):
        if not attrExists(self.node + '.fbxPropertiesDict'):
            cmds.addAttr(self.node, longName='fbxPropertiesDict', dt='string')
            self.fbxPropertiesDict = {'animInterpolation':'quaternion', 'upAxis':'default', 'triangulation':False}
            cmds.setAttr(self.node + '.fbxPropertiesDict', json.dumps(self.fbxPropertiesDict), type='string')
            return self.fbxPropertiesDict
        else:
            self.fbxPropertiesDict = json.loads(cmds.getAttr(self.node + '.fbxPropertiesDict'))
            return self.fbxPropertiesDict

    ## Properties
    ########################################################################

    #return and set the rendermeshes per LOD
    @property
    def rendermeshes_LOD0(self):
        conns = cmds.listConnections(self.node + '.rendermeshes_LOD0')
        if conns:
            return conns
        else: return []
    @rendermeshes_LOD0.setter
    def rendermeshes_LOD0(self, meshes):
        self.connectRenderMeshes(meshes, LOD=0)

    @property
    def rendermeshes_LOD1(self):
        conns = cmds.listConnections(self.node + '.rendermeshes_LOD1')
        if conns:
            return conns
        else: return []
    @rendermeshes_LOD1.setter
    def rendermeshes_LOD1(self, meshes):
        self.connectRenderMeshes(meshes, LOD=1)

    @property
    def rendermeshes_LOD2(self):
        conns = cmds.listConnections(self.node + '.rendermeshes_LOD2')
        if conns:
            return conns
        else: return []
    @rendermeshes_LOD2.setter
    def rendermeshes_LOD2(self, meshes):
        self.connectRenderMeshes(meshes, LOD=2)

    @property
    def rendermeshes_LOD3(self):
        conns = cmds.listConnections(self.node + '.rendermeshes_LOD3')
        if conns:
            return conns
        else: return []
    @rendermeshes_LOD3.setter
    def rendermeshes_LOD3(self, meshes):
        self.connectRenderMeshes(meshes, LOD=3)

    @property
    def rendermeshes_LOD4(self):
        conns = cmds.listConnections(self.node + '.rendermeshes_LOD4')
        if conns:
            return conns
        else: return []
    @rendermeshes_LOD4.setter
    def rendermeshes_LOD4(self, meshes):
        self.connectRenderMeshes(meshes, LOD=4)

    #number of lods
    @property
    def lodNum(self):
        att = self.node + '.lodNum'
        if attrExists(att):
            return cmds.getAttr(att)
        else:
            cmds.addAttr(self.node, ln='lodNum', at='byte')
            cmds.setAttr(att, 4)
            return cmds.getAttr(att)

    @lodNum.setter
    def lodNum(self, meshes):
        att = self.node + '.lodNum'
        if attrExists(att):
            return cmds.setAttr(att)
        else:
            cmds.addAttr(self.node, ln='lodNum', at='byte')
            cmds.setAttr(att, 4)
            return cmds.setAttr(att)

    #return ALL lod geometry
    @property
    def rendermeshes_ALL(self):
        meshes = []
        meshes.extend(self.rendermeshes_LOD0)
        meshes.extend(self.rendermeshes_LOD1)
        meshes.extend(self.rendermeshes_LOD2)
        meshes.extend(self.rendermeshes_LOD3)
        meshes.extend(self.rendermeshes_LOD4)
        return meshes

    #return and set export script paths
    @property
    def export_script_LOD0(self):
        return cmds.getAttr(self.node + '.export_script_LOD0')
    @export_script_LOD0.setter
    def export_script_LOD0(self, path):
        cmds.setAttr(self.node + '.export_script_LOD0', path, type='string')

    @property
    def export_script_LOD1(self):
        return cmds.getAttr(self.node + '.export_script_LOD1')
    @export_script_LOD1.setter
    def export_script_LOD1(self, path):
        cmds.setAttr(self.node + '.export_script_LOD1', path, type='string')

    @property
    def export_script_LOD2(self):
        return cmds.getAttr(self.node + '.export_script_LOD2')
    @export_script_LOD2.setter
    def export_script_LOD2(self, path):
        cmds.setAttr(self.node + '.export_script_LOD2', path, type='string')

    @property
    def export_script_LOD3(self):
        return cmds.getAttr(self.node + '.export_script_LOD3')
    @export_script_LOD3.setter
    def export_script_LOD3(self, path):
        cmds.setAttr(self.node + '.export_script_LOD3', path, type='string')

    @property
    def export_script_LOD4(self):
        return cmds.getAttr(self.node + '.export_script_LOD4')
    @export_script_LOD4.setter
    def export_script_LOD4(self, path):
        cmds.setAttr(self.node + '.export_script_LOD4', path, type='string')


    #return and set fbx export names
    @property
    def fbx_name_LOD0(self):
        return cmds.getAttr(self.node + '.fbx_name_LOD0')
    @fbx_name_LOD0.setter
    def fbx_name_LOD0(self, name):
        cmds.setAttr(self.node + '.fbx_name_LOD0', name, type='string')

    @property
    def fbx_name_LOD1(self):
        return cmds.getAttr(self.node + '.fbx_name_LOD1')
    @fbx_name_LOD1.setter
    def fbx_name_LOD1(self, name):
        cmds.setAttr(self.node + '.fbx_name_LOD1', name, type='string')

    @property
    def fbx_name_LOD2(self):
        return cmds.getAttr(self.node + '.fbx_name_LOD2')
    @fbx_name_LOD2.setter
    def fbx_name_LOD2(self, name):
        cmds.setAttr(self.node + '.fbx_name_LOD2', name, type='string')

    @property
    def fbx_name_LOD3(self):
        return cmds.getAttr(self.node + '.fbx_name_LOD3')
    @fbx_name_LOD3.setter
    def fbx_name_LOD3(self, name):
        cmds.setAttr(self.node + '.fbx_name_LOD3', name, type='string')

    @property
    def fbx_name_LOD4(self):
        return cmds.getAttr(self.node + '.fbx_name_LOD4')
    @fbx_name_LOD4.setter
    def fbx_name_LOD4(self, path):
        cmds.setAttr(self.node + '.fbx_name_LOD4', path, type='string')


    #return joints
    @property
    def joints(self):
        if self.export_root:
            returnMe = []
            children = cmds.listRelatives(self.export_root, type='joint',allDescendents=True)
            if children:
                returnMe.extend(children)

            returnMe.append(self.export_root[0])
            return returnMe
    @joints.setter
    def joints(self):
        print 'Joints returned by walking hierarchy from the root, not directly settable.'

    #return fbxExportDict
    @property
    def fbxExportProperties(self):
        return self.getFbxExportPropertiesDict()
    @fbxExportProperties.setter
    def fbxExportProperties(self, dict):
        self.fbxPropertiesDict = dict
        cmds.setAttr(self.node + '.fbxPropertiesDict', json.dumps(self.fbxPropertiesDict), type='string')

########################################################################
## UEXPORT TOOL
########################################################################


class uExportTool(base_class, form_class):
    title = 'uExportTool 0.8'

    currentMesh = None
    currentSkin = None
    currentInf = None
    currentVerts = None
    currentNormalization = None

    scriptJobNum = None
    copyCache = None

    jointLoc = None

    iconLib = {}
    iconPath = os.environ.get('MAYA_LOCATION', None) + '/icons/'
    iconLib['joint'] = QtGui.QIcon(QtGui.QPixmap(iconPath + 'kinJoint.png'))
    iconLib['ikHandle'] = QtGui.QIcon(QtGui.QPixmap(iconPath + 'kinHandle.png'))
    iconLib['transform'] = QtGui.QIcon(QtGui.QPixmap(iconPath + 'orientJoint.png'))

    def __init__(self, parent=getMayaWindow()):
        self.closeExistingWindow()
        super(uExportTool, self).__init__(parent)


        self.setupUi(self)
        self.setWindowTitle(self.title)
        self.fbxVerLbl.setText('fbx plugin ' + str(self.fbxVersion()) + '  ')

        wName = openMayaUI.MQtUtil.fullName(long(shiboken.getCppPointer(self)[0]))

        ## Connect UI
        ########################################################################
        self.export_BTN.clicked.connect(self.export_FN)
        self.createUexportNode_BTN.clicked.connect(self.createUexportNode_FN)
        self.replaceUnknownNodes.clicked.connect(self.replaceUnknownNodes_FN)
        self.refreshBTN.clicked.connect(self.refreshUI)
        self.getTexturesP4BTN.clicked.connect(self.getTexturesP4_FN)

        # TODO: Add save settings, setting p4 menu for now
        self.p4CHK.setChecked(False)

        self.workSpaceCMB.currentIndexChanged.connect(self.workspaceSelected)

        #context menu
        self.export_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.export_tree.customContextMenuRequested.connect(self.openMenu)

        self.export_tree.itemClicked.connect(self.check_status)
        self.export_tree.itemClicked.connect(self.itemClicked)
        self.missingFilesTree.itemClicked.connect(self.itemClicked)


        #check for p4 lib
        yourP4Module = 'p4python.P4'
        try:
            __import__(yourP4Module)
        except ImportError:
            print 'Perforce lib not found.'
            self.perforce = False
        else:
            self.perforce = True
            print 'Perforce lib found.'

        #Connect event filter to grab right/left click
        self.export_tree.viewport().installEventFilter(self)
        self.mousePress = None

        self.snapRoot_CMB.setHidden(True)
        self.refreshUI()

## GENERAL
########################################################################

    #quick mesh check
    def isMesh(self, node):
        rels = cmds.listRelatives(node, children=True, s=True)
        if rels:
            for shp in rels:
                if cmds.nodeType(shp)=='mesh':
                    return True
        return False

    def setOutlinerToShowAssetContents(self):
        mel.eval('outlinerEditor -e -showContainerContents 1 outlinerPanel1; outlinerEditor -e \
        -showContainedOnly 0 outlinerPanel1;')

    def closeExistingWindow(self):
        for qt in QtWidgets.qApp.topLevelWidgets():
            try:
                if qt.__class__.__name__ == self.__class__.__name__:
                    qt.deleteLater()
                    print 'uExport: Closed ' + str(qt.__class__.__name__)
            except:
                pass

    def convertSkelSettingsToNN(delete=1):
        orig = 'SkeletonSettings_Cache'
        if cmds.objExists(orig):
            if cmds.nodeType(orig) == 'unknown':
                new = cmds.createNode('network')
                for att in cmds.listAttr(orig):
                    if not cmds.attributeQuery(att, node=new, exists=1):
                        typ = cmds.attributeQuery(att, node=orig, at=1)
                        if typ == 'typed':
                            cmds.addAttr(new, longName=att, dt='string')
                            if cmds.getAttr(orig + '.' + att):
                                cmds.setAttr(new + '.' + att, cmds.getAttr(orig + '.' + att), type='string')
                        elif typ == 'enum':
                            cmds.addAttr(new, longName=att, at='enum', enumName=cmds.attributeQuery(att, node=orig, listEnum=1)[0])
                cmds.delete(orig)
                cmds.rename(new, 'SkeletonSettings_Cache')

    def fbxVersion(self):
        for plugin in cmds.pluginInfo(q=True, listPlugins=True):
            if "fbxmaya" in plugin:
                return cmds.pluginInfo(plugin, q=True, version=True)

    def replaceUnknownNodes_FN(self):
        self.convertSkelSettingsToNN()

    def isBlendshape(self, mesh):
        future = cmds.listHistory(mesh, future=1)
        isShape = False
        for node in future:
            if cmds.nodeType(node) == 'blendShape':
                return True
        return False

    def LOD_transferWeights(meshes, jointsToRemove, jointToTransferTo, debug=1, pruneWeights=0.001, *args):
        '''
        Original function by Charles Anderson @ Epic Games
        '''
        for mesh in meshes:

            # Find the skin cluster for the current mesh
            cluster = findCluster(mesh)

            if debug:
                print "MESH: ", mesh
                print "CLUSTER: ", cluster

            # Prune weights on the current mesh
            if pruneWeights:
                cmds.skinPercent(cluster, mesh, prw=pruneWeights)

            # Find all of the current influences on the current skin cluster.
            meshInfluences = cmds.skinCluster(cluster, q=True, inf=True)
            #print "Current Influences: ", meshInfluences

            for joint in jointsToRemove:
                if joint in meshInfluences:
                    #print "Current Joint: ", joint

                    # If the jointToTransferTo is not already an influence on the current mesh then add it.
                    currentInfluences = cmds.skinCluster(cluster, q=True, inf=True)
                    if jointToTransferTo not in currentInfluences:
                        cmds.skinCluster(cluster, e=True, wt=0, ai=jointToTransferTo)

                    # Now transfer all of the influences we want to remove onto the jointToTransferTo.
                    for x in range(cmds.polyEvaluate(mesh, v=True)):
                        #print "TRANSFERRING DATA....."
                        value = cmds.skinPercent(cluster, (mesh+".vtx["+str(x)+"]"), t=joint, q=True)
                        if value > 0:
                            cmds.skinPercent(cluster, (mesh+".vtx["+str(x)+"]"), tmw=[joint, jointToTransferTo])

            # Remove unused influences
            currentInfluences = cmds.skinCluster(cluster, q=True, inf=True)
            #print "Current Influences: ", currentInfluences
            influencesToRemove = []
            weightedInfs = cmds.skinCluster(cluster, q=True, weightedInfluence=True)
            #print "Weighted Influences: ", weightedInfs
            for inf in currentInfluences:
                #print "Influence: ", inf
                if inf not in weightedInfs:
                    #print "Update Influences to Remove List: ", inf
                    influencesToRemove.append(inf)

            #print "ToRemove Influences: ", influencesToRemove
            if influencesToRemove != []:
                for inf in influencesToRemove:
                    cmds.skinCluster(cluster, e=True, ri=inf)

## UI RELATED
########################################################################

    #event filter to grab and discern right/left click
    def eventFilter(self, source, event):
        if (event.type() == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.RightButton and source is self.export_tree.viewport()):
            self.mousePress = 'right'
        elif (event.type() == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.LeftButton and source is self.export_tree.viewport()):
            self.mousePress = 'left'
        return super(uExportTool, self).eventFilter(source, event)

    #contextual menus
    def openMenu(self, position):
        menu = QtWidgets.QMenu()
        clickedWid = self.export_tree.itemAt(position)

        if 'P4_FILE_LIST' in self.export_tree.itemAt(position).text(0):
            checkOut = menu.addAction("Check out files")
            pos = self.export_tree.mapToGlobal(position)
            action = menu.exec_(pos)

            if action:
                print 'checkin gout files'

        if 'LOD ' in clickedWid.text(0):
            addMeshes = menu.addAction("Add selected meshes")
            removeMeshes = menu.addAction("Remove selected meshes")
            resetMeshes = menu.addAction("Set only selected meshes")

            pos = self.export_tree.mapToGlobal(position)
            action = menu.exec_(pos)

            if action:
                if action == addMeshes:
                    meshes = [mesh for mesh in cmds.ls(sl=1) if self.isMesh(mesh)]
                    uNode = clickedWid.uExport
                    lod = clickedWid.lod
                    existingMeshes = eval('uNode.rendermeshes_LOD' + str(lod))
                    existingMeshes.extend(meshes)
                    uNode.connectRenderMeshes(existingMeshes, LOD=clickedWid.lod)
                    self.refreshUI()
                elif action == removeMeshes:
                    meshes = [mesh for mesh in cmds.ls(sl=1) if self.isMesh(mesh)]
                    uNode = clickedWid.uExport
                    lod = clickedWid.lod
                    existingMeshes = eval('uNode.rendermeshes_LOD' + str(lod))
                    newMeshes = [mesh for mesh in existingMeshes if mesh not in meshes]
                    uNode.connectRenderMeshes(newMeshes, LOD=lod)
                    self.refreshUI()
                elif action == resetMeshes:
                    newMeshes = cmds.ls(sl=1)
                    uNode = clickedWid.uExport
                    lod = clickedWid.lod
                    uNode.connectRenderMeshes(newMeshes, LOD=lod)
                    self.refreshUI()

        if not self.export_tree.itemAt(position).parent():
            rootRewire = menu.addAction("Re-wire root joint attr to current selected joint")

            meshSubmenu = menu.addMenu('EDIT RENDERMESHES >>')

            addLOD0 = meshSubmenu.addAction("Add selected as LOD0 render meshes")
            addLOD1 = meshSubmenu.addAction("Add selected as LOD1 render meshes")
            addLOD2 = meshSubmenu.addAction("Add selected as LOD2 render meshes")
            addLOD3 = meshSubmenu.addAction("Add selected as LOD3 render meshes")
            addLOD4 = meshSubmenu.addAction("Add selected as LOD4 render meshes")

            scriptSubmenu = menu.addMenu('ADD EXPORT SCRIPTS >>')

            addScriptLOD0 = scriptSubmenu.addAction("Add LOD0 export script")
            addScriptLOD1 = scriptSubmenu.addAction("Add LOD1 export script")
            addScriptLOD2 = scriptSubmenu.addAction("Add LOD2 export script")
            addScriptLOD3 = scriptSubmenu.addAction("Add LOD3 export script")
            addScriptLOD4 = scriptSubmenu.addAction("Add LOD4 export script")

            pos = self.export_tree.mapToGlobal(position)
            action = menu.exec_(pos)


            if action:
                if action == rootRewire:
                    index = self.export_tree.selectedIndexes()[0]
                    uExportNode = self.export_tree.itemFromIndex(index).uExport.node
                    root = cmds.ls(sl=1)
                    if len(root) == 1:
                        self.connectRoot(uExportNode, root[0])
                    else:
                        cmds.error('Select a single joint, you == fail, bro. ' + str(root))

                elif action in (addLOD0, addLOD1, addLOD2, addLOD3, addLOD4):
                    for index in self.export_tree.selectedIndexes():
                        uExportNode = self.export_tree.itemFromIndex(index).uExport
                        meshes = cmds.ls(sl=1)
                        #TODO: check if theyre actually meshes
                        if action == addLOD0: uExportNode.rendermeshes_LOD0 = meshes
                        if action == addLOD1: uExportNode.rendermeshes_LOD1 = meshes
                        if action == addLOD2: uExportNode.rendermeshes_LOD2 = meshes
                        if action == addLOD3: uExportNode.rendermeshes_LOD3 = meshes
                        if action == addLOD4: uExportNode.rendermeshes_LOD4 = meshes

                elif action in (addScriptLOD0, addScriptLOD1, addScriptLOD2, addScriptLOD3, addScriptLOD4):
                    for index in self.export_tree.selectedIndexes():
                        uExportNode = self.export_tree.itemFromIndex(index).uExport

                        fileName,_ = QtWidgets.QFileDialog.getOpenFileName(self,
                        "Choose a Python Script", '',
                        "Python (*.py);;All Files (*)")

                        if fileName:
                            if action == addScriptLOD0: uExportNode.export_script_LOD0 = fileName
                            if action == addScriptLOD1: uExportNode.export_script_LOD1 = fileName
                            if action == addScriptLOD2: uExportNode.export_script_LOD2 = fileName
                            if action == addScriptLOD3: uExportNode.export_script_LOD3 = fileName
                            if action == addScriptLOD4: uExportNode.export_script_LOD4 = fileName

                self.refreshUI()

    def refreshUI(self):
        start = time.time()

        self.export_tree.clear()
        self.missingFilesTree.clear()
        self.uNodes = []
        for node in self.getExportNodes():
            self.uNodes.append(uExport(node))
        self.buildExportTree(self.uNodes)
        self.buildMissingFilesTree()


        if self.p4CHK.isChecked():
            if self.perforce:
                self.getTexturesP4BTN.setEnabled(True)
                self.getP4Workspaces()

        # put export into the uExport class later

        elapsed = (time.time() - start)
        print 'uExport>>> Refreshed in %.2f seconds.' % elapsed


    def buildExportTree(self, uNodes):
        for uNode in uNodes:

            red = QtWidgets.QColor(200, 75, 75, 255)
            widRed = QtWidgets.QColor(200, 75, 75, 100)
            blue = QtWidgets.QColor(50, 130, 210, 255)
            widBlue = QtWidgets.QColor(50, 130, 210, 100)

            #top level
            wid1 = QtWidgets.QTreeWidgetItem()
            font = wid1.font(0)
            font.setPointSize(15)

            wid1.setText(0,uNode.asset_name)
            wid1.uExport = uNode

            wid1.setText(1, uNode.version)
            self.export_tree.addTopLevelItem(wid1)
            wid1.setExpanded(True)
            wid1.setFont(0,font)

            font = wid1.font(0)
            font.setPointSize(10)

            wid1.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsSelectable)
            wid1.setCheckState(0, QtCore.Qt.Checked)

            wid1.setBackground(0, QtWidgets.QColor(widBlue))

            #mesh branch
            meshTop = QtWidgets.QTreeWidgetItem()
            meshes = uNode.rendermeshes_LOD0
            if meshes:
                meshTop.setText(0, 'RENDER MESHES: (' + str(len(uNode.rendermeshes_ALL)) + ')  LODS: (' + str(uNode.lodNum) + ')')
            else:
                meshTop.setText(0, 'RENDER MESHES: NONE')
            meshTop.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsUserCheckable)
            meshTop.setCheckState(0, QtCore.Qt.Checked)
            wid1.addChild(meshTop)
            meshTop.setExpanded(True)

            allMeshRelated = []

            #get mat info
            start = time.time()
            shaderDict = uNode.getShaderDict()
            elapsed = (time.time() - start)
            print 'uExport>>> Built shader dict for ' + uNode.asset_name + ' in %.2f seconds.' % elapsed

            #meshes
            lodDicts = uNode.getLodDicts()
            if lodDicts:
                for lodNum in lodDicts:
                    lodWid = QtWidgets.QTreeWidgetItem()

                    #get mesh info
                    meshes = lodDicts[lodNum]['meshes']
                    numMeshes = '0'
                    if meshes:
                        numMeshes = str(len(meshes))
                    else:
                        lodWid.setForeground(0,red)
                        continue

                    numShaders = 0
                    usedShaders = []

                    if shaderDict:
                        numShaders = len(shaderDict.keys())
                        for mat in shaderDict.keys():
                            for mesh in meshes:
                                if mesh in shaderDict[mat]:
                                    usedShaders.append(mat)
                    else:
                        lodWid.setForeground(0,red)
                        wid1.setBackground(0, widRed)

                    usedShaders = set(usedShaders)

                    widText = 'LOD ' + str(lodNum) + '  (' + numMeshes + ' meshes) (' + str(len(usedShaders)) + ' materials)'
                    if lodDicts[lodNum]['export_script']:
                        widText += '  > Export Script: ' + lodDicts[lodNum]['export_script'].split('/')[-1]

                    lodWid.setText(0, widText)

                    #add metadata for later use
                    lodWid.lod = lodNum
                    lodWid.uExport = uNode

                    meshTop.addChild(lodWid)

                    #create mesh top widget
                    meshLodTop = QtWidgets.QTreeWidgetItem()
                    meshLodTop.setText(0, 'MESHES (' + numMeshes + ')')
                    lodWid.addChild(meshLodTop)

                    matLodTop = QtWidgets.QTreeWidgetItem()

                    if meshes:
                        for mesh in meshes:
                            meshWid = QtWidgets.QTreeWidgetItem()
                            meshWid.setText(0, mesh)
                            meshLodTop.addChild(meshWid)

                            if not findRelatedSkinCluster(mesh):
                                if self.isBlendshape(mesh):
                                    meshWid.setForeground(0, blue)
                                    meshWid.setText(0, mesh + '  (blendshape)')
                                else:
                                    meshWid.setForeground(0, red)
                                    wid1.setBackground(0, widRed)
                                    meshWid.setText(0, mesh + ': NO SKINCLUSTER')
                                    for item in getParents(meshWid):
                                        item.setExpanded(True)
                            meshWid.selectMe = [mesh]
                        meshLodTop.selectMe = meshes

                    else:
                        meshWid = QtWidgets.QTreeWidgetItem()
                        meshWid.setText(0, 'NONE')
                        meshLodTop.addChild(meshWid)

                    #create mat top widget
                    matLodTop = QtWidgets.QTreeWidgetItem()
                    lodWid.addChild(matLodTop)

                    usedShaders = list(set(usedShaders))

                    for shader in usedShaders:
                        matWid = QtWidgets.QTreeWidgetItem()
                        matWid.setText(0, shader)
                        matWid.setText(1, str(shaderDict[shader]))
                        matLodTop.addChild(matWid)
                        matWid.selectMe = [shader]
                    self.export_tree.sortItems(0, QtCore.Qt.SortOrder(0))

                    matLodTop.setText(0, 'MATERIALS (' + str(len(usedShaders)) + ')')
                    matLodTop.selectMe = usedShaders

                    lodWid.selectMe = usedShaders + meshes

                    allMeshRelated.extend(lodWid.selectMe)

                meshTop.selectMe = allMeshRelated



            #anim branch
            animTop = QtWidgets.QTreeWidgetItem()

            animTop.selectMe = uNode.joints

            if uNode.export_root:
                jnts = uNode.joints
                if jnts:
                    animTop.setText(0, 'ANIMATION:  (' + str(len(uNode.joints)) + ' JOINTS)')
            else:
                animTop.setText(0, 'ANIMATION: NO SKELETON ROOT SET')
                animTop.setForeground(0, red)
                wid1.setBackground(0, widRed)
            animTop.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsUserCheckable)
            animTop.setCheckState(0, QtCore.Qt.Checked)
            wid1.addChild(animTop)

            #anims
            animWid = QtWidgets.QTreeWidgetItem()
            animWid.setText(0, '<< CURRENT TIME RANGE >>')
            animTop.addChild(animWid)


            #meta branch
            metaTop = QtWidgets.QTreeWidgetItem()
            metaTop.setText(0, 'METADATA')
            wid1.addChild(metaTop)

            # uexport node meta
            ueWid = QtWidgets.QTreeWidgetItem()
            ueWid.setText(0, 'UEXPORT NODE:   ' + str(uNode.node))
            metaTop.addChild(ueWid)
            ueWid.selectMe = uNode.node

            #export path meta
            fpathWid = QtWidgets.QTreeWidgetItem()
            fpathWid.setText(0, 'EXPORT_FOLDER_PATH:   ' + str(uNode.folder_path))
            metaTop.addChild(fpathWid)

            fbxInfoRoot = QtWidgets.QTreeWidgetItem()
            fbxInfoRoot.setText(0, 'FBX_INFO ')
            metaTop.addChild(fbxInfoRoot)
            fbxInfoRoot.setExpanded(True)
            #fbx files meta
            fbxFiles = QtWidgets.QTreeWidgetItem()
            fbxFiles.setText(0, 'files ')
            fbxInfoRoot.addChild(fbxFiles)
            fileNum = 0
            for lodNum in lodDicts:
                if lodDicts[lodNum]['fbx_name']:
                    fbxMeshWid = QtWidgets.QTreeWidgetItem()
                    fbxMeshWid.setText(0, lodDicts[lodNum]['fbx_name'])
                    fbxFiles.addChild(fbxMeshWid)
                    fileNum += 1
            fbxFiles.setText(0, 'files on disk  (' + str(fileNum) + ')')

            #fbx settings meta
            fbxProps = uNode.fbxExportProperties
            fbxDefault = 1

            fbxSettings = QtWidgets.QTreeWidgetItem()
            fbxSettings.setText(0, 'export settings  (default)')
            if fbxProps != {u'animInterpolation':u'quaternion', u'upAxis':u'default', u'triangulation':False}:
                fbxSettings.setText(0, 'export settings  (non-default)')
                fbxDefault = 0
            fbxInfoRoot.addChild(fbxSettings)

            #fbx settings
            interpType = QtWidgets.QTreeWidgetItem()
            interpType_CMB = self.makeTreeCmb(['INTERP TYPE: Quaternion','INTERP TYPE: Euler', 'INTERP TYPE: Resample'], 160)
            interpType_CMB.currentIndexChanged.connect(functools.partial(self.setAnimInterpolation, interpType_CMB, uNode))

            if fbxProps['animInterpolation'].lower() == 'quaternion':
                interpType_CMB.setCurrentIndex(0)
            elif fbxProps['animInterpolation'].lower() == 'euler':
                interpType_CMB.setCurrentIndex(1)
            else:
                interpType_CMB.setCurrentIndex(2)


            upAxis = QtWidgets.QTreeWidgetItem()
            upAxis_CMB = self.makeTreeCmb(['UP AXIS: Default','UP AXIS: Y', 'UP AXIS: Z'], 150)
            upAxis_CMB.currentIndexChanged.connect(functools.partial(self.setUpAxis, upAxis_CMB, uNode))

            if fbxProps['upAxis'].lower() == 'default':
                upAxis_CMB.setCurrentIndex(0)
            elif fbxProps['upAxis'].lower() == 'y':
                upAxis_CMB.setCurrentIndex(1)
            else:
                upAxis_CMB.setCurrentIndex(2)

            #triangulate checkbox and logic to write properties
            triangulate = QtWidgets.QTreeWidgetItem()
            triangulate_CHK = QtWidgets.QCheckBox(parent=self.export_tree)
            triangulate_CHK.setText('Triangulate mesh')
            triangulate_CHK.setChecked(fbxProps['triangulation'])
            triangulate_CHK.stateChanged.connect(functools.partial(self.setTriangulation, triangulate_CHK, uNode))

            fbxSettings.addChild(interpType)
            fbxSettings.addChild(upAxis)
            fbxSettings.addChild(triangulate)
            self.export_tree.setItemWidget(interpType, 0, interpType_CMB)
            self.export_tree.setItemWidget(upAxis, 0, upAxis_CMB)
            self.export_tree.setItemWidget(triangulate, 0, triangulate_CHK)

            #if the settings don't match the defaults, set expanded for the user to keep an eye
            if not fbxDefault:
                fbxSettings.setExpanded(True)

            #p4
            if self.p4CHK.isChecked():
                p4FileList = QtWidgets.QTreeWidgetItem()
                p4FileList.setText(0, 'P4_FILE_LIST')
                metaTop.addChild(p4FileList)
                for lodNum in lodDicts:
                    if lodDicts[lodNum]['fbx_name']:
                        p4DepotFile = self.getP4Location(lodDicts[lodNum]['fbx_name'])
                        if p4DepotFile:
                            p4FileWid = QtWidgets.QTreeWidgetItem()
                            p4FileWid.setText(0, p4DepotFile[1])
                            p4FileList.addChild(p4FileWid)

                            #set tool tip with p4 info
                            p4FileWid.setToolTip(0, p4DepotFile[0] + '\n' + p4DepotFile[2] + '\n' + p4DepotFile[3])
            wid1.sortChildren(0, QtCore.Qt.SortOrder(0))

    def makeTreeCmb(self, items, width, select=None):
        if items:
            cmb = QtWidgets.QComboBox(parent=self.export_tree)
            cmb.addItems(items)
            cmb.setMaximumWidth(width)
            cmb.setMaximumHeight(15)
            return cmb
        else:
            return False

    #functions for auto-generated UI in the tree
    def setTriangulation(self, chk, uNode, *args):
        fbxDict = uNode.fbxExportProperties
        if chk.isChecked():
            fbxDict['triangulation'] = True
            uNode.fbxExportProperties = fbxDict
        else:
            fbxDict['triangulation'] = False
            uNode.fbxExportProperties = fbxDict

    def setUpAxis(self, cmb, uNode, *args):
        fbxDict = uNode.fbxExportProperties
        index = cmb.currentIndex()
        if index == 0:
            fbxDict['upAxis'] = 'default'
            uNode.fbxExportProperties = fbxDict
        elif index == 1:
            fbxDict['upAxis'] = 'y'
            uNode.fbxExportProperties = fbxDict
        else:
            fbxDict['upAxis'] = 'z'
            uNode.fbxExportProperties = fbxDict

    def setAnimInterpolation(self, cmb, uNode, *args):
        fbxDict = uNode.fbxExportProperties
        index = cmb.currentIndex()
        if index == 0:
            fbxDict['animInterpolation'] = 'quaternion'
            uNode.fbxExportProperties = fbxDict
        elif index == 1:
            fbxDict['animInterpolation'] = 'euler'
            uNode.fbxExportProperties = fbxDict
        else:
            fbxDict['animInterpolation'] = 'resample'
            uNode.fbxExportProperties = fbxDict

    def buildMissingFilesTree(self):
        missingFileDict = self.missingNodes()
        for f in missingFileDict.keys():
            wid1 = QtWidgets.QTreeWidgetItem()
            font = wid1.font(0)
            font.setPointSize(15)

            wid1.setText(0,f)

            wid1.setText(2, missingFileDict[f]['path'])
            wid1.setText(3, missingFileDict[f]['node'])
            self.missingFilesTree.addTopLevelItem(wid1)
            wid1.selectMe = missingFileDict[f]['node']

            self.missingFilesTree.header().resizeSections(QtWidgets.QHeaderView.ResizeToContents)

    def createUexportNode_FN(self):
        if cmds.ls(sl=1):
            if self.useRoot_CHK.isChecked():
                rootName = self.rootName_CMB.currentText()
                self.create(renderMeshes=cmds.ls(sl=1), rootJoint=rootName, lods=self.lodNum_SPIN.value())
            else:
                #TODO: modal picker with joint filter
                pass

    def getTexturesP4_FN(self):
        missingFileDict = self.missingNodes()
        self.rePathFileNodesP4(missingFileDict)

    def export_FN(self):
        #get what should be export in an exportTask fn
        exportWidgets = self.getExportNodeWidgets()
        for wid in exportWidgets:
            snapConst = None
            if self.snapRoot_CHK.isChecked():
                node = self.snapRoot_CMB.currentText()
                try:
                    if cmds.objExists(node):
                        snapConst = cmds.parentConstraint(node, wid.uExport.export_root)
                    else:
                        cmds.error('Unable to find node: ' + node)
                except:
                    cmds.warning('Could not constrain root' + wid.uExport.export_root + ', is it already constrained?')
            #export
            mpath = cmds.file(sceneName=1, q=1)
            fname = mpath.split('/')[-1]
            fpath = mpath.replace(fname,'').replace('/','\\')
            if wid.uExport.fbx_name:
                if wid.uExport.fbx_name != '':
                    fname = wid.uExport.fbx_name
            if wid.uExport.folder_path:
                if wid.uExport.folder_path != '':
                    fpath = wid.uExport.folder_path

            #prompt user for save location
            userPath = str()
            if self.suppressSaveCHK.isChecked():
                userPath = "{0}/{1}".format(wid.uExport.folder_path, wid.uExport.fbx_name)
                if not os.path.isfile(userPath):
                    userPath = QtWidgets.QFileDialog.getSaveFileName(caption = 'Export ' + wid.uExport.name + ' to:', filter='FBX Files (*.fbx)', dir=fpath + '\\' + fname)[0]
            else:
                userPath = QtWidgets.QFileDialog.getSaveFileName(caption = 'Export ' + wid.uExport.name + ' to:', filter='FBX Files (*.fbx)', dir=fpath + '\\' + fname)[0]

            if userPath:
                wid.uExport.fbx_name = userPath.split('/')[-1]
                wid.uExport.folder_path = userPath.replace(wid.uExport.fbx_name,'')

                #if set to save loc, save it
                if self.rememberSaveCHK.isChecked():
                    cmds.setAttr(wid.uExport.name + '.folder_path', wid.uExport.folder_path, type='string')
                    cmds.setAttr(wid.uExport.name + '.fbx_name', wid.uExport.fbx_name, type='string')

                    #set initial lod save names
                    if not wid.uExport.fbx_name_LOD0:
                        FbxBaseName = wid.uExport.fbx_name.split('.')[0]
                        wid.uExport.fbx_name_LOD0 = wid.uExport.fbx_name
                        wid.uExport.fbx_name_LOD1 = FbxBaseName + '_LOD1.fbx'
                        wid.uExport.fbx_name_LOD2 = FbxBaseName + '_LOD2.fbx'
                        wid.uExport.fbx_name_LOD3 = FbxBaseName + '_LOD3.fbx'
                        wid.uExport.fbx_name_LOD4 = FbxBaseName + '_LOD4.fbx'


                meshChk = 1
                animChk = 1
                for c in range(0, wid.childCount()):
                    if 'MESH' in wid.child(c).text(0):
                        if wid.child(c).checkState(0) == QtCore.Qt.Checked:
                            pass
                        else:
                            meshChk = 0

                start = time.time()
                #put export into the uExport class later
                export_success = self.export(wid.uExport, path=userPath, mesh=meshChk)
                if export_success:
                    elapsed = (time.time() - start)
                    print 'uExport>>> Exported ', wid.text(0), 'to', userPath ,'in %.2f seconds.' % elapsed

            else:
                cmds.warning('Invalid path specified: [' + str(userPath) + ']')
            #cleanup constraint
            if snapConst: cmds.delete(snapConst)

    def getExportNodeWidgets(self):
        nodes = []
        for i in range(0, self.export_tree.topLevelItemCount()):
            if self.export_tree.topLevelItem(i).checkState(0) == QtCore.Qt.Checked:
                nodes.append(self.export_tree.topLevelItem(i))
        return nodes


    def check_status(self):
        for i in range(0, self.export_tree.topLevelItemCount()):
            if self.export_tree.topLevelItem(i).checkState(0) == QtCore.Qt.Unchecked:
                for c in range(0, self.export_tree.topLevelItem(i).childCount()):
                    self.export_tree.topLevelItem(i).child(c).setCheckState(0,QtCore.Qt.Unchecked)

    def itemClicked(self, *args):
        #select nodes if there is selection metadata
        if self.mousePress is 'left':
            if hasattr(args[0], 'selectMe'):
                cmds.select(args[0].selectMe)


## P4 CRAP
########################################################################
    #check that P4 exists
    def getP4Location(self, asset, root='//depot/ArtSource/', debug=1):
        from p4python.P4 import P4, P4Exception

        if asset:
            p4 = P4()
            try: p4.connect()
            except:
                print 'Cannot connect to P4!'
                return False

            try:
                file =  p4.run_files(root + '...' + asset)
                depotLoc = file[0]['depotFile']
                describe = p4.run_describe(file[0]['change'])
                return [describe[0]['user'], depotLoc, describe[0]['desc'], file[0]['change']]
            except Exception as e:
                print "findFileP4>>>> Cannot find file.", asset
                if debug: print e
                return False
            finally:
                p4.disconnect()

    def workspaceSelected(self):
        self.settings = QtCore.QSettings(QtCore.QSettings.IniFormat,QtCore.QSettings.SystemScope, 'uExport', 'settings')
        self.settings.setFallbacksEnabled(False)
        # setPath() to try to save to current working directory
        self.settings.setPath(QtCore.QSettings.IniFormat,QtCore.QSettings.SystemScope, './uExport_settings.ini')
        self.settings.value('workspace', self.workSpaceCMB.currentText())

    def getP4Workspaces(self):
        import socket
        from p4python.P4 import P4, P4Exception

        #get computer name
        host = socket.gethostname()

        p4 = P4()
        try: p4.connect()
        except:
            print 'Cannot connect to P4!'
            return False

        for ws in p4.run('clients', '-u', p4.user):
            try:
                if ws['Host'] == host:
                    self.workSpaceCMB.addItem(ws['client'])
            except Exception as e:
                print e
        p4.disconnect()

    def colorTreeWidgetItemByName(self, tree, text, color):
        root = tree.invisibleRootItem()
        child_count = root.childCount()
        retWid = None
        for i in range(child_count):
            wid = root.child(i)
            if wid.text(0) == text:
                wid.setForeground(0, color)
                wid.setForeground(1, color)
                wid.setForeground(2, color)
                wid.setForeground(3, color)
                retWid = wid
        if retWid:
            return retWid

    def rePathFileNodesP4(self, missingFileDict, debug=1, checkHash=False):
        from p4python.P4 import P4, P4Exception

        if missingFileDict:
            p4 = P4()
            print self.workSpaceCMB.currentText()
            p4.client = str(self.workSpaceCMB.currentText())
            try: p4.connect()
            except:
                print 'Cannot connect to P4!'
                return False

            for f in missingFileDict.keys():
                floppedPath = missingFileDict[f]['path'].replace('\\', '/') + f
                pathBreak = floppedPath.split('/')

                #find parents since there are dupe files in p4 often
                parent = None
                if len(pathBreak) > 1:
                    parent = pathBreak[-2]
                parentParent = None
                if len(pathBreak) > 2:
                    parentParent = pathBreak[-3]

                depotFileToGrab = None

                files = None
                try:
                    files = p4.run_files(self.p4RootLINE.text() + '...' + f)
                except:
                    pass
                if files:
                    if len(files) > 1:
                        if debug:
                            print 'rePathFileNodesP4>>>> Multiple files [', len(files), '] found in depot search path with the name: ' + f
                            print 'P4 file paths:'
                            for i in range(0, len(files)):
                                print files[i]['depotFile']
                        for i in range(0, len(files)):
                            try:
                                newParent = files[i]['depotFile'].split('/')[-2]
                                if newParent == parent:
                                    if 'delete' in p4.run('fstat', files[i]['depotFile'])[0]['headAction']:
                                        print 'INVALID PATH: p4 asset head revision is deleted or moved. depotFile:', files[i]['depotFile']
                                        continue
                                    depotFileToGrab = files[i]['depotFile']
                                    continue
                                if checkHash:
                                    dupeCheck(files[i]['depotFile'])

                                #color widget red, change INFO
                                widc = self.colorTreeWidgetItemByName(self.missingFilesTree, f, QtWidgets.QColor(200, 75, 75, 255))
                                widc.setText(1, 'NOT FOUND')

                            except Exception as e:
                                if debug:
                                    print e
                        print 'rePathFileNodesP4>>>> No file path similarities to path:', floppedPath
                    else:
                        print 'rePathFileNodesP4>>>> File found on depot: ', files[0]['depotFile']
                        depotFileToGrab = files[0]['depotFile']

                else:
                    print 'rePathFileNodesP4>>>> FILE NOT FOUND IN PERFORCE SEARCH PATH - fName:', f, 'searchPath:', self.p4RootLINE.text()
                    #color widget red, change INFO
                    widc = self.colorTreeWidgetItemByName(self.missingFilesTree, f, QtWidgets.QColor(200, 75, 75, 255))
                    widc.setText(1, 'NOT FOUND')


                #if we found it in the depot
                if depotFileToGrab:
                    print 'GRABBING: ', depotFileToGrab
                    try:
                        p4.run('sync', ' -f', depotFileToGrab)
                    except Exception as e:
                        if 'up-to-date' in e.message:
                            pass
                        else:
                            print e

                    fileFstat = p4.run('fstat', depotFileToGrab)[0]
                    print fileFstat
                    newPath = fileFstat['clientFile']
                    newPath = newPath.replace('\\','/')

                    if debug: print 'rePathFileNodesP4>>>> NEW PATH>>', newPath, '\n\n'
                    cmds.setAttr((missingFileDict[f]['node'] + '.fileTextureName'), newPath, type='string')
                    #color widget green, change info
                    widc = self.colorTreeWidgetItemByName(self.missingFilesTree, f, QtWidgets.QColor(40, 230, 160, 255))
                    widc.setText(1, 'FOUND')

                self.repaint()

            p4.disconnect()


## UEXPORT NODE
########################################################################
    def getExportNodes(self):
        return cmds.ls('*.uexport_ver', o=1, r=1)

    def connectRoot(self, uNode, root, rewire=1):
        try:
            cmds.undoInfo(openChunk=True)
            if rewire:
                conns = cmds.listConnections(uNode + '.export_root', plugs=1, source=1)
                if conns:
                    for conn in conns:
                        cmds.disconnectAttr(conn, uNode + '.export_root')

            if not attrExists(root+'.export'):
                cmds.addAttr(root, longName='export', attributeType='message')
            cmds.connectAttr(root + '.export', uNode + '.export_root' )
        except Exception as e:
            print e
        finally:
            cmds.undoInfo(closeChunk=True)

    def create(self, renderMeshes=None, rootJoint=None, strName='uExport', lods=1):

        uExportNode = None
        if cmds.objExists(strName):
            #later re-hook up
            #set uExport
            cmds.warning('uExport>>>>> uExport node already exists with name: ' + strName)
            pass
        else:
            try:
                cmds.undoInfo(openChunk=True)

                text, ok = QtWidgets.QInputDialog.getText(None, 'Creating uExport Node', 'Enter node name:', text='uExport')
                if text:
                    strName = text

                uExportNode = cmds.group(em=1, name=strName)
                cmds.addAttr(uExportNode, ln='export_root', at='message')
                cmds.addAttr(uExportNode, ln='materials', at='message')
                cmds.addAttr(uExportNode, ln='uexport_ver', dt='string')
                cmds.setAttr(uExportNode + '.uexport_ver', '1.0', type='string')
                cmds.addAttr(uExportNode, ln='folder_path', dt='string')
                cmds.addAttr(uExportNode, ln='asset_name', dt='string')
                cmds.addAttr(uExportNode, ln='fbx_name', dt='string')
                cmds.addAttr(uExportNode, ln='lodNum', at='byte')

                cmds.setAttr(uExportNode + '.lodNum', lods)

                if self.createArtMetadata_CHK.isChecked():
                    #not used atm
                    cmds.addAttr(uExportNode, ln='joint_mover_template', dt='string')
                    cmds.addAttr(uExportNode, ln='skeleton_template', dt='string')
                    cmds.addAttr(uExportNode, ln='pre_script', dt='string')
                    cmds.addAttr(uExportNode, ln='post_script', dt='string')
                    cmds.addAttr(uExportNode, ln='export_file', dt='string')
                    cmds.addAttr(uExportNode, ln='anim_file', dt='string')
                    cmds.addAttr(uExportNode, ln='skeleton_uasset', dt='string')
                    cmds.addAttr(uExportNode, ln='skelmesh_uasset', dt='string')
                    cmds.addAttr(uExportNode, ln='physics_uasset', dt='string')
                    cmds.addAttr(uExportNode, ln='thumbnail_large', dt='string')
                    cmds.addAttr(uExportNode, ln='thumbnail_small', dt='string')

                text, ok = QtWidgets.QInputDialog.getText(None, 'Defining Asset', 'Enter asset name:', text='myAsset')

                if text:
                    #internal ART stuff
                    cmds.setAttr(uExportNode + '.asset_name', text, type='string')

            except Exception as e:
                cmds.warning(e)
                print 'Locals: ' + str(locals())
            finally:
                cmds.undoInfo(closeChunk=True)

        if uExportNode:

            uNode = uExport(uExportNode)

            try:
                if renderMeshes:
                    uNode.rendermeshes_LOD0 = renderMeshes

                #rootJoint
                if rootJoint:
                    if not attrExists(rootJoint+'.export'):
                        cmds.addAttr(rootJoint, longName='export', attributeType='message')
                    cmds.connectAttr(rootJoint + '.export', uExportNode + '.export_root')
                else:
                    cmds.warning('No root joint or could not find root: ' + str(rootJoint))

            except Exception as e:
                print cmds.warning(e)
                print 'Locals: ' + str(locals())

            self.tabWidget.setCurrentIndex(0)
            self.refreshUI()


## MISSING TEXTURES
########################################################################

    def missingNodes(self):
        fileNodes = cmds.ls(type='file')
        missingFiles = {}
        for f in fileNodes:
            filePath = cmds.getAttr(f + '.fileTextureName')
            if filePath != '':
                if not cmds.file(filePath, exists=1, q=1):
                    fileName = filePath.split('/')[-1]
                    path = filePath.replace(fileName,'')
                    missingFiles[fileName] = {'path':path, 'node':f}
        return missingFiles


## SANITY CHECK
########################################################################

    #general methods
    def hasPrefix(self, obj, prefix, fix=1):
        if obj.startswith(prefix):
            return True
        else:
            return False

    #triggers
    #TODO: remove issue class usage, hook up
    '''
    def matCheck(self, meshes, debug=1, mNum=1):
        import re

        issues = []
        allShaders = []

        for mesh in meshes:

            shaders = []
            shaders.extend(getAssocShaders(mesh))

            shaders = set(shaders)
            if debug:
                print 'Shaders found:', shaders

            for shader in shaders:

                allShaders.append(shader)

                shaderNum = re.search(r'\d+$', shader).group()
                if not shaderNum:
                    issue = Issue(shader, 'Shader [' + shader + '] does not end in a number', assocNode=mesh)
                    issues.append(issue)

                if not hasPrefix(shader,'M_'):
                    issue = Issue(shader, 'Shader [' + shader + '] does not have the prefix \'M_\'', assocNode=mesh)
                    issues.append(issue)
                    #FIX
                    if shader.startswith('m_'):
                        print shader
                        shader[0:1] = 'M_'
                        #cmds.rename(shader, )

                if '_skin' not in shader:
                    issue = Issue(shader, 'Shader [' + shader + '] does not have the suffix \'_skin\'', assocNode=mesh)
                    issues.append(issue)

        shaderDict = {}
        for shader in set(allShaders):
            shaderNum = re.search(r'\d+$', shader).group()
            if shaderNum in shaderDict.keys():
                issue = Issue(shader, 'Shader [' + shader + '] shader with slot number already exists: ' + shaderDict[shaderNum], assocNode=shaderDict[shaderNum])
                issues.append(issue)
            else:
                shaderDict[shaderNum] = shader

        if mNum:
            for key in shaderDict.keys():
                pass
                #cmds.rename(shaderDict[key], )

        return issues
    '''


## EXPORT
########################################################################

    #TODO: Find and export blendshape meshes!
    def setExportFlags(self, uNode):

        # set export properties from the fbxExportPropertiesDict of the uNode
        fbxDict = uNode.fbxExportProperties
        if fbxDict['triangulation'] == True:
            mel.eval("FBXExportTriangulate -v true")
        else:
            mel.eval("FBXExportTriangulate -v false")

        # Mesh
        mel.eval("FBXExportSmoothingGroups -v true")
        mel.eval("FBXExportHardEdges -v false")
        mel.eval("FBXExportTangents -v true")
        mel.eval("FBXExportInstances -v false")
        mel.eval("FBXExportInAscii -v true")
        mel.eval("FBXExportSmoothMesh -v false")

        # Animation
        mel.eval("FBXExportBakeResampleAnimation -v true")
        mel.eval("FBXExportBakeComplexAnimation -v true")
        mel.eval("FBXExportBakeComplexStart -v "+str(cmds.playbackOptions(minTime=1, q=1)))
        mel.eval("FBXExportBakeComplexEnd -v "+str(cmds.playbackOptions(maxTime=1, q=1)))
        mel.eval("FBXExportReferencedAssetsContent -v true")
        mel.eval("FBXExportBakeComplexStep -v 1")
        mel.eval("FBXExportUseSceneName -v false")
        mel.eval("FBXExportQuaternion -v quaternion")
        mel.eval("FBXExportShapes -v true")
        mel.eval("FBXExportSkins -v true")

        if fbxDict['animInterpolation'] == 'euler':
            mel.eval("FBXExportQuaternion -v euler")
        elif fbxDict['animInterpolation'] == 'resample':
            mel.eval("FBXExportQuaternion -v resample")

        if fbxDict['upAxis'].lower() == 'y':
            print 'FBX EXPORT OVERRIDE: setting y up axis'
            mel.eval("FBXExportUpAxis y")
        elif fbxDict['upAxis'].lower() == 'z':
            print 'FBX EXPORT OVERRIDE: setting Z up axis'
            mel.eval("FBXExportUpAxis z")

        #garbage we don't want
        # Constraints
        mel.eval("FBXExportConstraints -v false")
        # Cameras
        mel.eval("FBXExportCameras -v false")
        # Lights
        mel.eval("FBXExportLights -v false")
        # Embed Media
        mel.eval("FBXExportEmbeddedTextures -v false")
        # Connections
        mel.eval("FBXExportInputConnections -v false")

    def export(self, uNode, mesh=1, anim=1, path=None,bake=False):

        # check if the file is checked out/writeable
        if os.path.isfile(path):
            file_stat = os.stat(path)[0]
            if not file_stat & stat.S_IWRITE:
                message = "Please ensure you have {0} checked out".format(path)
                return QtWidgets.QMessageBox.information(QtWidgets.QWidget(), "Export Warning", message)

        toExport = []

        if not path:
            oldPath = path
            path = cmds.file(sceneName=1, q=1)
            cmds.warning('No valid path set for export [' + str(oldPath) + ']/nExporting to Maya file loc: ' + path)
            toExport.extend(cmds.listRelatives(uNode.export_root, type='joint',allDescendents=True,f=1))


        #kvassey -- adding support for baking to root in rig before export
        if self.bakeRoot_CHK.isChecked():
            print "Bake Root Checked"
            #copy root skeleton with input connections under new group
            cmds.select(cl=True)
            currRoot = uNode.export_root
            exportSkel = cmds.duplicate(currRoot, un=True, rc=False, po=False)
            tempGrp = cmds.group(exportSkel[0])
            #rename root joint
            dupRoot = cmds.rename(exportSkel[0], currRoot)
            #bake
            startTime = cmds.playbackOptions(min=True, q=True)
            endTime = cmds.playbackOptions(max=True, q=True)
            cmds.bakeResults(dupRoot, sm=True,  hi="below", s=True, sb=1, dic=True, t=(startTime, endTime))

            #move FBX export inside here, skip rest.
            #toExport.extend(cmds.listRelatives(cmds.listConnections(dupRoot), type='joint',allDescendents=True))
            #cmds.select(toExport)
            cmds.select(dupRoot, r=True, hi=True)
            toExport = cmds.ls(sl=True, type='joint')
            cmds.select(toExport, r=True)
            self.setExportFlags(uNode)
            # Export!
            print "FBXExport -f \""+ path +"\" -s"
            mel.eval("FBXExport -f \""+ path +"\" -s")

            cmds.delete(tempGrp)
            toExport = []


        #Assuming the meshes are skinned, maybe work with static later
        else:
            exportScript = False

            if mesh:
                #we're not exporting LODs
                if not self.exportLODs_CHK.isChecked():
                    meshes = uNode.rendermeshes_LOD0
                    if meshes:
                        toExport.extend(uNode.rendermeshes_LOD0)
                    else:
                        cmds.warning('uExport>>> export: No rendermeshes found.')
                #ok, we're exporting LODs
                else:
                    lodDicts = uNode.getLodDicts()
                    if lodDicts:
                        if self.exportLODs_CHK.isChecked():
                            for lodNum in lodDicts:
                                #check that there are meshes to be exported at this LOD
                                if lodDicts[lodNum]['meshes']:
                                    #check if there is a script
                                    if lodDicts[lodNum]['export_script']:
                                        if self.resetAfterExport_CHK.isChecked():
                                            # Warn the user that this operation will save their file.
                                            saveResult = 'Yes'
                                            if not self.suppressSaveCHK.isChecked():
                                                saveResult = cmds.confirmDialog(title = "Save Warning", message="In order to continue your file must be saved.  Would you like to save it?  If yes it will be saved and after the operation is complete your file will be re-opened.", button = ["Save and Continue", "Continue Without Saving"], defaultButton='Save and Continue', cancelButton='Continue Without Saving', dismissString='Continue Without Saving')
                                            if saveResult == 'Yes':
                                                cmds.file(save=True)
                                            else:
                                                cmds.warning('You chose not to save changes. Big-boy pants.')

                                            filePath = lodDicts[lodNum]['export_script']

                                            exportScript = True
                                            if os.path.isfile(filePath):
                                                uExportNode = uNode
                                                execfile(filePath)
                                            else:
                                                cmds.error('UEXPORT>> Cannot find export script: ' + filePath)

                                    #add items for export
                                    toExport.extend(lodDicts[lodNum]['meshes'])
                                    toExport.extend(cmds.listRelatives(uNode.export_root, type='joint',allDescendents=True, f=1))

                                    #setup export
                                    cmds.select(toExport)
                                    self.setExportFlags(uNode)
                                    new_fpath = path[:-4] + '_LOD' + str(lodNum) + '.fbx'

                                    #look for lod name overrides
                                    if lodDicts[lodNum]['fbx_name']:
                                        justFilePath = path.replace(path.split('/')[-1],'')
                                        new_fpath = justFilePath + lodDicts[lodNum]['fbx_name']

                                    # Export!
                                    print "FBXExport -f \"" + new_fpath + "\" -s"
                                    mel.eval("FBXExport -f \"" + new_fpath + "\" -s")

                                    if exportScript:
                                        # Re-open the file without saving.
                                        fullPath = cmds.file(q = True, sceneName = True)
                                        cmds.file(fullPath, open=True, f=True)

                                    #clear sel and export list
                                    cmds.select(d=1)
                                    toExport = []

            if not self.exportLODs_CHK.isChecked():
                if anim:
                    toExport.extend(cmds.listRelatives(uNode.export_root, type='joint', allDescendents=True, f=1) or [])

                    cmds.select(toExport)
                    self.setExportFlags(uNode)
                    # Export!
                    print "FBXExport -f \""+ path +"\" -s"
                    mel.eval("FBXExport -f \""+ path +"\" -s")
        return True


if __name__ == '__main__':
    show()
