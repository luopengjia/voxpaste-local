#!/usr/bin/env python3
"""Print pynput mouse button names for choosing a VoxPaste trigger button."""

from pynput import mouse


def on_click(x, y, button, pressed):
    action = "press" if pressed else "release"
    print(f"{action}: {button!r} ({type(button).__name__})")
    if button == mouse.Button.right and not pressed:
        return False


print("Click a mouse button. Release right button to quit.")
with mouse.Listener(on_click=on_click) as listener:
    listener.join()
