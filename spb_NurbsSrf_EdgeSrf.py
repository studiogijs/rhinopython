"""
As an alternative to _EdgeSrf, this script:
1. Matches unionizes knot vectors more exactly.
2. Offers face-face continuity above G0.
3. Can create a surface from 3 input curves that form an open loop.
4. Can create a surface from 2 input curves.

Send any questions, comments, or script development service needs to @spb on the McNeel Forums: https://discourse.mcneel.com/
"""
"""
211013-25: Created.

TODO:
    Allow continuity choice per edge.
    Convert some rational input to non-rational degree 5?
    Add preview?
"""

import Rhino
import Rhino.DocObjects as rd
import Rhino.Geometry as rg
import Rhino.Input as ri
import scriptcontext as sc

import spb_NurbsSrf_MatchSrf_1Edge as spb


W = rg.IsoStatus.West
S = rg.IsoStatus.South
E = rg.IsoStatus.East
N = rg.IsoStatus.North


class Opts:

    keys = []
    values = {}
    names = {}
    riOpts = {}
    listValues = {}
    stickyKeys = {}


    key = 'iContinuity'; keys.append(key)
    values[key] = 2
    names[key] = 'ContinuityTarget'
    listValues[key] = 'G0', 'G1', 'G2'
    stickyKeys[key] = '{}({})'.format(key, __file__)

    key = 'bEcho'; keys.append(key)
    values[key] = True
    riOpts[key] = ri.Custom.OptionToggle(values[key], 'No', 'Yes')
    stickyKeys[key] = '{}({})'.format(key, __file__)
    
    key = 'bDebug'; keys.append(key)
    values[key] = False
    riOpts[key] = ri.Custom.OptionToggle(values[key], 'No', 'Yes')
    stickyKeys[key] = '{}({})'.format(key, __file__)


    for key in keys:
        if key not in names:
            names[key] = key[1:]


    # Load sticky.
    for key in stickyKeys:
        if stickyKeys[key] in sc.sticky:
            if key in riOpts:
                riOpts[key].CurrentValue = values[key] = sc.sticky[stickyKeys[key]]
            else:
                # For OptionList.
                values[key] = sc.sticky[stickyKeys[key]]


    @classmethod
    def addOption(cls, go, key):

        idxOpt = None

        if key in cls.riOpts:
            if key[0] == 'b':
                idxOpt = go.AddOptionToggle(
                        cls.names[key], cls.riOpts[key])[0]
            elif key[0] == 'f':
                idxOpt = go.AddOptionDouble(
                    cls.names[key], cls.riOpts[key])[0]
            elif key[0] == 'i':
                idxOpt = go.AddOptionInteger(
                    englishName=cls.names[key], intValue=cls.riOpts[key])[0]
        else:
            idxOpt = go.AddOptionList(
                englishOptionName=cls.names[key],
                listValues=cls.listValues[key],
                listCurrentIndex=cls.values[key])

        if not idxOpt: print "Add option for {} failed.".format(key)

        return idxOpt


    @classmethod
    def setValue(cls, key, idxList=None):

        #if key == 'fPatchTol':
        #    if cls.riOpts[key].CurrentValue <= 1e-9:
        #        print "Invalid input for scale value."
        #        cls.riOpts[key].CurrentValue = cls.values[key]

        if key in cls.riOpts:
            cls.values[key] = cls.riOpts[key].CurrentValue
        elif key in cls.listValues:
            cls.values[key] = idxList
        else:
            return

        sc.sticky[cls.stickyKeys[key]] = cls.values[key]


def getInput():
    """
    Get edges or (wire) curves with optional input.
    """

    go = ri.Custom.GetObject()

    go.SetCommandPrompt("Select 2, 3, or 4 open curves")

    go.GeometryFilter = rd.ObjectType.Curve
    go.GeometryAttributeFilter = go.GeometryAttributeFilter.OpenCurve
    #    go.GeometryAttributeFilter.SurfaceBoundaryEdge |
    #    go.GeometryAttributeFilter.WireCurve)

    go.EnableUnselectObjectsOnExit(False) # Do not unselect object when an option selected, a number is entered, etc.

    idxs_Opt = {}

    while True:
        go.ClearCommandOptions()

        idxs_Opt.clear()

        def addOption(key): idxs_Opt[key] = Opts.addOption(go, key)

        addOption('iContinuity')
        addOption('bEcho')
        addOption('bDebug')

        sc.doc.Views.Redraw()

        res = go.GetMultiple(minimumNumber=2, maximumNumber=4)

        if res == ri.GetResult.Cancel:
            go.Dispose()
            return

        if res == ri.GetResult.Object:
            objrefs = go.Objects()
            go.Dispose()
            return (
                objrefs,
                Opts.values['iContinuity'],
                Opts.values['bEcho'],
                Opts.values['bDebug'],
                )

        # An option was selected.
        go.DeselectAllBeforePostSelect = False # So objects won't be deselected on repeats of While loop.
        go.EnablePreSelect(False, ignoreUnacceptablePreselectedObjects=True)
        go.EnableClearObjectsOnEntry(False) # Do not clear objects in go on repeats of While loop.

        for key in idxs_Opt:
            if go.Option().Index == idxs_Opt[key]:
                Opts.setValue(key, go.Option().CurrentListOptionIndex)
                break


def getFormattedDistance(fDistance):
    if fDistance is None: return "(No deviation provided)"
    if fDistance < 0.001:
        return "{:.2e}".format(fDistance)
    else:
        return "{:.{}f}".format(fDistance, sc.doc.ModelDistanceDisplayPrecision)


def getR3CurveOfGeom(geom):
    if isinstance(geom, rg.BrepTrim):
        return geom.Edge.DuplicateCurve()
    else:
        return geom


