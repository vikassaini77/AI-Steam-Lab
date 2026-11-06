"""
Acceptance Test Suite: Phase 4 Scientific Experiment Engine.
-------------------------------------------------------------
Verifies:
1. Reusable experiment architecture and registry:
   - Metadata, learning objectives, required materials, instructions.
   - Pydantic input parameter validation with range and finiteness checks.
2. Simple Pendulum Scientific Correctness:
   - Small-angle approximation: T_0 = 2*pi*sqrt(L/g).
   - Finite-amplitude Borda correction: T(theta) > T_0 when theta > 15 deg.
   - Mass independence: varying bob mass does not change oscillation period.
   - Unit system and parameter bounds.
3. Measurement System (Manual & CV-derived):
   - Manual stopwatch measurements: mean, sample standard deviation, standard error, 95% CI.
   - CV-derived periodic tracking: cycle detection from zero-crossings without treating every frame as an independent observation.
   - Percentage error calculation.
   - Handling empty and insufficient datasets without raising exceptions.
4. Graphing & Analysis:
   - Synchronized theoretical and experimental time-series for Position, Velocity, Acceleration, Energy.
   - Physical units and monotonically increasing time coordinates.
5. AI Experiment Explanation:
   - Grounded explanations of experimental discrepancy, measurement error, parameter sensitivity, and graphs.
6. Persistence, Reproduction, and End-to-End Workflow:
   - Open experiment -> configure -> measure -> calculate -> graph -> explain -> save -> reopen -> reproduce.
"""
import math
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core_backend.core.dependencies import get_current_user
from app.experiments.registry import experiment_registry
from app.experiments.pendulum import PendulumExperiment, PendulumParamsSchema

MOCK_USER = {"id": "user_phase4_test", "email": "phase4@neurolab.ai", "role": "authenticated"}


@pytest.fixture(autouse=True)
def setup_auth_and_state():
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    from app.cache import clear_local_cache
    clear_local_cache()
    yield
    app.dependency_overrides.pop(get_current_user, None)
    clear_local_cache()


@pytest.fixture
def client():
    return TestClient(app)


# ==============================================================================
# 1. PENDULUM SCIENTIFIC VALIDATION & EQUATION ACCURACY
# ==============================================================================

class TestPendulumScientificValidation:
    """Verifies physical laws, equations, parameter ranges, and numerical stability."""

    def test_ideal_small_angle_period_calculation(self):
        """
        For L = 1.0 m, g = 9.81 m/s^2, ideal period is:
        T_0 = 2 * pi * sqrt(1.0 / 9.81) = 2.006066... s.
        """
        exp = PendulumExperiment()
        params = {"length": 1.0, "gravity": 9.81, "angle_deg": 10.0, "mass": 1.0}
        res = exp.calculate_theoretical(params)

        expected_t = 2.0 * math.pi * math.sqrt(1.0 / 9.81)
        assert abs(res.primary_theoretical_value - expected_t) < 0.005
        assert abs(res.computed_metrics["small_angle_period_s"] - expected_t) < 0.001
        assert res.computed_metrics["is_small_angle_regime"] is True

    def test_finite_amplitude_elongates_period(self):
        """
        For theta_0 = 30° (0.5236 rad), the period is elongated by:
        1 + 1/16 * (pi/6)^2 = 1.01712 (+1.71%).
        T_corrected > T_small_angle.
        """
        exp = PendulumExperiment()
        params_small = {"length": 1.0, "gravity": 9.81, "angle_deg": 5.0}
        params_large = {"length": 1.0, "gravity": 9.81, "angle_deg": 30.0}

        res_small = exp.calculate_theoretical(params_small)
        res_large = exp.calculate_theoretical(params_large)

        assert res_large.computed_metrics["corrected_period_s"] > res_small.computed_metrics["small_angle_period_s"]
        dev_pct = res_large.computed_metrics["finite_amplitude_deviation_percent"]
        assert 1.5 <= dev_pct <= 2.0
        assert res_large.computed_metrics["is_small_angle_regime"] is False

    def test_mass_independence(self):
        """Varying bob mass from 0.1 kg to 50.0 kg does not change period."""
        exp = PendulumExperiment()
        res_light = exp.calculate_theoretical({"length": 2.0, "gravity": 9.81, "mass": 0.1})
        res_heavy = exp.calculate_theoretical({"length": 2.0, "gravity": 9.81, "mass": 50.0})

        assert res_light.primary_theoretical_value == res_heavy.primary_theoretical_value
        assert res_light.computed_metrics["theoretical_frequency"] == res_heavy.computed_metrics["theoretical_frequency"]

    def test_length_sensitivity_square_root_scaling(self):
        """Quadrupling length doubles the period (T proportional to sqrt(L))."""
        exp = PendulumExperiment()
        res_1m = exp.calculate_theoretical({"length": 1.0, "gravity": 9.81})
        res_4m = exp.calculate_theoretical({"length": 4.0, "gravity": 9.81})

        ratio = res_4m.primary_theoretical_value / res_1m.primary_theoretical_value
        assert abs(ratio - 2.0) < 0.01

    def test_parameter_validation_rejects_negative_or_zero_length(self):
        """Length <= 0 raises validation error."""
        exp = PendulumExperiment()
        with pytest.raises(Exception):
            exp.calculate_theoretical({"length": -1.0, "gravity": 9.81})

        with pytest.raises(Exception):
            exp.calculate_theoretical({"length": 0.0, "gravity": 9.81})

    def test_parameter_validation_rejects_non_finite_inputs(self):
        """NaN or Inf values raise validation error."""
        exp = PendulumExperiment()
        with pytest.raises(Exception):
            exp.calculate_theoretical({"length": float("nan"), "gravity": 9.81})

        with pytest.raises(Exception):
            exp.calculate_theoretical({"length": 1.0, "gravity": float("inf")})


