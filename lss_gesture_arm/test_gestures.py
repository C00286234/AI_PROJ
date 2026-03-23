import cv2
import config
from gesture_recogniser import GestureRecogniser

r = GestureRecogniser()
r.start()
cap = cv2.VideoCapture(config.CAMERA_GESTURE_INDEX)

while True:
    ret, frame = cap.read()
    if not ret:
        continue
    result = r.process_frame(frame)
    display = r.draw_landmarks(frame, result)
    cv2.imshow("Gesture Test  |  Press Q to quit", display)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