def getIsoCurveOfSide(isoStatus, srf):

    if isoStatus == W:
        return srf.IsoCurve(direction=1, constantParameter=srf.Domain(0).T0)
    elif isoStatus == S:
        return srf.IsoCurve(direction=0, constantParameter=srf.Domain(1).T0)
    elif isoStatus == E:
        return srf.IsoCurve(direction=1, constantParameter=srf.Domain(0).T1)
    elif isoStatus == N:
        return srf.IsoCurve(direction=0, constantParameter=srf.Domain(1).T1)
    raise ValueError(
        "Isostatus {} not allowed.  Needs to be West, South, East, or North".format(
            isoStatus))


def getCurveOfNurbs(geom):
    if geom[1] is None:
        c = geom[0]
        if not isinstance(c, rg.NurbsCurve):
            raise ValueError("Not a NurbsCurve.")
        return c

    if isinstance(geom[1], rg.Plane):
        if not isinstance(geom[0], rg.NurbsCurve):
            raise ValueError("Not a NurbsCurve.")
        return geom[0]
    else:
        c = getIsoCurveOfSide(*geom)
        if not isinstance(c, rg.NurbsCurve):
            raise ValueError("Not a NurbsCurve.")
        return c


def isPointAtEitherCrvEnd(pt, cA):
    """
    """

    tol = 2.0 * sc.doc.ModelAbsoluteTolerance
    if cA.PointAtStart.DistanceTo(pt) <= tol:
        return True
    if cA.PointAtEnd.DistanceTo(pt) <= tol:
        return True

    return False


def doCrvsFormAClosedLoop(cs):
    """
    """

    found = [[False, False] for i in range(len(cs))]
    tol = 2.0 * sc.doc.ModelAbsoluteTolerance

    for iA in range(len(cs)-1):
        cA = cs[iA]
        if not found[iA][0]:
            ptA = cA.PointAtStart
            for iB in range(1+iA,len(cs)):
                cB = cs[iB]
                if ptA.DistanceTo(cB.PointAtStart) <= tol:
                    #print "Start of [{}] matches start of [{}].".format(iA, iB)
                    found[iA][0] = True
                    found[iB][0] = True
                    if cA.PointAtEnd.DistanceTo(cB.PointAtEnd) <= tol:
                        raise Exception("2 curves completely overlap.")
                    break
                if ptA.DistanceTo(cB.PointAtEnd) <= tol:
                    #print "Start of [{}] matches end of [{}].".format(iA, iB)
                    found[iA][0] = True
                    found[iB][1] = True
                    if cA.PointAtEnd.DistanceTo(cB.PointAtStart) <= tol:
                        raise Exception("2 curves completely overlap.")
                    break
            else:
                #for c in cs: sc.doc.Objects.AddCurve(c)
                return False

        if not found[iA][1]:
            ptA = cA.PointAtEnd
            for iB in range(1+iA,len(cs)):
                cB = cs[iB]
                if ptA.DistanceTo(cB.PointAtStart) <= tol:
                    #print "End of [{}] matches start of [{}].".format(iA, iB)
                    found[iA][1] = True
                    found[iB][0] = True
                    if cA.PointAtEnd.DistanceTo(cB.PointAtEnd) <= tol:
                        raise Exception("2 curves completely overlap.")
                    break
                if ptA.DistanceTo(cB.PointAtEnd) <= tol:
                    #print "End of [{}] matches end of [{}].".format(iA, iB)
                    found[iA][1] = True
                    found[iB][1] = True
                    if cA.PointAtEnd.DistanceTo(cB.PointAtStart) <= tol:
                        raise Exception("2 curves completely overlap.")
                    break
            else:
                #for c in cs: sc.doc.Objects.AddCurve(c)
                return False

    return True


def endsMatchWithOtherEnds(cs, tol=None):

    if tol is None: tol = 2.0 * sc.doc.ModelAbsoluteTolerance

    bEndEndMatches = [[False, False] for i in range(len(cs))]

    for iA in range(len(cs)-1):
        cA = cs[iA]
        if bEndEndMatches[iA][0] and bEndEndMatches[iA][1]: continue

        if not bEndEndMatches[iA][0]:
            ptA = cA.PointAtStart
            for iB in range(iA+1,len(cs)):
                cB = cs[iB]
                if ptA.DistanceTo(cB.PointAtStart) <= tol:
                    #print "Start of [{}] matches start of [{}].".format(iA, iB)
                    bEndEndMatches[iA][0] = True
                    bEndEndMatches[iB][0] = True
                    if cA.PointAtEnd.DistanceTo(cB.PointAtEnd) <= tol:
                        raise Exception("2 curves completely overlap.")
                    break # out of iB loop.
                if ptA.DistanceTo(cB.PointAtEnd) <= tol:
                    #print "Start of [{}] matches end of [{}].".format(iA, iB)
                    bEndEndMatches[iA][0] = True
                    bEndEndMatches[iB][1] = True
                    if cA.PointAtEnd.DistanceTo(cB.PointAtStart) <= tol:
                        raise Exception("2 curves completely overlap.")
                    break # out of iB loop.

        if not bEndEndMatches[iA][1]:
            ptA = cA.PointAtEnd
            for iB in range(iA+1,len(cs)):
                cB = cs[iB]
                if ptA.DistanceTo(cB.PointAtStart) <= tol:
                    #print "End of [{}] matches start of [{}].".format(iA, iB)
                    bEndEndMatches[iA][1] = True
                    bEndEndMatches[iB][0] = True
                    if cA.PointAtEnd.DistanceTo(cB.PointAtEnd) <= tol:
                        raise Exception("2 curves completely overlap.")
                    break # out of iB loop.
                if ptA.DistanceTo(cB.PointAtEnd) <= tol:
                    #print "End of [{}] matches end of [{}].".format(iA, iB)
                    bEndEndMatches[iA][1] = True
                    bEndEndMatches[iB][1] = True
                    if cA.PointAtEnd.DistanceTo(cB.PointAtStart) <= tol:
                        raise Exception("2 curves completely overlap.")
                    break # out of iB loop.

    return bEndEndMatches


