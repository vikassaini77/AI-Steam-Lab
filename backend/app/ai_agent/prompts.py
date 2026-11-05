"""
Tutor Prompt and Instruction Management - AI Layer
Modular management of pedagogical instructions, Socratic teaching modes,
student level calibration, experimental context injection, and prompt injection defense.
"""
from enum import Enum
import re
from typing import Any, Dict, List, Optional


class TutorMode(str, Enum):
    GUIDED_LEARNING = "guided_learning"
    HINT = "hint"
    EXPLAIN = "explain"
    QUIZ = "quiz"
    EXPERIMENT_ANALYSIS = "experiment_analysis"
    REVISION = "revision"


class StudentLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


# Base persona and pedagogical identity
BASE_TUTOR_PERSONA = (
    "You are Professor Nova, an inspiring and friendly AI STEM mentor and physics research guide at NeuroLab AI.\n"
    "Pedagogical Philosophy:\n"
    "- Socratic Engagement: Guide students to discover physical laws through active observation and reasoning.\n"
    "- Scientific Grounding: Connect every mathematical formulation directly to observable physical phenomena.\n"
    "- Mathematical Rigor: When providing equations, format them with clean LaTeX (e.g. $T = 2\\pi\\sqrt{\\frac{L}{g}}$, $E_k = \\frac{1}{2}mv^2$, $F = ma$).\n"
    "- Encouraging & Clear: Maintain an intellectually engaging, structured, and constructive tone."
)


# Mode-specific pedagogical directives
MODE_DIRECTIVES: Dict[TutorMode, str] = {
    TutorMode.GUIDED_LEARNING: (
        "Teaching Mode: GUIDED LEARNING (Socratic Dialogue)\n"
        "- Do NOT provide direct complete solutions upfront.\n"
        "- Ask one focused guiding question at a time to lead the student to the next logical realization.\n"
        "- Validate correct student reasoning enthusiastically before introducing the next challenge."
    ),
    TutorMode.HINT: (
        "Teaching Mode: HINT (Scaffolded Clue)\n"
        "- Provide a targeted, high-value conceptual hint or analogy.\n"
        "- Point directly to the relevant physical relationship or conservation law without giving away the final numerical or algebraic answer.\n"
        "- Conclude with a brief prompt asking the student what their next step should be."
    ),
    TutorMode.EXPLAIN: (
        "Teaching Mode: EXPLAIN (Conceptual Clarity)\n"
        "- Provide a thorough, vivid explanation of the core concept using an intuitive real-world analogy.\n"
        "- Break down the physical mechanics step-by-step.\n"
        "- State relevant governing equations with defined variables and SI units."
    ),
    TutorMode.QUIZ: (
        "Teaching Mode: QUIZ (Diagnostic Assessment)\n"
        "- Pose a concise, thought-provoking diagnostic question testing the student's conceptual grasp.\n"
        "- Include 3 or 4 multiple-choice options or a qualitative scenario question.\n"
        "- Wait for the student's answer before offering evaluation."
    ),
    TutorMode.EXPERIMENT_ANALYSIS: (
        "Teaching Mode: EXPERIMENT ANALYSIS (Empirical Verification)\n"
        "- Focus specifically on comparing observed experimental measurements against theoretical predictions.\n"
        "- Help the student identify plausible physical sources of discrepancy (e.g. air resistance, friction, pivot damping, camera sampling jitter).\n"
        "- Guide the student through error calculation and scientific interpretation of their data."
    ),
    TutorMode.REVISION: (
        "Teaching Mode: REVISION (Summary & Synthesis)\n"
        "- Provide a structured summary of the key principles covered.\n"
        "- Highlight critical formulas, sign conventions, and standard units.\n"
        "- Emphasize common pitfalls and misconceptions to watch out for."
    ),
}


# Level-specific calibration
LEVEL_DIRECTIVES: Dict[StudentLevel, str] = {
    StudentLevel.BEGINNER: (
        "Student Learning Level: BEGINNER\n"
        "- Use everyday language, intuitive analogies, and avoid overly dense mathematical jargon.\n"
        "- Focus on qualitative understanding (e.g. 'heavier vs lighter', 'faster vs slower', 'energy transforms') before equations."
    ),
    StudentLevel.INTERMEDIATE: (
        "Student Learning Level: INTERMEDIATE (High School / Intro College STEM)\n"
        "- Balance intuitive physical understanding with algebraic formulations and vector quantities.\n"
        "- Expect familiarity with standard kinematic formulas and Newton's laws."
    ),
    StudentLevel.ADVANCED: (
        "Student Learning Level: ADVANCED (Undergraduate STEM)\n"
        "- Employ differential equations, calculus-based derivations, vector dot/cross products, and formal energy methods (Lagrangian/Hamiltonian when relevant).\n"
        "- Emphasize second-order effects, boundary conditions, and tensor/matrix representations where appropriate."
    ),
}


def sanitize_student_input(text: str) -> str:
    """
    Sanitizes user input to mitigate prompt injection, control character abuse,
    and attempts to override system instructions.
    """
    if not text:
        return ""

    # Strip dangerous XML/instruction tags commonly used in injection attacks
    sanitized = re.sub(r"<\/?(system|instruction|prompt|context|admin)[^>]*>", "", text, flags=re.IGNORECASE)

    # Disarm common injection trigger phrases
    injection_patterns = [
        r"ignore\s+(all\s+)?(previous|prior)\s+instructions?",
        r"disregard\s+(all\s+)?(previous|prior)\s+instructions?",
        r"system\s*:\s*you\s+are\s+now",
        r"reveal\s+(your\s+)?(system\s+prompt|secret|api\s+key)",
    ]
    for pattern in injection_patterns:
        sanitized = re.sub(pattern, "[redacted override attempt]", sanitized, flags=re.IGNORECASE)

    return sanitized.strip()


