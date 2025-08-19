"""
RideState is the high level similated coaster state that is displayed on the GUI

ConnectStatus is the status of connection between the contoller and NoLimits

"""

class RideState:
    DEACTIVATED, READY_FOR_DISPATCH, RUNNING, PAUSED, EMERGENCY_STOPPED, RESETTING = list(range(6))

RideStateStr = ("Deactivated", "Ready for dispatch", "Running", "Paused", "Emergency Stopped", "Resetting")

class TrainState:
    NOT_PLAY_MODE, STOPPED_AT_STATION, CAN_FOR_DISPATCH, RUNNING, PAUSED = list(range(5))
    
class SystemStatus(object):
    def __init__(self): 
        self._is_pc_connected = False
        self._is_nl2_connected = False
        self._is_in_play_mode = False 
        self._is_ready_to_dispatch = False 
        self._is_moving = False
        self._is_paused = False

    def _refresh(self):
        # if rpc update the remote client with the updated status
        pass

    @property
    def is_pc_connected(self):
        return self._is_pc_connected
    @is_pc_connected.setter
    def is_pc_connected(self, value):
        self._is_pc_connected = value
        self._refresh()

    @property
    def is_nl2_connected(self):
        return self._is_nl2_connected
    @is_nl2_connected.setter
    def is_nl2_connected(self, value):
        self._is_nl2_connected = value
        self._refresh()

    @property
    def is_in_play_mode(self):
        return self._is_in_play_mode
    @is_in_play_mode.setter
    def is_in_play_mode(self, value):
        self._is_in_play_mode = value
        self._refresh()

    @property
    def is_moving(self):
        return self._is_moving
    @is_moving.setter
    def is_moving(self, value):
        self._is_moving = value
        self._refresh()

    @property
    def is_paused(self):
        return self._is_paused
    @is_paused.setter
    def is_paused(self, value):
        self._is_paused = value
        self._refresh()

    @property
    def is_ready_to_dispatch(self):
        return self._is_ready_to_dispatch
    @is_ready_to_dispatch.setter
    def is_ready_to_dispatch(self, value):
        self._is_ready_to_dispatch = value
        self._refresh()
"""
      def update_pc_connected(self, state):
          is_pc_connected = state 
          print "in update pc state", state
          self._refresh()
      def update_nl2_connected(self, state):
          () = state
          self._refresh()
      def ()(self, state):
          is_in_play_mode = state
          self._refresh()
      def update_ready_to_dispatch(self, state):
          is_ready_to_dispatch = state 
          self._refresh()
      def update_is_moving(self, state):
          is_moving = state
          self._refresh()
      def update_is_paused(self, state):
          is_paused = state
          self._refresh()
"""

"""
class ConnectStatus():
   is_pc_connected = 0x1
   () = 0x2
   is_in_play_mode = 0x4
   is_ready_to_dispatch = 0x8
"""

if __name__ == "__main__":

    s = SystemStatus()
    print(s.is_pc_connected)
    s.is_pc_connected = True
    print(s.is_pc_connected)
