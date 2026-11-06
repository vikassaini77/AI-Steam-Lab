# NeuroLab AI: Computer Vision Setup & Kinematics Guide

**Subsystem**: Real-Time Computer Vision & Motion Tracking  
**Primary Files**: `backend/app/machine_learning/cv_service.py`, `backend/app/core_backend/routes/cv_tracker.py`, `frontend/src/components/webcam/WebcamPanel.tsx`  
**Document Version**: 1.0.0

---

## 1. Supported Detection Modes

NeuroLab AI provides three genuinely implemented computer vision tracking architectures tailored for educational physics laboratories:

```mermaid
flowchart LR
    A["Raw Video Frame (Webcam)"] --> B{"Selected Detector"}
    B -->|"Color (HSV)"| C["HSV Thresholding + Morph Opening/Closing + Centroid Moments"]
    B -->|"Optical Flow"| D["Shi-Tomasi Good Features + Lucas-Kanade Pyramidal Flow"]
    B -->|"Deep Learning"| E["YOLOv8 ONNX/PyTorch Inference + NMS (COCO-80)"]
    C --> F["Kinematic Solver: Velocity, Acceleration, Gravity (g)"]
    D --> F
    E --> F
    F --> G["Live Canvas HUD & Recharts Kinematics Plot"]
```

### A. Color Segmentation (HSV Centroid Tracking)
- **Methodology**: Converts frames from BGR to HSV color space. Applies morphological opening kernels ($3 \times 3$ ellipse) to eliminate high-frequency sensor noise, followed by morphological closing kernels ($5 \times 5$ ellipse) to bridge internal object voids. Computes spatial moments ($M_{00}, M_{10}, M_{01}$) to derive centroid coordinates:
  $$x_c = \frac{M_{10}}{M_{00}}, \quad y_c = \frac{M_{01}}{M_{00}}$$
- **Ideal For**: Brightly colored physical lab objects (e.g., neon red or blue pendulum bobs, tennis balls).
- **Latency / Throughput**: Median **2.61 ms** (up to **374.5 FPS**).
- **Memory Footprint**: Extremely lightweight ($< 150\,\text{MB}$ RAM).

### B. Optical Flow Tracking (Lucas-Kanade)
- **Methodology**: Initializes feature points on high-contrast corners using the Shi-Tomasi detector (`cv2.goodFeaturesToTrack`). Tracks trajectories across consecutive frames via multi-level pyramidal Lucas-Kanade optical flow (`cv2.calcOpticalFlowPyrLK`).
- **Lost-Track Recovery**: If tracked feature points drop below a safety threshold ($N < 5$), the detector automatically re-extracts candidate points within the last valid bounding window.
- **Latency / Throughput**: Median **1.54 ms** (up to **602.4 FPS**).
- **Ideal For**: Arbitrary objects without distinct primary colors in consistent laboratory lighting.

### C. Deep-Learning Detection (YOLOv8)
- **Methodology**: Loads YOLOv8 weights (`yolov8n.pt` or ONNX runtime). Performs class filtering (e.g., sports ball, bottle, apple) and Non-Maximum Suppression (NMS) with an IoU threshold of 0.45.
- **Latency / Throughput**: Median **14.67 ms** (approx. **65.8 FPS** on modern 12-core CPU).
- **Graceful Fallback**: If model weights are missing or corrupt, or if memory allocation fails, the system automatically falls back to HSV color segmentation (`is_degraded: true`).

---

## 2. Low-Memory Production Deployment (512 MB Containers)

> [!IMPORTANT]
> **Avoid OOM Kills on Free-Tier Deployments**:
> - The YOLOv8 model and PyTorch runtime consume approximately **+958.8 MB of RAM** upon initialization.
> - Free container tiers (e.g., Render Free Tier, AWS t4g.small with shared workloads) limit memory to 512 MB.
> - **Production Recommendation**:
>   - Set `ENABLE_YOLO=false` in container environment variables.
>   - This keeps memory usage below 180 MB while delivering high-speed, sub-3ms kinematics tracking.
>   - Enable YOLOv8 only on instances with $\ge 2\,\text{GB}$ RAM.

---

## 3. Physical Lab Setup & Calibration

### 3.1 Browser Camera & HTTPS Requirements
1. **HTTPS Enforcement**: Web browsers (Chrome, Safari, Firefox, Edge) restrict `navigator.mediaDevices.getUserMedia` exclusively to secure contexts (`https://` or `http://localhost`). Ensure all production deployments terminate SSL.
2. **Lighting**: Position lamps to illuminate the tracking arena from the front or 45-degree angle. Avoid harsh backlighting or reflective glare behind the moving object.
3. **Contrast**: Use a background that contrasts clearly with the object under test (e.g., a white whiteboard background for a red bob).

### 3.2 Spatial Calibration (Pixels-to-Meters)
Physical measurements (velocity in $\text{m/s}$, acceleration in $\text{m/s}^2$) require calibrating the optical scale factor $S = \text{meters per pixel}$:
1. Place a known reference object (e.g., a 30 cm ruler or 1-meter stick) in the plane of motion.
2. Call the calibration API endpoint:
   ```http
   POST /api/cv/calibrate
   Content-Type: application/json
   Authorization: Bearer <token>

   {
     "session_id": "sess_112233",
     "pixel_distance": 400.0,
     "real_world_distance_meters": 1.0
   }
   ```
3. The server computes $S = 1.0 / 400.0 = 0.0025\,\text{m/pixel}$ and applies this scaling factor to all subsequent coordinate streams.

---

## 4. Real-Time Numerical Kinematics Derivation

The kinematics solver derives real-time physical properties across consecutive video frames:

1. **Time Delta**: Derived from frame hardware timestamps:
   $$\Delta t = t_k - t_{k-1}$$
2. **Instantaneous Velocity**: Central difference formula:
   $$v_x(t) = \frac{x(t + \Delta t) - x(t - \Delta t)}{2\Delta t} \cdot S$$
   $$v_y(t) = \frac{y(t + \Delta t) - y(t - \Delta t)}{2\Delta t} \cdot S$$
   $$v(t) = \sqrt{v_x(t)^2 + v_y(t)^2}$$
3. **Instantaneous Acceleration**:
   $$a(t) = \frac{v(t + \Delta t) - v(t - \Delta t)}{2\Delta t}$$
4. **Experimental Gravity Estimation ($g$)**: During free-fall tracking, the vertical acceleration $a_y$ directly estimates local gravitational acceleration ($g \approx 9.81\,\text{m/s}^2$).
