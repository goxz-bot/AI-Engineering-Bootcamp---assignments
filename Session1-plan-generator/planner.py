"""Core workout plan generation logic and Groq LLM integration."""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from groq import (
    APIConnectionError,
    APIError,
    APIStatusError,
    AuthenticationError,
    Groq,
    RateLimitError,
)

# Load environment variables from .env file
load_dotenv()

DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
MODEL_ALIASES = {
    "gpt-oss-20b": "openai/gpt-oss-20b",
    "gpt-oss-120b": "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
}


@dataclass
class PlanGenerationResult:
    """Structured response container for LLM calls to avoid uncaught crashes."""

    success: bool
    plan_markdown: str = ""
    error_message: str = ""
    model_used: str = ""


def validate_workout_inputs(
    fitness_goal: str,
    experience_level: str,
    days_per_week: int,
    equipment: list[str] | str,
    session_duration_mins: int = 45,
    injuries: Optional[str] = None,
) -> tuple[bool, str]:
    """Validate structured user inputs before making an LLM API call.

    Returns:
        tuple[bool, str]: (is_valid, friendly_error_message)
    """
    if not fitness_goal or not fitness_goal.strip():
        return False, "Please select a valid fitness goal before generating a plan."

    if not experience_level or not experience_level.strip():
        return False, "Please select your fitness experience level."

    if not isinstance(days_per_week, int) or days_per_week < 1 or days_per_week > 7:
        return (
            False,
            f"Invalid training frequency ({days_per_week} days selected). "
            "Please select between 1 and 7 training days per week so we can build a realistic schedule.",
        )

    if isinstance(equipment, list):
        cleaned_equipment = [item.strip() for item in equipment if item and item.strip()]
    elif isinstance(equipment, str):
        cleaned_equipment = [equipment.strip()] if equipment.strip() else []
    else:
        cleaned_equipment = []

    if not cleaned_equipment:
        return (
            False,
            "Please select at least one equipment option (e.g., 'No equipment', 'Home dumbbells', or 'Full gym').",
        )

    if session_duration_mins < 15 or session_duration_mins > 180:
        return (
            False,
            "Please choose a realistic session duration between 15 and 180 minutes.",
        )

    if injuries and len(injuries.strip()) > 500:
        return (
            False,
            "Your injuries/limitations description is too long (max 500 characters). "
            "Please summarize key movement restrictions.",
        )

    return True, ""


def normalize_equipment_list(equipment: list[str] | str) -> list[str]:
    """Normalize equipment input and resolve contradictory selections."""
    if isinstance(equipment, str):
        items = [equipment.strip()] if equipment.strip() else []
    else:
        items = [item.strip() for item in equipment if item and item.strip()]

    # If the user selected "No equipment" along with actual equipment, keep only "No equipment"
    # when it's the sole item; otherwise clarify what is available.
    if len(items) > 1 and "No equipment" in items:
        items = [item for item in items if item != "No equipment"]

    return items


