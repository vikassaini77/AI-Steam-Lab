import base64
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core_backend.core.dependencies import get_current_user
from app.machine_learning.cv_service import (
    CVTracker,
    TrajectoryTracker,
    CVTrackerSessionManager,
    cv_tracker_manager,
)

client = TestClient(app)

USER_ALICE = {"id": "user_alice_111", "email": "alice@neurolab.ai", "role": "authenticated"}
USER_BOB = {"id": "user_bob_222", "email": "bob@neurolab.ai", "role": "authenticated"}

_current_test_user = USER_ALICE


def get_mock_user():
    return _current_test_user


@pytest.fixture(autouse=True)
def setup_test_context():
    global _current_test_user
    _current_test_user = USER_ALICE
    app.dependency_overrides[get_current_user] = get_mock_user
    cv_tracker_manager.clear_all()
    from app.cache import clear_local_cache
    clear_local_cache()
    yield
    cv_tracker_manager.clear_all()
    clear_local_cache()
    app.dependency_overrides.clear()


def make_frame_with_circle(cx: int, cy: int, radius: int = 30, color=(0, 0, 255), width=640, height=480) -> str:
    """Creates a base64 encoded JPEG frame with a colored circle at (cx, cy)."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.circle(img, (cx, cy), radius, color, -1)
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def make_binary_frame_with_circle(cx: int, cy: int, radius: int = 30, color=(0, 0, 255), width=640, height=480) -> bytes:
    """Creates raw binary JPEG frame bytes with a colored circle at (cx, cy)."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.circle(img, (cx, cy), radius, color, -1)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


# ==============================================================================
# 1. TrajectoryTracker Serialization & Multi-Backend State Sync
# ==============================================================================

def test_trajectory_tracker_serialization_and_restoration():
    """
    Verifies that TrajectoryTracker can be serialized to a JSON-compatible dict
    and restored on another instance without losing active tracks, positions, or velocities.
    """
    tracker = TrajectoryTracker()
    now = 1000.0

    # Observation 1: (100, 100)
    id1, v1, a1 = tracker.update((100, 100), now, px_to_meters=0.01)
    assert id1 == 1

    # Observation 2: (150, 100)
    now += 0.1
    id2, v2, a2 = tracker.update((150, 100), now, px_to_meters=0.01)
    assert id2 == 1
    assert v2 > 0.0

    # Serialize to dict (as would be stored in Redis)
    serialized = tracker.to_dict()
    assert "next_id" in serialized
    assert "tracks" in serialized
    assert "1" in serialized["tracks"]
    assert len(serialized["tracks"]["1"]["positions"]) == 2

    # Hydrate new tracker instance (simulating another backend replica)
    replica_tracker = TrajectoryTracker()
    replica_tracker.from_dict(serialized)

    assert replica_tracker.next_id == tracker.next_id
    assert 1 in replica_tracker.tracks

    # Observation 3 on replica: (200, 100)
    now += 0.1
    id3, v3, a3 = replica_tracker.update((200, 100), now, px_to_meters=0.01)
    assert id3 == 1  # Track persists seamlessly across replicas
    assert abs(v3 - 5.0) < 0.1  # (50px * 0.01m) / 0.1s = 5.0 m/s


# ==============================================================================
# 2. Cross-User Tracking Isolation (User A cannot influence User B)
# ==============================================================================

