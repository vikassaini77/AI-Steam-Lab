from app.services.physics_engine import PhysicsEngine


def test_free_fall():
    res = PhysicsEngine.solve_free_fall(height=50.0, mass=1.0, gravity=9.81)

    assert "parameters" in res
    assert "series" in res

    assert res["time_of_flight"] > 0
    assert "final_velocity" in res


def test_pendulum():
    res = PhysicsEngine.solve_pendulum(
        length=2.5, angle_deg=45.0, mass=1.2, gravity=9.81, damping=0.0
    )

    assert res["theoretical_period"] > 0
    assert res["theoretical_frequency"] > 0


def test_collision():
    res = PhysicsEngine.solve_collision(
        mass_a=2.0, mass_b=1.5, vel_a=5.0, vel_b=-3.0, collision_type="Elastic"
    )

    assert res["final"]["momentum"] == 5.5  # (2.0 * 5.0) + (1.5 * -3.0) = 10.0 - 4.5 = 5.5
    assert res["energy_loss_joules"] >= 0.0
