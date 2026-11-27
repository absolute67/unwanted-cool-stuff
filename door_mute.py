"""
door_mute.py - mutes your Windows PC when your door opens.

How it works:
  Phone stuck on the door runs Phyphox (accelerometer) with remote access on.
  This script polls the phone over Wi-Fi, watches for a sudden movement,
  and mutes the PC volume. It unmutes after the door has been still for a while.

Install (Windows):
  pip install requests pycaw comtypes

Usage:
  python door_mute.py --test      # only prints readings, never touches volume (use this to tune)
  python door_mute.py             # live mode
"""

import argparse
import math
import sys
import time

import requests

# ====================== SETTINGS (edit these) ======================
PHONE_URL = "PHONE_URL"  # the address Phyphox shows under "Allow remote access"
POLL_INTERVAL = 0.05      # seconds between readings (0.05 = 20 per second)
THRESHOLD = 0.8           # m/s^2 change from resting that counts as "door moved". Lower = more sensitive
MIN_HITS = 1             # readings in a row above THRESHOLD needed to trigger (filters noise)
UNMUTE_AFTER = 15         # seconds of stillness before unmuting. Set 0 to never auto-unmute
CALIBRATION_SECONDS = 2   # time spent learning the resting value at startup
# ===================================================================


def read_accel():
    """Return (x, y, z) from Phyphox, or None if the experiment isn't running."""
    r = requests.get(f"{PHONE_URL}/get?accX&accY&accZ", timeout=2)
    buf = r.json()["buffer"]
    vals = []
    for key in ("accX", "accY", "accZ"):
        data = buf[key]["buffer"]
        if not data or data[-1] is None:
            return None
        vals.append(float(data[-1]))
    return tuple(vals)


def magnitude(v):
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


class Volume:
    """Mute/unmute the Windows master volume using pycaw (works with old and new versions)."""

    def __init__(self):
        from pycaw.pycaw import AudioUtilities

        speakers = AudioUtilities.GetSpeakers()
        if hasattr(speakers, "EndpointVolume"):  # newer pycaw
            self.endpoint = speakers.EndpointVolume
        else:  # older pycaw
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import IAudioEndpointVolume

            interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self.endpoint = cast(interface, POINTER(IAudioEndpointVolume))

    def is_muted(self):
        return bool(self.endpoint.GetMute())

    def set_mute(self, state):
        self.endpoint.SetMute(1 if state else 0, None)


def calibrate():
    print(f"Calibrating for {CALIBRATION_SECONDS}s - keep the door still...")
    samples = []
    end = time.time() + CALIBRATION_SECONDS
    while time.time() < end:
        v = read_accel()
        if v:
            samples.append(magnitude(v))
        time.sleep(POLL_INTERVAL)
    if not samples:
        sys.exit("No data from phone. Is the Phyphox experiment running (press play)?")
    base = sum(samples) / len(samples)
    print(f"Resting value: {base:.2f} m/s^2")
    return base


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="print readings only, don't change volume")
    args = parser.parse_args()

    volume = None
    if not args.test:
        volume = Volume()

    try:
        baseline = calibrate()
    except requests.RequestException as e:
        sys.exit(f"Can't reach the phone at {PHONE_URL}: {e}")

    hits = 0
    muted_by_us = False
    last_motion = time.time()
    print("Watching the door. Press Ctrl+C to stop.\n")

    while True:
        try:
            v = read_accel()
        except requests.RequestException:
            print("Lost connection to phone, retrying...")
            time.sleep(1)
            continue

        if v is None:
            time.sleep(POLL_INTERVAL)
            continue

        mag = magnitude(v)
        deviation = abs(mag - baseline)

        if args.test:
            bar = "#" * int(min(deviation * 10, 60))
            print(f"deviation {deviation:5.2f} {bar}")

        if deviation > THRESHOLD:
            hits += 1
            last_motion = time.time()
            if hits >= MIN_HITS and not muted_by_us:
                print(f"[{time.strftime('%H:%M:%S')}] Door moved (deviation {deviation:.2f}) -> MUTE")
                if volume:
                    already_muted = volume.is_muted()
                    volume.set_mute(True)
                    muted_by_us = not already_muted
        else:
            hits = 0
            # slowly follow the resting value so small drift doesn't cause false triggers
            baseline = baseline * 0.995 + mag * 0.005

        if muted_by_us and UNMUTE_AFTER and time.time() - last_motion > UNMUTE_AFTER:
            print(f"[{time.strftime('%H:%M:%S')}] Door still for {UNMUTE_AFTER}s -> UNMUTE")
            if volume:
                volume.set_mute(False)
            muted_by_us = False

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