def test_cross_user_tracking_isolation():
    """
    Problem 3 verification:
    User A and User B stream camera frames. Their tracking state must be
    completely isolated: User A's movements must not affect User B's velocity.
    """
    global _current_test_user

    # Frame for Alice: object at (100, 100)
    _current_test_user = USER_ALICE
    frame_alice_1 = make_frame_with_circle(100, 100)
    res_a1 = client.post("/api/cv/process-frame", json={"image": frame_alice_1, "color_target": "red"})
    assert res_a1.status_code == 200
    data_a1 = res_a1.json()
    assert data_a1["user_id"] == USER_ALICE["id"]
    track_id_a = data_a1["physics"]["track_id"]
    assert track_id_a == 1
    assert data_a1["physics"]["velocity_mps"] == 0.0

    # Frame for Bob: object at SAME coordinate (100, 100)
    _current_test_user = USER_BOB
    frame_bob_1 = make_frame_with_circle(100, 100)
    res_b1 = client.post("/api/cv/process-frame", json={"image": frame_bob_1, "color_target": "red"})
    assert res_b1.status_code == 200
    data_b1 = res_b1.json()
    assert data_b1["user_id"] == USER_BOB["id"]
    track_id_b = data_b1["physics"]["track_id"]
    assert track_id_b == 1  # Bob gets his own independent track #1
    assert data_b1["physics"]["velocity_mps"] == 0.0

    # User Alice moves object to (160, 100)
    _current_test_user = USER_ALICE
    frame_alice_2 = make_frame_with_circle(160, 100)
    res_a2 = client.post("/api/cv/process-frame", json={"image": frame_alice_2, "color_target": "red"})
    assert res_a2.status_code == 200
    data_a2 = res_a2.json()
    assert data_a2["physics"]["track_id"] == 1
    assert data_a2["physics"]["velocity_mps"] > 0.0, "Alice moved 60px so velocity must be > 0"

    # User Bob sends frame with object STILL at (100, 100)
    _current_test_user = USER_BOB
    frame_bob_2 = make_frame_with_circle(100, 100)
    res_b2 = client.post("/api/cv/process-frame", json={"image": frame_bob_2, "color_target": "red"})
    assert res_b2.status_code == 200
    data_b2 = res_b2.json()
    # Bob did NOT move, so his velocity must be 0.0 (Alice's motion must NOT leak to Bob)
    assert data_b2["physics"]["track_id"] == 1
    assert data_b2["physics"]["velocity_mps"] == 0.0, "Bob's velocity must be 0.0 since Bob did not move"


# ==============================================================================
# 3. Cross-User Reset Isolation (User B cannot reset User A's tracker)
# ==============================================================================

def test_user_reset_does_not_affect_other_users():
    """
    Problem 3 verification:
    When User B calls /reset-tracker, User A's active trajectory tracking
    must NOT be cleared or disrupted.
    """
    global _current_test_user

    # Alice creates an active track at (120, 120)
    _current_test_user = USER_ALICE
    frame_a1 = make_frame_with_circle(120, 120)
    res_a1 = client.post("/api/cv/process-frame", json={"image": frame_a1, "color_target": "red"})
    assert res_a1.status_code == 200
    assert res_a1.json()["physics"]["track_id"] == 1

    # Bob creates an active track
    _current_test_user = USER_BOB
    frame_b1 = make_frame_with_circle(200, 200)
    res_b1 = client.post("/api/cv/process-frame", json={"image": frame_b1, "color_target": "red"})
    assert res_b1.status_code == 200

    # Bob resets his tracker
    reset_res = client.post("/api/cv/reset-tracker")
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "success"
    assert reset_res.json()["user_id"] == USER_BOB["id"]

    # Alice sends a new frame at (150, 120) - Alice should STILL have her track #1
    _current_test_user = USER_ALICE
    frame_a2 = make_frame_with_circle(150, 120)
    res_a2 = client.post("/api/cv/process-frame", json={"image": frame_a2, "color_target": "red"})
    assert res_a2.status_code == 200
    data_a2 = res_a2.json()
    assert data_a2["physics"]["track_id"] == 1, "Alice's track must persist despite Bob's reset"
    assert data_a2["physics"]["velocity_mps"] > 0.0, "Alice's velocity should calculate against her previous frame"


# ==============================================================================
# 4. Multi-Session Isolation for Same User (Multiple Camera Feeds)
# ==============================================================================