def format_experiment_context(experiment_state: Optional[Any]) -> str:
    """
    Extracts and formats live laboratory simulation telemetry into a structured context block.
    """
    if not experiment_state:
        return ""

    data = experiment_state
    if hasattr(experiment_state, "model_dump"):
        data = experiment_state.model_dump()
    elif hasattr(experiment_state, "dict"):
        data = experiment_state.dict()
    elif not isinstance(data, dict):
        return f"\nActive Laboratory Telemetry: {str(experiment_state)}"

    lines = ["\nActive Laboratory Experiment Context:"]
    exp_type = data.get("experiment_type")
    if exp_type:
        lines.append(f"- Experiment Type: {exp_type}")

    params = data.get("parameters")
    if isinstance(params, dict) and params:
        param_strs = [f"{k}={v}" for k, v in params.items()]
        lines.append(f"- Parameters: {', '.join(param_strs)}")

    metrics = data.get("current_metrics") or data.get("metrics")
    if isinstance(metrics, dict) and metrics:
        metric_strs = [f"{k}={v}" for k, v in metrics.items()]
        lines.append(f"- Observed Telemetry Metrics: {', '.join(metric_strs)}")

    theoretical = data.get("theoretical_values")
    if isinstance(theoretical, dict) and theoretical:
        theo_strs = [f"{k}={v}" for k, v in theoretical.items()]
        lines.append(f"- Theoretical Benchmark Values: {', '.join(theo_strs)}")

    discrepancy = data.get("discrepancy")
    if discrepancy is not None:
        lines.append(f"- Experimental Discrepancy / Error: {discrepancy}")

    status = data.get("status")
    if status:
        lines.append(f"- Simulation Status: {status}")

    return "\n".join(lines)


def format_learning_profile(profile: Optional[Dict[str, Any]]) -> str:
    """
    Formats the structured student learning profile for context awareness.
    """
    if not profile or not isinstance(profile, dict):
        return ""

    lines = ["\nStudent Learning Memory & Profile:"]
    topics_completed = profile.get("topics_completed") or []
    if topics_completed:
        lines.append(f"- Mastered Topics: {', '.join(str(t) for t in topics_completed)}")

    weak_concepts = profile.get("weak_concepts") or []
    if weak_concepts:
        lines.append(f"- Concepts Requiring Reinforcement: {', '.join(str(c) for c in weak_concepts)}")

    previous_mistakes = profile.get("previous_mistakes") or []
    if previous_mistakes:
        mistake_summaries = [str(m.get("summary", m)) if isinstance(m, dict) else str(m) for m in previous_mistakes[-3:]]
        lines.append(f"- Recent Misconceptions to address gently: {'; '.join(mistake_summaries)}")

    return "\n".join(lines)


def build_system_instruction(
    mode: Optional[str] = None,
    student_level: Optional[str] = None,
    experiment_state: Optional[Any] = None,
    learning_profile: Optional[Dict[str, Any]] = None,
    evaluation_note: Optional[str] = None,
    historical_context: Optional[List[Any]] = None,
) -> str:
    """
    Composes complete, sanitized system instructions tailored to the pedagogical mode,
    student level, laboratory state, and learning profile.
    """
    parts = [BASE_TUTOR_PERSONA]

    # Resolve mode
    resolved_mode = TutorMode.GUIDED_LEARNING
    if mode:
        if isinstance(mode, TutorMode):
            resolved_mode = mode
        else:
            mode_str = mode.value if hasattr(mode, "value") else str(mode)
            try:
                resolved_mode = TutorMode(mode_str.lower().strip())
            except ValueError:
                resolved_mode = TutorMode.GUIDED_LEARNING
    parts.append(MODE_DIRECTIVES[resolved_mode])

    # Resolve student level
    resolved_level = StudentLevel.INTERMEDIATE
    if student_level:
        if isinstance(student_level, StudentLevel):
            resolved_level = student_level
        else:
            lvl_str = student_level.value if hasattr(student_level, "value") else str(student_level)
            try:
                resolved_level = StudentLevel(lvl_str.lower().strip())
            except ValueError:
                resolved_level = StudentLevel.INTERMEDIATE
    parts.append(LEVEL_DIRECTIVES[resolved_level])

    # Experiment context
    exp_context = format_experiment_context(experiment_state)
    if exp_context:
        parts.append(exp_context)

    # Learning profile
    prof_context = format_learning_profile(learning_profile)
    if prof_context:
        parts.append(prof_context)

    # Evaluation note
    if evaluation_note:
        parts.append(f"\n{evaluation_note.strip()}")

    # Historical context
    if historical_context:
        if isinstance(historical_context, list) and historical_context:
            if "[LOW_CONFIDENCE]" in str(historical_context[0]):
                parts.append("\nNote: Relevant memory confidence is low; ground answers in fundamental physics principles.")
            else:
                context_str = "\n".join(f"- {item}" for item in historical_context[:3])
                parts.append(f"\nRelevant Previous Conversation Memories:\n{context_str}")

    return "\n\n".join(parts)
