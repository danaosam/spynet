__author__ = 'adeb'

import numpy as np

from scipy.ndimage.interpolation import rotate


def create_pick_patch(config_ini):
    """
    Factory function to create the objects responsible for picking the patches
    """
    how_patch = config_ini.pick_patch["how"]
    patch_width = config_ini.pick_patch["patch_width"]
    if how_patch == "3D":
        pick_patch = PickPatch3DSimple(patch_width)
    elif how_patch == "2Dortho":
        axis = config_ini.pick_patch["axis"]
        pick_patch = PickPatchParallelOrthogonal(patch_width, axis)
    elif how_patch == "2DorthoRotated":
        axis = config_ini.pick_patch["axis"]
        max_degree_rotation = config_ini.pick_patch["max_degree_rotation"]
        pick_patch = PickPatchSlightlyRotated(patch_width, axis, max_degree_rotation)
    elif how_patch == "ultimate":
        pick_patch = PickUltimate(patch_width)
    else:
        print "error in pick_patch"
        return

    return pick_patch


class PickInput():
    """
    Manage the selection and extraction of patches in an mri image from their central voxels
    """
    def __init__(self, n_features):
        self.n_features = n_features

    def pick(self, vx, mri, label):
        raise NotImplementedError


class PickXYZ(PickInput):
    def __init__(self):
        PickInput.__init__(self, 3)

    def pick(self, vx, mri, label):
        idx_patch = 0
        patch = vx
        return patch, idx_patch


class PickPatch2D(PickInput):
    def __init__(self, patch_width):
        PickInput.__init__(self, patch_width**2)
        self.patch_width = patch_width

    def pick(self, vx, mri, label):
        n_vx = vx.shape[0]
        idx_patch = np.zeros((n_vx, self.n_features), dtype=int)
        patch = np.zeros((n_vx, self.n_features), dtype=np.float32)
        self.pick_virtual2d(patch, idx_patch, vx, mri, label)
        return patch, idx_patch

    def pick_virtual2d(self, patch, idx_patch, vx, mri, label):
        raise NotImplementedError


class PickPatchParallelOrthogonal(PickPatch2D):
    """
    Pick a 2D patch centered on the voxels. No rotation
    """
    def __init__(self, patch_width, orthogonal_axis):
        PickPatch2D.__init__(self, patch_width)
        self.orhtogonal_axis = orthogonal_axis

    def pick_virtual2d(self, patch, idx_patch, vx, mri, label):
        dims = mri.shape
        radius = self.patch_width / 2

        def find_limits_along_axis(axis):
            s1_inf = vx[:, axis] - radius
            s1_sup = vx[:, axis] + radius + 1
            s2_inf = np.zeros(s1_inf.shape, dtype=s1_inf.dtype)
            s2_sup = self.patch_width * np.ones(s1_inf.shape, dtype=s1_inf.dtype)

            # Too low
            s1_too_low = s1_inf < 0
            s2_inf[s1_too_low] = -s1_inf[s1_too_low]
            s1_inf[s1_too_low] = 0

            # Too high
            s1_too_high = s1_sup > dims[axis]
            s2_sup[s1_too_high] = self.patch_width - (s1_sup[s1_too_high] - dims[axis])
            s1_sup[s1_too_high] = dims[axis]

            assert (s1_sup - s1_inf == s2_sup - s2_inf).all()

            return s1_inf, s1_sup, s2_inf, s2_sup

        parallel_axis = range(3)
        del parallel_axis[self.orhtogonal_axis]
        s1_inf_0, s1_sup_0, s2_inf_0, s2_sup_0 = find_limits_along_axis(parallel_axis[0])
        s1_inf_1, s1_sup_1, s2_inf_1, s2_sup_1 = find_limits_along_axis(parallel_axis[1])

        for i in xrange(idx_patch.shape[0]):

            s1 = [0]*3
            s1[self.orhtogonal_axis] = vx[i, self.orhtogonal_axis]
            s1[parallel_axis[0]] = slice(s1_inf_0[i], s1_sup_0[i])
            s1[parallel_axis[1]] = slice(s1_inf_1[i], s1_sup_1[i])

            s2 = [0]*2
            s2[0] = slice(s2_inf_0[i], s2_sup_0[i])
            s2[1] = slice(s2_inf_1[i], s2_sup_1[i])

            patch_temp = np.zeros((self.patch_width,)*2)
            patch_temp[s2[0], s2[1]] = mri[s1[0], s1[1], s1[2]]
            patch[i, :] = patch_temp.ravel()


