import re
from typing import List, Dict

import streamlit as st
import pandas as pd
import google.generativeai as genai

# =====================  API KEY (HARD-CODED) =====================
GENAI_API_KEY = "AIzaSyA9OQMnlQm92Dp63QGDjXHv7I6WG3a5Aq0"  # <-- put your real Gemini API key here
genai.configure(api_key=GENAI_API_KEY)
# ================================================================


# -------------------------- Task Model --------------------------
class Task:
    def __init__(self, key: str, title: str, description: str, prompt_template: str):
        self.key = key
        self.title = title
        self.description = description
        self.prompt_template = prompt_template


# --------------------------- Tasks List --------------------------
TASKS: List[Task] = [
    Task(
        key="workout_full",
        title="Full-body Workout Plan",
        description="7-day full-body plan with sets x reps, rest, RPE, warm-up & cooldown.",
        prompt_template=(
            "Act as an elite youth {sport} coach. Create a 7-day progressive full-body training plan for a "
            "{age}-year-old {position}. Fitness: {fitness_level}. Goals: {goals}. "
            "Injuries: {injuries}. Constraints: {constraints}. Provide sets x reps, rest, RPE (1-10), cues. "
            "Include warm-up and cooldown for each day."
        ),
    ),
    Task(
        key="recovery_schedule",
        title="Safe Recovery Training",
        description="5-day low-impact recovery microcycle.",
        prompt_template=(
            "Design a 5-day low-impact recovery plan for a youth {sport} {position} with injuries: {injuries}. "
            "Emphasize mobility, tissue tolerance, flexibility, and pain-free ranges. Avoid contraindicated moves."
        ),
    ),
    Task(
        key="tactical_coaching",
        title="Tactical Coaching",
        description="6 drills with tactical cues and objectives.",
        prompt_template=(
            "Provide tactical coaching for {sport}. Role: {position}. Priority skills: {goals}. "
            "Include 6 drills with tactical cues, constraints-led variations, and session objectives."
        ),
    ),
    Task(
        key="nutrition_week",
        title="Week-long Nutrition Guide",
        description="7-day plan with hydration; macros/day if possible.",
        prompt_template=(
            "Create a 7-day nutrition plan for a {age}-year-old youth {sport} athlete. Diet: {diet}. "
            "Allergies: {allergies}. Calorie target: {calorie_goal}. Provide daily macros and hydration tips."
        ),
    ),
    Task(
        key="warmup_cooldown",
        title="Warm-up & Cooldown",
        description="Position-specific, injury-aware warm-up and cooldown.",
        prompt_template=(
            "Generate a dynamic warm-up (10-15 min) and cooldown (10 min) for {sport} {position}. "
            "Avoid or regress movements unsafe for: {injuries}."
        ),
    ),
    Task(
        key="hydration_strategy",
        title="Hydration & Electrolytes",
        description="Daily hydration and match-day plan.",
        prompt_template=(
            "Outline a hydration and electrolyte strategy for a {sport} athlete training {training_days} days/week in a warm climate. "
            "Include pre/during/post guidelines and practical measures for school tournaments."
        ),
    ),
    Task(
        key="mental_routine",
        title="Mental Focus Routine",
        description="Breath work, cues, imagery, pre-match routine.",
        prompt_template=(
            "Provide a mental skills routine for a youth {sport} {position}, including breath work, focus cues, imagery, and a pre-match routine. "
            "Keep language coach-like and age-appropriate."
        ),
    ),
    Task(
        key="visualization_drills",
        title="Visualization Drills",
        description="Three short pre-match scripts.",
        prompt_template=(
            "Write 3 short visualization scripts for {sport} {position} to rehearse key decisions linked to goals: {goals}."
        ),
    ),
    Task(
        key="post_injury_mobility",
        title="Post-Injury Mobility",
        description="30-minute mobility/tissue-prep circuit.",
        prompt_template=(
            "Create a 30-minute mobility and tissue-prep circuit safe for: {injuries}. "
            "List exercises, dosage, tempo, and pain-monitoring rules."
        ),
    ),
    Task(
        key="matchday_plan",
        title="Match-day Plan",
        description="Warm-up timing, fueling, pacing, recovery checklist.",
        prompt_template=(
            "Create a match-day checklist for a {sport} {position}. Include meals/snacks timing, hydration, activation, pacing, "
            "and immediate post-match recovery."
        ),
    ),
]  # <- end of TASKS list