def getPtsAtNonEndIntersects(cs, tol=None):

    if tol is None: tol = 2.0 * sc.doc.ModelAbsoluteTolerance

    bEndEndMatches = endsMatchWithOtherEnds(cs)

    pts_Xs = [[] for i in range(len(cs))]

    for iA in range(len(cs)-1):
        if bEndEndMatches[iA][0] and bEndEndMatches[iA][1]:
            continue
        cA = cs[iA]
        for iB in range(1+iA, len(cs)):
            if bEndEndMatches[iB][0] and bEndEndMatches[iB][1]:
                continue
            cB = cs[iB]
            crvinters = rg.Intersect.Intersection.CurveCurve(
                cA, cB, tolerance=tol, overlapTolerance=0.0)
            if crvinters.Count == 0: continue # to next curve.
            for crvinter in crvinters:
                pt = crvinter.PointA
                if not isPointAtEitherCrvEnd(pt, cA):
                    pts_Xs[iA].append(pt)
                if not isPointAtEitherCrvEnd(pt, cB):
                    pts_Xs[iB].append(pt)

    return pts_Xs


def getTrimInterval_NurbsSrf(iso, ns, pt_End_ToRemain, pts_Xs):
    """
    """
    if pt_End_ToRemain is None:
        uvs_DomainEndsToKeep = None
    else:
        b, u, v = ns.ClosestPoint(pt_End_ToRemain)
        if not b:
            raise Exception("ClosestPoint failed.")

        if (abs(u - ns.Domain(0).T0) <= 1e-6) and (abs(v - ns.Domain(1).T0) <= 1e-6):
            uvs_DomainEndsToKeep = (u,v)
        elif (abs(u - ns.Domain(0).T1) <= 1e-6) and (abs(v - ns.Domain(1).T0) <= 1e-6):
            uvs_DomainEndsToKeep = (u,v)
        elif (abs(u - ns.Domain(0).T1) <= 1e-6) and (abs(v - ns.Domain(1).T1) <= 1e-6):
            uvs_DomainEndsToKeep = (u,v)
        elif (abs(u - ns.Domain(0).T0) <= 1e-6) and (abs(v - ns.Domain(1).T1) <= 1e-6):
            uvs_DomainEndsToKeep = (u,v)
        else:
            uvs_DomainEndsToKeep = None

    #sEval = "t_DomainEndToKeep"; print sEval+':',eval(sEval)

    uvs_InsideDomain = []
    for pt in pts_Xs:
        b, u, v = ns.ClosestPoint(pt)
        if not b:
            raise Exception("ClosestPoint failed.")
        uvs_InsideDomain.append((u,v))


    if iso in (N, S):
        us = [uv[0] for uv in uvs_InsideDomain]
        if uvs_DomainEndsToKeep is not None:
            us += [uvs_DomainEndsToKeep[0]]
        us.sort()
        return rg.Interval(us[0], us[1]), ns.Domain(1)
    else:
        vs = [uv[1] for uv in uvs_InsideDomain]
        if uvs_DomainEndsToKeep is not None:
            vs += [uvs_DomainEndsToKeep[1]]
        vs.sort()
        return ns.Domain(0), rg.Interval(vs[0], vs[1])


def getTrimInterval_NurbsCrv(nc, pt_End_ToRemain, pts_Xs):
    """
    """

    b, t = nc.ClosestPoint(pt_End_ToRemain)
    if not b:
        raise Exception("ClosestPoint failed.")

    if (abs(t - nc.Domain.T0) <= 1e-6):
        t_DomainEndToKeep = t
    elif (abs(t - nc.Domain.T1) <= 1e-6):
        t_DomainEndToKeep = t

    ts_InsideDomain = []
    for pt in pts_Xs:
        b, t = nc.ClosestPoint(pt)
        if not b:
            raise Exception("ClosestPoint failed.")
        ts_InsideDomain.append(t)


    ts = ts_InsideDomain
    if pt_End_ToRemain:
        ts += [t_DomainEndToKeep]

    ts.sort()

    return rg.Interval(ts[0], ts[1])


def trimNurbsAtCrvIntersections(ngs_In, tol=None):
    """
    At this time, only len(ngs_In) == 4.
    """

    cs = [getCurveOfNurbs(geom) for geom in ngs_In]
    if tol is None: tol = 2.0 * sc.doc.ModelAbsoluteTolerance

    bEndEndMatches = endsMatchWithOtherEnds(cs, tol)

    bTrims_NeedIntersect = [not (bEndEndMatches[i][0] and bEndEndMatches[i][1]) for i in range(len(ngs_In))]

    if not any(bTrims_NeedIntersect):
        raise Exception("No trims can be split to create good input for surface.")

    if sum(bTrims_NeedIntersect) == 1:
        #print bTrims_NeedIntersect
        raise Exception("Only 1 trim to split.")

    pts_Xs = getPtsAtNonEndIntersects(cs, tol)

    #print found
    #print pts_Xs

    ngs_Out = []

    for i in range(len(ngs_In)):
        ng_In = ngs_In[i]
        if len(pts_Xs[i]) == 0:
            ngs_Out.append(ng_In)
            continue

        pt_End_ToRemain = None
        if bEndEndMatches[i][0]:
            pt_End_ToRemain = cs[i].PointAtStart
        if bEndEndMatches[i][1]:
            if pt_End_ToRemain is not None:
                sEval = "len(pts_Ends)"
                raise ValueError("{}: {}".format(sEval, eval(sEval)))

            pt_End_ToRemain = cs[i].PointAtEnd


        if isinstance(ng_In[1], rg.NurbsSurface):
            iso, ns = ng_In
            intvls_Trim = getTrimInterval_NurbsSrf(iso, ns, pt_End_ToRemain, pts_Xs[i])
            ns_Trimmed = ns.Trim(intvls_Trim[0], intvls_Trim[1])
            ngs_Out.append((iso, ns_Trimmed))
        else:
            nc = ng_In[0]
            intvl_Trim = getTrimInterval_NurbsCrv(nc, pt_End_ToRemain, pts_Xs[i])
            nc_Trimmed = nc.Trim(intvl_Trim[0], intvl_Trim[1])
            ngs_Out.append((nc_Trimmed, ng_In[1]))


    return ngs_Out


