###############################################################################
#	Author:			Sebastien Parent-Charette (support@robotshop.com)
#	Version:		1.0.0
#	Licence:		LGPL-3.0 (GNU Lesser General Public License version 3)
#	
#	Desscription:	An example using the LSS and the Python module.
#	Mar 2026:		Dr Oisin Cawley
#					Code to show the ranges of the different servos.
###############################################################################

# Import required liraries
import time
import serial

# Import LSS library
import lss
import lss_const as lssc

# Constants
#CST_LSS_Port = "/dev/ttyUSB0"		# For Linux/Unix platforms
CST_LSS_Port = "COM7"				# For windows platforms
CST_LSS_Baud = lssc.LSS_DefaultBaud

# Create and open a serial port
lss.initBus(CST_LSS_Port, CST_LSS_Baud)
print("LSS connection done")
print(lss.LSS.bus)

# Create an LSS object
myLSS2 = lss.LSS(2)
myLSS3 = lss.LSS(3)
myLSS4 = lss.LSS(4)
print("LSS object2: " + str(myLSS2.servoID))
print("LSS object3: " + str(myLSS3.getPosition()))
print("LSS object4: " + str(myLSS4.getPosition()))

# Initialize LSS to position 0.0 deg
myLSS2.move(-900)
myLSS3.move(850)
myLSS4.move(300)
print("Move done.")
time.sleep(1)

#The following for the Gripper range (actuator 5)
#for i in range(0,850):
#    print("Trying position: " + str(i))
#    myLSS.move(i*-1)
#    time.sleep(.03) #0.03 seems to be  the minmum delay to get smooth movement on the Gripper

#The following for actuator 2 (bottom arm)
# -900 is about parallel with ground
# lss4Position = int(myLSS4.getPosition())
# for i in range(-900,-450):
    # print("Trying position: " + str(i))
    # myLSS2.move(i)
    # time.sleep(.03) #0.03 seems to be  the minmum delay to get smooth movement on the Gripper
    # lss4Position = lss4Position-1
    # myLSS4.move(lss4Position)

#The following for actuator 3 (top arm)
# 850 is parallel to bottom arm, 0 is straight up
# for i in range(-850,0):
    # print("Trying position: " + str(i))
    # myLSS3.move(i*-1)
    # time.sleep(.03) #0.03 seems to be  the minmum delay to get smooth movement on the Gripper

#The following for actuator 4
# About -800 is straight up, 0 is straight out from arm
lss4Position = int(myLSS4.getPosition())
for i in range(lss4Position, -800, -1):
    print("Trying position: " + str(i))
    myLSS4.move(i)
    time.sleep(.03) #0.03 seems to be  the minmum delay to get smooth movement on the Gripper


# Destroy objects
del myLSS2
del myLSS3
del myLSS4

# Destroy the bus
lss.closeBus()

### EOF #######################################################################
