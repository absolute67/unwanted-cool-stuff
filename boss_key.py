"""
Boss Key: when a second face shows up in your webcam, the script
instantly reacts (hide windows, open a file or page, lock, and more).
Choose what happens in the ACTIONS setting below.

Install:   pip install "opencv-python<5" numpy pyautogui
Run:       python boss_key.py
Quit:      press Q (while the small preview window is focused) or Ctrl+C
"""

import ctypes
import os
import time
import webbrowser

import cv2
import numpy as np

try:
    import pyautogui
except ImportError:  # works without it, you just lose "minimise everything"
    pyautogui = None

# =====================================================================
#  HOW TO USE THIS SCRIPT (read this first)
# =====================================================================
#  1. Install:   pip install "opencv-python<5" numpy pyautogui
#  2. Run:       python boss_key.py
#  3. A small preview window opens. Green boxes = faces it can see.
#  4. When a SECOND face appears behind you, the script does whatever
#     you chose in ACTIONS below.
#  5. Press Q in the preview window to quit.
#
#  CHOOSING WHAT HAPPENS
#  Pick ONE option below. Remove the "#" at the start of the line you
#  want, and keep every other ACTIONS line commented out with "#".
#  If more than one line is active, the LAST one wins.
# =====================================================================

# ACTIONS = ["hide_windows"]   # minimise all windows (Win+D)
# ACTIONS = ["fake_screen"]    # show a fake spreadsheet, closes itself when clear
# ACTIONS = ["open_file"]        # open a real file (set FILE_PATH below)
ACTIONS = ["open_url"]       # open a web page (set URL below)
# ACTIONS = ["lock"]           # lock your PC
# ACTIONS = ["mute"]           # mute the volume
# ACTIONS = ["photo"]          # save a photo of who walked in (PHOTO_DIR below)

# TIP: you can also combine options, for example:
# ACTIONS = ["hide_windows", "mute", "open_file"]
# They run in the order you write them.

# ---- extra settings used by some options ----
FILE_PATH = r"C:\path\to\your_real_file.xlsx"   # used by "open_file": a real file on your PC
URL = "https://www.youtube.com/@ShortSpan-fixes"    # used by "open_url": the page to open
PHOTO_DIR = "intruder_photos"                   # used by "photo": folder for saved snapshots

# ---- tuning (change these if detection is too sensitive or not sensitive enough) ----
CAMERA_INDEX = 0          # 0 = default webcam, try 1 if the wrong camera opens
MIN_FACE_SIZE = 80        # ignore faces smaller than this (lower = detects people farther away)
MIN_NEIGHBORS = 10        # higher = stricter detector = fewer fake faces (try 8 to 14)
FRAMES_TO_TRIGGER = 12    # extra face must be seen this many frames in a row (about 0.4 sec)
CALIBRATION_SECONDS = 3   # at start, sit alone: any extra "face" seen now is a fake (poster, pattern) and gets ignored
BOOST_CONTRAST = False    # True helps in dark rooms but can create fake faces from noise
DETECT_WIDTH = 480        # shrink the frame to this width before detecting (faster, and big close-up faces are easier)
CLOSE_FACE_RATIO = 0.25   # a second detector looks for BIG faces (wider than this fraction of the frame) = you, up close
SECONDS_TO_RELEASE = 2.0  # how long the room must be clear before "fake_screen" closes
COOLDOWN_SECONDS = 10     # after it triggers, wait this long before it can trigger again
SHOW_PREVIEW = True       # show the small preview window with face boxes

FAKE_WINDOW = "Budget_Q4_FINAL_v7.xlsx - Excel"
PREVIEW_WINDOW = "Boss Key preview"


