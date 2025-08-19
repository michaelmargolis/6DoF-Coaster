""" kinematics

Copyright Michael Margolis, Middlesex University 2019; see LICENSE for software rights.

finds actuator lengths L such that the platform is in position defined by
    request as:  [surge, sway, heave, roll, pitch yaw]

"""

import math
import copy
import numpy as np


class Kinematics(object):
    def __init__(self):
        pass

    def set_geometry(self, base_pos, platform_pos, platform_mid_height):
        self.base_pos = base_pos
        self.platform_pos = platform_pos
        self.platform_mid_height = platform_mid_height

    """ 
    returns numpy array of actuator lengths for given request orientation
    """
    def inverse_kinematics(self, request):
        # print "kinematics request: ", request,
        adj_req = copy.copy(request)
        
        adj_req[2] = self.platform_mid_height + adj_req[2]  # z axis displacement value is offset from center 
        if self.platform_mid_height < 0: # is fixed platform above moving platform
            adj_req[2] = -adj_req[2]  # invert z value on inverted stewart platform

        # print "z = ", request[2], "adjusted z =:", adj_req[2], "mid height",self.platform_mid_height
        a = np.array(adj_req).transpose()
        roll = a[3]  # positive roll is right side down
        pitch = -a[4]  # positive pitch is nose down
        yaw = a[5]  # positive yaw is CCW
        #  Translate platform coordinates into base coordinate system
        #  Calculate rotation matrix elements
        cos_roll = math.cos(roll)
        sin_roll = math.sin(roll)
        cos_pitch = math.cos(pitch)
        sin_pitch = math.sin(pitch)
        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)
        #  calculate rotation matrix
        #  Note that it is a 3-2-1 rotation matrix
        Rzyx = np.array([[cos_yaw*cos_pitch, cos_yaw*sin_pitch*sin_roll - sin_yaw*cos_roll, cos_yaw*sin_pitch*cos_roll + sin_yaw*sin_roll],
                         [sin_yaw*cos_pitch, sin_yaw*sin_pitch*sin_roll + cos_yaw*cos_roll, sin_yaw*sin_pitch*cos_roll - cos_yaw*sin_roll],
                         [-sin_pitch, cos_pitch*sin_roll, cos_pitch*cos_roll]])
        #  platform actuators points with respect to the base coordinate system
        xbar = a[0:3] - self.base_pos

        #  orientation of platform wrt base

        uvw = np.zeros(self.platform_pos.shape)
        for i in range(6):
            uvw[i, :] = np.dot(Rzyx, self.platform_pos[i, :])

        #  leg lengths are the length of the vector (xbar+uvw)
        L = np.sum(np.square(xbar + uvw), 1)
        return np.sqrt(L)

if __name__ == "__main__":
    from ConfigV3 import *
    from kinematics import Kinematics
    import plot_config
    
    cfg = PlatformConfig()    
    k = Kinematics()

    if len(cfg.BASE_POS) == 3:
        #  if only three vertices, reflect around X axis to generate right side coordinates
        otherSide = copy.deepcopy(cfg.BASE_POS[::-1])  # order reversed
        for inner in otherSide:
            inner[1] = -inner[1]   # negate Y values
        cfg.BASE_POS.extend(otherSide)

        otherSide = copy.deepcopy(cfg.PLATFORM_POS[::-1])  # order reversed
        for inner in otherSide:
            inner[1] = -inner[1]   # negate Y values
        cfg.PLATFORM_POS.extend(otherSide)

    base_pos = np.array(cfg.BASE_POS)
    platform_pos = np.array(cfg.PLATFORM_POS)
    print("base\n",base_pos)
    print("platform\n",platform_pos)

    
    #  uncomment the following to plot the array coordinates
    # plot_config.plot(base_pos, platform_pos, cfg.PLATFORM_MID_HEIGHT, cfg.PLATFORM_NAME )
    
    k.set_geometry( base_pos, platform_pos, cfg.PLATFORM_MID_HEIGHT)
#  calculates inverse kinematics and prints actuator lenghts
    while True:
        request = input("enter orientation on command line as: surge, sway, heave, roll, pitch yaw ")
        if request == "":
            exit()
        request = list(map( float, request.split(',') ))
        if len(request) == 6:
            actuator_lengths = k.inverse_kinematics(request)
            print(actuator_lengths.astype(int))
        else:
           print("expected 3 translation values in mm and 3 rotations values in radians")
    