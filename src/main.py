## native
import sys
import os
import multiprocessing
import threading
from threading import Thread
import signal
import logging
import atexit
import termios
from logging.handlers import RotatingFileHandler, QueueListener
from pathlib import Path
from typing import Any, override

## third party
from prompt_toolkit.patch_stdout import patch_stdout

## custom
import arg_parse as argp
import command_handling as cmd
import vision as vsn

ROOT_DIR: Path = Path(__file__).resolve().parent.parent
th_exit = threading.Event()
mp_exit = multiprocessing.Event()

log = logging.getLogger(__name__)

## Basic logging config to print logs in sys.stdout and in a log file
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

## Prompt Toolkit changes how the terminal is displayed.
## It is important to restore the default settings of the terminal after exiting the program
def _restore_terminal():
	termios.tcsetattr(_stdin_fd, termios.TCSADRAIN, _original_term_settings)

_ = atexit.register(_restore_terminal)

## This class overrides the Thread's run and join functions so that a subthread raises an exception to the main thread
class PropagatingThread(Thread):
	@override
	def run(self):
		self.exc = None
		try:
			if hasattr(self, '_Thread__target'):
				self.ret = self._Thread__target(*self._Thread__args, **self._Thread__kwargs)
			else:
				self.ret = self._target(*self._args, **self._kwargs)
		except BaseException as e:
			self.exc = e

	@override
	def join(self, timeout=None):
		super(PropagatingThread, self).join(timeout)
		if self.exc:
			raise self.exc
		return self.ret

## This defines the behavior of the KeyboardInterrupt so that all processes and threads exits gracefully
def sigint_handling(signum, frame) -> None:
	log.info("Shutting down...\n")
	th_exit.set()
	mp_exit.set()

def main():
	_ = signal.signal(signal.SIGINT, sigint_handling)

	with patch_stdout(raw=True):
		conf_log()

		argv = argp.get_args()	
		try:
			argp.eval(argv)
		except argp.InvalidStateError as e:
			log.warning(f"Invalid state: '{e}'. Fallback to 'IDLE'")
			argv.start = "idle"
		except argp.InvalidThresholdError as e:
			log.warning(f"Invalid detection threshold: {e}. Fallback to '0.5'")
			argv.threshold = .5

		model_path: Path = ROOT_DIR / "models" / argv.model
		log_queue: multiprocessing.Queue[Any] = multiprocessing.Queue()
		listener = QueueListener(log_queue, *log.handlers)
		listener.start()

		threading.Thread(target=cmd.handling, args=(th_exit,), daemon=True).start()

		vision = PropagatingThread(
			target=vsn.init_vision,
			args=(
				model_path,
				argv.convert,
				argv.threshold,
				argv.camera,
				argv.resWidth,
				argv.resHeight,
				th_exit,
				log_queue,
				),
			daemon=False
		)

		vision.start()
		try:
			vision.join()
		except Exception as e:
			log.fatal(f"Failed to start Vision: {e}")
			os.kill(os.getpid(), signal.SIGINT)

		while not th_exit.is_set():
			_ = th_exit.wait(1)

		listener.stop()

if __name__ == "__main__":
	main()