def build_system_prompt(has_injuries: bool) -> str:
    """Construct a strict, constraint-aware system prompt for the personal trainer LLM."""
    disclaimer_rule = (
        "4. MANDATORY INJURY & SAFETY DISCLAIMER: Because the user reported an injury or physical limitation, "
        "you MUST begin the plan with a clearly visible '> ⚠️ **Safety & Medical Disclaimer:**' block stating that "
        "this plan is for informational and educational purposes only, does not constitute medical advice or physical "
        "therapy, and the user should consult a qualified healthcare professional or physical therapist before starting, "
        "stopping immediately if any sharp pain occurs."
        if has_injuries
        else "4. SCOPE & SAFETY: Stay strictly within the scope of certified personal training. Do not make medical claims "
        "or diagnoses. Include a brief general fitness safety note reminding the user to warm up properly and use good form."
    )

    return f"""You are an elite, evidence-based Certified Strength and Conditioning Specialist (CSCS) and Personal Trainer.
Your job is to create a highly practical, personalized, week-long workout plan that a real person can immediately follow.

CRITICAL RULES YOU MUST OBEY WITHOUT EXCEPTION:
1. STRICT EQUIPMENT COMPLIANCE:
   - You may ONLY prescribe exercises that can be performed with the exact equipment listed by the user.
   - If the user has "No equipment", prescribe ONLY bodyweight/calisthenics exercises. NEVER include dumbbells, barbells, cables, pull-up bars, or gym machines.
   - If the user has "Home dumbbells" (and NOT "Full gym"), prescribe ONLY dumbbell and bodyweight exercises. NEVER include barbell bench presses, cable pulldowns, leg presses, or smith machines.
   - If the user has "Full gym", you may use barbells, dumbbells, cables, machines, and bodyweight appropriately for their experience level.

2. STRICT INJURY & LIMITATION COMPLIANCE:
   - Carefully analyze any reported injuries or movement limitations.
   - NEVER prescribe exercises that load, aggravate, or conflict with the stated injury/limitation (e.g., if "bad knees", avoid heavy deep barbell squats, jumping plyometrics, or forward lunges; substitute knee-friendly glute/hamstring/hinge or supported movements).
   - For every day, briefly note how the chosen exercises accommodate their limitations.

3. STRICT SCHEDULE & EXPERIENCE COMPLIANCE:
   - Create EXACTLY the number of training days requested (e.g., if 3 days/week is requested, output Workout Day 1, Workout Day 2, and Workout Day 3, plus brief guidance on how to space rest/active recovery days across the 7-day week).
   - Match volume (sets/reps), exercise complexity, and intensity (RPE) to their Experience Level:
     * Beginner: Focus on foundational movement patterns, controlled tempo, moderate volume (2–3 sets per exercise), RPE 6–7, clear form cues.
     * Intermediate: Balanced split, progressive overload focus, moderate-high volume (3–4 sets per exercise), RPE 7–8.
     * Advanced: Higher specificity, optimal stimulus-to-fatigue ratio, targeted accessory work (3–5 sets), RPE 8–9.

{disclaimer_rule}

5. REQUIRED OUTPUT FORMAT (Clean Markdown, NO wall of text):
   Structure your response using these exact Markdown sections:
   - **Disclaimer Block** (Required at the very top if injuries are mentioned)
   - **## 📋 Plan Overview & Training Split**: A concise summary table or bullet list confirming Goal, Level, Schedule (Days/Week & Session Duration), Equipment Used, and how constraints/injuries are respected.
   - **## 🔥 Daily Warm-Up Protocol (5–8 Mins)**: 3–4 specific dynamic warm-up movements tailored to the user's equipment and joints.
   - **## 🗓️ Weekly Workout Schedule**:
     Break down each workout day clearly (`### Day 1: [Focus/Split Name]`, `### Day 2: ...`, up to the exact number of requested training days).
     For EACH workout day, provide a Markdown table with columns:
     `| # | Exercise | Target Muscle | Sets | Reps / Duration | Rest | RPE | Form & Modification Cue |`
   - **## 🧘 Cool-Down & Recovery Recommendations**: Brief rest-day and mobility guidelines.
   - **## 📈 4-Week Progression Strategy**: Concrete rules on how the user should progress week-to-week (e.g., double progression, adding reps before weight)."""


