READ THIS PLEASE PEOPLE.
THE ONLY THING DONE HERE IS THE GESTURES.
test_gestures.py                                                                                            │
      ├── gesture_recogniser.py   ← does all the work                                                         │       │
      │       └── config.py       ← reads CAMERA_GESTURE_INDEX and GESTURE_STABLE_FRAMES
      │
      └── config.py               ← reads CAMERA_GESTURE_INDEX directly
test_gestures.py — opens the camera, loops, passes each frame to the recogniser, shows the result window. That's it.
gesture_recogniser.py — Downloads the model on first run, runs MediaPipe on every frame, classifies finger positions into gesture names, applies the stability filter
config.py — just supplies constants (camera index = 0, stable frames = 8)


REQUIREMENTS: TURN ON YOUR CAMERA AND TEST THE GESTURES. THE GESTURES ARE IN gesture_recogniser.py
GESTURES TO TEST:
  ┌─────┬──────────────────────────────────────────┬────────────────┐
  │  #  │                Show this                 │ Should display │
  ├─────┼──────────────────────────────────────────┼────────────────┤
  │ 1   │ All 5 fingers open, palm facing camera   │ OPEN_PALM      │
  ├─────┼──────────────────────────────────────────┼────────────────┤
  │ 2   │ Make a fist                              │ FIST           │
  ├─────┼──────────────────────────────────────────┼────────────────┤
  │ 3   │ Peace sign ✌ (index + middle up)         │ PEACE         │
  ├─────┼──────────────────────────────────────────┼────────────────┤
  │ 4   │ Thumbs up 👍                             │ THUMBS_UP      │
  ├─────┼──────────────────────────────────────────┼────────────────┤
  │ 5   │ Point ☝ (index finger only up)           │ POINT         │
  ├─────┼──────────────────────────────────────────┼────────────────┤
  │ 6   │ Three fingers up (index + middle + ring) │ THREE_FINGERS  │
  └─────┴──────────────────────────────────────────┴────────────────┘
  
ADJUST THE PARAMETERS IF IT DOESNT WORK
  
