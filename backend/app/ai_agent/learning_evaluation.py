import re
import json
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
from pydantic import BaseModel, Field
from app.logger import logger


class LearningState(str, Enum):
    QUESTION_PRESENTED = "question_presented"
    ANSWER_RECEIVED = "answer_received"
    ANSWER_EVALUATED = "answer_evaluated"
    MASTERY_CONFIRMED = "mastery_confirmed"


class EvaluationResult(BaseModel):
    concept: str = Field(..., description="Target physics concept being evaluated")
    is_correct: bool = Field(..., description="Whether the answer demonstrates genuine conceptual understanding")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Evaluation confidence score")
    explanation: str = Field(..., description="Pedagogical explanation of why the answer is correct or incorrect")
    feedback: str = Field(..., description="Guiding feedback to support student learning progression")
    state: LearningState = Field(..., description="Current learning interaction state")
    mastery_awarded: bool = Field(False, description="Whether mastery milestone was newly awarded")
    xp_awarded: int = Field(0, description="Amount of XP awarded in this transaction")


# ==============================================================================
# Deterministic Conceptual Rubrics & Adversarial Detectors
# ==============================================================================

def evaluate_deterministic_rubric(
    concept: str,
    question: str,
    answer: str,
) -> Optional[Tuple[bool, float, str, str]]:
    """
    Applies deterministic physics rubrics to prevent adversarial trigger-phrase attacks
    (e.g. testing for negations, missing physical causality, or buzzword gaming).
    Returns (is_correct, confidence, explanation, feedback) if rubric applies, else None.
    """
    ans = answer.strip().lower()
    c_lower = concept.lower()

    # 1. Newton's Third Law Rubrics (Action-Reaction / Rocket thrust / Wall push)
    if "newton" in c_lower or "third law" in c_lower or "3rd law" in c_lower or "action" in c_lower:
        # Check for direct contradictions / negations
        negations = [
            "not go up", "doesn't go up", "does not go up", "never moves up",
            "not move up", "stays still", "remains stationary", "goes down",
            "moves down", "falls down", "no reaction", "stays down"
        ]
        if any(neg in ans for neg in negations):
            return (
                False,
                0.95,
                "The answer asserts that the rocket does not move up or moves downward, which violates Newton's Third Law.",
                "Remember that when hot exhaust gases are pushed downward by the rocket engine, an equal and opposite reaction force pushes the rocket upward.",
            )

        # Check for nonsensical / adversarial justifications (e.g. "it goes up because aliens/magic")
        if any(bogus in ans for bogus in ["magic", "alien", "luck", "random", "because i said so"]):
            return (
                False,
                0.95,
                "The response provides a non-physical justification rather than physical principles.",
                "Focus on the physical forces involved: What force does the downward expelled gas exert on the rocket body?",
            )

        # Check for adversarial / trivial trigger phrases without physical justification
        # E.g. "it goes up" or "moves up" with no explanation of reaction force
        has_trigger_phrase = bool(re.search(r"\b(it goes up|moves up|going up|goes up)\b", ans))
        has_physical_cause = any(kw in ans for kw in [
            "reaction", "force", "opposite", "thrust", "push", "exhaust", "gas",
            "momentum", "equal and opposite", "action"
        ])

        if has_trigger_phrase and not has_physical_cause:
            return (
                False,
                0.85,
                "The answer simply asserts 'it goes up' without explaining the physical mechanism.",
                "You mentioned it goes up, but why? Explain the action and reaction forces acting on the rocket according to Newton's Third Law.",
            )

        # Valid conceptual understanding: connects downward action to upward reaction force
        demonstrates_action_reaction = (
            ("reaction" in ans or "equal and opposite" in ans or "opposite" in ans)
            and ("up" in ans or "upward" in ans or "forward" in ans)
            and ("gas" in ans or "exhaust" in ans or "down" in ans or "force" in ans)
        )
        if demonstrates_action_reaction:
            return (
                True,
                0.95,
                "The answer accurately identifies Newton's Third Law: the downward expulsion of gas produces an equal and opposite upward reaction force on the rocket.",
                "Excellent scientific reasoning! You correctly identified the action-reaction force pair.",
            )

    return None


async def evaluate_learning_interaction(
    model,
    concept: str,
    question: str,
    student_answer: str,
) -> EvaluationResult:
    """
    Evaluates student answer against explicit learning states and criteria:
    1. Checks deterministic rubrics and adversarial filters first.
    2. Uses Gemini model for nuanced conceptual evaluation if available.
    3. Guarantees structured EvaluationResult with explicit confidence.
    """
    # Step 1: Run deterministic rubric verification
    rubric_match = evaluate_deterministic_rubric(concept, question, student_answer)
    if rubric_match:
        is_corr, conf, expl, fb = rubric_match
        state = LearningState.MASTERY_CONFIRMED if is_corr and conf >= 0.80 else LearningState.ANSWER_EVALUATED
        return EvaluationResult(
            concept=concept,
            is_correct=is_corr,
            confidence=conf,
            explanation=expl,
            feedback=fb,
            state=state,
        )

    # Step 2: Model-driven evaluation if model is configured
    if model:
        eval_prompt = (
            f"You are a rigorous, encouraging AI physics tutor evaluating a student's answer.\n"
            f"Target Concept: {concept}\n"
            f"Question: {question}\n"
            f"Student Answer: {student_answer}\n\n"
            f"Assess whether the student's answer demonstrates genuine understanding of {concept}.\n"
            f"CRITICAL RULE: Do NOT award credit for simple buzzwords or guessing without physical reasoning.\n\n"
            f"Return ONLY valid JSON matching this schema:\n"
            f'{{"is_correct": boolean, "confidence": float between 0.0 and 1.0, "explanation": string, "feedback": string}}\n'
        )
        try:
            if hasattr(model, "generate_content_async") and not hasattr(model, "_mock_return_value"):
                res = await model.generate_content_async(eval_prompt)
            else:
                res = await asyncio.to_thread(model.generate_content, eval_prompt)
            raw_text = res.text.strip()
            # Clean markdown codeblocks if present
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].split("```")[0].strip()

            parsed = json.loads(raw_text)
            is_corr = bool(parsed.get("is_correct", False))
            conf = min(1.0, max(0.0, float(parsed.get("confidence", 0.70))))
            expl = parsed.get("explanation", "Conceptual evaluation performed.")
            fb = parsed.get("feedback", "Keep practicing!")

            state = LearningState.MASTERY_CONFIRMED if is_corr and conf >= 0.80 else LearningState.ANSWER_EVALUATED
            return EvaluationResult(
                concept=concept,
                is_correct=is_corr,
                confidence=conf,
                explanation=expl,
                feedback=fb,
                state=state,
            )
        except Exception as e:
            logger.warning(f"Model evaluation fallback due to: {e}")

    # Step 3: Default conservative evaluation
    return EvaluationResult(
        concept=concept,
        is_correct=False,
        confidence=0.50,
        explanation="The response could not be verified as demonstrating concept mastery.",
        feedback="Please provide a more detailed explanation of the physical forces involved.",
        state=LearningState.ANSWER_EVALUATED,
    )
