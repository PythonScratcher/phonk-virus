#
import os
import sys

import os
import random
import threading
import time
import tkinter as tk
from PIL import Image, ImageTk, ImageGrab, ImageOps
import pygame
from pynput import mouse, keyboard

# ---------------- CONFIG ----------------
MUSIC_DIR = "music"
PHOTO_DIR = "photo"
SHAKE_INTENSITY = 18     # pixels
FRAME_MS = 30            # frame delay in ms
MAX_OVERLAY_RATIO = 0.6  # overlay max size relative to screen
# ----------------------------------------

_running_lock = threading.Lock()  # prevents reentry while run

def choose_random_file(folder, exts):
    try:
        files = [f for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in exts]
    except FileNotFoundError:
        return None
    if not files:
        return None
    return os.path.join(folder, random.choice(files))

def run_effect_once(mp3_path, png_path):
    """Create fullscreen shaking overlay while mp3 plays. Runs in its own thread."""
    # prevent reentry
    if not _running_lock.acquire(blocking=False):
        return  # already running

    try:
        # init audio
        pygame.mixer.init()
        try:
            pygame.mixer.music.load(mp3_path)
        except Exception as e:
            print("Failed to load music:", e)
            return

        # screenshot + grayscale
        screenshot = ImageGrab.grab()
        screenshot = ImageOps.grayscale(screenshot).convert("RGBA")

        # load overlay png (keep alpha)
        overlay = Image.open(png_path).convert("RGBA")

        # scale overlay if too big
        screen_w, screen_h = screenshot.size
        max_ow = int(screen_w * MAX_OVERLAY_RATIO)
        max_oh = int(screen_h * MAX_OVERLAY_RATIO)
        ow, oh = overlay.size
        scale = min(1.0, max_ow / ow, max_oh / oh)
        if scale < 1.0:
            overlay = overlay.resize((int(ow * scale), int(oh * scale)), Image.LANCZOS)

        # ---------- build tkinter uI ----------
        # Tk must be created in the thread that will run its mainloop. This function runs in a thread.
        root = tk.Tk()
        root.title("phonk")
        # fullscreen + keep on top
        root.attributes('-fullscreen', True)
        root.attributes('-topmost', True)
        root.config(cursor="none")  # hide cursor

        screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
        canvas = tk.Canvas(root, width=screen_w, height=screen_h, highlightthickness=0)
        canvas.pack()

        # Convert images to PhotoImage and keep references
        screenshot_tk = ImageTk.PhotoImage(screenshot.resize((screen_w, screen_h), Image.LANCZOS))
        overlay_tk = ImageTk.PhotoImage(overlay)
        overlay_w, overlay_h = overlay.size
        overlay_cx = screen_w // 2
        overlay_cy = screen_h // 2

        # ESC key binding to stop early
        def stop_and_quit(event=None):
            try:
                pygame.mixer.music.stop()
            except:
                pass
            try:
                root.destroy()
            except:
                pass

        # bind Escape to root (works while root has focus)
        root.bind("<Escape>", stop_and_quit)

        # start music and animation
        pygame.mixer.music.play()

        def frame():
            canvas.delete("all")
            x_off = random.randint(-SHAKE_INTENSITY, SHAKE_INTENSITY)
            y_off = random.randint(-SHAKE_INTENSITY, SHAKE_INTENSITY)
            canvas.create_image(x_off, y_off, anchor='nw', image=screenshot_tk)
            canvas.create_image(overlay_cx + x_off, overlay_cy + y_off, image=overlay_tk)
            if pygame.mixer.music.get_busy():
                root.after(FRAME_MS, frame)
            else:
                try:
                    root.destroy()
                except:
                    pass

        root.after(80, frame)
        try:
            root.mainloop()
        except Exception as e:
            # if the UI loop error than make sure music stops and we exit cleanly
            try:
                pygame.mixer.music.stop()
            except:
                pass
            print("tkinter mainloop ended:", e)

    finally:
        _running_lock.release()

def on_click_listener(x, y, button, pressed):
    # trigger only on press (not release)
    if not pressed:
        return
    # choose random media
    mp3 = choose_random_file(MUSIC_DIR, {'.mp3'})
    png = choose_random_file(PHOTO_DIR, {'.png', '.png'})
    if mp3 is None:
        print(f"No .mp3 found in {MUSIC_DIR}")
        return
    if png is None:
        print(f"No .png found in {PHOTO_DIR}")
        return

    # spawn a thread to run the effect (so listener keeps working)
    # the effect function itself will prevent re-entry with a lock
    t = threading.Thread(target=run_effect_once, args=(mp3, png), daemon=True)
    t.start()

def start_listening():
    # start mouse listener in main thread, keyboard listener only to catch ESC globally if you want
    # NOTE: we are not suppressing events-ESC inside overlay closes it because overlay has focus.
    with mouse.Listener(on_click=on_click_listener) as m_listener:
        print("Listening for clicks. Click anywhere to trigger effect. Ctrl+C to quit.")
        m_listener.join()

if __name__ == "__main__":
    # quick idiot checks
    if not os.path.isdir(MUSIC_DIR):
        print(f"create a folder named '{MUSIC_DIR}' and drop .mp3 files in it.")
    if not os.path.isdir(PHOTO_DIR):
        print(f"create a folder named '{PHOTO_DIR}' and drop .png files in it.")

    try:
        start_listening()
    except KeyboardInterrupt:
        print("exiting.")
