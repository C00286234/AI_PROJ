###############################################################################
#	Author:			Sebastien Parent-Charette (support@robotshop.com)
#	Version:		1.0.0
#	Licence:		LGPL-3.0 (GNU Lesser General Public License version 3)
#	
#	Desscription:	Basic example of reading values from the LSS.
#	Mar 2026:		Dr Oisin Cawley
#					Code to show how to access the LEDs.
#
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

# Create an LSS object
myLSS1 = lss.LSS(1)
myLSS2 = lss.LSS(2)
myLSS3 = lss.LSS(3)
myLSS4 = lss.LSS(4)
myLSS5 = lss.LSS(5)

print("Setting all LEDs to GREEN...")
myLSS1.setColorLED(2)
time.sleep(.5)
myLSS2.setColorLED(2)
time.sleep(.5)
myLSS3.setColorLED(2)
time.sleep(.5)
myLSS4.setColorLED(2)
time.sleep(.5)
myLSS5.setColorLED(2)
time.sleep(.5)
print("Run through a range for all LEDs...")
# Wait 1 second
time.sleep(1)
for x in range(8):
    myLSS1.setColorLED(x)
    myLSS2.setColorLED(x)
    myLSS3.setColorLED(x)
    myLSS4.setColorLED(x)
    myLSS5.setColorLED(x)
    time.sleep(.5)
print("Turning all LEDs OFF...")
# Wait 1 second
time.sleep(1)
myLSS1.setColorLED(0)
time.sleep(.5)
myLSS2.setColorLED(0)
time.sleep(.5)
myLSS3.setColorLED(0)
time.sleep(.5)
myLSS4.setColorLED(0)
time.sleep(.5)
myLSS5.setColorLED(0)
print("DONE.")

### EOF #######################################################################
