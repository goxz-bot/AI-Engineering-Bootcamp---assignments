"""Streamlit UI for the Personalized Workout Plan Generator (Session 1 Assignment)."""

import streamlit as st

from planner import generate_workout_plan, normalize_equipment_list, swap_exercise_in_plan

# Page configuration
st.set_page_config(
    page_title="AI Personal Trainer — Workout Plan Generator",
    page_icon="🏋️",
    layout="wide",
)


def init_session_state() -> None:
    """Initialize Streamlit session_state keys so plans persist across reruns."""
    if "workout_plan" not in st.session_state:
        st.session_state.workout_plan = ""
    if "last_inputs" not in st.session_state:
        st.session_state.last_inputs = {}
    if "variation_number" not in st.session_state:
        st.session_state.variation_number = 1
    if "model_used" not in st.session_state:
        st.session_state.model_used = ""
    if "last_error" not in st.session_state:
        st.session_state.last_error = ""


def render_header() -> None:
    """Render the page title and subtitle."""
    st.title("🏋️ Personalized Workout Plan Generator")
    st.markdown(
        "Tell your **AI Personal Trainer** about your fitness goals, schedule, equipment, and any "
        "physical limitations to get a structured, constraint-aware weekly workout routine you can actually follow."
    )
    st.divider()