def make_fake_spreadsheet(width, height):
    """Draw a boring-looking spreadsheet so we don't need any image file."""
    img = np.full((height, width, 3), 255, dtype=np.uint8)

    # green title bar + ribbon
    cv2.rectangle(img, (0, 0), (width, 40), (80, 120, 33), -1)
    cv2.putText(img, "Budget_Q4_FINAL_v7.xlsx - Excel", (15, 27),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.rectangle(img, (0, 40), (width, 110), (240, 240, 240), -1)
    for i, name in enumerate(["File", "Home", "Insert", "Formulas", "Data", "Review", "View"]):
        cv2.putText(img, name, (20 + i * 110, 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (60, 60, 60), 1, cv2.LINE_AA)

    # grid
    top, left = 150, 60
    col_w, row_h = 150, 32
    cols = (width - left) // col_w
    rows = (height - top) // row_h
    headers = ["Item", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Total"]
    rng = np.random.default_rng(7)

    for c in range(cols + 1):
        x = left + c * col_w
        cv2.line(img, (x, top - row_h), (x, height), (210, 210, 210), 1)
    for r in range(rows + 2):
        y = top - row_h + r * row_h
        cv2.line(img, (0, y), (width, y), (210, 210, 210), 1)

    for c in range(min(cols, len(headers))):
        cv2.putText(img, headers[c], (left + c * col_w + 10, top - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2, cv2.LINE_AA)

    items = ["Marketing", "Salaries", "Software", "Travel", "Rent", "Support",
             "Hardware", "Training", "Legal", "Misc"]
    for r in range(min(rows, len(items))):
        y = top + r * row_h + 22
        cv2.putText(img, items[r], (left + 10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (30, 30, 30), 1, cv2.LINE_AA)
        total = 0
        for c in range(1, min(cols, 7)):
            val = int(rng.integers(1200, 9800))
            total += val
            cv2.putText(img, f"{val:,}", (left + c * col_w + 10, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (30, 30, 30), 1, cv2.LINE_AA)
        if cols > 7:
            cv2.putText(img, f"{total:,}", (left + 7 * col_w + 10, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 150), 1, cv2.LINE_AA)
    return img


def screen_size():
    if pyautogui:
        w, h = pyautogui.size()
        return int(w), int(h)
    return 1920, 1080


def show_fake(fake_img):
    cv2.namedWindow(FAKE_WINDOW, cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty(FAKE_WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setWindowProperty(FAKE_WINDOW, cv2.WND_PROP_TOPMOST, 1)
    cv2.imshow(FAKE_WINDOW, fake_img)
    cv2.waitKey(1)


def hide_fake():
    try:
        cv2.destroyWindow(FAKE_WINDOW)
    except cv2.error:
        pass


def run_actions(frame, fake_img):
    """Run everything listed in ACTIONS. Returns True if the fake screen is up."""
    fake_up = False
    for action in ACTIONS:
        if action == "hide_windows" and pyautogui:
            pyautogui.hotkey("win", "d")
            time.sleep(0.15)
        elif action == "fake_screen":
            show_fake(fake_img)
            fake_up = True
        elif action == "open_file":
            try:
                os.startfile(FILE_PATH)  # Windows only
            except OSError as err:
                print("open_file failed, check FILE_PATH:", err)
        elif action == "open_url":
            webbrowser.open(URL)
        elif action == "lock":
            ctypes.windll.user32.LockWorkStation()
        elif action == "mute" and pyautogui:
            pyautogui.press("volumemute")
        elif action == "photo":
            os.makedirs(PHOTO_DIR, exist_ok=True)
            name = time.strftime("%Y%m%d_%H%M%S") + ".jpg"
            cv2.imwrite(os.path.join(PHOTO_DIR, name), frame)
    return fake_up


def remove_duplicates(faces):
    """Haar sometimes draws 2 boxes on ONE face. Keep only the biggest of any overlapping pair."""
    boxes = sorted((tuple(int(v) for v in f) for f in faces),
                   key=lambda b: b[2] * b[3], reverse=True)
    kept = []
    for (x, y, w, h) in boxes:
        cx, cy = x + w / 2, y + h / 2
        duplicate = any(abs(cx - (kx + kw / 2)) < kw * 0.6 and
                        abs(cy - (ky + kh / 2)) < kh * 0.6
                        for (kx, ky, kw, kh) in kept)
        if not duplicate:
            kept.append((x, y, w, h))
    return kept


def detect_faces(gray, cascade, close_cascade):
    """Find faces on a shrunken frame, plus a second pass tuned for very close, big faces."""
    h, w = gray.shape[:2]
    scale = DETECT_WIDTH / w if w > DETECT_WIDTH else 1.0
    small = cv2.resize(gray, None, fx=scale, fy=scale) if scale < 1.0 else gray
    min_size = max(24, int(MIN_FACE_SIZE * scale))
    found = [tuple(b) for b in cascade.detectMultiScale(
        small, scaleFactor=1.1, minNeighbors=MIN_NEIGHBORS,
        minSize=(min_size, min_size))]

    # close-up pass: only keeps BIG faces, so it can't add small fake ones
    big = int(small.shape[1] * CLOSE_FACE_RATIO)
    if big > min_size:
        found += [tuple(b) for b in close_cascade.detectMultiScale(
            small, scaleFactor=1.1, minNeighbors=MIN_NEIGHBORS, minSize=(big, big))]

    # back to full-frame coordinates
    return [(int(x / scale), int(y / scale), int(fw / scale), int(fh / scale))
            for (x, y, fw, fh) in found]


def in_ignore_zone(box, zones):
    """True if this box sits on a spot that was a fake face during calibration."""
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    return any(zx - zw * 0.3 < cx < zx + zw * 1.3 and zy - zh * 0.3 < cy < zy + zh * 1.3
               for (zx, zy, zw, zh) in zones)


def main():
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    close_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml")
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise SystemExit("Could not open the webcam. Try another CAMERA_INDEX.")

    fake_img = make_fake_spreadsheet(*screen_size())
    hidden = False
    fake_up = False
    last_trigger = 0.0
    extra_face_frames = 0
    clear_since = None
    ignore_zones = []
    start_time = time.time()

    print(f"Calibrating for {CALIBRATION_SECONDS}s: sit alone in front of the camera...")
    print("Boss key is ON. Press Q in the preview window to quit.")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if BOOST_CONTRAST:
                gray = cv2.equalizeHist(gray)
            faces = remove_duplicates(detect_faces(gray, cascade, close_cascade))

            # calibration: you are alone, so every face except the biggest is fake
            calibrating = time.time() - start_time < CALIBRATION_SECONDS
            if calibrating:
                for box in faces[1:]:
                    if len(ignore_zones) < 30 and not in_ignore_zone(box, ignore_zones):
                        ignore_zones.append(box)
                extra_face_frames = 0
            else:
                faces = [f for f in faces if not in_ignore_zone(f, ignore_zones)]
            face_count = len(faces)

            # count consecutive frames with 2+ faces (never during calibration)
            if calibrating:
                pass
            elif face_count >= 2:
                extra_face_frames += 1
                clear_since = None
            else:
                extra_face_frames = 0
                if clear_since is None:
                    clear_since = time.time()

            # trigger: someone else is in view
            if (not hidden and extra_face_frames >= FRAMES_TO_TRIGGER
                    and time.time() - last_trigger >= COOLDOWN_SECONDS):
                hidden = True
                last_trigger = time.time()
                fake_up = run_actions(frame, fake_img)

            # release: room has been clear for a while
            if hidden and clear_since and time.time() - clear_since >= SECONDS_TO_RELEASE:
                hidden = False
                if fake_up:
                    hide_fake()
                    fake_up = False

            if SHOW_PREVIEW:
                for (x, y, w, h) in faces:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                state = "CALIBRATING" if calibrating else ("HIDDEN" if hidden else "watching")
                label = f"faces: {face_count}  {state}"
                cv2.putText(frame, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            0.8, (0, 255, 255), 2, cv2.LINE_AA)
                preview = cv2.resize(frame, (480, 270))
                cv2.imshow(PREVIEW_WINDOW, preview)

            if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                break
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()