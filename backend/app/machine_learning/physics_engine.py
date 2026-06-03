import numpy as np

class PhysicsEngine:
    def __init__(self):
        self.history = []

    def calculate_velocity(self, p1, p2, dt):
        if dt == 0: return 0.0
        return np.linalg.norm(np.array(p2) - np.array(p1)) / dt

    def calculate_acceleration(self, v1, v2, dt):
        if dt == 0: return 0.0
        return (v2 - v1) / dt

    def harmonic_motion(self, t, A, omega, phi):
        return A * np.cos(omega * t + phi)
