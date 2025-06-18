# me - this DAT
#
# frame - the current frame
# state - True if the timeline is paused
#
# Make sure the corresponding toggle is enabled in the Execute DAT.
seq = 0

def onStart():
    print("on start")
    return


def onCreate():
    print("on create")
    return


def onExit():
    print("on exit")
    return


def onFrameStart(frame):
    print("on frame start")
    return


def onFrameEnd(frame):
    global seq
    seq += 1
    if seq % 10 == 1:
        print(f"on frame({seq}) end")
    return


def onPlayStateChange(state):
    print("on playstate change")
    return


def onDeviceChange():
    print("on device change")
    return


def onProjectPreSave():
    print("on project pre save")
    return


def onProjectPostSave():
    print("on project post save")
    return