def createAlignedRefGeom_PerStart(geom_R_In, ns_M, side_M):
    """
    Variation to a function in spb_Match1 in that
    the start locations of the edges are used to determine whether
    NS or NC needs to be reversed.

    Returns either
        NurbsSurface with parameterizations aligned with ns_M along side_M or
        NurbsCurve with parameterization aligned with ns_M
    """


    def areSrfParamsAlignedAlongMatchingSides(ns_A, side_A, ns_B, side_B):
        """
        """

        def getSideEndPtsInAscendingSrfParam(ns, side):
            cps = ns.Points
            pt_SW = cps.GetControlPoint(           0,            0).Location
            pt_SE = cps.GetControlPoint(cps.CountU-1,            0).Location
            pt_NE = cps.GetControlPoint(cps.CountU-1, cps.CountV-1).Location
            pt_NW = cps.GetControlPoint(           0, cps.CountV-1).Location
            if side == E:
                return pt_SE, pt_NE
            elif side == W:
                return pt_SW, pt_NW
            elif side == S:
                return pt_SW, pt_SE
            elif side == N:
                return pt_NW, pt_NE
            else:
                raise ValueError("{} is not a valid side.".format(side))


        pts_A = getSideEndPtsInAscendingSrfParam(ns_A, side_A)
        pts_B = getSideEndPtsInAscendingSrfParam(ns_B, side_B)

        #for pt in pts_A: sc.doc.Objects.AddPoint(pt)
        #for pt in pts_B: sc.doc.Objects.AddPoint(pt)

        tol = 2.0 * sc.doc.ModelAbsoluteTolerance

        if (
            (pts_A[0].DistanceTo(pts_B[0]) < tol) and 
            (pts_A[1].DistanceTo(pts_B[1]) < tol)
        ):
            return True

        if (
            (pts_A[0].DistanceTo(pts_B[1]) < tol) and 
            (pts_A[1].DistanceTo(pts_B[0]) < tol)
        ):
            return False

        #sc.doc.Objects.AddSurface(ns_A)
        #sc.doc.Objects.AddSurface(ns_B)
        #sc.doc.Views.Redraw()


        raise Exception("The 2 sides' positions do not match.")


    def createAlignedRefSrfs(side_M, ns_R, side_R):
        """
        Notes:
        ns_R.Reverse(int direction, bool inPlace)
        Transpose(bool inPlace)
        """

        if side_M == side_R:
            pass
        elif side_M in (S, N) and side_R in (S, N):
            ns_R.Reverse(1, True)
        elif side_M in (W, E) and side_R in (W, E):
            ns_R.Reverse(0, True)
        else:
            ns_R.Transpose(True)

            if side_M == S and side_R == E:
                ns_R.Reverse(1, True)
            elif side_M == S and side_R == W:
                pass
            elif side_M == E and side_R == N:
                pass
            elif side_M == E and side_R == S:
                ns_R.Reverse(0, True)
            elif side_M == N and side_R == W:
                ns_R.Reverse(1, True)
            elif side_M == N and side_R == E:
                pass
            elif side_M == W and side_R == S:
                pass
            elif side_M == W and side_R == N:
                ns_R.Reverse(0, True)
            else:
                raise Exception("What happened?")

        if (not areSrfParamsAlignedAlongMatchingSides(
            ns_M, side_M, ns_R, side_M)
        ):
            ns_R.Reverse(0 if side_M in (S, N) else 1, True)


    if isinstance(geom_R_In[1], rg.NurbsSurface):
        side_R, ns_R = geom_R_In
        rc = createAlignedRefSrfs(side_M, ns_R, side_R)
        return ns_R # Don't bother returning IsoStatus since R now matches that of M.

    # Reference alignment is per Edge.
    c_M = getIsoCurveOfSide(side_M, ns_M)
    c_R = geom_R_In[0]
    if not rg.Curve.DoDirectionsMatch(c_M, c_R):
        c_R.Reverse()

    return c_R # Don't bother returning tuple since none is needed for NS.


def transferUniqueKnotVector(nurbsA, nurbsB, sideA=None, sideB=None, paramTol=None):
    """
    Union the knot vectors of nurbsA and nurbsB and apply to nurbsB (modify reference).

    nurbsA and nurbsB: Any combination of NurbsSurface or NurbsCurve.
    Return True if nsB was modified.
    """

    if paramTol is None: paramTol = Rhino.RhinoMath.ZeroTolerance


    def knotCount(geom, side):
        if isinstance(geom, rg.NurbsSurface):
            if side in (S, N): return geom.KnotsU.Count
            else: return geom.KnotsV.Count
        else:
            return geom.Knots.Count

    def degree(geom, side):
        if isinstance(geom, rg.NurbsSurface):
            iDir = 0 if side in (S, N) else 1
            return geom.Degree(iDir)
        else:
            return geom.Degree

    def knotMultiplicity(geom, side, iK):
        if isinstance(geom, rg.NurbsSurface):
            if side in (S, N): return geom.KnotsU.KnotMultiplicity(iK)
            else: return geom.KnotsV.KnotMultiplicity(iK)
        else:
            return geom.Knots.KnotMultiplicity(iK)

    def getKnot(geom, side, iK):
        if isinstance(geom, rg.NurbsSurface):
            if side in (S, N): return geom.KnotsU[iK]
            else: return geom.KnotsV[iK]
        else:
            return geom.Knots[iK]

    def insertKnot(geom, side, t, m):
        if isinstance(geom, rg.NurbsSurface):
            if side in (S, N): return geom.KnotsU.InsertKnot(t, m)
            else: return geom.KnotsV.InsertKnot(t, m)
        else:
            return geom.Knots.InsertKnot(t, m)


    knotCt_In = knotCount(nurbsB, sideB)

    iK = degree(nurbsA, sideA)
    while iK < knotCount(nurbsA, sideA)-degree(nurbsA, sideA):
        sc.escape_test()
        t_A = getKnot(nurbsA, sideA, iK)
        m = knotMultiplicity(nurbsA, sideA, iK)
        if abs(t_A - getKnot(nurbsB, sideB, iK)) > paramTol:
            insertKnot(nurbsB, sideB, t_A, m)
        iK += m

    return knotCount(nurbsB, sideB) > knotCt_In


