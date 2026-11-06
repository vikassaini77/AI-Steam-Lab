# NeuroLab AI: Scientific Experiment Engine Documentation

**Subsystems**: `backend/app/experiments/`, `frontend/src/pages/ExperimentWorkspace.tsx`  
**Document Version**: 1.0.0 (Production Release Preparation)

---

## 1. Overview of Supported Experiments

NeuroLab AI provides six scientifically validated physics experiment modules. Each experiment combines:
- Theoretical models with analytical formulas and numerical integrations (Runge-Kutta 4th order).
- Rigorous parameter validation with physical boundary constraints.
- Real-time measurement collection via Computer Vision tracking or interactive simulation controls.
- Statistical error analysis comparing measured vs. theoretical values.
- Pedagogical Socratic AI tutoring linked to active experiment context.

---

## 2. Detailed Experiment Formulations

### 2.1 Simple Pendulum (`pendulum`)
- **Physical Concept**: Harmonic oscillation of a point mass suspended by a massless string of length $L$ under uniform gravity $g$.
- **Small-Angle Approximation** ($\theta_0 \le 15^\circ$):
  $$T_0 = 2\pi\sqrt{\frac{L}{g}}$$
- **Large-Angle Correction** (Borda's series expansion):
  $$T \approx T_0 \left(1 + \frac{1}{16}\theta_0^2 + \frac{11}{3072}\theta_0^4\right)$$
- **Numerical Solver**: 4th-order Runge-Kutta (RK4) solving the non-linear differential equation:
  $$\frac{d^2\theta}{dt^2} + \frac{g}{L}\sin\theta = 0$$
- **Validated Parameter Ranges**:
  - Length ($L$): $0.1\,\text{m} \le L \le 10.0\,\text{m}$ (Default: $1.0\,\text{m}$)
  - Gravity ($g$): $1.0\,\text{m/s}^2 \le g \le 25.0\,\text{m/s}^2$ (Default: $9.81\,\text{m/s}^2$)
  - Initial Angle ($\theta_0$): $1.0^\circ \le \theta_0 \le 80.0^\circ$ (Default: $15.0^\circ$)
- **Tolerance**: Theoretical vs. numerical RK4 matches within $\pm 0.5\%$.

---

### 2.2 Projectile Motion (`projectile_motion`)
- **Physical Concept**: Two-dimensional motion under constant vertical acceleration ($g$) with zero horizontal acceleration (neglecting air drag).
- **Theoretical Trajectory Equations**:
  $$x(t) = v_0 \cos(\theta) t$$
  $$y(t) = y_0 + v_0 \sin(\theta) t - \frac{1}{2}gt^2$$
- **Key Metrics**:
  - Flight Time: $t_{\text{flight}} = \frac{v_0 \sin\theta + \sqrt{(v_0\sin\theta)^2 + 2gy_0}}{g}$
  - Horizontal Range: $R = v_0 \cos(\theta) t_{\text{flight}}$
  - Maximum Height: $H = y_0 + \frac{(v_0\sin\theta)^2}{2g}$
- **Validated Parameter Ranges**:
  - Velocity ($v_0$): $1.0\,\text{m/s} \le v_0 \le 100.0\,\text{m/s}$
  - Angle ($\theta$): $0.0^\circ \le \theta \le 90.0^\circ$
  - Initial Height ($y_0$): $0.0\,\text{m} \le y_0 \le 50.0\,\text{m}$

---

### 2.3 Free Fall (`free_fall`)
- **Physical Concept**: One-dimensional vertical motion of a body falling from rest under gravitational acceleration $g$.
- **Analytical Formulas**:
  $$v(t) = -gt$$
  $$y(t) = y_0 - \frac{1}{2}gt^2$$
  $$t_{\text{impact}} = \sqrt{\frac{2y_0}{g}}, \quad v_{\text{impact}} = \sqrt{2gy_0}$$
- **Validated Parameter Ranges**:
  - Height ($y_0$): $0.5\,\text{m} \le y_0 \le 100.0\,\text{m}$
  - Gravity ($g$): $1.0\,\text{m/s}^2 \le g \le 25.0\,\text{m/s}^2$

---

### 2.4 Uniform Circular Motion (`circular_motion`)
- **Physical Concept**: Motion of an object traversing a circular path of radius $r$ at constant speed $v$.
- **Key Metrics**:
  - Angular Velocity: $\omega = \frac{v}{r} = 2\pi f = \frac{2\pi}{T}$
  - Centripetal Acceleration: $a_c = \frac{v^2}{r} = \omega^2 r$
  - Centripetal Force: $F_c = m a_c = \frac{m v^2}{r}$
- **Validated Parameter Ranges**:
  - Radius ($r$): $0.1\,\text{m} \le r \le 10.0\,\text{m}$
  - Speed ($v$): $0.5\,\text{m/s} \le v \le 50.0\,\text{m/s}$
  - Mass ($m$): $0.01\,\text{kg} \le m \le 10.0\,\text{kg}$

---

### 2.5 Simple Harmonic Motion (`harmonic_motion`)
- **Physical Concept**: Linear mass-spring oscillator governed by Hooke's Law ($F = -kx$).
- **Equations of Motion**:
  $$x(t) = A \cos(\omega_0 t + \phi)$$
  $$\omega_0 = \sqrt{\frac{k}{m}}, \quad T = 2\pi\sqrt{\frac{m}{k}}$$
- **Conservation of Energy**:
  $$E_{\text{total}} = \frac{1}{2}kA^2 = \frac{1}{2}kx(t)^2 + \frac{1}{2}mv(t)^2$$
- **Validated Parameter Ranges**:
  - Mass ($m$): $0.05\,\text{kg} \le m \le 20.0\,\text{kg}$
  - Spring Constant ($k$): $1.0\,\text{N/m} \le k \le 500.0\,\text{N/m}$
  - Amplitude ($A$): $0.01\,\text{m} \le A \le 2.0\,\text{m}$

---

### 2.6 Collision and Momentum (`collision`)
- **Physical Concept**: One-dimensional collision between two bodies with masses $m_1, m_2$ and velocities $v_1, v_2$.
- **Conservation of Linear Momentum**:
  $$m_1 v_1 + m_2 v_2 = m_1 v_1' + m_2 v_2'$$
- **Coefficient of Restitution ($e$)**:
  $$e = -\frac{v_1' - v_2'}{v_1 - v_2}$$
  - $e = 1.0$: Perfectly elastic (kinetic energy conserved).
  - $0 < e < 1.0$: Inelastic collision.
  - $e = 0.0$: Completely inelastic (objects stick together).
- **Post-Collision Velocities**:
  $$v_1' = \frac{m_1 - e m_2}{m_1 + m_2}v_1 + \frac{(1+e)m_2}{m_1 + m_2}v_2$$
  $$v_2' = \frac{(1+e)m_1}{m_1 + m_2}v_1 + \frac{m_2 - e m_1}{m_1 + m_2}v_2$$
- **Validated Parameter Ranges**:
  - Masses: $0.05\,\text{kg} \le m_1, m_2 \le 50.0\,\text{kg}$
  - Restitution ($e$): $0.0 \le e \le 1.0$

---

## 3. Experimental Error Analysis

Whenever a student records experimental measurements ($V_{\text{exp}}$) via webcam tracking or manual sensor logging, the system automatically computes standard educational error metrics:

1. **Absolute Error**:
   $$\Delta = |V_{\text{exp}} - V_{\text{theo}}|$$
2. **Percentage Error**:
   $$\% \text{ Error} = \frac{|V_{\text{exp}} - V_{\text{theo}}|}{V_{\text{theo}}} \times 100\%$$
3. **Automated Feedback Categorization**:
   - $\% \text{ Error} \le 5\%$: **Excellent Agreement** (award mastery badge).
   - $5\% < \% \text{ Error} \le 15\%$: **Acceptable Experimental Variance** (prompts student to review friction/air drag).
   - $\% \text{ Error} > 15\%$: **Significant Discrepancy** (AI Tutor prompts student to check camera calibration and initial release angles).
