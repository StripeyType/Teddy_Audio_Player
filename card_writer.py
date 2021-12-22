import board
import digitalio
import analogio
import time
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
pn532 = PN532_SPI(spi, CS, debug=False)
#     Digital IO "IRQ" pin setup
irq   = digitalio.DigitalInOut(board.GP20)
irq.direction = digitalio.Direction.INPUT
#     Initialize RFID listener
pn532.listen_for_passive_target()
#     Setup MiFare Constants
KEY   = b'\xFF\xFF\xFF\xFF\xFF\xFF'

##### END PN532 Setup

# Debugging Heartbeat
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
led.value = 0

# ##### Set up DFPlayer
# #      uart for serial communication with DFPlayer
# UART_RX = board.GP1
# UART_TX = board.GP0
# uart    = busio.UART(UART_TX, UART_RX, baudrate=9600)
# #      Use uart to connect
# dfp     = DFPlayer.DFPlayer(uart=uart)
# #      turn off looping of folders or recordings
# ##### END DFPlayer setup.

##### Set up Volume Slider
volume = analogio.AnalogIn(board.GP26)

##### Set up Play/Pause Button
button = digitalio.DigitalInOut(board.GP22)
button.direction = digitalio.Direction.INPUT

##### Initialize Recording Library
# from recordings import recording_map as recording_library
TRACK_DATA_IS_IN_BLOCK_8 = 8

# Sensible Defaults
vol_set  = 10 # Lower-third volume setting by default
track_id = 42 # Put some sort of charming error noise in /42/42.mp3
album_id = 42 #
written  = {}

data = bytearray(b'\x01\x00\x01\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff')
# Main Loop
while True:
    # # Update Volume
    # #new_vol = int((volume.value / 65535) * 100)
    # #if not new_vol == vol_set:
    # #    vol_set = new_vol
    # dfp.set_volume(vol_set)
    #
    # # Check Play/Pause Button
    # if button.value:
    #     if dfp.isPlaying():
    #         dfp.pause()
    #     elif dfp.isPaused():
    #         dfp.pause()
    #     else:
    #         dfp.play(folder=album_id,track=track_id)
    #
    # # Set Current Track based on RFID Card
    # uid = pn532.read_passive_target(timeout=0.1)
    # if uid:
    #     if pn532.mifare_classic_authenticate_block(uid, TRACK_DATA_IS_IN_BLOCK_8, MIFARE_CMD_AUTH_A, KEY):
    #         track_data = mifare_classic_read_block(TRACK_DATA_IS_IN_BLOCK_8)
    #         album_id = int(track_data[0]) # The very first byte tells us which folder to look in
    #         track_id = int(track_data[1])*256 + int(track_data[2]) # 2nd and 3rd bytes form an int for track_id MSB order
    # else: # we've got no card inserted; reset track_id and album_id
    #     track_id = 42
    #     album_id = 42
    #

    led.value = 1 - led.value
    if irq.value == 0:
        uid = pn532.read_passive_target(timeout=0.1)
        if not written.get(bytes(uid)):
            print("Found new card with UID {}".format([int(i) for i in uid]))
            if pn532.mifare_classic_authenticate_block(uid, TRACK_DATA_IS_IN_BLOCK_8, MIFARE_CMD_AUTH_A, KEY):
                print(" - Successfully Authenticated to Card. Writing to block {}".format(TRACK_DATA_IS_IN_BLOCK_8))
                pn532.mifare_classic_write_block(TRACK_DATA_IS_IN_BLOCK_8, bytes(data))
                print(" - Wrote to block {}, now trying to read that data:".format(TRACK_DATA_IS_IN_BLOCK_8))
                on_card = pn532.mifare_classic_read_block(TRACK_DATA_IS_IN_BLOCK_8)
                if on_card:
                    print(" - found:")
                    print([hex(i) for i in on_card])
                    if on_card == data:
                        print("SUCCESS! Next card please!")
                        data[2] += 1
                        written[bytes(uid)] = True
                        time.sleep(5)
                    else:
                        print("Data does not match. Bad Card?\n Track Number NOT Incremented! :(")
                        time.sleep(5)
        else:
            print("Found PREVIOUSLY-WRITTEN Card! UID={}".format([int(i) for i in uid]))
            if pn532.mifare_classic_authenticate_block(uid, TRACK_DATA_IS_IN_BLOCK_8, MIFARE_CMD_AUTH_A, KEY):
                print(" - Successfully Authenticated to Card.")
                on_card = pn532.mifare_classic_read_block(TRACK_DATA_IS_IN_BLOCK_8)
                if on_card:
                    print(" - This card is programmed for Track: {1}, Album: {0}".format(int(on_card[0]), int(on_card[1])*256 + int(on_card[2])))
                    time.sleep(10)
                else:
                    print(" ERROR: Unable to cread card?")
    else:
        print("Card Not Detected")