def build_workout_prompt(
    fitness_goal: str,
    experience_level: str,
    days_per_week: int,
    equipment: list[str] | str,
    injuries: Optional[str] = None,
    session_duration_mins: int = 45,
    preferred_style: str = "Balanced / Coach's Optimal Choice",
    variation_number: int = 1,
) -> str:
    """Build a structured, detailed user prompt from the collected form inputs."""
    equipment_list = normalize_equipment_list(equipment)
    equipment_str = ", ".join(equipment_list)
    injuries_clean = injuries.strip() if injuries and injuries.strip() else "None reported"

    # Explicit equipment boundary reminder in the user prompt so the LLM never hallucinates gear
    if equipment_list == ["No equipment"]:
        equipment_boundary = (
            "STRICT CONSTRAINT: Bodyweight ONLY. Do NOT include any weights, dumbbells, bands, pull-up bars, or machines."
        )
    elif "Full gym" not in equipment_list:
        equipment_boundary = (
            f"STRICT CONSTRAINT: Use ONLY [{equipment_str}] and bodyweight. "
            "Do NOT include barbells, cable machines, leg curl/extension machines, or gym-only apparatus."
        )
    else:
        equipment_boundary = f"Available equipment: {equipment_str}."

    variation_instruction = ""
    if variation_number > 1:
        variation_instruction = (
            f"\nVARIATION REQUEST (Variation #{variation_number}): "
            "The user requested a fresh variation of their plan. Choose a DIFFERENT weekly split structure "
            "or a fresh set of biomechanically equivalent exercises compared to a standard default template, "
            "while still strictly obeying every equipment, injury, and schedule constraint."
        )

    return f"""Please design a complete, personalized weekly workout plan for the following client profile:

### Client Profile & Constraints
- **Primary Fitness Goal:** {fitness_goal}
- **Experience Level:** {experience_level}
- **Training Frequency:** Exactly {days_per_week} training day(s) per week
- **Target Session Duration:** ~{session_duration_mins} minutes per workout (including warm-up)
- **Equipment Access:** {equipment_str} ({equipment_boundary})
- **Preferred Training Style / Focus:** {preferred_style}
- **Injuries / Physical Limitations:** {injuries_clean}
{variation_instruction}

### Checklist Before You Output:
1. Are there EXACTLY {days_per_week} workout days (`Day 1` through `Day {days_per_week}`) with Markdown exercise tables?
2. Does every single exercise strictly use ONLY `{equipment_str}`?
3. Does every single exercise safely avoid aggravating `{injuries_clean}`?
4. Do the total sets and rest times realistically fit within a {session_duration_mins}-minute window?

Generate the structured Markdown workout plan now."""


def _validate_llm_plan_output(content: Optional[str]) -> tuple[bool, str]:
    """Check if the LLM output is non-empty and properly structured."""
    if not content or not content.strip():
        return False, "The AI returned an empty response. Please try clicking 'Generate Plan' again."

    # Normalize narrow non-breaking spaces (\u202f) and non-breaking spaces (\u00a0) to standard spaces
    cleaned = content.replace("\u202f", " ").replace("\u00a0", " ").strip()
    if len(cleaned) < 120 or ("day 1" not in cleaned.lower() and "|" not in cleaned):
        return (
            False,
            "The AI returned a malformed or incomplete workout plan. Please click 'Generate Plan' or 'Regenerate' to try again.",
        )

    return True, cleaned


def _get_groq_client_and_model() -> tuple[Optional[Groq], str, Optional[str]]:
    """Retrieve Groq client and configured model from environment variables."""
    # Reload .env in case user updated it while app is running
    load_dotenv(override=True)
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    raw_model = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL).strip() or DEFAULT_GROQ_MODEL
    model = MODEL_ALIASES.get(raw_model, raw_model)

    # Handle case where .env has placeholder or empty key
    if not api_key or api_key in {"<api-key>", "your_groq_api_key_here", "your_key_here"}:
        return (
            None,
            model,
            "Missing or placeholder `GROQ_API_KEY` in `.env`. "
            "Please open the `.env` file, set `GROQ_API_KEY=gsk_...` with your valid Groq API key, and try again.",
        )

    return Groq(api_key=api_key), model, None


