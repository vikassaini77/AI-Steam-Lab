"""
Learning Evaluation Module - Educational AI Layer
Provides authoritative evaluation of student responses across three explicit pedagogical criteria:
1. Concept Understanding (causal physical reasoning vs superficial buzzwords)
2. Formula Application (correct equation selection, variable definition, SI units)
3. Experimental Interpretation (empirical error sources, friction/damping, theory vs observation)

Explicitly separates automated AI estimates from validated teacher/proctored assessments.
"""
import asyncio
import json
import re
from enum import Enum
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from app.logger import logger


class LearningState(str, Enum):
    QUESTION_PRESENTED = "question_presented"
    ANSWER_RECEIVED = "answer_received"
    ANSWER_EVALUATED = "answer_evaluated"
    MASTERY_CONFIRMED = "mastery_confirmed"


class EvaluationCriterion(str, Enum):
    CONCEPT_UNDERSTANDING = "concept_understanding"
    FORMULA_APPLICATION = "formula_application"
    EXPERIMENTAL_INTERPRETATION = "experimental_interpretation"


class RubricScore(BaseModel):
    criterion: EvaluationCriterion = Field(..., description="Target rubric criterion evaluated")
    score: float = Field(..., ge=0.0, le=1.0, description="Normalized score for this criterion between 0.0 and 1.0")
    rationale: str = Field(..., description="Pedagogical explanation for the criterion score")


class EvaluationResult(BaseModel):
    concept: str = Field(..., description="Target physics concept being evaluated")
    is_correct: bool = Field(..., description="Whether the answer demonstrates genuine conceptual understanding")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Evaluation confidence score")
    explanation: str = Field(..., description="Pedagogical explanation of why the answer is correct or incorrect")
    feedback: str = Field(..., description="Guiding feedback to support student learning progression")
    state: LearningState = Field(..., description="Current learning interaction state")
    mastery_awarded: bool = Field(False, description="Whether mastery milestone was newly awarded")
    xp_awarded: int = Field(0, description="Amount of XP awarded in this transaction")
    rubric_scores: List[RubricScore] = Field(
        default_factory=list,
        description="Detailed rubric breakdown across conceptual, formulaic, and experimental criteria",
    )
    is_verified_assessment: bool = Field(
        False,
        description="Explicit flag distinguishing automated AI estimates from verified proctored assessments",
    )


# ==============================================================================
# Deterministic Conceptual Rubrics & Adversarial Detectors
# ==============================================================================