# ------------------------ Reference Data ------------------------
SPORT_POSITIONS: Dict[str, List[str]] = {
    "cricket": ["batter", "bowler", "fast bowler", "spinner", "wicketkeeper", "all-rounder"],
    "football": ["goalkeeper", "defender", "fullback", "midfielder", "winger", "striker"],
    "basketball": ["point guard", "shooting guard", "small forward", "power forward", "center"],
    "athletics": ["sprinter", "middle distance", "long distance", "jumps", "throws"],
    "badminton": ["singles", "doubles"],
    "tennis": ["baseline player", "serve-and-volley"],
    "hockey": ["goalkeeper", "defender", "midfielder", "forward"],
}  # <- end of SPORT_POSITIONS dict

SAFETY_RULES: Dict[str, List[str]] = {
    "knee": ["deep lunges", "box jumps", "full-depth squat", "plyometric jumps"],
    "ankle": ["cutting drills", "high-impact jumps"],
    "shoulder": ["overhead pressing", "kipping", "snatch"],
    "hamstring": ["max sprinting", "good mornings (heavy)"],
    "back": ["heavy deadlifts", "back extensions (loaded)"],
}


# --------------------------- Utilities ---------------------------
def validate_inputs(age: int, training_days: int, goals: List[str]) -> List[str]:
    warnings: List[str] = []
    if age < 10:
        warnings.append("Age is below 10; keep loads playful and technique-focused.")
    if training_days > 7:
        warnings.append("Training days exceed 7; adjust to a realistic weekly schedule.")
    if not goals:
        warnings.append("No goals selected; add at least one training objective.")
    return warnings


def detect_risks(text: str, injuries: List[str]) -> List[str]:
    flags: List[str] = []
    lt = text.lower()
    for injury in injuries:
        key = injury.split()[0].lower()
        for risk in SAFETY_RULES.get(key, []):
            if risk in lt:
                flags.append(f"Potential risk for {injury}: mentions '{risk}'.")
    return flags


def extract_macros(text: str):
    # Parse lines like: "Day 1 ... 2300 kcal ... 140 g ... 300 g ... 70 g"
    days = []
    for line in text.splitlines():
        m = re.search(r"day\s*(\d+).*?(\d{2,4})\s*kcal.*?(\d{2,4})\s*g.*?(\d{2,4})\s*g.*?(\d{2,4})\s*g", line, re.I)
        if m:
            d, kcal, p, c, f = m.groups()
            days.append({"Day": int(d), "Calories": int(kcal), "Protein(g)": int(p), "Carbs(g)": int(c), "Fat(g)": int(f)})
    if days:
        return pd.DataFrame(days).sort_values("Day")
    return None


# ------------------------------ UI ------------------------------
st.set_page_config(page_title="CoachBot AI – Youth Sports Assistant", page_icon="🏅", layout="wide")
st.title("🏅 CoachBot AI – Smart Fitness Assistant")
st.caption("Personalized workouts, recovery, tactics, and nutrition for youth athletes. (Educational use only)")

with st.sidebar:
    st.header("Configuration")
    temperature = st.slider("Temperature", 0.0, 1.0, 0.7, 0.05)
    st.markdown("---")
    st.write("Select which features to include:")
    selected_keys: List[str] = []
    for t in TASKS:
        if st.checkbox(t.title, value=True, help=t.description):
            selected_keys.append(t.key)

st.subheader("1) Athlete Profile")
c1, c2, c3 = st.columns(3)
with c1:
    sport = st.selectbox("Sport", list(SPORT_POSITIONS.keys()), key="sport")