def generate_workout_plan(
    fitness_goal: str,
    experience_level: str,
    days_per_week: int,
    equipment: list[str] | str,
    injuries: Optional[str] = None,
    session_duration_mins: int = 45,
    preferred_style: str = "Balanced / Coach's Optimal Choice",
    variation_number: int = 1,
) -> PlanGenerationResult:
    """Validate inputs, build a constraint-aware prompt, call the Groq API, and return the result.

    Wrapped in try/except to guarantee the Streamlit app never crashes on invalid inputs,
    network issues, bad API keys, rate limits, or malformed LLM responses.
    """
    try:
        # 1. Validate structured inputs
        is_valid, validation_error = validate_workout_inputs(
            fitness_goal=fitness_goal,
            experience_level=experience_level,
            days_per_week=days_per_week,
            equipment=equipment,
            session_duration_mins=session_duration_mins,
            injuries=injuries,
        )
        if not is_valid:
            return PlanGenerationResult(success=False, error_message=validation_error)

        # 2. Initialize Groq client from .env
        client, model, key_error = _get_groq_client_and_model()
        if key_error or client is None:
            return PlanGenerationResult(
                success=False,
                error_message=key_error or "Could not initialize Groq client.",
                model_used=model,
            )

        # 3. Build prompts
        has_injuries = bool(injuries and injuries.strip())
        system_prompt = build_system_prompt(has_injuries=has_injuries)
        user_prompt = build_workout_prompt(
            fitness_goal=fitness_goal,
            experience_level=experience_level,
            days_per_week=days_per_week,
            equipment=equipment,
            injuries=injuries,
            session_duration_mins=session_duration_mins,
            preferred_style=preferred_style,
            variation_number=variation_number,
        )

        # Slightly increase temperature on regeneration for creative exercise variety
        temperature = 0.5 if variation_number == 1 else min(0.8, 0.5 + (variation_number * 0.1))

        # 4. Call Groq Chat Completions API
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=6000,
        )

        if not completion or not getattr(completion, "choices", None):
            return PlanGenerationResult(
                success=False,
                error_message="Received an empty response structure from Groq API. Please try again.",
                model_used=model,
            )

        raw_content = completion.choices[0].message.content
        is_output_ok, processed_content = _validate_llm_plan_output(raw_content)
        if not is_output_ok:
            return PlanGenerationResult(
                success=False,
                error_message=processed_content,
                model_used=model,
            )

        return PlanGenerationResult(
            success=True,
            plan_markdown=processed_content,
            model_used=model,
        )

    except AuthenticationError:
        return PlanGenerationResult(
            success=False,
            error_message=(
                "Authentication failed with Groq API. Your `GROQ_API_KEY` in `.env` appears to be invalid or expired. "
                "Please verify your key at https://console.groq.com/keys."
            ),
        )
    except RateLimitError:
        return PlanGenerationResult(
            success=False,
            error_message=(
                "Groq API rate limit reached. Please wait a few seconds and try generating your workout plan again."
            ),
        )
    except APIConnectionError:
        return PlanGenerationResult(
            success=False,
            error_message=(
                "Network connection failed while contacting the Groq API. "
                "Please check your internet connection and try again."
            ),
        )
    except APIStatusError as exc:
        return PlanGenerationResult(
            success=False,
            error_message=(
                f"Groq API returned an error (HTTP {exc.status_code}). "
                "If you set a custom `GROQ_MODEL` in `.env`, verify that the model name is supported (e.g. `llama-3.3-70b-versatile`)."
            ),
        )
    except APIError as exc:
        return PlanGenerationResult(
            success=False,
            error_message=f"Groq API error occurred: {exc.message}. Please try again shortly.",
        )
    except Exception as exc:
        return PlanGenerationResult(
            success=False,
            error_message=f"An unexpected error occurred while generating your plan: {str(exc)}",
        )


