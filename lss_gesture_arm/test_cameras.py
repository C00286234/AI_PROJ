import cv2
import time
import config

gesture_cap   = cv2.VideoCapture(config.CAMERA_GESTURE_INDEX)
workspace_cap = cv2.VideoCapture(config.CAMERA_VISION_INDEX)
time.sleep(2)  # allow USB webcam to initialise

print(f"Gesture camera (index {config.CAMERA_GESTURE_INDEX}): {gesture_cap.isOpened()}")
print(f"Workspace camera (index {config.CAMERA_VISION_INDEX}): {workspace_cap.isOpened()}")
print("Press Q to quit.")

while True:
    ret_g, gesture_frame   = gesture_cap.read()
    ret_w, workspace_frame = workspace_cap.read()

    if ret_g:
        cv2.putText(gesture_frame, "GESTURE CAM (you)", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow("Gesture Camera", gesture_frame)

    if ret_w:
        cv2.putText(workspace_frame, "WORKSPACE CAM (arm)", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)
        cv2.imshow("Workspace Camera", workspace_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

gesture_cap.release()
workspace_cap.release()
cv2.destroyAllWindows()
