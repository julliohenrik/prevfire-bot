from gpiozero import Robot
from time import sleep

# The Robot class takes tuples of (forward_pin, backward_pin) for each motor
# left=(IN1, IN2), right=(IN3, IN4)
robot = Robot(left=(27, 17), right=(23, 22))

print("Starting motor test sequence...")

robot.forward(.2)
sleep(1)

robot.left(.2)
sleep(.5)

robot.backward(.2)
sleep(1)

robot.right(.2)
sleep(.5)

print("Stopping")
robot.stop()
