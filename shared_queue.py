from queue import Queue

# A single global queue used to pass events from capture.py to the GUI.
capture_queue = Queue()
