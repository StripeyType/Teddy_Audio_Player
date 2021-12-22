import board
import digitalio
import analogio
import pwmio
import time
import math
import busio
import DFPlayer

from adafruit_pn532.spi import PN532_SPI
from adafruit_pn532.adafruit_pn532 import MIFARE_CMD_AUTH_B, MIFARE_CMD_AUTH_A

###### PN532 RFID SETUP ##################
#     SPI Setup for PN532
MOSI  = board.GP19
MISO  = board.GP16
SCK   = board.GP18
CS    = digitalio.DigitalInOut(board.GP17)
spi   = busio.SPI(SCK, MOSI, MISO)
#     Digital IO "IRQ" pin setup
irq   = digitalio.DigitalInOut(board.GP20)
irq.direction = digitalio.Direction.INPUT
pn532 = PN532_SPI(spi, CS, debug=False, irq=irq)

#     Initialize RFID listener
pn532.listen_for_passive_target()
#     Setup MiFare Constants
KEY   = b'\xFF\xFF\xFF\xFF\xFF\xFF'

##### END PN532 Setup

# Debugging Heartbeat
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
led.value = 0

##### Set up DFPlayer
#      uart for serial communication with DFPlayer
UART_RX = board.GP1
UART_TX = board.GP0
uart    = busio.UART(UART_TX, UART_RX, baudrate=9600)
#      Use uart to connect
dfp     = DFPlayer.DFPlayer(uart=uart)
#      turn off looping of folders or recordings
##### END DFPlayer setup.

##### Set up Volume Slider
volume = analogio.AnalogIn(board.GP26)

##### Set up Play/Pause Button
button    = digitalio.DigitalInOut(board.GP21)
button.switch_to_input(pull=digitalio.Pull.DOWN)
playlight = pwmio.PWMOut(board.GP22, duty_cycle=2**15, frequency=1000)
slowness  = 100
buttoncount = 0

##### Initialize Recording Library
# from recordings import recording_map as recording_library
TRACK_DATA_IS_IN_BLOCK_8 = 8

# Sensible Defaults
vol_set      = 10 # Lower-third volume setting by default
track_id     = 42 # Put some sort of charming error noise in /42/42.mp3
album_id     = 42 #
dfp_status   = None
card_present = True
status_counter = 0
cycles = 0
dfp_lookup   = {
    dfp.STATUS_BUSY   : "BUSY   ",
    dfp.STATUS_PAUSED : "PAUSED ",
    dfp.STATUS_STOPPED: "STOPPED",
    0x211             : "UNKNOWN"
}
##### Main Loop
while True:
    ### First read fast hardware statuses
    b    = int(button.value)
    v    = int((volume.value / 65535) * 75) # no reason to go louder than necessary

    ### incr cycles
    cycles += 1

    ### Now get slow DFP status once in a while
    if status_counter >= 15:
        dfp_status = dfp.get_status()
        status_counter = 0
    else:
        status_counter += 1

    ### Reset card_present if we're not playing a recording
    if (dfp_status == dfp.STATUS_STOPPED) or (dfp_status == dfp.STATUS_PAUSED):
        if irq.value:
            card_present = False

    ### Update Volume only if it needs to be, because the UART is slow
    if not v == vol_set:
       vol_set = v
       dfp.set_volume(vol_set)

    ### Handle Play/Pause Button if pressed
    if b:
        buttoncount += 1
        if   dfp_status == dfp.STATUS_BUSY:
            dfp.pause()
        elif dfp_status == dfp.STATUS_PAUSED:
            if not card_present:
                dfp.stop()
            else:
                dfp.play()
        elif dfp_status == dfp.STATUS_STOPPED:
            dfp.stop()
            dfp.play(track=track_id)
    else:
        buttoncount = 0

    if buttoncount >= 15:
        print("E-Stop!")
        dfp.stop()

    if dfp_status == dfp.STATUS_PAUSED: # paused with nobody pressing the button
        playlight.duty_cycle = int((2**16-1)*math.sin(((cycles%slowness)/slowness)*math.pi))
        if cycles >= 2**16:
            cycles = 0

    led.value = 1 - led.value

    ### Handle RFID Cards to set current track
    if irq.value == False: # pin has been pulled low
        uid = pn532.read_passive_target(timeout=0.1)
        if uid:
            if pn532.mifare_classic_authenticate_block(uid, TRACK_DATA_IS_IN_BLOCK_8, MIFARE_CMD_AUTH_A, KEY):
                on_card = pn532.mifare_classic_read_block(TRACK_DATA_IS_IN_BLOCK_8)
                if on_card:
                    album_id = int(on_card[0])
                    track_id = int(on_card[1]*256)+int(on_card[2])
                    card_present = True
                else:
                    print(" ERROR: Unable to read card?")
            pn532.listen_for_passive_target() #reset reader
    else: # no card
        track_id = 42 # Put some sort of charming error noise in /42/0042.mp3

    ### CONSOLE DEBUG MSG
    print("Vol: {} Track: {} Button: {} DFP: {} Card?: {}".format(vol_set, track_id, button.value, dfp_lookup.get(dfp_status, "UNKNOWN: {}".format(dfp_status)), card_present))
