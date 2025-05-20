import serial
import time
from datetime import datetime

# Interpreting the three byte packets:
#         D7      D6      D5      D4      D3      D2      D1      D0
#
# Byte 1  X       1       LB      RB      Y7      Y6      X7      X6
# Byte 2  X       0       X5      X4      X3      X2      X1      X0
# Byte 3  X       0       Y5      Y4      Y3      Y2      Y1      Y0
#
# LB is the state of the left button (1 means down)
# RB is the state of the right button (1 means down)
# X7-X0 movement in X direction since last packet (signed byte)
# Y7-Y0 movement in Y direction since last packet (signed byte)

PORT = "/dev/ttyUSB3"
BAUD = 1200
BYTESIZE = serial.SEVENBITS
PARITY = serial.PARITY_NONE
STOPBITS = serial.STOPBITS_ONE

def decode_signed_x(b1, b2):
    b1 &= 0x03
    val = b2 + (b1<<6)
    val &= 0x3F
    return val - 64 if val >= 32 else val

def parse_mouse_packet(packet):
    if len(packet) != 3:
        return None
    
    b1, b2, b3 = packet
    if b1 & 0x40 == 0:
        return None  # Invalid packet start
    dx = decode_signed_x(b1, b2)
    return b1, b2, b3, dx

def scale_from_speed(delta_t):
    if delta_t > 0.1:
        return 1
    elif delta_t > 0.05:
        return 4
    elif delta_t > 0.025:
        return 16
    else:
        return 64

def main():
    accum_linear = 0
    accum_scaled = 0
    last_movement_time = None  # Track only time of actual ΔX ≠ 0

    with serial.Serial(PORT, BAUD, bytesize=BYTESIZE,
                       parity=PARITY, stopbits=STOPBITS, timeout=1) as ser:
        print(f"Listening on {PORT} @ {BAUD} baud...\n", flush=True)
        buffer = bytearray()

        while True:
            byte = ser.read(1) 
            if byte:
                b = byte[0] & 0x7f # ignore D7
                if b & 0x40:
                    buffer = bytearray([b])
                else:
                    buffer.append(b)

                if len(buffer) == 3:
                    result = parse_mouse_packet(buffer)
                    if result:
                        b1, b2, b3, dx = result
                        now = time.time()
                        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                        accum_linear += dx
                        delta_t = 0

                        if dx != 0:
                            if last_movement_time is None:
                                scale = 1
                            else:
                                delta_t = min(now - last_movement_time, 0.999)
                                scale = scale_from_speed(delta_t)
                            last_movement_time = now
                            accum_scaled += dx * scale
                        else:
                            scale = "-"  # No scaling applied to ΔX = 0
                        if dx != 0:
                          print(f"{timestamp} Δt:{int(delta_t*1000):03d}| "
                                f"Packet: {b1:02X} {b2:02X} {b3:02X} | "
                                f"ΔX: {dx:>3}, "
                                f"Linear X: {accum_linear:>4}, "
                                f"Scaled X: {accum_scaled:>4} (×{scale})",
                                flush=True)

                    buffer.clear()

if __name__ == "__main__":
    main()
