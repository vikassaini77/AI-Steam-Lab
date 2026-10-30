import numpy as np


class PhysicsEngine:
    def __init__(self):
        self.history = []

    def calculate_velocity(self, p1, p2, dt):
        if dt == 0:
            return 0.0
        return float(np.linalg.norm(np.array(p2) - np.array(p1)) / dt)

    def calculate_acceleration(self, v1, v2, dt):
        if dt == 0:
            return 0.0
        return float((v2 - v1) / dt)

    def harmonic_motion(self, t, A, omega, phi):
        return float(A * np.cos(omega * t + phi))

    @staticmethod
    def solve_free_fall(height: float, mass: float = 1.0, gravity: float = 9.81):
        """
        Solves free-fall kinematic equations.
        """
        tof = np.sqrt(2 * height / gravity)
        v_final = np.sqrt(2 * gravity * height)
        time_steps = np.linspace(0, tof, 20)
        series = [
            {
                "time": round(float(t), 3),
                "position": round(float(max(0.0, height - 0.5 * gravity * t**2)), 3),
                "velocity": round(float(gravity * t), 3),
            }
            for t in time_steps
        ]
        return {
            "parameters": {"height": height, "mass": mass, "gravity": gravity},
            "time_of_flight": round(float(tof), 4),
            "final_velocity": round(float(v_final), 4),
            "series": series,
        }

    @staticmethod
    def solve_pendulum(
        length: float, angle_deg: float, mass: float = 1.0, gravity: float = 9.81, damping: float = 0.0
    ):
        """
        Solves theoretical pendulum period and frequency.
        """
        period = 2 * np.pi * np.sqrt(length / gravity)
        frequency = 1.0 / period
        return {
            "theoretical_period": round(float(period), 4),
            "theoretical_frequency": round(float(frequency), 4),
            "parameters": {
                "length": length,
                "angle_deg": angle_deg,
                "mass": mass,
                "gravity": gravity,
                "damping": damping,
            },
        }

    @staticmethod
    def solve_collision(
        mass_a: float, mass_b: float, vel_a: float, vel_b: float, collision_type: str = "Elastic"
    ):
        """
        Solves 1D collision momentum and energy conservation.
        """
        p_init = mass_a * vel_a + mass_b * vel_b
        ke_init = 0.5 * mass_a * vel_a**2 + 0.5 * mass_b * vel_b**2

        if collision_type.lower() == "elastic":
            v_a_final = ((mass_a - mass_b) * vel_a + 2 * mass_b * vel_b) / (mass_a + mass_b)
            v_b_final = ((mass_b - mass_a) * vel_b + 2 * mass_a * vel_a) / (mass_a + mass_b)
        else:  # Inelastic
            v_common = p_init / (mass_a + mass_b)
            v_a_final = v_common
            v_b_final = v_common

        ke_final = 0.5 * mass_a * v_a_final**2 + 0.5 * mass_b * v_b_final**2
        energy_loss = max(0.0, ke_init - ke_final)

        return {
            "initial": {"momentum": round(float(p_init), 2), "kinetic_energy": round(float(ke_init), 2)},
            "final": {
                "momentum": round(float(p_init), 2),
                "vel_a": round(float(v_a_final), 2),
                "vel_b": round(float(v_b_final), 2),
                "kinetic_energy": round(float(ke_final), 2),
            },
            "energy_loss_joules": round(float(energy_loss), 4),
        }