def createSurface(rhCrvs_In, **kwargs):
    """
    rhCrvs_In: Can be ObjRefs or Geometry of any Curve, including BrepEdge.
    Returns NurbsSurface on success.
    """


    def getOpt(key): return kwargs[key] if key in kwargs else Opts.values[key]

    iContinuity = getOpt('iContinuity')
    bEcho = getOpt('bEcho')
    bDebug = getOpt('bDebug')


    if len(rhCrvs_In) not in (2,3,4):
        return None, "{} curves provided.  Need 2, 3, or 4.".format(len(rhCrvs_In))


    tol0 = Rhino.RhinoMath.ZeroTolerance


    def getGeomFromIn(In):
        """ Returns BrepTrim, (wire) Curve, or None """

        def getMostUsefulGeomFromEdge(edge):
            if len(edge.TrimIndices()) == 1:
                trim = edge.Brep.Trims[edge.TrimIndices()[0]]
                if trim.IsoStatus == rg.IsoStatus.None:
                    trim.Brep.Faces.ShrinkFaces()
                return trim
            print "Edge with more than one face selected." \
                "  Only G0 continuity will result for it."
            return edge.DuplicateCurve()

        def getMostUsefulGeomFromCrv(geom):
            if isinstance(geom, rg.BrepEdge):
                return getMostUsefulGeomFromEdge(geom)
            if isinstance(geom, rg.Curve):
                return geom
            raise ValueError(
                "{} provided instead of something from which a curve can derive.".format(
                    geom.GetType().Name))

        def getMostUsefulGeomFromObjRef(objref):
            """ Returns BrepTrim, (wire) Curve, or None """

            if not isinstance(objref, rd.ObjRef): return

            trim = objref.Trim()

            if trim is not None:
                if trim.IsoStatus == rg.IsoStatus.None:
                    trim.Brep.Faces.ShrinkFaces()
                return trim

            edge = objref.Edge()

            if edge is not None:
                return getMostUsefulGeomFromEdge(edge)

            crv = objref.Curve()
            if crv is not None:
                return crv

            raise ValueError("{} provided instead of something from which a curve can derive.".format(
                    objref.Geometry().GetType().Name))

        if isinstance(In, rd.ObjRef):
            return getMostUsefulGeomFromObjRef(In)

        if isinstance(In, rg.Curve):
            return getMostUsefulGeomFromCrv(In)

        raise ValueError("{} passed as input.".format(In.GetType().Name))

    geoms_In = [getGeomFromIn(In) for In in rhCrvs_In]


    def areAllBrepTrimsUnique(geoms):
        isos = []
        srfs = []

        for geom in geoms:
            if not isinstance(geom, rg.BrepTrim): continue

            trim = geom

            iso = trim.IsoStatus
            if iso not in (W,S,E,N): continue

            srf = trim.Face.UnderlyingSurface()

            for iso_InList, srf_InList in zip(isos, srfs):
                if rg.GeometryBase.GeometryReferenceEquals(srf_InList, srf):
                    if iso_InList == iso:
                        return False

            isos.append(iso)
            srfs.append(srf)

        return True

    if not areAllBrepTrimsUnique(geoms_In):
        return None, "2 edges of the same isostatus of the same surface were selected."


    cs_In = [getR3CurveOfGeom(g) for g in geoms_In]


    def doAnyCrvsCompletelyOverlap(cs):
        """
        """

        found = [[False, False] for i in range(len(cs))]
        tol = 2.0 * sc.doc.ModelAbsoluteTolerance

        for iA in range(len(cs)-1):
            cA = cs[iA]
            if not found[iA][0]:
                ptA = cA.PointAtStart
                for iB in range(1+iA, len(cs)):
                    cB = cs[iB]
                    if ptA.DistanceTo(cB.PointAtStart) <= tol:
                        found[iA][0] = True
                        found[iB][0] = True
                        if cA.PointAtEnd.DistanceTo(cB.PointAtEnd) <= tol:
                            return True
                        break
                    if ptA.DistanceTo(cB.PointAtEnd) <= tol:
                        found[iA][0] = True
                        found[iB][1] = True
                        if cA.PointAtEnd.DistanceTo(cB.PointAtStart) <= tol:
                            return True
                        break

            if not found[iA][1]:
                ptA = cA.PointAtEnd
                for iB in range(1+iA, len(cs)):
                    cB = cs[iB]
                    if ptA.DistanceTo(cB.PointAtStart) <= tol:
                        found[iA][1] = True
                        found[iB][0] = True
                        if cA.PointAtEnd.DistanceTo(cB.PointAtEnd) <= tol:
                            return True
                        break
                    if ptA.DistanceTo(cB.PointAtEnd) <= tol:
                        found[iA][1] = True
                        found[iB][1] = True
                        if cA.PointAtEnd.DistanceTo(cB.PointAtStart) <= tol:
                            return True
                        break

        return False

    if doAnyCrvsCompletelyOverlap(cs_In):
        return None, "Some edges/trims completely overlap."

    geoms_Nurbs = []
    for geom in geoms_In:
        geom_Nurbs = spb.getShrunkNurbsSrfFromGeom(geom, bUseUnderlyingIsoCrvs=False)
        if geom_Nurbs is None:
            geom_Nurbs = spb.getNurbsGeomFromGeom(geom, iContinuity, bEcho)
            if geom_Nurbs is None:
                if bEcho:
                    print "NURBS geometry could not be obtained from input."
                return
        geoms_Nurbs.append(geom_Nurbs)


    cs_R = [getCurveOfNurbs(geom) for geom in geoms_Nurbs]


    ns_M_Start = None

    # TODO: Clean this if block.
    if len(rhCrvs_In) == 4:
        if not doCrvsFormAClosedLoop(cs_R):
            s = "No matching endpoint of some curves found, "
            geoms_Nurbs = trimNurbsAtCrvIntersections(geoms_Nurbs)
            cs_R = [getCurveOfNurbs(geom) for geom in geoms_Nurbs]
            if not doCrvsFormAClosedLoop(cs_R):
                print s + "and attempt ot split some trims at intersections failed."
                return
            print s + "but attempt ot split some trims at intersections succeeded."
    elif len(rhCrvs_In) == 3:
        if any(getPtsAtNonEndIntersects(cs_R)):
            print "Input contains non-end-to-end intersections.  Split curves and rerun sctipt."
            return

        pCrvs = rg.Curve.JoinCurves(cs_R, sc.doc.ModelAbsoluteTolerance)

        if len(pCrvs) == 1 and pCrvs[0].IsClosed:
            print "3-curve input can join into a closed loop.  This is not (yet) supported."
            return

        if len(pCrvs) > 1:
            if len(pCrvs) == 1 and pCrvs[0].IsClosed:
                print "Input forms a Single, closed loop."
                return

            s = "Curve do not form a single open loop, "
            geoms_Nurbs = trimNurbsAtCrvIntersections(geoms_Nurbs)
            cs_R = [getCurveOfNurbs(geom) for geom in geoms_Nurbs]

            pCrvs = rg.Curve.JoinCurves(cs_R, sc.doc.ModelAbsoluteTolerance)

            if len(pCrvs) != 1:
                print s + "and attempt ot split some trims at intersections failed."
                return
            print s + "but attempt ot split some trims at intersections succeeded."

        joined = rg.Curve.JoinCurves(cs_R, sc.doc.ModelAbsoluteTolerance)
        polyCrv = joined[0]
        nc_ToAdd = rg.LineCurve(polyCrv.PointAtStart, polyCrv.PointAtEnd).ToNurbsCurve()
        cs_R.append(nc_ToAdd)
        geoms_Nurbs.append((nc_ToAdd, None))
    elif len(rhCrvs_In) == 2:
        if any(getPtsAtNonEndIntersects(cs_R)):
            print "Input contains non-end-to-end intersections.  Split curves and rerun sctipt."
            return

        pCrvs = rg.Curve.JoinCurves(cs_R, sc.doc.ModelAbsoluteTolerance)

        if pCrvs[0].IsClosed:
            print "2-curve input can join into a closed loop.  This is not (yet) supported."
            return

        if len(pCrvs) == 1:
            pCrv = pCrvs[0]
            pt = pCrv.PointAt(pCrv.SegmentDomain(0).T1)
            if cs_R[0].PointAtEnd.DistanceTo(pt) <= sc.doc.ModelAbsoluteTolerance:
                cs_R[0].Reverse()
            if cs_R[1].PointAtEnd.DistanceTo(pt) <= sc.doc.ModelAbsoluteTolerance:
                cs_R[1].Reverse()

            sumsrf = rg.SumSurface.Create(cs_R[0], cs_R[1])
            if bDebug: spb.addGeoms(sumsrf)

            ns_M_Start = sumsrf.ToNurbsSurface()
            #spb.addGeoms(sumsrf)

            cs_C = [getIsoCurveOfSide(s, ns_M_Start) for s in (W,S,E,N)]

            idx_R_per_Ms_WSEN = spb.findMatchingCurveByEndPoints(
                cs_C, cs_R, bEcho)
            if idx_R_per_Ms_WSEN is None: return

            for side, idx in zip((W,S,E,N), idx_R_per_Ms_WSEN):
                if idx is None:
                    nc_ToAdd = getIsoCurveOfSide(side, ns_M_Start)
                    cs_R.append(nc_ToAdd)
                    geoms_Nurbs.append((nc_ToAdd, None))

        elif len(pCrvs) == 2:
            # Create blend surface.  Can optionally do this using Brep.CreateFromLoft.
            if rg.Curve.DoDirectionsMatch(cs_R[0], cs_R[1]):
                pts = (
                    (cs_R[0].PointAtStart, cs_R[1].PointAtStart),
                    (cs_R[0].PointAtEnd, cs_R[1].PointAtEnd))
            else:
                pts = (
                    (cs_R[0].PointAtStart, cs_R[1].PointAtEnd),
                    (cs_R[0].PointAtEnd, cs_R[1].PointAtStart))
            for i in 0,1:
                nc_ToAdd = rg.LineCurve(pts[i][0], pts[i][1]).ToNurbsCurve()
                nc_ToAdd.IncreaseDegree((iContinuity+1)*2-1)
                cs_R.append(nc_ToAdd)
                geoms_Nurbs.append((nc_ToAdd, None))


    if ns_M_Start is None:
        rgB_Res = rg.Brep.CreateEdgeSurface(cs_R)
        if rgB_Res is None:
            return None, "CreateEdgeSurface returned None."


        if rgB_Res.Surfaces.Count != 1:
            sc.doc.Objects.AddBrep(rgB_Res)
            return None, "Polyface brep with no continuity matching added to document."

        ns_M_Start = rgB_Res.Surfaces[0]


    if ns_M_Start.IsRational:
        spb.makeNonRational(ns_M_Start)


    # Brep.CreateEdgeSurface (always?) produces a surface with the
    # largest degree in chain of surfaces in each direction but
    # may have missing knots and point distributions.
    # Both it and the surfaces from which the reference trims are taken
    # need to match along the relevant direction.
    # Create 4 modified surfaces to use for remainder of script.


    # Match references to the Coons.
    cs_C = [getIsoCurveOfSide(s, ns_M_Start) for s in (W,S,E,N)]

    idx_R_per_Ms_WSEN = spb.findMatchingCurveByEndPoints(
        cs_C, cs_R, bEcho)
    if idx_R_per_Ms_WSEN is None: return

    if len(rhCrvs_In) == 3:
        # Last item in geoms_Nurbs_SideMatched is the added NC.
        sides_Loose = (W,S,E,N)[idx_R_per_Ms_WSEN.index(3)],
        if bDebug: print "Sides of EdgeSrf with open input: {}".format(sides_Loose)
    elif len(rhCrvs_In) == 2:
        # Last 2 items in geoms_Nurbs_SideMatched are the added NCs.
        sides_Loose = (
            (W,S,E,N)[idx_R_per_Ms_WSEN.index(2)],
            (W,S,E,N)[idx_R_per_Ms_WSEN.index(3)])
        if bDebug: print "Sides of EdgeSrf with open input: {}".format(sides_Loose)
    else:
        sides_Loose = ()


    geoms_Nurbs_SideMatched = [geoms_Nurbs[i] for i in idx_R_per_Ms_WSEN]

    # Align each reference to the Coons by side and parameterization.
    # This results in opposite u x v directions between each Refernce and the Coons.
    geoms_Nurbs_AR = {}

    for i, side in enumerate((W,S,E,N)):
        rc = createAlignedRefGeom_PerStart(
            geoms_Nurbs_SideMatched[i], ns_M_Start, side)
        if rc is None: return
        geoms_Nurbs_AR[side] = rc

    # Match reference curve or surface degrees to Coons patch surface in relevant direction.

    bResults = []
    for side in W,S,E,N:
        bResult = spb.transferHigherDegree(
            ns_M_Start, geoms_Nurbs_AR[side], side, side)
    bResults.append(bResult)
    if bDebug: print bResults

    #for ns in geoms_ARs:
    #    sc.doc.Objects.AddSurface(ns)
    #sc.doc.Views.Redraw()


    # Match reference srf relevant domains to Coons patch srf.
    bResults = []
    for side in W,S,E,N:
        bResult = spb.transferDomain(
            ns_M_Start, geoms_Nurbs_AR[side], side, side)
    bResults.append(bResult)
    if bDebug: print bResults

    #for ns in geoms_ARs:
    #    sc.doc.Objects.AddSurface(ns)
    #sc.doc.Views.Redraw()



    # Match reference srf knot vectors to Coons patch srf.

    # First, transfer unique knots to Coons so that the latter can contain all unqiue knots
    # to transfer to reference surfaces.
    [transferUniqueKnotVector(geoms_Nurbs_AR[side], ns_M_Start, side, side) for side in (S,N,W,E)]

    #sc.doc.Objects.AddSurface(ns_M_Start)#; sc.doc.Views.Redraw(); return


    # Back to reference surfaces.
    [transferUniqueKnotVector(ns_M_Start, geoms_Nurbs_AR[side], side, side) for side in (S,N,W,E)]

    #for ns in geoms_ARs:
    #    sc.doc.Objects.AddSurface(ns)
    #sc.doc.Views.Redraw(); return


    if iContinuity == 0:
        return ns_M_Start

    if ns_M_Start.Points.CountU < 4 and ns_M_Start.Points.CountV < 4:
        if bEcho: print "Not enough points to modify continuity."
        return ns_M_Start

    if bEcho:
        iCt = sum(isinstance(geoms_Nurbs_AR[key], rg.NurbsSurface) for key in geoms_Nurbs_AR)
        print "Modifying continuity of up to {} sides.".format(iCt)



    ptsM_PreG1 = [cp.Location for cp in ns_M_Start.Points]

    pts_G1_corners = {}
    pts_G2_corners = {}

    ns_WIP = ns_M_Start.Duplicate()


    def areThereEnoughPtsToModify(side, iG):
        if side in (W,E):
            ct = ns_M_Start.Points.CountU
            if ct < 2*(iG+1):
                if side == W:
                    print "Not enough CPs to modify to G{} along U.".format(iG)
                return False
        else:
            ct = ns_M_Start.Points.CountV
            if ct < 2*(iG+1):
                if side == S:
                    print "Not enough CPs to modify to G{} along V.".format(iG)
                return False
        return True


    def getUvIdxFromNsPoint1dIdx(ns, idxFlat):
        return idxFlat // ns.Points.CountV, idxFlat % ns.Points.CountV


    for side in W,S,E,N:

        if not areThereEnoughPtsToModify(side, 1):
            continue

        geom_AR = geoms_Nurbs_AR[side]

        if isinstance(geom_AR, rg.Curve):
            continue # Since surface is already G0.

        ns_R = geom_AR

        #sc.doc.Objects.AddSurface(ns_R)

        idxPts = {} # Key is tuple(str('M' or 'R'), int(G continuity))
        for i in range(iContinuity+1):
            idxPts['M',i] = spb.getPtRowIndicesPerG(ns_M_Start, side, i)
            idxPts['R',i] = spb.getPtRowIndicesPerG(ns_R, side, i)

        iRowLn = len(idxPts['M',0])


        def setModifyRowEnd(side, sides_loose):
            if side in (W,E):
                bModifyRowEnd_T0 = S in sides_loose
                bModifyRowEnd_T1 = N in sides_Loose
            else:
                bModifyRowEnd_T0 = W in sides_loose
                bModifyRowEnd_T1 = E in sides_Loose
            return bModifyRowEnd_T0, bModifyRowEnd_T1


        rc = setModifyRowEnd(side, sides_Loose)
        bModifyRowEnd_T0, bModifyRowEnd_T1 = rc

        # G0 row is already set.

        ns_M_G1 = spb.setContinuity_G1(
            ns_M_BeforeAnyMatching=ns_M_Start,
            ns_M_In=ns_WIP,
            side_M=side,
            nurbs_R=ns_R,
            side_R=side,
            bModifyRowEnd_T0=bModifyRowEnd_T0,
            bModifyRowEnd_T1=bModifyRowEnd_T1,
            )

        if ns_M_G1 is None:
            continue

        #if side == S:
        #    sc.doc.Objects.AddSurface(ns_M_G1); sc.doc.Views.Redraw(); return

        # Update.
        ns_WIP.Dispose()
        ns_WIP = ns_M_G1
        pts_WIP = [cp.Location for cp in ns_WIP.Points]

        # Record the G1 point from each 2nd from end for later average.
        if iRowLn >= 4:
            for i in (1, iRowLn-2):
                iM1 = idxPts['M',1][i]
                if iM1 in pts_G1_corners.keys():
                    pts_G1_corners[iM1].append(pts_WIP[iM1])
                else:
                    pts_G1_corners[iM1] = [pts_WIP[iM1]]
        #sc.doc.Objects.AddPoint(pts_WIP[idxPts['M',1][1]])
        #sc.doc.Objects.AddPoint(pts_WIP[idxPts['M',1][len(idxPts['M',1])-2]])

        if iContinuity == 2 and areThereEnoughPtsToModify(side, 2):
            ns_M_G2 = spb.setContinuity_G2(
                ns_M_BeforeAnyMatching=ns_M_Start,
                ns_M_In=ns_WIP,
                side_M=side,
                nurbs_R=ns_R,
                side_R=side,
                bModifyRowEnd_T0=bModifyRowEnd_T0,
                bModifyRowEnd_T1=bModifyRowEnd_T1,
                bDebug=bDebug,
                bAddRefs=True,
                )

            # Update.
            ns_WIP.Dispose()
            ns_WIP = ns_M_G2
            pts_WIP = [cp.Location for cp in ns_M_G2.Points]

            # Record the G2 point from each 2nd from end for later average.
            if iRowLn >= 6:
                for i in (2, iRowLn-3):
                    iM2 = idxPts['M',2][i]
                    if iM2 in pts_G2_corners.keys():
                        pts_G2_corners[iM2].append(pts_WIP[iM2])
                    else:
                        pts_G2_corners[iM2] = [pts_WIP[iM2]]
                #sc.doc.Objects.AddPoint(pts_WIP[idxPts['M',1][1]])
                #sc.doc.Objects.AddPoint(pts_WIP[idxPts['M',1][len(idxPts['M',1])-2]])

                # Return the 3rd G2 points on each end to their original positions.
                for idx in (2, iRowLn-3):
                    iM2 = idxPts['M',2][idx]
                    iUT_A, iVT_A = getUvIdxFromNsPoint1dIdx(ns_M_Start, iM2)
                    ns_WIP.Points.SetPoint(
                        iUT_A, iVT_A, ptsM_PreG1[iM2],
                        weight=ns_M_Start.Points.GetWeight(iUT_A, iVT_A))


        # Return the 2nd G1 points on each end to their original positions.
        if iRowLn >= 4:
            for idx in (1, iRowLn-2):
                iM1 = idxPts['M',1][idx]
                iUT_A, iVT_A = getUvIdxFromNsPoint1dIdx(ns_M_Start, iM1)
                ns_WIP.Points.SetPoint(
                    iUT_A, iVT_A, ptsM_PreG1[iM1],
                    weight=ns_M_Start.Points.GetWeight(iUT_A, iVT_A))


    # Average the corner G1 locations.
    for iM1 in pts_G1_corners:
        iUT_A, iVT_A = getUvIdxFromNsPoint1dIdx(ns_M_Start, iM1)
        if len(pts_G1_corners[iM1]) == 1:
            ns_WIP.Points.SetPoint(
                iUT_A, iVT_A, pts_G1_corners[iM1][0],
                weight=ns_M_Start.Points.GetWeight(iUT_A, iVT_A))
        elif len(pts_G1_corners[iM1]) == 2:
            pt_Avg = (pts_G1_corners[iM1][0] + pts_G1_corners[iM1][1]) / 2.0
            ns_WIP.Points.SetPoint(
                iUT_A, iVT_A, pt_Avg,
                weight=ns_M_Start.Points.GetWeight(iUT_A, iVT_A))
        else:
            raise Exception(
                "{} corner points recorded at index {}.".format(
                    len(pts_G1_corners[iM1]), iM1))

    # Average the corner G2 locations.
    for iM2 in pts_G2_corners:
        iUT_A, iVT_A = getUvIdxFromNsPoint1dIdx(ns_M_Start, iM2)
        if len(pts_G2_corners[iM2]) == 1:
            ns_WIP.Points.SetPoint(
                iUT_A, iVT_A, pts_G2_corners[iM2][0],
                weight=ns_M_Start.Points.GetWeight(iUT_A, iVT_A))
        elif len(pts_G2_corners[iM2]) == 2:
            pt_Avg = (pts_G2_corners[iM2][0] + pts_G2_corners[iM2][1]) / 2.0
            ns_WIP.Points.SetPoint(
                iUT_A, iVT_A, pt_Avg,
                weight=ns_M_Start.Points.GetWeight(iUT_A, iVT_A))
        else:
            raise Exception(
                "{} corner points recorded at index {}.".format(
                    len(pts_G2_corners[iM2]), iM2))



    #pts_WIP = [cp.Location for cp in ns_M_Start.Points]

    return ns_WIP


