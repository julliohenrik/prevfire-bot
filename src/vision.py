from pathlib import Path
from time import sleep
from typing import Any
from ultralytics import YOLO
import cv2
import logging

log = logging.getLogger(__name__)

## Suppress Qt warnings for OpenCV
#os.environ["QT_LOGGING_RULES"] = "*.warning=false"
#os.environ["QT_QPA_PLATFORM"] = "xcb"

def init_vision(
	model_path: Path,
	convert: bool,
	min_thresh: float,
	cam_id: int,
	res_width: int,
	res_height: int,
	mp_exit
) -> None:
	
	tries = 1
	for n in range(tries):
		try: 
			model = load_model(model_path, convert)
			log.info(f"Loading model: {model.names}")
			break

		except FileNotFoundError as e:
			log.error(f"{e}")
			model_path = model_path.parent / "default-fd_ncnn_model"
	else:
		raise Exception(f"Failed to start Vision: Invalid or not found model")

	tries = 3
	for n in range(tries):
		try:
			cap = init_capture(cam_id, res_width, res_height)
			break

		except IndexError as e:
			if 'cap' in locals() and cap.isOpened():
				cap.release()
			cv2.destroyAllWindows()

			if (n < tries-1):
				log.error(f"{e}. Retrying in 10 seconds")
				mp_exit.wait(10)
	else:
		raise Exception(f"Unreachable camera index (usb{cam_id})")

	parse_detections(model, cap, min_thresh, mp_exit)


def load_model(model_path: Path, convert: bool) -> YOLO:
	if not model_path.exists():
		raise FileNotFoundError(f"Invalid or not found model path: '{model_path}'. Trying fallback")

	model: YOLO = YOLO(str(model_path), task="detect")

	model_ncnn_path: Path = model_path.parent / f"{model_path.stem}_ncnn_model"

	if (convert):
		if (model_ncnn_path / "model.ncnn.param").is_file():
			model_ncnn = YOLO(model_ncnn_path, task="detect")
			log.info("Using existing ncnn model")
			return model_ncnn
		else:
			return convert_model(model)

	return model

def convert_model(model_pt: YOLO) -> YOLO:
	model_ncnn_name: str = model_pt.export(format="ncnn", imgsz=640)
	# use this instead if extra speed is desired in cost of accuracy
	# model.export(format="ncnn", int8=True)
	model_ncnn: YOLO = YOLO(model_ncnn_name, task="detect")

	log.info("Using converted ncnn model")

	return model_ncnn


def init_capture(camera_id: int, res_w: int, res_h: int) -> cv2.VideoCapture:

	# camera_id = 0 or 1
	# depends on which usb interface is plugged in
	cap: cv2.VideoCapture = cv2.VideoCapture(camera_id)

	if not cap.isOpened():
		raise IndexError(f"Could not open camera on interface {camera_id}")

	_ = cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(res_w))
	_ = cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(res_h))

	return cap


def parse_detections(model: YOLO, cap: cv2.VideoCapture, min_thresh: float, mp_exit: Event) -> None:
	consecutive_detections: int = 0
	required_consecutive: int = 5

	while not (mp_exit and mp_exit.is_set()):
		ret: bool
		frame: Any
		ret, frame = cap.read()

		if not ret:
			log.warning("Frame dropped or camera disconnected")
			break  # Or attempt to reconnect

		results: list[Any] = model(frame, stream=True, verbose=False)

		if not results:
			continue

		detections: Any = results[0].boxes
		fire_detected_this_frame: bool = False

		for i in range(len(detections)):
			confidence: float = float(detections[i].conf.item())

			if confidence > min_thresh:
				fire_detected_this_frame = True
				break

		if fire_detected_this_frame:
			consecutive_detections += 1
			if consecutive_detections >= required_consecutive:
				log.info(f"\nFIRE DETECTED (Confidence > {min_thresh:.2f})\n")
				# TODO: send signal to arbiter

		else:
			consecutive_detections = 0

		sleep(0.20)
