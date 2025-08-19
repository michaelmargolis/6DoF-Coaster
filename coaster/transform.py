# transform.py
# input is nl2 telemetry msg, output is: surge, sway, heave, roll, pitch, yaw

from __future__ import division, print_function

import math
from .my_quaternion import Quaternion


class Transform(object):
    def __init__(self, gain=0.6):
        self.prev_yaw = None
        self.gain = float(gain)  # adjusts level of outputs
        self.lift_height = 32.0  # max height of lift in meters

    def reset_xform(self):
        # call this when train is dispatched (todo test if needed)
        self.prev_yaw = None

    def set_lift_height(self, height):
        # max height of lift in meters
        try:
            self.lift_height = float(height)
        except Exception:
            # keep previous value if bad input
            pass

    def get_transform(self, tm_msg):
        """returns [surge, sway, heave, roll, pitch, yaw_rate] from NL2 telemetry"""
        quat = Quaternion(tm_msg.quatX, tm_msg.quatY, tm_msg.quatZ, tm_msg.quatW)

        roll = self.gain * (quat.toRollFromYUp() / math.pi)
        pitch = self.gain * (-quat.toPitchFromYUp())
        yaw_rate = self.gain * self.process_yaw(-quat.toYawFromYUp())

        # y from coaster is vertical. z forward, x side
        if tm_msg.posY > self.lift_height:
            # track max height seen so far
            try:
                self.lift_height = float(tm_msg.posY)
            except Exception:
                pass

        denom = self.lift_height if self.lift_height else 1.0  # avoid /0
        heave = ((tm_msg.posY * 2.0) / denom) - 1.0

        # signed square-root mapping for surge/sway
        gz = tm_msg.gForceZ
        if gz >= 0:
            surge = math.sqrt(gz)
        else:
            surge = -math.sqrt(-gz)

        gx = tm_msg.gForceX
        if gx >= 0:
            sway = math.sqrt(gx)
        else:
            sway = -math.sqrt(-gx)

        return [surge, sway, heave, roll, pitch, yaw_rate]

    def process_yaw(self, yaw):
        if self.prev_yaw is not None:
            # handle crossings between 0 and 2*pi
            dy = yaw - self.prev_yaw
            if dy > math.pi:
                yaw_rate = (self.prev_yaw - yaw) + (2.0 * math.pi)
            elif dy < -math.pi:
                yaw_rate = (self.prev_yaw - yaw) - (2.0 * math.pi)
            else:
                yaw_rate = self.prev_yaw - yaw
        else:
            yaw_rate = 0.0

        self.prev_yaw = yaw

        # limit dynamic range
        if yaw_rate > math.pi:
            yaw_rate = math.pi
        elif yaw_rate < -math.pi:
            yaw_rate = -math.pi

        yaw_rate = yaw_rate / 2.0
        if yaw_rate >= 0.0:
            yaw_rate = math.sqrt(yaw_rate)
        else:
            yaw_rate = -math.sqrt(-yaw_rate)

        return yaw_rate
