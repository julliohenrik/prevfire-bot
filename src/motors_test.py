from gpiozero import Robot
from time import sleep

# The Robot class takes tuples of (forward_pin, backward_pin) for each motor
# left=(IN1, IN2), right=(IN3, IN4)
robot = Robot(left=(27, 17), right=(23, 22))

print("Starting motor test sequence...")

print("Moving Forward")
robot.forward()
sleep(0.25)

robot.stop()
sleep(1)

print("Moving Backward")
robot.backward()
sleep(0.25)

robot.stop()
sleep(1)

# Turning left makes the right motor go forward and left motor go backward
print("Turning Left")
robot.left()
sleep(0.25)

robot.stop()
sleep(1)

# Turning right makes the left motor go forward and right motor go backward
print("Turning Right")
robot.right()
sleep(0.25)

robot.stop()
sleep(1)

print("Stopping")
robot.stop()

print("Test complete!")
