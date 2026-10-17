from logging.handlers import QueueHandler
from pathlib import Path
from time import sleep
from typing import Any
from ultralytics import YOLO
import cv2
import logging
import sys
import stream_yolo

log = logging.getLogger(__name__)

def init_vision(
	model_path: Path,
	convert: bool,
	min_thresh: float,
	cam_id: int,
	res_width: int,
	res_height: int,
	stream: bool,
	exit_event,
	log_queue,
	result_q=None,
) -> None:

	log.addHandler(QueueHandler(log_queue))

	try:
		tries = 1
		for n in range(tries):
			try:
				model = load_model(model_path, convert)
				log.info(f"Loading model: {model.names}")
				break

			except FileNotFoundError as e:
				log.error(f"{e}")
				model_path = model_path.parent / "default_ncnn_model"
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

				if (n < tries-1):
					log.error(f"{e}. Retrying in 10 seconds")
					exit_event.wait(10)
		else:
			raise Exception(f"Unreachable camera index (usb{cam_id})")

		if (stream==True):
			stream_yolo.start_server()

		parse_detections(model, cap, min_thresh, exit_event, stream, result_q)

	except Exception:
		log.exception("Vision process crashed")
		sys.exit(1)


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
	## use this instead if extra speed is desired in cost of accuracy
	#model.export(format="ncnn", int8=True)
	model_ncnn: YOLO = YOLO(model_ncnn_name, task="detect")

	log.info("Using converted ncnn model")

	return model_ncnn


def init_capture(camera_id: int, res_w: int, res_h: int) -> cv2.VideoCapture:

	## camera_id should be 0 or 1 in the pi
	## depends on which usb interface is plugged in
	cap: cv2.VideoCapture = cv2.VideoCapture(camera_id)

	if not cap.isOpened():
		raise IndexError(f"Could not open camera on interface {camera_id}")

	_ = cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(res_w))
	_ = cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(res_h))
	
	return cap


def _drain_latest(q) -> None:
	## Clears out any stale result still sitting in the queue, so the one
	## we're about to put is always the only (and therefore newest) thing
	## in it.
	while True:
		try:
			q.get_nowait()
		except Exception:
			break


def parse_detections(model: YOLO, cap: cv2.VideoCapture, min_thresh: float, exit_event, stream: bool = False, result_q=None) -> None:
	consecutive_detections: int = 0
	required_consecutive: int = 5

	log.debug("Starting detections parsing.")

	while not exit_event.is_set():
		ret: bool
		frame: Any
		ret, frame = cap.read()

		if not ret:
			log.warning("Frame dropped or camera disconnected")
			break  # Or attempt to reconnect

		results = model(frame, verbose=False)
		results_list = list(results)

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
			log.info(f"consecutive detections: {consecutive_detections}")
			if consecutive_detections >= required_consecutive:
				log.info(f"\nFIRE DETECTED (Confidence: {confidence:.1f})\n")

		else:
			consecutive_detections = 0

		if result_q is not None:
			is_fire_confirmed: bool = consecutive_detections >= required_consecutive
			reported_confidence: float = confidence if fire_detected_this_frame else 0.0

			_drain_latest(result_q)
			try:
				result_q.put_nowait((is_fire_confirmed, reported_confidence))
			except Exception:
				pass

		if stream:
			annotated_frame = results_list[0].plot()
			ret_encode, buffer = cv2.imencode('.jpg', annotated_frame)
			if ret_encode:
				stream_yolo.update_stream(buffer.tobytes())

		sleep(0.05)
