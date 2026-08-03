## This is the master script: the entry point of the robot
##
## It manages the robot's current state, manual override, 
## and all other branches: vision, motors, and system monitoring

import os
import sys
import signal
import threading
from threading import Lock
import multiprocessing
import argparse
import logging
from logging.handlers import RotatingFileHandler
import queue
import atexit
import termios
from pathlib import Path
import vision
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

CURRENT_SCRIPT: Path = Path(__file__).resolve()
ROOT: Path = CURRENT_SCRIPT.parent.parent

stop_event = threading.Event()

_stdin_fd = sys.stdin.fileno()
_original_term_settings = termios.tcgetattr(_stdin_fd)

#### SIGNAL HANDLER ####

def handle_sigint(signum, frame) -> None:
	log.info("Shutting down...\n")
	stop_event.set()

	if _prompt_session is not None and _prompt_session.app.is_running:
		_prompt_session.app.exit()

#### TERMINAL SAFETY #### 

def _restore_terminal():
	termios.tcsetattr(_stdin_fd, termios.TCSADRAIN, _original_term_settings)

_ = atexit.register(_restore_terminal)

#### LOG SETUP ####

log = logging.getLogger(__name__)

def setup_logging(log_file: str = "prevfire.log"):
	root = logging.getLogger()
	root.setLevel(logging.DEBUG)
	fmt = logging.Formatter("[%(levelname)s] %(message)s")

	console = logging.StreamHandler(sys.stdout)
	console.setFormatter(fmt)
	console.setLevel(logging.INFO)
	root.addHandler(console)

	file_handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3)
	file_handler.setFormatter(fmt)
	file_handler.setLevel(logging.DEBUG)
	root.addHandler(file_handler)

#### VISION PROCESS ENTRY ####
 
def _vision_entry(**kwargs) -> None:
	"""
	Runs inside the child process. Responsible for making the child behave
	well on its own before handing off to vision.start().
	"""
	# The parent owns the shutdown decision. Ignore raw SIGINT here so we
	# only stop when the parent explicitly tells us to via mp_stop_event --
	# avoids two independent, racing shutdown paths.
	_ = signal.signal(signal.SIGINT, signal.SIG_IGN)
 
	# fork() copied the parent's already-configured root logger (console +
	# RotatingFileHandler). Strip that and set up our own file so the two
	# processes never write to the same rotating file concurrently.
	root = logging.getLogger()
	for h in list(root.handlers):
		root.removeHandler(h)
	setup_logging(log_file="prevfire-vision.log")
 
	try:
		vision.start(**kwargs)
	except Exception:
		logging.getLogger(__name__).exception("Vision process crashed")
		raise  # non-zero exitcode lets the parent detect the failure

#### COMMAND HANDLING ####

cmd_queue = queue.Queue()

class SharedState:
	def __init__(self):
		self._lock: Lock = threading.Lock()
		self._mode: str = "auto"

	def set_mode(self, mode: str):
		with self._lock:
			self._mode = mode

	def get_mode(self):
		with self._lock:
			return self._mode

state = SharedState()

_prompt_session: PromptSession | None = None

def get_cmd():
	global _prompt_session
	_prompt_session = PromptSession()
	while not stop_event.is_set():
		try:
			raw = _prompt_session.prompt(">>> ")
		except (KeyboardInterrupt, EOFError):
			os.kill(os.getpid(), signal.SIGINT)
			break

		raw = raw.strip().lower()
		cmd_queue.put(raw)
		if raw == "exit":
			break

def handle_cmd():
	while not stop_event.is_set():
		try:
			cmd = cmd_queue.get(timeout=0.5)
		except queue.Empty:
			continue

		if cmd == "exit":
			#stop_event.set()
			os.kill(os.getpid(), signal.SIGINT)
		elif cmd == "auto":
			state.set_mode("auto")
			log.debug("Set state to AUTO")
		elif cmd == "manual":
			state.set_mode("manual")
			log.debug("Set state to MANUAL")
		else:
			log.error("Invalid command")

#### ARGUMENT HANDLING ####

def parse_args() -> argparse.Namespace:
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

class ThresholdError(Exception):
	pass

def eval_args(args: argparse.Namespace) -> None:
	if args.start == "idle":
		log.info("Initiating in IDLE state")
	elif args.start == "patrol":
		log.info("Initiating in PATROL state")
	else:
		raise ValueError(f"Invalid starting state: '{args.start}'")

	if args.threshold > 1:
		raise ThresholdError("Threshold must not be greater than 1")
	elif args.threshold < 0:
		raise ThresholdError("Threshold must not be less than 0")


def main():
	_ = signal.signal(signal.SIGINT, handle_sigint)

	args: argparse.Namespace = parse_args()

	with patch_stdout(raw=True):
		setup_logging()

		try:
			eval_args(args)
		except ValueError as e:
			log.error(f"{e}. Fallbacking to default 'IDLE'")
			args.start = "idle"
		except ThresholdError as e:
			log.error(f"{e}. Fallbacking to default '0.5'")
			args.threshold = 0.5

		for key, value in vars(args).items():
			log.debug(f"{key} = {value}")

		model_path: Path = ROOT / "models" / args.model

		mp_stop_event = multiprocessing.Event()
 
		vision_process = multiprocessing.Process(
			target=_vision_entry,
			kwargs=dict(
				model_path  = model_path,
				convert     = args.convert,
				min_thresh  = args.threshold,
				cam_id      = args.camera,
				res_width   = args.resWidth,
				res_height  = args.resHeight,
				stop_event  = mp_stop_event,
			),
			daemon=False,
		)

		t1 = threading.Thread(target=get_cmd, daemon=True)
		t2 = threading.Thread(target=handle_cmd, daemon=True)

		try:
			vision_process.start()
		except RuntimeError as e:
			log.fatal(f"{e}")
			sys.exit(1)
		
		t1.start()
		t2.start()

		# Supervisor loop: wakes once a second (or immediately on shutdown),
		# and also notices if the vision process died on its own so a crash
		# doesn't just go unnoticed.
		while not stop_event.is_set():
			if vision_process.exitcode is not None:
				log.error(f"Vision process exited unexpectedly (code={vision_process.exitcode})")
				stop_event.set()
				break
			_ = stop_event.wait(timeout=1.0)
 
		log.info("Stopping vision process...")
		mp_stop_event.set()
		vision_process.join(timeout=5)
		if vision_process.is_alive():
			log.warning("Vision process did not exit in time, terminating")
			vision_process.terminate()
			vision_process.join()

if __name__ == "__main__":
	main()