def test_multi_session_isolation_same_user():
    """
    Verifies that multiple camera sessions for the SAME authenticated user
    (e.g., overhead camera vs side camera) maintain independent tracking states.
    """
    global _current_test_user
    _current_test_user = USER_ALICE

    # Camera 1 (overhead)
    frame_cam1_1 = make_frame_with_circle(100, 100)
    res_c1_1 = client.post(
        "/api/cv/process-frame",
        json={"image": frame_cam1_1, "session_id": "overhead_cam", "color_target": "red"},
    )
    assert res_c1_1.status_code == 200
    assert res_c1_1.json()["session_id"] == "overhead_cam"
    assert res_c1_1.json()["physics"]["track_id"] == 1

    # Camera 2 (side view)
    frame_cam2_1 = make_frame_with_circle(300, 300)
    res_c2_1 = client.post(
        "/api/cv/process-frame",
        json={"image": frame_cam2_1, "session_id": "side_cam", "color_target": "red"},
    )
    assert res_c2_1.status_code == 200
    assert res_c2_1.json()["session_id"] == "side_cam"
    assert res_c2_1.json()["physics"]["track_id"] == 1

    # Reset ONLY the overhead camera session
    reset_res = client.post("/api/cv/reset-tracker", json={"session_id": "overhead_cam"})
    assert reset_res.status_code == 200
    assert reset_res.json()["session_id"] == "overhead_cam"

    # Side camera continues tracking without being reset
    frame_cam2_2 = make_frame_with_circle(340, 300)
    res_c2_2 = client.post(
        "/api/cv/process-frame",
        json={"image": frame_cam2_2, "session_id": "side_cam", "color_target": "red"},
    )
    assert res_c2_2.status_code == 200
    assert res_c2_2.json()["physics"]["track_id"] == 1
    assert res_c2_2.json()["physics"]["velocity_mps"] > 0.0


# ==============================================================================
# 5. Reset All Sessions Option for User
# ==============================================================================

def test_reset_all_sessions_for_user():
    """
    Verifies that all_sessions=True resets all sessions for the calling user,
    leaving other users' sessions completely unaffected.
    """
    global _current_test_user

    # Alice sets up 2 sessions
    _current_test_user = USER_ALICE
    client.post("/api/cv/process-frame", json={"image": make_frame_with_circle(50, 50), "session_id": "sess_1"})
    client.post("/api/cv/process-frame", json={"image": make_frame_with_circle(60, 60), "session_id": "sess_2"})

    # Bob sets up 1 session
    _current_test_user = USER_BOB
    client.post("/api/cv/process-frame", json={"image": make_frame_with_circle(70, 70), "session_id": "sess_bob"})

    # Alice resets all her sessions
    _current_test_user = USER_ALICE
    reset_res = client.post("/api/cv/reset-tracker", json={"all_sessions": True})
    assert reset_res.status_code == 200
    assert reset_res.json()["session_id"] == "all"
    assert reset_res.json()["user_id"] == USER_ALICE["id"]

    # Bob's session remains active
    _current_test_user = USER_BOB
    res_bob_2 = client.post(
        "/api/cv/process-frame",
        json={"image": make_frame_with_circle(110, 70), "session_id": "sess_bob"},
    )
    assert res_bob_2.status_code == 200
    assert res_bob_2.json()["physics"]["track_id"] == 1
    assert res_bob_2.json()["physics"]["velocity_mps"] > 0.0


# ==============================================================================
# 6. Binary Upload Endpoint Session Isolation
# ==============================================================================

def test_process_frame_binary_session_isolation():
    """
    Verifies that the high-performance binary frame endpoint isolates
    tracking state per user and session via query parameter or header.
    """
    global _current_test_user

    # Alice binary frame 1
    _current_test_user = USER_ALICE
    raw_a1 = make_binary_frame_with_circle(100, 100)
    res_a1 = client.post(
        "/api/cv/process-frame-binary?session_id=binary_alice",
        content=raw_a1,
        headers={"Content-Type": "image/jpeg"},
    )
    assert res_a1.status_code == 200
    assert res_a1.json()["user_id"] == USER_ALICE["id"]
    assert res_a1.json()["session_id"] == "binary_alice"

    # Bob binary frame 1
    _current_test_user = USER_BOB
    raw_b1 = make_binary_frame_with_circle(100, 100)
    res_b1 = client.post(
        "/api/cv/process-frame-binary",
        content=raw_b1,
        headers={"Content-Type": "image/jpeg", "X-Session-ID": "binary_bob"},
    )
    assert res_b1.status_code == 200
    assert res_b1.json()["user_id"] == USER_BOB["id"]
    assert res_b1.json()["session_id"] == "binary_bob"
    assert res_b1.json()["physics"]["track_id"] == 1


