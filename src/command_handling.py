import os
import signal
import logging
import threading
from prompt_toolkit import PromptSession

log = logging.getLogger(__name__)

def handling(exit: threading.Event):
	session = PromptSession(">>> ")
	while not exit.is_set():
		try:
			cmd = session.prompt()
		except (KeyboardInterrupt, EOFError):
			os.kill(os.getpid(), signal.SIGINT)
			break

		cmd = cmd.strip().lower()

		if cmd == "exit" or cmd == "quit" or cmd == "stop":
			os.kill(os.getpid(), signal.SIGINT)
		else:
			log.error("Invalid command")
