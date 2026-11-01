# 🏋️ Personalized Workout Plan Generator

A single-page **Streamlit** application that collects structured personal-trainer inputs and generates a customized, constraint-aware weekly workout plan using an LLM via the **Groq API**.

Built for the **Codebasics AI Engineering Cohort — Session 1 Assignment**.

---

## ✨ Features

### Core Requirements
1. **Structured Personal Trainer Inputs**:
   - **Fitness Goal** (`Build muscle`, `Lose fat`, `General fitness`, `Improve endurance`)
   - **Experience Level** (`Beginner`, `Intermediate`, `Advanced`)
   - **Days Available per Week** (`1–7` training days, with friendly validation if `0` is selected)
   - **Equipment Access** (`No equipment`, `Home dumbbells`, `Full gym`, `Resistance bands`, `Pull-up bar`, `Kettlebells`)
   - **Additional Trainer Context** (Session duration in minutes & preferred training style)
   - **Optional Injuries or Physical Limitations** (Free text, e.g., `"bad knees"`, `"no overhead pressing"`)
2. **Constraint-Aware Prompt Engineering**:
   - Strictly enforces available equipment (e.g., zero gym machines or weights when `No equipment` is selected).
   - Substitutes joint-friendly alternatives whenever injuries/limitations are provided and includes a prominent **Safety & Medical Disclaimer**.
   - Formats the output into structured Markdown tables (`Day 1`, `Day 2`, ... with Exercise, Target Muscle, Sets, Reps, Rest, RPE, and Form Cues), plus warm-up, cool-down, and 4-week progression guidelines.
3. **Clean Python Architecture & Error Handling**:
   - Type-hinted functions separated into [`planner.py`](./planner.py) and [`app.py`](./app.py).
   - Wrapped in `try/except` blocks handling invalid inputs, missing/bad API keys, rate limits, network errors, and empty/malformed LLM responses without crashing.

### Stretch Goals Included
- 🔄 **Regenerate Plan Variation**: Generate fresh exercise selections or weekly split variations while keeping all user constraints intact.
- 💾 **Session State Persistence**: Stores the generated plan and active profile in `st.session_state` across reruns.
- 📥 **Export / Download**: Download the plan directly as a Markdown (`.md`) or Plain Text (`.txt`) file.
- 🔀 **Swap This Exercise**: Replace any single exercise in the active plan with a biomechanically similar alternative that respects all equipment and injury constraints.

---

## 🚀 Setup & Installation

### 1. Configure Environment Variables (`.env`)

Copy `.env.sample` to `.env` inside `Session1-plan-generator/` and add your Groq API key from [console.groq.com/keys](https://console.groq.com/keys):

```bash
cp .env.sample .env
```

Edit `.env`:
```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
```

### 2. Install Dependencies & Run

#### Option A: Using `uv` (Recommended)
```bash
cd Session1-plan-generator
uv sync
uv run streamlit run app.py
```

#### Option B: Using `venv` + `pip`
```bash
cd Session1-plan-generator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