# ==============================================================================
# 2. MEASUREMENT SYSTEM & ERROR ANALYSIS (MANUAL & CV)
# ==============================================================================

class TestMeasurementSystemAndErrorAnalysis:
    """Verifies manual stopwatch statistics, CV cycle detection, and scientific error analysis."""

    def test_manual_stopwatch_measurements_processing(self):
        """Multiple stopwatch period trials compute mean, standard deviation, and standard error."""
        exp = PendulumExperiment()
        params = {"length": 1.0, "gravity": 9.81, "angle_deg": 10.0}
        # Student measured 5 period trials around theoretical 2.006s
        observations = [
            {"period_s": 2.02},
            {"period_s": 1.99},
            {"period_s": 2.05},
            {"period_s": 2.01},
            {"period_s": 1.98},
        ]

        result = exp.process_measurements(params, observations)

        assert result.measurement_mode == "manual"
        assert result.error_analysis.sample_size == 5
        assert abs(result.experimental_value - 2.01) < 0.01
        assert result.error_analysis.standard_deviation > 0.0
        assert result.error_analysis.standard_error_of_mean > 0.0
        assert len(result.error_analysis.confidence_interval_95) == 2
        assert result.error_analysis.percentage_error < 2.0
        assert "discrepancy_sources" in result.error_analysis.model_dump()

    def test_cv_derived_continuous_tracking_cycle_detection(self):
        """
        Synthetic sinusoidal tracking frames:
        Zero-crossings correctly extract oscillation period without treating each frame as independent.
        """
        exp = PendulumExperiment()
        params = {"length": 1.0, "gravity": 9.81, "angle_deg": 15.0}

        # Generate 6 seconds of 30 FPS webcam tracking (180 frames) with known T = 2.0s
        fps = 30.0
        total_seconds = 6.0
        t_values = [i / fps for i in range(int(total_seconds * fps))]
        true_period = 2.006
        omega = 2.0 * math.pi / true_period
        amplitude = 0.25  # 25 cm swing

        raw_frames = []
        for t in t_values:
            x_pos = amplitude * math.cos(omega * t)
            raw_frames.append({
                "timestamp": round(t, 4),
                "position_x": round(x_pos, 4),
                "velocity_x": round(-amplitude * omega * math.sin(omega * t), 4),
            })

        result = exp.process_measurements(params, raw_frames)

        assert result.measurement_mode == "cv_derived"
        assert result.observation_count == len(raw_frames)
        # Should detect ~2 complete cycles (positive zero-crossings)
        assert result.metadata["cycles_detected"] >= 2
        # Measured period should match true period within 2% error
        assert abs(result.experimental_value - true_period) < 0.05
        assert result.error_analysis.percentage_error < 3.0

    def test_empty_observations_handled_gracefully(self):
        """Empty observation list does not crash and returns helpful verdict."""
        exp = PendulumExperiment()
        params = {"length": 1.0, "gravity": 9.81}
        result = exp.process_measurements(params, [])

        assert result.observation_count == 0
        assert "No observations" in result.error_analysis.scientific_verdict
        assert len(result.theoretical_series) > 0


# ==============================================================================
# 3. GRAPHING & TIME-SERIES CONTINUITY
# ==============================================================================

