# rhinopython
Most of these scripts were last developed for Rhino V6, although most will also work in V5 and V7.

## Preparation for use
Save all the **.py** files to a folder that Rhino can access for running Python scripts and run from Rhino UI or Rhino Python Editor.  For help, see **Getting Started** and **Python Editor for Windows** at https://developer.rhino3d.com/guides/rhinopython/

## Script types
### Runable scripts
#### xBrep_mergeAllFaces.py
Alternative to _MergeAllFaces
#### xBrep_mergeFace.py
Alternative to _MergeFace
#### xBrep_contiguousCoshapedFaces.py
After picking a starting face of a brep, will chain select all contiguous co-shaped faces.

#### Library-only scripts required by runable and/or other library scripts
* xBrep_createFromShape.py,
* xBrepObject.py,
* xPlaneSurface.py,
* xPrimitiveShape.py
