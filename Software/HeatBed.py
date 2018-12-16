#!/usr/bin/env python

import RPi.GPIO as GPIO     # Import the GPIO Library
import smbus                # Required to read the MPU6250
import LM75                 # Only required if the LM75 is used
import math
import ZeroSeg.led as led   # Required to support the ZeroSeg pHAT
import time
import random
from datetime import datetime
import os

# Power management registers for the MPU6250
power_mgmt_1 = 0x6b
power_mgmt_2 = 0x6c

# Set the GPIO modes
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

#Setup the ZeroSeg buttons...
sw_L = 17
sw_R = 26
GPIO.setup(sw_L, GPIO.IN)
GPIO.setup(sw_R, GPIO.IN)

# Setup the pin to control the PSU and turn it off
# PSU control pin is active low / False to turn on, High / True to turn off
pinPSUctrl = 15
PSUctrlOn = False # Set PSUctrlOn to False if pulling the control pin to GND turns the supply on
                  # Set PSUctrlOn to True if pulling the control pin to 3.3V turns the supply on
GPIO.setup(pinPSUctrl, GPIO.OUT)
# Make sure that the supply off at start-up
GPIO.output(pinPSUctrl,not PSUctrlOn) 

sensor = LM75.LM75()

bus = smbus.SMBus(1) # or bus = smbus.SMBus(1) for Revision 2 boards
address = 0x68       # This is the I2C address value for the MPU6250 read via the i2cdetect command

# Wake the MPU6050 up as it starts in sleep mode
#bus.write_byte_data(address, power_mgmt_1, 0)

# Read a byte from an address over the I2C interface
def read_byte(adr):
    return bus.read_byte_data(address, adr)

# Read a 16-bit word from an address over the I2C interface
def read_word(adr):
    high = bus.read_byte_data(address, adr)
    low = bus.read_byte_data(address, adr+1)
    val = (high << 8) + low
    return val

# Read a word over I2C and format the result
def read_word_2c(adr):
    val = read_word(adr)
    if (val >= 0x8000):
        return -((65535 - val) + 1)
    else:
        return val

# Read the temperature from the MPU6250
def read_temp_mpu6050():
    temp_raw = read_word_2c(0x41)
    temp = temp_raw/340.0+36.53
    return temp

# Read the temperature from the LM75
def read_temp_lm75():
    temp_raw = sensor.getTemp()
    temp = temp_raw
    if temp > 128:
        temp = temp - 256
    return temp

# Function for turning the heatbed power off
def Heater_TurnOn():
    GPIO.output(pinPSUctrl,PSUctrlOn)

# Function for turning the heatbed power on
def Heater_TurnOff():
    GPIO.output(pinPSUctrl,not PSUctrlOn)

#device = led.sevensegment()
device = led.sevensegment(cascaded=2)

# ------------------------------------------------------------------------------
# Main temperature control function
def tempctrl():
    
    GPIO.output(pinPSUctrl,not PSUctrlOn) 
    Heater_On = False
    BedRunning = True
    
    # Set the initial temperature...
    # It's advisable to start-up with a low target temperature so that
    # on power up the heater is off by default until the user sets the
    # temperature. This helps to ensure that a power cut doesn't leave the
    # heater on when the power returns
    BedTemp_Target = 5 # Low temperature 
    #BedTemp_Target = 60 # Good for PLA
    #BedTemp_Target = 95 # Good for ABS
    
    # Set some hysterisis so that the control to the heater doesn't flicker
    TempHisterisis = 1
    TempGoodHisterisis = 1.5
    
    # Initialise average measurements so they are non-zero for first three measurements
    BedTemp1 = 20
    BedTemp2 = 20
    BedTemp3 = 20
    
    # The prog_state variable just toggles a decimal point on the ZeroSeg to give us
    # an indication that the program is running. Initialised here...
    prog_state = "."
    
    while True:
        time.sleep(1)
        
        # ----------------------------------------------------------------------
        # Use the ZeroSeg buttons to control the target temperature...
        if GPIO.input(sw_L) == False and GPIO.input(sw_R) == False:
            if BedTemp_Target > 10:
                BedTemp_Target = 10
        elif GPIO.input(sw_L) == False:
            BedTemp_Target = BedTemp_Target + 5
        elif GPIO.input(sw_R) == False:
            # Execute a safe power down if the target temperature is reduced below zero DegC
            if BedTemp_Target == 0:
                device.write_text(1, "OFF.....")
                os.system("sudo halt")
                BedRunning = False
            else:
                BedTemp_Target = BedTemp_Target - 5
                
        # ----------------------------------------------------------------------
        # Read the temperature sensor...
        # Build up a history of three readings and take the average
        # to reduce noise / small variations
        BedTemp3 = BedTemp2
        BedTemp2 = BedTemp1
        BedTemp1 = read_temp_lm75()     # Uncomment this line to use the LM75 as a temperature sensor
        #BedTemp1 = read_temp_mpu6050()  # Uncomment this line to use the MPU6050 as a temperature sensor
        BedTemp = round((BedTemp1 + BedTemp2 + BedTemp3)/3,1)
        
        # ----------------------------------------------------------------------
        # Print the current status to the screen (if connected)
        print ""
        print "Temperature: ", BedTemp, " Target: ", BedTemp_Target

        if Heater_On == True and BedTemp > BedTemp_Target + TempHisterisis/2:
            print "Turning heating off (Over-temperature)"
            Heater_On = False
            Heater_TurnOff()
        elif Heater_On == False and BedTemp < BedTemp_Target - TempHisterisis/2:
            print "Turning heating on (Under-temperature)"
            Heater_On = True
            Heater_TurnOn()
        
        if Heater_On == True:
            print "Heater on"
        else:
            print "Heater off"
            
        if BedTemp > BedTemp_Target - TempGoodHisterisis/2 and BedTemp < BedTemp_Target + TempGoodHisterisis/2:
            print "Ready to print!"
        elif BedTemp > BedTemp_Target + TempGoodHisterisis/2:
            print "Over-temperature"
        else:
            print "Under-temperature"

        
        # ----------------------------------------------------------------------
        # Print the current status to the ZeroSeg
        # Only do it when BedRunning is true - this is to prevent the last update
        # from over-writing the "Off....." message to the ZeroSeg
        if BedRunning:
            BedTemp_text = '{:3}'.format(int(BedTemp))
            BedTemp_Target_text = '{:3}'.format(int(BedTemp_Target))
            
            # Toggle the 'prog_state' (decimal point on display) to 
            # provide indication the program is running ok
            if prog_state == ".":
                prog_state = " "
            else:
                prog_state = "."
            
            # Simple indication of heater status for the display
            # Display '1' if the heater is on, '0' if off
            if Heater_On == True:
                heater_state = "1"
            else:
                heater_state = "0"
                
            display_text = BedTemp_Target_text + BedTemp_text + prog_state + heater_state
            
            device.write_text(1, display_text)
        

# ------------------------------------------------------------------------------
# Main program loop
try:

	tempctrl()
	
# ------------------------------------------------------------------------------
# If you press CTRL+C, turn the heater off, cleanup GPIO and exit
except KeyboardInterrupt:

    print "Switching off"
    GPIO.output(pinPSUctrl,not PSUctrlOn) 
    
    # Reset GPIO settings
    GPIO.cleanup()