class PickPatchSlightlyRotated(PickPatch2D):
    """
    Pick a 2D patch centered on the voxels. Brains are slightly rotated.
    """
    def __init__(self, patch_width, orhtogonal_axis, max_degree_rotation):
        PickPatch2D.__init__(self, patch_width)
        self.orthogonal_axis = orhtogonal_axis
        self.max_degree_rotation = max_degree_rotation

    def pick_virtual2d(self, patch, idx_patch, vx, mri, label):
        dims = mri.shape
        radius = self.patch_width / 2

        # The following part is verifying that we are not leaving the cube
        def crop(j, voxel):
            s1_inf = voxel[j] - radius
            s1_sup = voxel[j] + radius + 1
            s2_inf = 0
            s2_sup = self.patch_width
            if s1_inf < 0:
                s2_inf = -s1_inf
                s1_inf = 0
            if s1_sup > dims[j]:
                s2_sup = self.patch_width - (s1_sup - dims[j])
                s1_sup = dims[j]

            assert s1_sup - s1_inf == s2_sup - s2_inf

            return slice(s1_inf, s1_sup), slice(s2_inf, s2_sup)

        for i in xrange(idx_patch.shape[0]):
            vx_cur = vx[i]
            ls_slice1 = []
            ls_slice2 = []
            cube = np.zeros((self.patch_width,)*3)
            for ax in range(3):
                s1, s2 = crop(ax, vx_cur)
                ls_slice1.append(s1)
                ls_slice2.append(s2)

            cube[ls_slice2[0], ls_slice2[1], ls_slice2[2]] = mri[ls_slice1[0], ls_slice1[1], ls_slice1[2]]
            cube = rotate(cube, np.random.uniform(-self.max_degree_rotation, -self.max_degree_rotation), axes=(0, 1))
            cube = rotate(cube, np.random.uniform(-self.max_degree_rotation, -self.max_degree_rotation), axes=(1, 2))
            cube = rotate(cube, np.random.uniform(-self.max_degree_rotation, -self.max_degree_rotation), axes=(2, 0))

            central_vx_cube = np.array(cube.shape)/2
            li = central_vx_cube - radius
            ls = central_vx_cube + radius + 1
            li[self.orthogonal_axis] = central_vx_cube[self.orthogonal_axis]
            ls[self.orthogonal_axis] = central_vx_cube[self.orthogonal_axis]+1

            patch[i] = cube[li[0]:ls[0], li[1]:ls[1], li[2]:ls[2]].ravel()


class PickPatch3D(PickInput):
    def __init__(self, patch_width):
        PickInput.__init__(self, patch_width**3)
        self.patch_width = patch_width

    def pick(self, vx, mri, label):
        n_vx = vx.shape[0]
        idx_patch = np.zeros((n_vx, self.n_features), dtype=int)
        patch = np.zeros((n_vx, self.n_features), dtype=np.float32)
        self.pick_virtual3d(patch, idx_patch, vx, mri, label)
        return patch, idx_patch

    def pick_virtual3d(self, patch, idx_patch, vx, mri, label):
        raise NotImplementedError


class PickPatch3DSimple(PickPatch3D):
    """
    Pick 3D patches centered on the voxels. No rotation
    """
    def __init__(self, patch_width):
        PickPatch3D.__init__(self, patch_width)

    def pick_virtual3d(self, patch, idx_patch, vx, mri, label):
        dims = mri.shape
        radius = self.patch_width / 2

        def crop(j, voxel):
            v = np.arange(voxel[j] - radius, voxel[j] + radius + 1)
            v[v < 0] = 0
            v[v >= dims[j]] = dims[j]-1
            return v

        for i in xrange(idx_patch.shape[0]):
            vx_cur = vx[i]
            v_axis = []
            for ax in range(3):
                v_axis.append(crop(ax, vx_cur))

            x, y, z = np.meshgrid(v_axis[0], v_axis[1], v_axis[2])
            idx_patch[i] = np.ravel_multi_index((x.ravel(), y.ravel(), z.ravel()), dims)
            patch[i] = mri[x, y, z].ravel()


class PickUltimate(PickInput):
    """
    An input is composed of three orthogonal patches and the three coordinates of the central voxel.
    """
    def __init__(self, patch_width):
        PickInput.__init__(self, 3 * patch_width**2)
        self.patch_width = patch_width
        self.pick_axis0 = PickPatchParallelOrthogonal(patch_width, 0)
        self.pick_axis1 = PickPatchParallelOrthogonal(patch_width, 1)
        self.pick_axis2 = PickPatchParallelOrthogonal(patch_width, 2)

    def pick(self, vx, mri, label):
        n_vx = vx.shape[0]
        idx_patch = np.zeros((n_vx, self.n_features), dtype=int)
        patch = np.zeros((n_vx, self.n_features), dtype=np.float32)

        temp = self.patch_width**2
        s0 = slice(0, temp)
        patch[:,s0], idx_patch[:,s0] = self.pick_axis0.pick(vx, mri, label)
        s1 = slice(1*temp, 2*temp)
        patch[:,s1], idx_patch[:,s1] = self.pick_axis1.pick(vx, mri, label)
        s2 = slice(2*temp, 3*temp)
        patch[:,s2], idx_patch[:,s2] = self.pick_axis2.pick(vx, mri, label)

        return patch, idx_patch