def main():
    
    rc = getInput()
    if rc is None: return

    (
        objrefs_Crvs,
        iContinuity,
        bEcho,
        bDebug,
        ) = rc

    Rhino.RhinoApp.CommandPrompt = "Working ..."

    if not bDebug: sc.doc.Views.RedrawEnabled = False


    rc = createSurface(
        rhCrvs_In=objrefs_Crvs,
        iContinuity=iContinuity,
        bEcho=bEcho,
        bDebug=bDebug,
        )
    if rc is None:
        sc.doc.Views.RedrawEnabled = True
        return
    if isinstance(rc, rg.NurbsSurface):
        ns_Res = rc
    elif isinstance(rc, tuple):
        ns_Res, sLog = rc
        print sLog
        if ns_Res is None:
            sc.doc.Views.RedrawEnabled = True
            return
    else:
        raise ValueError("Bad output: {}".format(rc))

    if ns_Res.IsRational:
        print "New surface is rational.  Check continuity."

    gB_Res = sc.doc.Objects.AddSurface(ns_Res)
    if gB_Res == gB_Res.Empty:
        print "Brep could not be added to the document."
    #else:
    #    print gB_Res
    sc.doc.Views.Redraw()
    sc.doc.Views.RedrawEnabled = True


if __name__ == '__main__': main()
    #try: main()
    #except Exception as ex:
    #    print "{0}: {1}".format(type(ex).__name__, "\n".join(ex.args))
