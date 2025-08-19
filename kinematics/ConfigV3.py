"""
Created 5 Sep 2018
@author: mem
configuration for V3 chair
"""

"""
This file defines the coordinates of the upper (base) and lower (platform) attachment points
Note: because the chair is an inverted stewart platform, the base is the plane defined by the upper attachment points

The coordinate frame used follow ROS conventions, positive X is forward, positive Y us left, positive Z is up,
positive yaw is CCW from the persepective of person on the chair.

The origin is the center of the circle intersecting the attachment points. The X axis is the line through the origin running
 from back to front (X values increase moving from back to front). The Y axis passes through the origin with values increasing
 to the left.

The attachment coordinates can be specified explicitly or with vectors from the origin to
 each attachment point. Uncomment the desired method of entry.

You only need enter values for the left side, the other side is a mirror image and is calculated for you
"""

import math

class PlatformConfig(object):
    PLATFORM_NAME = "Chair v3"
    GEOMETRY_PERFECT = False  # set to false for wide front spacing
    GEOMETRY_WIDE = not GEOMETRY_PERFECT


    PLATFORM_UNLOADED_WEIGHT = 25  # weight of moving platform without 'passenger' in killograms
    DEFAULT_PAYLOAD_WEIGHT = 65    # weight of 'passenger'
    TOTAL_WEIGHT = PLATFORM_UNLOADED_WEIGHT + DEFAULT_PAYLOAD_WEIGHT
    MAX_MUSCLE_LEN = 800           # length of muscle at minimum pressure
    MIN_MUSCLE_LEN = MAX_MUSCLE_LEN * .75 # length of muscle at maximum pressure
    FIXED_LEN = 200                #  length of fixing hardware
    MIN_ACTUATOR_LEN = MIN_MUSCLE_LEN + FIXED_LEN  # total min actuator distance including fixing hardware
    MAX_ACTUATOR_LEN = MAX_MUSCLE_LEN + FIXED_LEN # total max actuator distance including fixing hardware
    MAX_ACTUATOR_RANGE = MAX_ACTUATOR_LEN - MIN_ACTUATOR_LEN
    MID_ACTUATOR_LEN = MIN_ACTUATOR_LEN + (MAX_ACTUATOR_RANGE/2)

    DISABLED_LEN = MAX_ACTUATOR_LEN *.95
    PROPPING_LEN = MAX_ACTUATOR_LEN *.92  # length to enable fitting of stairs
    HAS_PISTON = False  # platform does not have piston actuated prop


    #  uncomment this to enter hard coded coordinates

    #  input x and y coordinates with origin as center of the base plate
    #  the z value should be zero for both base and platform
    #  only -Y side is needed as other side is symmetrical (see figure)

    if GEOMETRY_PERFECT:
        GEOMETRY_TYPE = "Using geometry values with ideally spaced front attachment points"
        BASE_POS = [  # upper attachment point
                    [373.8, -517.7, 0.],  # left front (facing platform)
                    [258.7, -585.4, 0],
                    [-636.0, -71.4, 0]
                   ]

        PLATFORM_POS = [    # lower (movable) attachment point
                         [636.3, -68.6, 0], # left front (facing platform)
                        [-256.2, -586.5, 0],
                        [-377.6, -516.7, 0]
                   ]
                   
        PLATFORM_MID_HEIGHT = -715

    elif GEOMETRY_WIDE:
        GEOMETRY_TYPE = "Using geometry values based on 34cm spaced front attachment points"
        BASE_POS = [   
                    [379.8, -515.1, 0],
                    [258.7, -585.4, 0],
                    [-636.0, -71.4, 0]
                  ]
        PLATFORM_POS = [
                        [617.0, -170.0, 0],
                        [-256.2, -586.5, 0],
                        [-377.6, -516.7, 0]
                       ]
        PLATFORM_MID_HEIGHT = -715


    else:
        GEOMETRY_TYPE = "Geometry type not defined"
                   


    #  the max movement in a single DOF
    PLATFORM_1DOF_LIMITS = [100, 122, 140, math.radians(15), math.radians(20), math.radians(12)]

    # limits at extremes of movement
    PLATFORM_6DOF_LIMITS = [80, 80, 80, math.radians(12), math.radians(12), math.radians(10)]