# ==============================================================================
# 7. Multi-Backend Replica Cross-Instance State Synchronization
# ==============================================================================

@pytest.mark.asyncio
async def test_multi_backend_replica_cross_instance_sync():
    """
    Verifies that multiple independent backend instances (replicas) share
    and synchronize tracking state via the shared state manager.
    Pod 1 updates state; Pod 2 hydrates that state and continues tracking smoothly.
    """
    pod1_manager = CVTrackerSessionManager(ttl_seconds=300)
    pod2_manager = CVTrackerSessionManager(ttl_seconds=300)

    user_id = "user_student_multi_node"
    session_id = "pendulum_session_xyz"
    b64_frame1 = make_frame_with_circle(100, 100)
    b64_frame2 = make_frame_with_circle(150, 100)

    # 1. Pod 1 handles Frame 1
    tracker_pod1 = await pod1_manager.get_tracker(user_id=user_id, session_id=session_id)
    res1 = tracker_pod1.process_frame(b64_frame1, tracking_method="color", color_target="red")
    assert res1["physics"]["track_id"] == 1
    await pod1_manager.save_tracker_state(user_id=user_id, session_id=session_id, tracker=tracker_pod1)

    # 2. Pod 2 (separate manager with NO prior local memory of this user) handles Frame 2
    tracker_pod2 = await pod2_manager.get_tracker(user_id=user_id, session_id=session_id)
    assert 1 in tracker_pod2.trajectory_tracker.tracks, "Pod 2 should have hydrated track 1 from shared store"

    res2 = tracker_pod2.process_frame(b64_frame2, tracking_method="color", color_target="red")
    assert res2["physics"]["track_id"] == 1, "Track ID must persist on Pod 2"
    assert res2["physics"]["velocity_mps"] > 0.0, "Velocity must be calculated against Pod 1's previous position"

    # 3. Pod 2 resets session
    await pod2_manager.reset_tracker(user_id=user_id, session_id=session_id)

    # 4. Pod 1 resets and confirms session was reset
    await pod1_manager.reset_tracker(user_id=user_id, session_id=session_id)
    tracker_pod1_after_reset = await pod1_manager.get_tracker(user_id=user_id, session_id=session_id)
    assert len(tracker_pod1_after_reset.trajectory_tracker.tracks) == 0, "Tracker tracks should be reset"


# ==============================================================================
# 8. Multi-Camera Isolation in Same Session (Problem 11)
# ==============================================================================