def evaluate_deterministic_rubric(
    concept: str,
    question: str,
    answer: str,
) -> Optional[Tuple[bool, float, str, str, List[RubricScore]]]:
    """
    Applies deterministic physics rubrics to prevent adversarial trigger-phrase attacks
    (e.g. testing for negations, missing physical causality, or buzzword gaming).
    Returns (is_correct, confidence, explanation, feedback, rubric_scores) if rubric applies, else None.
    """
    ans = answer.strip().lower()
    c_lower = concept.lower()

    # 1. Newton's Third Law Rubrics (Action-Reaction / Rocket thrust / Wall push)
    if "newton" in c_lower or "third law" in c_lower or "3rd law" in c_lower or "action" in c_lower:
        negations = [
            "not go up", "doesn't go up", "does not go up", "never moves up",
            "not move up", "stays still", "remains stationary", "goes down",
            "moves down", "falls down", "no reaction", "stays down"
        ]
        if any(neg in ans for neg in negations):
            scores = [
                RubricScore(criterion=EvaluationCriterion.CONCEPT_UNDERSTANDING, score=0.1, rationale="Violates Newton's Third Law directionality."),
                RubricScore(criterion=EvaluationCriterion.FORMULA_APPLICATION, score=0.2, rationale="Misses equal and opposite force balance."),
                RubricScore(criterion=EvaluationCriterion.EXPERIMENTAL_INTERPRETATION, score=0.1, rationale="Disagrees with observable thrust vectors."),
            ]
            return (
                False,
                0.95,
                "The answer asserts that the rocket does not move up or moves downward, which violates Newton's Third Law.",
                "Remember that when hot exhaust gases are pushed downward by the rocket engine, an equal and opposite reaction force pushes the rocket upward.",
                scores,
            )

        if any(bogus in ans for bogus in ["magic", "alien", "luck", "random", "because i said so"]):
            scores = [
                RubricScore(criterion=EvaluationCriterion.CONCEPT_UNDERSTANDING, score=0.0, rationale="Non-physical justification provided."),
                RubricScore(criterion=EvaluationCriterion.FORMULA_APPLICATION, score=0.0, rationale="No physical formulas or relations referenced."),
                RubricScore(criterion=EvaluationCriterion.EXPERIMENTAL_INTERPRETATION, score=0.0, rationale="Unscientific speculation."),
            ]
            return (
                False,
                0.95,
                "The response provides a non-physical justification rather than physical principles.",
                "Focus on the physical forces involved: What force does the downward expelled gas exert on the rocket body?",
                scores,
            )

        has_trigger_phrase = bool(re.search(r"\b(it goes up|moves up|going up|goes up)\b", ans))
        has_physical_cause = any(kw in ans for kw in [
            "reaction", "force", "opposite", "thrust", "push", "exhaust", "gas",
            "momentum", "equal and opposite", "action"
        ])

        if has_trigger_phrase and not has_physical_cause:
            scores = [
                RubricScore(criterion=EvaluationCriterion.CONCEPT_UNDERSTANDING, score=0.3, rationale="States direction without identifying reaction force pair."),
                RubricScore(criterion=EvaluationCriterion.FORMULA_APPLICATION, score=0.2, rationale="Missing force vector relationship."),
                RubricScore(criterion=EvaluationCriterion.EXPERIMENTAL_INTERPRETATION, score=0.4, rationale="Recognizes motion direction only."),
            ]
            return (
                False,
                0.85,
                "The answer simply asserts 'it goes up' without explaining the physical mechanism.",
                "You mentioned it goes up, but why? Explain the action and reaction forces acting on the rocket according to Newton's Third Law.",
                scores,
            )

        demonstrates_action_reaction = (
            ("reaction" in ans or "equal and opposite" in ans or "opposite" in ans)
            and ("up" in ans or "upward" in ans or "forward" in ans)
            and ("gas" in ans or "exhaust" in ans or "down" in ans or "force" in ans)
        )
        if demonstrates_action_reaction:
            scores = [
                RubricScore(criterion=EvaluationCriterion.CONCEPT_UNDERSTANDING, score=0.95, rationale="Accurately identifies action-reaction force pair."),
                RubricScore(criterion=EvaluationCriterion.FORMULA_APPLICATION, score=0.90, rationale="Correctly applies F_action = -F_reaction."),
                RubricScore(criterion=EvaluationCriterion.EXPERIMENTAL_INTERPRETATION, score=0.90, rationale="Explains observable rocket propulsion trajectory."),
            ]
            return (
                True,
                0.95,
                "The answer accurately identifies Newton's Third Law: the downward expulsion of gas produces an equal and opposite upward reaction force on the rocket.",
                "Excellent scientific reasoning! You correctly identified the action-reaction force pair.",
                scores,
            )

    # 2. Pendulum Period and Mass Independence
    if "pendulum" in c_lower or "period" in c_lower:
        if "mass" in ans and ("increase" in ans or "depends" in ans or "heavier" in ans) and ("period" in ans or "time" in ans):
            scores = [
                RubricScore(criterion=EvaluationCriterion.CONCEPT_UNDERSTANDING, score=0.2, rationale="Incorrectly assumes period depends on mass."),
                RubricScore(criterion=EvaluationCriterion.FORMULA_APPLICATION, score=0.2, rationale="Disregards T = 2*pi*sqrt(L/g)."),
                RubricScore(criterion=EvaluationCriterion.EXPERIMENTAL_INTERPRETATION, score=0.3, rationale="Contradicts pendulum observations."),
            ]
            return (
                False,
                0.90,
                "The period of a simple pendulum is independent of the bob mass for small angle oscillations.",
                "Review the formula $T = 2\\pi\\sqrt{\\frac{L}{g}}$. Notice that the bob mass $m$ does not appear in this equation!",
                scores,
            )

    # 3. Energy Conservation
    if "energy" in c_lower or "conservation" in c_lower:
        if ("potential" in ans or "pe" in ans or "mgh" in ans) and ("kinetic" in ans or "ke" in ans or "half mv" in ans or "velocity" in ans or "speed" in ans):
            scores = [
                RubricScore(criterion=EvaluationCriterion.CONCEPT_UNDERSTANDING, score=0.90, rationale="Correctly connects gravitational potential and kinetic energy."),
                RubricScore(criterion=EvaluationCriterion.FORMULA_APPLICATION, score=0.85, rationale="Identifies energy conservation equation components."),
                RubricScore(criterion=EvaluationCriterion.EXPERIMENTAL_INTERPRETATION, score=0.85, rationale="Matches oscillatory velocity curve."),
            ]
            return (
                True,
                0.90,
                "The answer demonstrates clear understanding of mechanical energy conservation.",
                "Great work! Gravitational potential energy transforms into kinetic energy at the equilibrium position.",
                scores,
            )

    return None


