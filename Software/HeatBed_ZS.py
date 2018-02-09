#!/usr/bin/env python

import RPi.GPIO as GPIO # Import the GPIO Library
import smbus
import math
import ZeroSeg.led as led
import time
import random
from datetime import datetime
import os

# Power management registers
power_mgmt_1 = 0x6b
power_mgmt_2 = 0x6c

#ZeroSeg buttons...
sw_L = 17
sw_R = 26

def read_byte(adr):
    return bus.read_byte_data(address, adr)

def read_word(adr):
    high = bus.read_byte_data(address, adr)
    low = bus.read_byte_data(address, adr+1)
    val = (high << 8) + low
    return val

def read_word_2c(adr):
    val = read_word(adr)
    if (val >= 0x8000):
        return -((65535 - val) + 1)
    else:
        return val

# Set the GPIO modes
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Setup the pin to control the PSU and turn it off
# PSU control pin is active low / False to turn on, High / True to turn off
pinPSUctrl = 15
GPIO.setup(pinPSUctrl, GPIO.OUT)
GPIO.output(pinPSUctrl,True) 

GPIO.setup(sw_L, GPIO.IN)
GPIO.setup(sw_R, GPIO.IN)

# Function for turning the heatbed power off
def psu_ON():
    GPIO.output(pinPSUctrl,False)

# Function for turning the heatbed power on
def psu_OFF():
    GPIO.output(pinPSUctrl,True)

bus = smbus.SMBus(1) # or bus = smbus.SMBus(1) for Revision 2 boards
address = 0x68       # This is the address value read via the i2cdetect command

# Now wake the 6050 up as it starts in sleep mode
bus.write_byte_data(address, power_mgmt_1, 0)

#device = led.sevensegment()
device = led.sevensegment(cascaded=2)

# Main temperature control function
def tempctrl():
    
    GPIO.output(pinPSUctrl,True) 
    psu = False
    
    # Set the initial temperature...
    BedTemperature = 55 # PLA
    #BedTemperature = 95 # ABS
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
        
        if GPIO.input(sw_L) == False and GPIO.input(sw_R) == False:
            if BedTemperature > 10:
                BedTemperature = 10
        elif GPIO.input(sw_L) == False:
            BedTemperature = BedTemperature + 5
        elif GPIO.input(sw_R) == False:
            if BedTemperature == 0:
                device.write_text(1, "OFF.....")
                os.system("sudo halt")
            else:
                BedTemperature = BedTemperature - 5
        
        temp_out = read_word_2c(0x41)
        temp_scaled = temp_out/340.0+36.53
        
        BedTemp3 = BedTemp2
        BedTemp2 = BedTemp1
        BedTemp1 = temp_scaled
        
        BedTemp = (BedTemp1 + BedTemp2 + BedTemp3)/3
        
        #print "1: ", BedTemp1, " 2: ", BedTemp2, " 3: ", BedTemp3
        print ""
        print "Temperature: ", BedTemp, " Target: ", BedTemperature
        
        current_temp_text = '{:3}'.format(int(BedTemp))
        target_temp_text = '{:3}'.format(int(BedTemperature))
        
        # Toggle the 'prog_state' (decimal point on display) to 
        # provide indication the program is running ok
        if prog_state == ".":
            prog_state = " "
        else:
            prog_state = "."
        
        # Simple indication of heater status for the display
        # Display '1' if the heater is on, '0' if off
        if psu == True:
            heater_state = "1"
        else:
            heater_state = "0"
            
        display_text = target_temp_text + current_temp_text + prog_state + heater_state
        
        device.write_text(1, display_text)
        
        if psu == True and BedTemp > BedTemperature + TempHisterisis/2:
            print "Turning heating off (Over-temperature)"
            psu = False
            psu_OFF()
        elif psu == False and BedTemp < BedTemperature - TempHisterisis/2:
            print "Turning heating on (Under-temperature)"
            psu = True
            psu_ON()
        
        if psu == True:
            print "Plate on"
        else:
            print "Plate off"
            
        if BedTemp > BedTemperature - TempGoodHisterisis/2 and BedTemp < BedTemperature + TempGoodHisterisis/2:
            print "Ready to print!"
        elif BedTemp > BedTemperature + TempGoodHisterisis/2:
            print "Over-temperature"
        else:
            print "Under-temperature"


try:

	tempctrl()
	
# If you press CTRL+C, cleanup and stop
except KeyboardInterrupt:

    print "Switching off"
    GPIO.output(pinPSUctrl,True) 
    
    # Reset GPIO settings
    GPIO.cleanup()