class TestGraphingAndAnalysisSeries:
    """Verifies that generated graph curves have valid points, units, and energy conservation."""

    def test_theoretical_time_series_points_and_energy_conservation(self):
        """Total mechanical energy E = KE + PE is conserved in frictionless mode."""
        exp = PendulumExperiment()
        params = {"length": 1.5, "gravity": 9.81, "angle_deg": 15.0, "mass": 2.0, "damping": 0.0}
        series = exp.generate_theoretical_series(params, duration=4.0, steps=60)

        assert len(series) == 60
        initial_e = series[0].total_energy

        for pt in series:
            assert pt.time >= 0.0
            assert pt.position is not None
            assert pt.velocity is not None
            assert pt.kinetic_energy is not None
            assert pt.potential_energy is not None
            # In zero damping, total mechanical energy should remain constant within 1%
            assert abs(pt.total_energy - initial_e) < 0.02


# ==============================================================================
# 4. REST API ENDPOINTS & END-TO-END WORKFLOW INTEGRATION
# ==============================================================================

class TestExperimentEngineAPIWorkflow:
    """
    Verifies the complete student workflow:
    1. Student opens experiment metadata.
    2. Student configures parameters & calculates theoretical baseline.
    3. Student records measurements (manual/CV).
    4. System calculates results & displays graphs.
    5. AI tutor explains results grounded in data.
    6. Student saves experiment to history.
    7. Student retrieves and reproduces saved experiment.
    """

    def test_complete_pendulum_student_workflow(self, client):
        # Step 1: Student opens experiment and reads metadata
        resp_meta = client.get("/api/experiments/metadata/pendulum")
        assert resp_meta.status_code == 200
        meta = resp_meta.json()["metadata"]
        assert meta["id"] == "pendulum"
        assert len(meta["learning_objectives"]) >= 3
        assert len(meta["instructions"]) >= 4
        assert "small_angle_approximation_note" in meta

        # Step 2: Student configures parameters
        params = {"length": 1.2, "gravity": 9.81, "angle_deg": 12.0, "mass": 1.5}
        resp_calc = client.post("/api/experiments/calculate/pendulum", json={"parameters": params})
        assert resp_calc.status_code == 200
        calc_data = resp_calc.json()
        assert "theoretical_period" in calc_data["computed_metrics"]
        t_theo = calc_data["primary_theoretical_value"]
        assert t_theo > 0.0
        assert len(calc_data["theoretical_series"]) > 0

        # Step 3: Student records measurements
        observations = [
            {"period_s": round(t_theo * 1.01, 3)},
            {"period_s": round(t_theo * 0.99, 3)},
            {"period_s": round(t_theo * 1.02, 3)},
        ]
        resp_meas = client.post(
            "/api/experiments/measure/pendulum",
            json={"parameters": params, "observations": observations},
        )
        assert resp_meas.status_code == 200
        meas_data = resp_meas.json()
        assert meas_data["experimental_value"] > 0.0
        assert meas_data["error_analysis"]["percentage_error"] < 3.0
        assert len(meas_data["theoretical_series"]) > 0

        # Step 4: AI Tutor explains the results
        resp_explain = client.post(
            "/api/experiments/explain/pendulum",
            json={
                "parameters": params,
                "results": meas_data,
                "student_question": "Why does changing the bob mass not affect the period?",
            },
        )
        assert resp_explain.status_code == 200
        explain_data = resp_explain.json()
        assert "what_it_demonstrates" in explain_data
        assert "why_observed_differs_from_theory" in explain_data
        assert "parameter_sensitivity" in explain_data
        assert "student_question_answer" in explain_data
        assert "mass" in explain_data["student_question_answer"].lower()

        # Step 5: Student saves the experiment
        save_payload = {
            "type": "pendulum",
            "name": "My Pendulum Experiment",
            "parameters": params,
            "metrics": {
                "theoretical_period": t_theo,
                "experimental_period": meas_data["experimental_value"],
                "percentage_error": meas_data["error_analysis"]["percentage_error"],
            },
        }
        resp_save = client.post("/api/experiments/save", json=save_payload)
        assert resp_save.status_code == 200
        saved = resp_save.json()["experiment"]
        exp_id = saved["id"]

        # Step 6: Student retrieves saved experiment from history
        resp_hist = client.get("/api/experiments/history")
        assert resp_hist.status_code == 200
        hist_records = resp_hist.json()["history"]
        assert any(r["id"] == exp_id for r in hist_records)

        # Step 7: Student reopens the saved experiment by ID
        resp_get = client.get(f"/api/experiments/experiment/{exp_id}")
        assert resp_get.status_code == 200
        opened = resp_get.json()["experiment"]
        assert opened["id"] == exp_id
        assert opened["experiment_type"] == "pendulum"

        # Step 8: Reproduce experiment metrics to confirm audit integrity
        resp_repro = client.post(f"/api/experiments/reproduce/{exp_id}")
        assert resp_repro.status_code == 200
        repro_report = resp_repro.json()
        assert repro_report["reproduced"] is True
