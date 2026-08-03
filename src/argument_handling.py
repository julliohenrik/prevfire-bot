import logging
import argparse

log = logging.getLogger(__name__)

class InvalidStateError(Exception):
	pass

class InvalidThresholdError(Exception):
	pass

def get_parse() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Robot Entry Point")

	_ = parser.add_argument(
			"-s", "--start", 
			help="set starting state: idle (default), patrol",
			type=str, 
			default="idle"
			)
	_ = parser.add_argument(
			"-m", "--model",
			help="set vision's AI",
			type=str, 
			default="default-fd_ncnn_model"
			)
	_ = parser.add_argument(
			"-t", "--threshold",
			help="set minimum threshold for object detection",
			type=float, 
			default=0.5
			)
	_ = parser.add_argument(
			"-c", "--camera",
			help="usb interface ID",
			type=int, 
			default=0
			)
	_ = parser.add_argument(
			"-rw", "--resWidth",
			help="camera width",
			type=int, 
			default=1280
			)
	_ = parser.add_argument(
			"-rh", "--resHeight",
			help="camera height",
			type=int, 
			default=720
			)
	_ = parser.add_argument(
			"-o", "--convert",
			help="convert pt to ncnn model",
			action="store_true"
			)

	return parser.parse_args()

def eval(args: argparse.Namespace) -> None:
	if args.start == "idle":
		log.info("Initiating in IDLE state")
	elif args.start == "patrol":
		log.info("Initiating in PATROL state")
	else:
		raise InvalidStateError(f"{args.start}")

	if args.threshold > 1:
		raise InvalidThresholdError("Must not be greater than 1")
	elif args.threshold < 0:
		raise InvalidThresholdError("Must not be less than 0")
