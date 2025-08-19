# platform_config.py

"""
Uncomment one of the above to select the client
"""
client_selection = 'coaster.nl2_coaster'  # for latest NoLimits2
#  client_selection = 'coaster.coaster_client'  # for NoLimits2
#  client_selection = 'space_coaster.space_coaster_player'
#  client_selection = 'flight_sim.flight_sim_client'
#  client_selection = 'client.platform_input_tk'   #  tkinter gui
#  client_selection = 'client.platform_input'    #  keyboard
#  client_selection = 'client.platform_input_simple_UDP' #  UDP
#  client_selection = 'client.platform_input_threadedUDP' #  threaded UDP'
#  client_selection = 'client.elite'

"""
Uncomment one of the following to select the platform configuration
"""
#  platform_selection = 'ConfigV1'
#  platform_selection = 'ConfigV2'
platform_selection = 'kinematics.ConfigV3'
# platform_selection = 'configNextgen'
# platform_selection = 'kinematics.cfg_SuspendedChair'


"""
The following default values should be changed only if you know what you are doing
"""
FRAME_RATE_SECS = .05

Festo_IP_ADDR = '192.168.0.10'
Festo_Port = 995

# set the following to None if using auto discovery of NoLimits, otherwise set to static address of NoLimits PC
HARD_CODED_IP = None  # default addr is '192.168.0.4'
# note the default addr for optional computer running control software is 192.168.0.2

SHOW_CHAIR_IMAGES = False  # set True to display orientation of chair in GUI (Requires Python PIL lib)

USE_PI_SWITCHES = True # uses hardware switches on Pi if set true, ignored if controller is not running on Pi

# see serial_remote.py module to change baud rate and driver name for serial remote control
