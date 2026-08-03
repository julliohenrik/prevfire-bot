# import time
import sys
import os
# import gpiozero

# ignore this
os.environ["QT_LOGGING_RULES"] = "*.warning=false"
os.environ["QT_QPA_PLATFORM"] = "xcb"

from ultralytics import YOLO
import cv2

min_thresh = 0.5    # minimum detection threshold
# res_w, res_h = 1280, 720

# gpio_pin = 14       # which pin we are using for cam
# led = gpiozero.LED(gpio_pin)

## initial config
# model selection
version = input("Which model version to use? [1/2/3]: ")
filename = f"fire-detect-ver{version}.pt" 
model_path = ROOT / "models" / filename

if not os.path.exists(model_path):
  print(f'ERROR: invalid or not found model path: "{model_path}"')
  sys.exit()

model = YOLO(model_path, task="detect")
labels = model.names

print(f"INFO: loading model: {labels}")

# image/video source selection
frame_source = input("Which frame source to use? [camera/image]: ")

if "ca" in frame_source:
  frame_source = input("Set usb camera source [usb0/usb1]: ")
  cam_idx = int(frame_source[3:])
  frame = cv2.VideoCapture(cam_idx)
  ret = frame.set(3, res_w)
  ret = frame.set(4, res_h)

elif "im" in frame_source:
  frame_source = ROOT / "assets" / input("Set image name and extension: ")
  if not os.path.exists(frame_source):
    print(f'ERROR: invalid image path: "{frame_source}"')
    sys.exit()

  frame = cv2.imread(frame_source) 

  if frame is None:
    print(f'ERROR: unable to decode or read the image file: {frame_source}')
    sys.exit()

else:
  print("ERROR: source not supported. Needs to be camera/image.")
  sys.exit()

results = model(frame)
detections = results[0].boxes

print(f"INFO: Processing complete. Found {len(detections)} potential objects.")

## iteration of potential objects
for i in range(len(detections)):
  class_idx = int(detections[i].cls.item())
  class_name = labels[class_idx]

  confidence = detections[i].conf.item()

  if confidence > min_thresh:
    print(f"INFO: {class_name.upper()} DETECTED with confidence {confidence:.2f}")

annotated_frame = results[0].plot()
cv2.imshow("YOLO Test Result", annotated_frame)
cv2.waitKey(0) 
cv2.destroyAllWindows()