def main() -> None:
    """Main Streamlit app entrypoint."""
    init_session_state()
    render_header()

    # Left column: Structured Inputs | Right column: Generated Plan & Stretch Goal Tools
    input_col, output_col = st.columns([1, 1.55], gap="large")

    with input_col:
        st.subheader("1️⃣ Your Fitness Profile")
        st.caption("Complete the structured inputs below so the plan fits your exact situation.")

        fitness_goal: str = st.selectbox(
            "🎯 Fitness Goal",
            options=[
                "Build muscle",
                "Lose fat",
                "General fitness",
                "Improve endurance",
            ],
            index=0,
            help="Select your primary training objective.",
        )

        experience_level: str = st.selectbox(
            "📊 Experience Level",
            options=[
                "Beginner",
                "Intermediate",
                "Advanced",
            ],
            index=0,
            help="Determines exercise complexity, weekly volume (sets/reps), and intensity (RPE).",
        )

        # Allow 0..7 so selecting 0 demonstrates friendly validation handling without crashing
        days_per_week: int = st.slider(
            "🗓️ Days Available per Week",
            min_value=0,
            max_value=7,
            value=4,
            step=1,
            help="Select how many days per week you can realistically train (1–7 days).",
        )

        equipment: list[str] = st.multiselect(
            "🏠 Equipment Access",
            options=[
                "No equipment",
                "Home dumbbells",
                "Full gym",
                "Resistance bands",
                "Pull-up bar",
                "Kettlebells",
            ],
            default=["Home dumbbells"],
            help="Select all equipment you have access to. The AI will strictly limit exercises to these options.",
        )

        with st.expander("⚙️ Additional Trainer Context (Duration & Style)", expanded=True):
            session_duration_mins: int = st.select_slider(
                "⏱️ Target Session Duration (minutes)",
                options=[20, 30, 45, 60, 75, 90],
                value=45,
                help="Helps the trainer calibrate the number of exercises and sets per workout.",
            )

            preferred_style: str = st.selectbox(
                "⚡ Preferred Training Style",
                options=[
                    "Balanced / Coach's Optimal Choice",
                    "Strength & Compound Focus",
                    "Time-Efficient Supersets / Circuit",
                    "Joint-Friendly & Controlled Tempo",
                ],
                index=0,
            )

        injuries: str = st.text_area(
            "🩹 Optional: Injuries or Physical Limitations",
            placeholder='e.g., "bad knees", "no overhead pressing", "lower back tightness"',
            max_chars=500,
            help="List any painful movements, past injuries, or exercises you need to avoid.",
        )

        generate_clicked: bool = st.button(
            "🚀 Generate Plan",
            type="primary",
            use_container_width=True,
        )

        if generate_clicked:
            st.session_state.variation_number = 1
            current_inputs = {
                "fitness_goal": fitness_goal,
                "experience_level": experience_level,
                "days_per_week": days_per_week,
                "equipment": equipment,
                "injuries": injuries,
                "session_duration_mins": session_duration_mins,
                "preferred_style": preferred_style,
            }
            st.session_state.last_inputs = current_inputs

            with st.spinner("Designing your personalized weekly workout plan..."):
                result = generate_workout_plan(
                    fitness_goal=fitness_goal,
                    experience_level=experience_level,
                    days_per_week=days_per_week,
                    equipment=equipment,
                    injuries=injuries,
                    session_duration_mins=session_duration_mins,
                    preferred_style=preferred_style,
                    variation_number=1,
                )

            if result.success:
                st.session_state.workout_plan = result.plan_markdown
                st.session_state.model_used = result.model_used
                st.session_state.last_error = ""
                st.toast("Workout plan generated!", icon="✅")
            else:
                st.session_state.last_error = result.error_message
                st.error(f"⚠️ **Could not generate plan:** {result.error_message}")

    with output_col:
        st.subheader("2️⃣ Your Personalized Weekly Plan")

        if st.session_state.last_error:
            st.error(f"⚠️ **Could not generate plan:** {st.session_state.last_error}")

        if not st.session_state.workout_plan:
            st.info(
                "👈 Configure your fitness goals and constraints on the left, then click **Generate Plan** "
                "to create your custom day-by-day workout schedule."
            )
            return

        # Summary pills of the active plan's constraints
        saved = st.session_state.last_inputs
        if saved:
            eq_display = ", ".join(normalize_equipment_list(saved.get("equipment", [])))
            inj_display = saved.get("injuries", "").strip() or "None"
            st.caption(
                f"**Active Profile:** 🎯 {saved.get('fitness_goal')} · "
                f"📊 {saved.get('experience_level')} · "
                f"🗓️ {saved.get('days_per_week')} days/wk ({saved.get('session_duration_mins')}m) · "
                f"🏋️ {eq_display} · "
                f"🩹 Injuries: {inj_display} · "
                f"🔢 Variation #{st.session_state.variation_number}"
            )

        # Action bar: Stretch Goals (Regenerate + Download as .md or .txt)
        act_col1, act_col2, act_col3 = st.columns([1.2, 1, 1])

        with act_col1:
            regenerate_clicked = st.button(
                "🔄 Regenerate Plan Variation",
                use_container_width=True,
                help="Generate a fresh variation of the plan with different exercise selections or split structure.",
            )

        with act_col2:
            st.download_button(
                label="📥 Download (.md)",
                data=st.session_state.workout_plan,
                file_name="workout_plan.md",
                mime="text/markdown",
                use_container_width=True,
            )

        with act_col3:
            st.download_button(
                label="📄 Download (.txt)",
                data=st.session_state.workout_plan,
                file_name="workout_plan.txt",
                mime="text/plain",
                use_container_width=True,
            )

        if regenerate_clicked and saved:
            next_variation = st.session_state.variation_number + 1
            with st.spinner(f"Generating Variation #{next_variation} with fresh exercises..."):
                regen_result = generate_workout_plan(
                    fitness_goal=saved["fitness_goal"],
                    experience_level=saved["experience_level"],
                    days_per_week=saved["days_per_week"],
                    equipment=saved["equipment"],
                    injuries=saved["injuries"],
                    session_duration_mins=saved["session_duration_mins"],
                    preferred_style=saved["preferred_style"],
                    variation_number=next_variation,
                )

            if regen_result.success:
                st.session_state.variation_number = next_variation
                st.session_state.workout_plan = regen_result.plan_markdown
                st.session_state.model_used = regen_result.model_used
                st.rerun()
            else:
                st.error(f"⚠️ **Could not regenerate plan:** {regen_result.error_message}")

        # Stretch Goal: Swap a single exercise mini-feature
        with st.expander("🔀 Swap This Exercise (Replace One Exercise in Your Plan)", expanded=False):
            st.caption(
                "Don't like a specific movement or missing a piece of gear? Enter the exercise name below "
                "to swap just that movement while keeping the rest of your plan intact."
            )
            swap_col1, swap_col2 = st.columns(2)
            with swap_col1:
                exercise_to_swap: str = st.text_input(
                    "Exercise to Replace",
                    placeholder='e.g., "Bulgarian Split Squat" or "Push-ups"',
                )
            with swap_col2:
                swap_reason: str = st.text_input(
                    "Optional Reason / Preference",
                    placeholder='e.g., "Uncomfortable on my hip" or "Want a glute-focused alternative"',
                )

            if st.button("🔀 Swap Exercise", use_container_width=True):
                with st.spinner(f"Finding the best replacement for '{exercise_to_swap}'..."):
                    swap_result = swap_exercise_in_plan(
                        current_plan=st.session_state.workout_plan,
                        exercise_to_swap=exercise_to_swap,
                        fitness_goal=saved.get("fitness_goal", fitness_goal),
                        experience_level=saved.get("experience_level", experience_level),
                        equipment=saved.get("equipment", equipment),
                        injuries=saved.get("injuries", injuries),
                        swap_reason=swap_reason,
                    )

                if swap_result.success:
                    st.session_state.workout_plan = swap_result.plan_markdown
                    st.toast("Exercise swapped successfully!", icon="🔄")
                    st.rerun()
                else:
                    st.warning(f"⚠️ {swap_result.error_message}")

        # Display the formatted Markdown plan inside a clean bordered container
        with st.container(border=True):
            st.markdown(st.session_state.workout_plan)


if __name__ == "__main__":
    main()

