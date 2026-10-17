import logging
import queue
import time

try:
	from gpiozero import DigitalInputDevice
except ImportError:
	class DigitalInputDevice:
		def __init__(self, pin, *a, **k):
			self.pin = pin
			self.value = 1  # defaults to "no line"

		def close(self):
			pass

from motor_control import DCMotor, DifferentialDrive

log = logging.getLogger(__name__)

# (BCM numbering)
LEFT_MOTOR_PINS = dict(forward_pin=17, backward_pin=27, enable_pin=None)
RIGHT_MOTOR_PINS = dict(forward_pin=23, backward_pin=24, enable_pin=None)
LEFT_SENSOR_PIN = 5
RIGHT_SENSOR_PIN = 6

LOOP_HZ = 50
LOOP_PERIOD = 1.0 / LOOP_HZ

BASE_SPEED = 0.3
TURN_SPEED_OUTER = 0.3
TURN_SPEED_INNER = 0.1

LINE_LOST_TIMEOUT = 0.6
FIRE_CONFIDENCE_THRESHOLD = 0.6


class Mode:
	FOLLOW_LINE = "follow_line"
	PAUSED = "paused"


log = logging.getLogger(__name__)


def read_sensors(left_sensor, right_sensor):
	left_on = left_sensor.value == 0
	right_on = right_sensor.value == 0
	return left_on, right_on


def drain_latest(q):
	# Pull the newest item off a queue, discarding anything older.
	item = None
	while True:
		try:
			item = q.get_nowait()
		except queue.Empty:
			break
	return item


def run(vision_q=None, quit_event=None):
	left_sensor = DigitalInputDevice(LEFT_SENSOR_PIN)
	right_sensor = DigitalInputDevice(RIGHT_SENSOR_PIN)

	left_motor = DCMotor(**LEFT_MOTOR_PINS, name="left")
	right_motor = DCMotor(**RIGHT_MOTOR_PINS, name="right")
	drive = DifferentialDrive(left_motor, right_motor)

	mode = Mode.FOLLOW_LINE
	fire_detected, fire_confidence = False, 0.0
	last_seen_line = time.monotonic()

	log.info("arbiter starting, mode=%s", mode)

	def should_quit():
		return quit_event is not None and quit_event.is_set()

	try:
		while not should_quit():
			tick_start = time.monotonic()

			if vision_q is not None:
				latest = drain_latest(vision_q)
				if latest is not None:
					fire_detected, fire_confidence = latest

			left_on, right_on = read_sensors(left_sensor, right_sensor)
			fire_flag = fire_detected and fire_confidence >= FIRE_CONFIDENCE_THRESHOLD
			line_visible = left_on or right_on

			if mode == Mode.FOLLOW_LINE:
				if fire_flag:
					drive.stop()
					mode = Mode.PAUSED
					log.info("PAUSED: fire detected (confidence=%.2f)", fire_confidence)
				elif line_visible:
					last_seen_line = tick_start
					if left_on and right_on:
						drive.drive(BASE_SPEED, BASE_SPEED)
					elif left_on:
						# tape has drifted toward center/left -> steer left
						drive.drive(TURN_SPEED_INNER, TURN_SPEED_OUTER)
					else:
						# tape has drifted toward center/right -> steer right
						drive.drive(TURN_SPEED_OUTER, TURN_SPEED_INNER)
				elif tick_start - last_seen_line > LINE_LOST_TIMEOUT:
					drive.stop()
					mode = Mode.PAUSED
					log.info("PAUSED: line lost")
				# else: brief gap (e.g. a crossing) -- keep going on the last command

			elif mode == Mode.PAUSED:
				if not fire_flag and line_visible:
					mode = Mode.FOLLOW_LINE
					last_seen_line = tick_start
					log.info("RESUMED: line reacquired, no fire")
				# else: stay stopped, nothing to do this tick

			elapsed = time.monotonic() - tick_start
			time.sleep(max(0.0, LOOP_PERIOD - elapsed))

	except KeyboardInterrupt:
		log.info("shutting down (keyboard interrupt)")
	else:
		log.info("shutting down (quit command)")
	finally:
		drive.stop()
		drive.close()
		left_sensor.close()
		right_sensor.close()


if __name__ == "__main__":
	run(vision_q=None, quit_event=None)