def test_multi_camera_isolation_same_session():
    """
    Problem 11 verification:
    Within the same user session, separate camera feeds (e.g. overhead vs side view)
    maintain strictly isolated trajectory and kinematics states.
    """
    global _current_test_user
    _current_test_user = USER_ALICE

    # 1. Overhead camera observation 1 at (100, 100)
    frame_overhead_1 = make_frame_with_circle(100, 100)
    res_ov_1 = client.post(
        "/api/cv/process-frame",
        json={
            "image": frame_overhead_1,
            "session_id": "lab_physics_101",
            "camera_id": "overhead_cam",
            "color_target": "red",
        },
    )
    assert res_ov_1.status_code == 200
    data_ov_1 = res_ov_1.json()
    assert data_ov_1["session_id"] == "lab_physics_101"
    assert data_ov_1["camera_id"] == "overhead_cam"
    assert data_ov_1["physics"]["track_id"] == 1
    assert data_ov_1["physics"]["velocity_mps"] == 0.0

    # 2. Side camera observation 1 at (300, 300) in the SAME session
    frame_side_1 = make_frame_with_circle(300, 300)
    res_sd_1 = client.post(
        "/api/cv/process-frame",
        json={
            "image": frame_side_1,
            "session_id": "lab_physics_101",
            "camera_id": "side_cam",
            "color_target": "red",
        },
    )
    assert res_sd_1.status_code == 200
    data_sd_1 = res_sd_1.json()
    assert data_sd_1["session_id"] == "lab_physics_101"
    assert data_sd_1["camera_id"] == "side_cam"
    assert data_sd_1["physics"]["track_id"] == 1
    assert data_sd_1["physics"]["velocity_mps"] == 0.0

    # 3. Overhead camera moves 50px to (150, 100)
    frame_overhead_2 = make_frame_with_circle(150, 100)
    res_ov_2 = client.post(
        "/api/cv/process-frame",
        json={
            "image": frame_overhead_2,
            "session_id": "lab_physics_101",
            "camera_id": "overhead_cam",
            "color_target": "red",
        },
    )
    assert res_ov_2.status_code == 200
    assert res_ov_2.json()["physics"]["velocity_mps"] > 0.0

    # 4. Side camera object has NOT moved (still at 300, 300)
    frame_side_2 = make_frame_with_circle(300, 300)
    res_sd_2 = client.post(
        "/api/cv/process-frame",
        json={
            "image": frame_side_2,
            "session_id": "lab_physics_101",
            "camera_id": "side_cam",
            "color_target": "red",
        },
    )
    assert res_sd_2.status_code == 200
    # Must be 0.0: Overhead movement did NOT bleed into side camera
    assert res_sd_2.json()["physics"]["velocity_mps"] == 0.0

    # 5. Granular Reset: reset ONLY overhead_cam
    reset_ov = client.post(
        "/api/cv/reset-tracker",
        json={"session_id": "lab_physics_101", "camera_id": "overhead_cam"},
    )
    assert reset_ov.status_code == 200
    assert reset_ov.json()["camera_id"] == "overhead_cam"

    # Side camera tracking still intact
    frame_side_3 = make_frame_with_circle(360, 300)
    res_sd_3 = client.post(
        "/api/cv/process-frame",
        json={
            "image": frame_side_3,
            "session_id": "lab_physics_101",
            "camera_id": "side_cam",
            "color_target": "red",
        },
    )
    assert res_sd_3.status_code == 200
    assert res_sd_3.json()["physics"]["track_id"] == 1
    assert res_sd_3.json()["physics"]["velocity_mps"] > 0.0, "Side camera was not affected by overhead camera reset"


# ==============================================================================
# 9. Inactive Session Expiration and Pruning Policies (Problem 11)
# ==============================================================================

def test_inactive_session_expiration_and_cleanup_policy():
    """
    Problem 11 verification:
    Verify TTL-based expiration and cleanup policies for inactive sessions.
    Inactive sessions are safely evicted from process memory, async locks, and cache.
    """
    import time
    mgr = CVTrackerSessionManager(ttl_seconds=1)

    # Create active session 1
    tracker1 = mgr.get_tracker_sync(user_id="user_exp_1", session_id="sess_exp_1", camera_id="cam_main")
    assert mgr.get_active_sessions_count() == 1

    # Immediate cleanup: session should NOT be pruned because it was just accessed
    stats1 = mgr.cleanup_expired_sessions()
    assert stats1["purged_count"] == 0
    assert mgr.get_active_sessions_count() == 1

    # Simulate passage of time beyond TTL
    time.sleep(1.1)

    # Create active session 2 (fresh)
    tracker2 = mgr.get_tracker_sync(user_id="user_exp_2", session_id="sess_exp_2", camera_id="cam_main")
    assert mgr.get_active_sessions_count() == 2

    # Prune with TTL=1s: session 1 must be evicted, session 2 must remain
    stats2 = mgr.cleanup_expired_sessions()
    assert stats2["purged_count"] == 1
    assert stats2["remaining_count"] == 1

    # Verify endpoint works for explicit cleanup
    res_cleanup = client.post("/api/cv/cleanup-sessions?max_age_seconds=1")
    assert res_cleanup.status_code == 200
    data = res_cleanup.json()
    assert data["status"] == "success"
    assert "purged_count" in data
    assert "remaining_count" in data


