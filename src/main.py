#!/bin/python

## native
import sys
import multiprocessing
import threading
import signal
import logging
import atexit
import termios
from logging.handlers import RotatingFileHandler, QueueListener
from pathlib import Path
from typing import Any

## third party
from prompt_toolkit.patch_stdout import patch_stdout

## custom
import arg_parse as argp
import arbiter as arb
import command_handling as cmd
import vision as vsn

ROOT_DIR: Path = Path(__file__).resolve().parent.parent

shutdown_event = threading.Event()
vision_exit_event = multiprocessing.Event()

log = logging.getLogger(__name__)

def conf_log(log_file: str = "prevfire.log"):
	root = logging.getLogger()
	root.setLevel(logging.DEBUG)
	fmt = logging.Formatter("[%(levelname)s] %(message)s")

	console = logging.StreamHandler(sys.stdout)
	console.setFormatter(fmt)
	console.setLevel(logging.INFO)
	root.addHandler(console)

	file_handler = RotatingFileHandler(log_file, maxBytes=2_000_000)
	file_handler.setFormatter(fmt)
	file_handler.setLevel(logging.DEBUG)
	root.addHandler(file_handler)

_stdin_fd = sys.stdin.fileno()
_original_term_settings = termios.tcgetattr(_stdin_fd)

def _restore_terminal():
	termios.tcsetattr(_stdin_fd, termios.TCSADRAIN, _original_term_settings)

_ = atexit.register(_restore_terminal)

def request_shutdown() -> None:
	shutdown_event.set()
	vision_exit_event.set()

def sigint_handling(signum, frame) -> None:
	log.info("Shutting down...\n")
	request_shutdown()

def main():
	_ = signal.signal(signal.SIGINT, sigint_handling)

	with patch_stdout(raw=True):
		conf_log()

		argv = argp.get_args()	
		try:
			argp.eval(argv)
		except argp.InvalidStateError as e:
			log.warning(f"Invalid state: '{e}'. Fallback to 'IDLE'")
			argv.state = "idle"
		except argp.InvalidThresholdError as e:
			log.warning(f"Invalid detection threshold: {e}. Fallback to '0.5'")
			argv.threshold = .5

		model_path: Path = ROOT_DIR / "models" / argv.model
		log_queue: multiprocessing.Queue[Any] = multiprocessing.Queue()
		## Carries (fire_detected: bool, confidence: float)
		vision_result_q: multiprocessing.Queue = multiprocessing.Queue(maxsize=1)
		listener = QueueListener(log_queue, *log.handlers)
		listener.start()

		threading.Thread(target=cmd.handling, args=(shutdown_event,), daemon=True).start()

		vision_process = multiprocessing.Process(
			target=vsn.init_vision,
			args=(
				model_path,
				argv.convert,
				argv.threshold,
				argv.camera,
				argv.resWidth,
				argv.resHeight,
				argv.stream,
				vision_exit_event,
				log_queue,
				vision_result_q,
			),
			daemon=True,
		)
		vision_process.start()

		arbiter_thread = threading.Thread(
			target=arb.run,
			kwargs=dict(vision_q=vision_result_q, quit_event=shutdown_event),
			daemon=True,
		)
		arbiter_thread.start()

		try:
			while not shutdown_event.is_set():
				if not vision_process.is_alive():
					if vision_process.exitcode:
						log.fatal(f"Vision process exited unexpectedly (code {vision_process.exitcode})")
					request_shutdown()
					break
				_ = shutdown_event.wait(1)
		finally:
			request_shutdown()

			arbiter_thread.join(timeout=2)
			if arbiter_thread.is_alive():
				log.warning("Arbiter thread did not stop in time")

			vision_process.join(timeout=5)
			if vision_process.is_alive():
				log.warning("Vision process did not exit in time, terminating")
				vision_process.terminate()
				vision_process.join()

			listener.stop()

if __name__ == "__main__":
	main()
