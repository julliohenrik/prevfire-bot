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
from logging.handlers import RotatingFileHandler
from pathlib import Path

## third party
from prompt_toolkit.patch_stdout import patch_stdout

## custom
import argument_handling as argh
import command_handling as cmd
import vision as vsn

ROOT_DIR: Path = Path(__file__).resolve().parent.parent
th_exit = threading.Event()
mp_exit = multiprocessing.Event()
logging.basicConfig(
	level=logging.DEBUG,
    format='[%(levelname)s] %(message)s',
    handlers=[
		RotatingFileHandler("prevfire.log", maxBytes=2_000_000),
		logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

_stdin_fd = sys.stdin.fileno()
_original_term_settings = termios.tcgetattr(_stdin_fd)

def _restore_terminal():
	termios.tcsetattr(_stdin_fd, termios.TCSADRAIN, _original_term_settings)

_ = atexit.register(_restore_terminal)

class PropagatingThread(Thread):
    def run(self):
        self.exc = None
        try:
            if hasattr(self, '_Thread__target'):
                # Thread uses name mangling prior to Python 3.
                self.ret = self._Thread__target(*self._Thread__args, **self._Thread__kwargs)
            else:
                self.ret = self._target(*self._args, **self._kwargs)
        except BaseException as e:
            self.exc = e

    def join(self, timeout=None):
        super(PropagatingThread, self).join(timeout)
        if self.exc:
            raise self.exc
        return self.ret

def sigint_handling(signum, frame) -> None:
	log.info("Shutting down...\n")
	th_exit.set()
	mp_exit.set()

def main():
	_ = signal.signal(signal.SIGINT, sigint_handling)

	with patch_stdout(raw=True):
		args = argh.get_parse()	
		try:
			argh.eval(args)
		except argh.InvalidStateError as e:
			log.warning(f"Invalid state: '{e}'. Fallback to 'IDLE'")
			args.start = "idle"
		except argh.InvalidThresholdError as e:
			log.warning(f"Invalid detection threshold: {e}. Fallback to '0.5'")
			args.threshold = .5

		model_path: Path = ROOT_DIR / "models" / args.model

		threading.Thread(target=cmd.handling, args=(th_exit,), daemon=True).start()

		vision = PropagatingThread(
			target=vsn.init_vision,
			args=(
				model_path,
				args.convert,
				args.threshold,
				args.camera,
				args.resWidth,
				args.resHeight,
				mp_exit,
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

if __name__ == "__main__":
	main()