with c2:
    position = st.selectbox("Position/Role", SPORT_POSITIONS.get(st.session_state.get("sport", sport), SPORT_POSITIONS[sport]))
with c3:
    age = st.number_input("Age (years)", min_value=8, max_value=19, value=15)

c4, c5, c6 = st.columns(3)
with c4:
    fitness_level = st.selectbox("Fitness level", ["beginner", "intermediate", "advanced"])
with c5:
    training_days = st.slider("Training days per week", 1, 7, 4)
with c6:
    session_time = st.slider("Session duration (minutes)", 20, 120, 60, 5)

goals = st.multiselect(
    "Training goals",
    ["stamina", "strength", "speed", "agility", "tactical improvement", "post-injury recovery", "injury prevention", "mobility", "weight management"],
    default=["stamina", "tactical improvement"],
)

injuries = st.multiselect("Injury history or risk zones", ["knee", "ankle", "shoulder", "hamstring", "back", "none"], default=["none"])
if "none" in injuries and len(injuries) > 1:
    injuries.remove("none")

constraints = st.text_area("Constraints (equipment/time/facility)", "School gym access, limited equipment.")

st.subheader("2) Nutrition Preferences")
n1, n2, n3 = st.columns(3)
with n1:
    diet = st.selectbox("Diet preference", ["veg", "non-veg", "vegan"])
with n2:
    allergies = st.text_input("Allergies (comma-separated)", "none")
with n3:
    calorie_goal = st.text_input("Calorie goal (kcal/day, optional)", "")

warns = validate_inputs(age, training_days, goals)
if warns:
    st.warning("\n".join(warns))

if st.button("Generate Coaching Plan 🚀", type="primary"):
    ctx: Dict[str, str | int] = {
        "sport": sport,
        "position": position,
        "age": age,
        "fitness_level": fitness_level,
        "goals": ", ".join(goals) if goals else "general development",
        "injuries": ", ".join(injuries) if injuries else "none",
        "constraints": constraints,
        "diet": diet,
        "allergies": allergies,
        "calorie_goal": calorie_goal or "not specified",
        "training_days": training_days,
        "session_time": session_time,
    }

    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        generation_config={"temperature": float(temperature)},
    )

    outputs: Dict[str, str] = {}
    with st.spinner("Calling Gemini and assembling plans..."):
        for task in TASKS:
            if task.key not in selected_keys:
                continue
            prompt = (
                task.prompt_template.format(**ctx)
                + "\n\nRules: Use simple language for a teenager. Keep advice safe, conservative, and age-appropriate. If unsure, say so."
            )
            try:
                resp = model.generate_content([prompt])
                text = resp.text if hasattr(resp, "text") else str(resp)
            except Exception as e:
                text = f"Error generating content: {e}"
            outputs[task.title] = text

    st.success("Plan generated. Review each section below.")

    tabs = st.tabs(list(outputs.keys()))
    for i, (title, text) in enumerate(outputs.items()):
        with tabs[i]:
            st.markdown(text)

            # Nutrition table if macros detected (no charts)
            if "nutrition" in title.lower():
                df = extract_macros(text)
                if df is not None:
                    st.markdown("**Estimated macros from the plan:**")
                    st.dataframe(df, use_container_width=True)

            # Simple risk flags
            flags = detect_risks(text, injuries)
            if flags:
                st.error("\n".join(flags))

    # Download all sections as Markdown
    combined = [f"## {k}\n\n{v}" for k, v in outputs.items()]
    md = "\n\n---\n\n".join(combined)
    st.download_button("⬇️ Download full plan (Markdown)", data=md, file_name="coachbot_plan.md", mime="text/markdown")

st.markdown("---")
st.caption("Disclaimer: CoachBot AI is for educational purposes only and does not replace qualified medical or coaching advice.")

# ------------------------------- Helper Data ---------------------------------
SPORT_POSITIONS = {
    "cricket": ["batter", "bowler", "fast bowler", "spinner", "wicketkeeper", "all-rounder"],