def swap_exercise_in_plan(
    current_plan: str,
    exercise_to_swap: str,
    fitness_goal: str,
    experience_level: str,
    equipment: list[str] | str,
    injuries: Optional[str] = None,
    swap_reason: Optional[str] = None,
) -> PlanGenerationResult:
    """Replace a single exercise in an existing workout plan while preserving structure and constraints.

    Implements the 'Swap this exercise' stretch goal with full type hints and try/except protection.
    """
    try:
        if not current_plan or not current_plan.strip():
            return PlanGenerationResult(
                success=False,
                error_message="No active workout plan found. Please generate a workout plan first.",
            )

        target_exercise = exercise_to_swap.strip() if exercise_to_swap else ""
        if not target_exercise:
            return PlanGenerationResult(
                success=False,
                error_message="Please enter the name of the exercise you would like to swap.",
            )

        if len(target_exercise) > 120:
            return PlanGenerationResult(
                success=False,
                error_message="Exercise name is too long. Please enter just the name of the single exercise to swap.",
            )

        client, model, key_error = _get_groq_client_and_model()
        if key_error or client is None:
            return PlanGenerationResult(
                success=False,
                error_message=key_error or "Could not initialize Groq client.",
                model_used=model,
            )

        equipment_str = ", ".join(normalize_equipment_list(equipment))
        injuries_str = injuries.strip() if injuries and injuries.strip() else "None reported"
        reason_str = swap_reason.strip() if swap_reason and swap_reason.strip() else "User preference / variety"

        system_prompt = """You are an expert Certified Strength and Conditioning Specialist (CSCS).
The user wants to SWAP ONE SPECIFIC EXERCISE in their current weekly workout plan for a biomechanically similar alternative.

CRITICAL INSTRUCTIONS:
1. Replace ONLY the requested exercise (`exercise_to_swap`) in the workout plan with a safe, effective alternative that targets the same primary muscle group / movement pattern.
2. Strictly respect the user's Available Equipment and Injuries/Limitations.
3. Keep the rest of the weekly workout plan (all other exercises, days, warm-up, cool-down, and disclaimers) intact.
4. At the very top of your response, add a brief callout block:
   `> 🔄 **Exercise Swapped:** Replaced **[Old Exercise]** with **[New Exercise]** — *[1-sentence explanation of why this alternative fits their goal, equipment, and joint constraints].*`
5. Then output the complete updated Markdown workout plan."""

        user_prompt = f"""### User Constraints
- **Fitness Goal:** {fitness_goal}
- **Experience Level:** {experience_level}
- **Available Equipment (STRICT):** {equipment_str}
- **Injuries / Limitations (STRICT):** {injuries_str}

### Swap Request
- **Exercise to Replace:** {target_exercise}
- **Reason for Swap:** {reason_str}

### Current Workout Plan to Update
{current_plan}"""

        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=6000,
        )

        if not completion or not getattr(completion, "choices", None):
            return PlanGenerationResult(
                success=False,
                error_message="Received an empty response from Groq API while swapping the exercise.",
                model_used=model,
            )

        raw_content = completion.choices[0].message.content
        is_output_ok, processed_content = _validate_llm_plan_output(raw_content)
        if not is_output_ok:
            return PlanGenerationResult(
                success=False,
                error_message=processed_content,
                model_used=model,
            )

        return PlanGenerationResult(
            success=True,
            plan_markdown=processed_content,
            model_used=model,
        )

    except AuthenticationError:
        return PlanGenerationResult(
            success=False,
            error_message="Authentication failed with Groq API. Please check your `GROQ_API_KEY` in `.env`.",
        )
    except RateLimitError:
        return PlanGenerationResult(
            success=False,
            error_message="Groq API rate limit reached. Please wait a moment before swapping an exercise.",
        )
    except APIConnectionError:
        return PlanGenerationResult(
            success=False,
            error_message="Network connection failed while contacting the Groq API. Please check your internet connection.",
        )
    except APIStatusError as exc:
        return PlanGenerationResult(
            success=False,
            error_message=f"Groq API error (HTTP {exc.status_code}). Please check your `GROQ_MODEL` setting in `.env`.",
        )
    except Exception as exc:
        return PlanGenerationResult(
            success=False,
            error_message=f"Could not swap the exercise due to an unexpected error: {str(exc)}",
        )

