try:
    from gpiozero import Motor
except ImportError:
    class Motor:
        def __init__(self, forward=None, backward=None, enable=None, pwm=True):
            self.forward_pin = forward
            self.backward_pin = backward
            self.enable_pin = enable
            self.value = 0.0

        def forward(self, speed=1.0):
            self.value = speed

        def backward(self, speed=1.0):
            self.value = -speed

        def stop(self):
            self.value = 0.0

        def close(self):
            pass


class DCMotor:
    def __init__(self, forward_pin, backward_pin, enable_pin=None, name=""):
        self.name = name
        self._motor = Motor(forward=forward_pin, backward=backward_pin,
                             enable=enable_pin, pwm=True)

    def set_speed(self, speed_frac):
        # speed_frac in [-1, 1]: sign = direction, magnitude = PWM duty cycle.
        speed_frac = max(-1.0, min(1.0, speed_frac))
        if speed_frac > 0:
            self._motor.forward(speed_frac)
        elif speed_frac < 0:
            self._motor.backward(-speed_frac)
        else:
            self._motor.stop()

    def stop(self):
        self._motor.stop()

    def close(self):
        self._motor.close()


class DifferentialDrive:
    def __init__(self, left_motor, right_motor, invert_right=True):
        self.left = left_motor
        self.right = right_motor
        self.invert_right = invert_right

    def drive(self, left_frac, right_frac):
        self.left.set_speed(left_frac)
        self.right.set_speed(-right_frac if self.invert_right else right_frac)

    def stop(self):
        self.left.stop()
        self.right.stop()

    def close(self):
        self.left.close()
        self.right.close()
