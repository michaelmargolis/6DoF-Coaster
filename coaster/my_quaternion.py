# Helper class to decode rotation quaternion into pitch/yaw/roll
from __future__ import division, print_function, absolute_import

import numpy as np

class Quaternion(object):
    def __init__(self, x, y, z, w):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.w = float(w)

    def __repr__(self):
        # Native str in both Py2/3
        return "%.5f,%.5f,%.5f,%.5f" % (self.x, self.y, self.z, self.w)

    def toPitchFromYUp(self):
        vx = 2.0 * (self.x * self.y + self.w * self.y)
        vy = 2.0 * (self.w * self.x - self.y * self.z)
        vz = 1.0 - 2.0 * (self.x * self.x + self.y * self.y)
        return np.arctan2(vy, np.sqrt(vx * vx + vz * vz))

    def toYawFromYUp(self):
        return np.arctan2(
            2.0 * (self.x * self.y + self.w * self.y),
            1.0 - 2.0 * (self.x * self.x + self.y * self.y)
        )

    def toRollFromYUp(self):
        return np.arctan2(
            2.0 * (self.x * self.y + self.w * self.z),
            1.0 - 2.0 * (self.x * self.x + self.z * self.z)
        )

    def toYawRate(self):
        raise NotImplementedError("toYawRate requires angular velocity calculation not provided here.")
