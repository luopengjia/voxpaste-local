#!/usr/bin/env python3
"""Print pynput keyboard names for choosing a VoxPaste trigger key."""

from pynput import keyboard


def on_press(key):
    print(f"press: {key!r} ({type(key).__name__})")


def on_release(key):
    print(f"release: {key!r}")
    if key == keyboard.Key.esc:
        return False


print("Press a key. Press Esc to quit.")
with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()
