"""
telemetry_logger.py

Writes telemetry data to CSV file
"""

import time

class TelemetryLogger(object):
    def __init__(self, is_enabled): 
       self.is_enabled = is_enabled
       print("telemetry logger enable state is", is_enabled)

    def start(self):
        if self.is_enabled:
            timestr = time.strftime("%m%d-%H%M")
            fname = "telemetry-" + timestr + ".csv"
            print("Opening log file:", fname)
            self.outfile = open(fname,"w")
            self.outfile.write("time,surge,sway,heave,roll,pitch,yaw\n")
    
    def stop(self):
        if self.is_enabled:
            self.outfile.close()
            print("Closing log file")

    def write(self, data):
        if self.is_enabled:
            self.outfile.write(data)

if __name__ == "__main__":

    t = TelemetryLogger(True)
    t.start()
    t.write("0,1,2,3,4,5,6\n")
    t.write("1,2,3,4,5,6,7\n")
    t.stop()