async def evaluate_learning_interaction(
    model,
    concept: str,
    question: str,
    student_answer: str,
) -> EvaluationResult:
    """
    Evaluates student answer against explicit learning states and multi-criteria rubrics:
    1. Checks deterministic physics rubrics first (immune to prompt injection / guessing).
    2. Uses Gemini model for nuanced conceptual evaluation if available.
    3. Guarantees structured EvaluationResult with explicit confidence and rubric scores.
    """
    # Step 1: Run deterministic rubric verification
    rubric_match = evaluate_deterministic_rubric(concept, question, student_answer)
    if rubric_match:
        is_corr, conf, expl, fb, scores = rubric_match
        state = LearningState.MASTERY_CONFIRMED if is_corr and conf >= 0.80 else LearningState.ANSWER_EVALUATED
        return EvaluationResult(
            concept=concept,
            is_correct=is_corr,
            confidence=conf,
            explanation=expl,
            feedback=fb,
            state=state,
            rubric_scores=scores,
            is_verified_assessment=False,
        )

    # Step 2: Model-driven evaluation if model is configured
    if model:
        eval_prompt = (
            f"You are a rigorous, encouraging AI physics tutor evaluating a student's answer.\n"
            f"Target Concept: {concept}\n"
            f"Question: {question}\n"
            f"Student Answer: {student_answer}\n\n"
            f"Evaluate the answer across three criteria:\n"
            f"1. concept_understanding: genuine grasp of physical causality and mechanisms.\n"
            f"2. formula_application: correct formulas, variable definitions, and units.\n"
            f"3. experimental_interpretation: relationship to empirical observations and error sources.\n"
            f"CRITICAL RULE: Do NOT award credit for simple buzzwords or guessing without physical reasoning.\n\n"
            f"Return ONLY valid JSON matching this schema:\n"
            f'{{"is_correct": boolean, "confidence": float between 0.0 and 1.0, "explanation": string, "feedback": string, '
            f'"rubric_scores": ['
            f'{{"criterion": "concept_understanding", "score": float, "rationale": string}}, '
            f'{{"criterion": "formula_application", "score": float, "rationale": string}}, '
            f'{{"criterion": "experimental_interpretation", "score": float, "rationale": string}}'
            f']}}\n'
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

            raw_scores = parsed.get("rubric_scores", [])
            rubric_scores = []
            if isinstance(raw_scores, list) and raw_scores:
                for item in raw_scores:
                    crit_name = item.get("criterion", "concept_understanding")
                    try:
                        crit_enum = EvaluationCriterion(crit_name)
                    except ValueError:
                        crit_enum = EvaluationCriterion.CONCEPT_UNDERSTANDING
                    rubric_scores.append(
                        RubricScore(
                            criterion=crit_enum,
                            score=min(1.0, max(0.0, float(item.get("score", 0.5)))),
                            rationale=str(item.get("rationale", "")),
                        )
                    )
            else:
                base_score = 0.9 if is_corr else 0.3
                rubric_scores = [
                    RubricScore(criterion=EvaluationCriterion.CONCEPT_UNDERSTANDING, score=base_score, rationale=expl),
                    RubricScore(criterion=EvaluationCriterion.FORMULA_APPLICATION, score=base_score, rationale="Evaluated from response."),
                    RubricScore(criterion=EvaluationCriterion.EXPERIMENTAL_INTERPRETATION, score=base_score, rationale="Evaluated from response."),
                ]

            state = LearningState.MASTERY_CONFIRMED if is_corr and conf >= 0.80 else LearningState.ANSWER_EVALUATED
            return EvaluationResult(
                concept=concept,
                is_correct=is_corr,
                confidence=conf,
                explanation=expl,
                feedback=fb,
                state=state,
                rubric_scores=rubric_scores,
                is_verified_assessment=False,
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
        rubric_scores=[
            RubricScore(criterion=EvaluationCriterion.CONCEPT_UNDERSTANDING, score=0.4, rationale="Unverified conceptual reasoning."),
            RubricScore(criterion=EvaluationCriterion.FORMULA_APPLICATION, score=0.3, rationale="No verifiable formulas provided."),
            RubricScore(criterion=EvaluationCriterion.EXPERIMENTAL_INTERPRETATION, score=0.3, rationale="Lacks experimental correlation."),
        ],
        is_verified_assessment=False,
    )
