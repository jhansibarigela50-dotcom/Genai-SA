import re
from typing import List, Dict
import streamlit as st
import pandas as pd
import google.generativeai as genai

# ===================== API KEY (HARDCODED) =====================
GENAI_API_KEY = "AIzaSyA9OQMnlQm92Dp63QGDjXHv7I6WG3a5Aq0"  # <-- Replace this with your real key
genai.configure(api_key=GENAI_API_KEY)
# ==============================================================


# ---------------------- TASK DEFINITIONS -----------------------
TASKS = [
    {
        "key": "workout_full",
        "title": "Full-body Workout Plan",
        "tpl": (
            "Act as an elite youth {sport} coach. Create a 7-day progressive full-body plan for a "
            "{age}-year-old {position}. Fitness: {fitness_level}. Goals: {goals}. Injuries: {injuries}. "
            "Constraints: {constraints}. Include sets x reps, rest, RPE, warm-up and cooldown."
        ),
    },
    {
        "key": "recovery_schedule",
        "title": "Safe Recovery Training",
        "tpl": (
            "Create a 5-day low-impact recovery plan for a youth {sport} {position} with injuries: {injuries}. "
            "Focus on mobility, flexibility, and pain-free progressions. Avoid unsafe exercises."
        ),
    },
    {
        "key": "tactical_coaching",
        "title": "Tactical Coaching",
        "tpl": (
            "Provide tactical coaching for {sport}. Role: {position}. Skill priority: {goals}. "
            "Give 6 drills with tactical cues and session objectives."
        ),
    },
    {
        "key": "nutrition_week",
        "title": "Week-long Nutrition Guide",
        "tpl": (
            "Create a 7-day nutrition plan for a {age}-year-old youth athlete in {sport}. Diet: {diet}. "
            "Allergies: {allergies}. Calorie goal: {calorie_goal}. Include hydration and daily macro estimates."
        ),
    },
    {
        "key": "warmup_cooldown",
        "title": "Warm-up & Cooldown",
        "tpl": (
            "Create a dynamic warm-up and cooldown routine for {sport} {position}. Avoid movements unsafe for: {injuries}."
        ),
    },
    {
        "key": "hydration_strategy",
        "title": "Hydration and Electrolytes",
        "tpl": (
            "Provide a hydration and electrolyte strategy for a {sport} athlete training {training_days} days/week."
        ),
    },
    {
        "key": "mental_routine",
        "title": "Mental Focus Routine",
        "tpl": (
            "Write a mental routine for a youth {sport} {position}. Include breath work, mindset cues, and pre-match focus steps."
        ),
    },
    {
        "key": "visualization_drills",
        "title": "Visualization Drills",
        "tpl": (
            "Write 3 short visualization drills for {sport} {position} to rehearse key decisions and goals: {goals}."
        ),
    },
    {
        "key": "post_injury_mobility",
        "title": "Post-injury Mobility",
        "tpl": (
            "Create a 30-min mobility session safe for injuries: {injuries}. Include tempo, dosage, and safety cues."
        ),
    },
    {
        "key": "matchday_plan",
        "title": "Match-day Plan",
        "tpl": (
            "Create a match-day checklist for a {sport} {position}. Include meals, hydration, warm-up timing, pacing, recovery."
        ),
    },
]


# ---------------------- REFERENCE DATA -------------------------
SPORT_POSITIONS = {
    "cricket": ["batter", "bowler", "fast bowler", "spinner", "wicketkeeper", "all-rounder"],
    "football": ["goalkeeper", "defender", "fullback", "midfielder", "winger", "striker"],
    "basketball": ["point guard", "shooting guard", "small forward", "power forward", "center"],
    "athletics": ["sprinter", "middle distance", "long distance", "jumps", "throws"],
    "badminton": ["singles", "doubles"],
    "tennis": ["baseline player", "serve-and-volley"],
    "hockey": ["goalkeeper", "defender", "midfielder", "forward"],
}

SAFETY_RULES = {
    "knee": ["box jumps", "deep lunges", "full-depth squat"],
    "ankle": ["cutting drills", "high-impact jumps"],
    "shoulder": ["overhead pressing", "snatch"],
    "hamstring": ["max sprinting", "heavy good mornings"],
    "back": ["heavy deadlifts", "loaded back extensions"],
}


# --------------------------- HELPERS ---------------------------
def detect_risks(text, injuries):
    flags = []
    t = text.lower()
    for inj in injuries:
        for risk in SAFETY_RULES.get(inj, []):
            if risk in t:
                flags.append(f"⚠️ Risk for {inj}: includes '{risk}'")
    return flags


def extract_macros(text):
    rows = []
    for line in text.splitlines():
        m = re.search(
            r"day\s*(\d+).*?(\d{3,4})\s*kcal.*?(\d{2,3})\s*g.*?(\d{2,3})\s*g.*?(\d{2,3})\s*g",
            line, re.I
        )
        if m:
            d, kcal, p, c, f = m.groups()
            rows.append(
                {"Day": int(d), "Calories": int(kcal), "Protein(g)": int(p),
                 "Carbs(g)": int(c), "Fat(g)": int(f)}
            )
    return pd.DataFrame(rows) if rows else None


def reset_app():
    st.session_state.clear()
    st.rerun()


# --------------------------- UI SETUP ---------------------------
st.set_page_config(page_title="CoachBot AI", page_icon="⚽", layout="wide")
st.title("🏅 CoachBot AI — Youth Athlete Fitness Assistant")

# RESET BUTTON
st.button("🔄 Reset", on_click=reset_app)

st.subheader("0) Athlete Details")
athlete_name = st.text_input("Athlete Name (optional):", "")


# -------------------- Athlete Profile Section --------------------
st.subheader("1) Athlete Profile")
c1, c2, c3 = st.columns(3)
with c1:
    sport = st.selectbox("Sport", list(SPORT_POSITIONS.keys()))
with c2:
    position = st.selectbox("Position/Role", SPORT_POSITIONS[sport])
with c3:
    age = st.number_input("Age", min_value=8, max_value=19, value=15)

c4, c5, c6 = st.columns(3)
with c4:
    fitness_level = st.selectbox("Fitness Level", ["beginner", "intermediate", "advanced"])
with c5:
    training_days = st.slider("Training Days/Week", 1, 7, 4)
with c6:
    session_time = st.slider("Session Duration (min)", 20, 120, 60)


goals = st.multiselect(
    "Goals",
    ["stamina", "strength", "speed", "agility", "tactics", "mobility", "injury prevention"],
    default=["stamina"]
)

injuries = st.multiselect(
    "Injury History",
    ["knee", "ankle", "shoulder", "hamstring", "back", "none"],
    default=["none"]
)
if "none" in injuries and len(injuries) > 1:
    injuries.remove("none")

constraints = st.text_input("Training Constraints", "Limited equipment")


# --------------------- Nutrition Section ------------------------
st.subheader("2) Nutrition Preferences")
diet = st.selectbox("Diet Preference", ["veg", "non-veg", "vegan"])
allergies = st.text_input("Allergies", "none")
calorie_goal = st.text_input("Calorie Goal (optional)", "")


# ------------------------ GENERATE PLAN --------------------------
if st.button("Generate Plan 🚀"):
    ctx = {
        "sport": sport,
        "position": position,
        "age": age,
        "fitness_level": fitness_level,
        "goals": ", ".join(goals),
        "injuries": ", ".join(injuries),
        "constraints": constraints,
        "diet": diet,
        "allergies": allergies,
        "calorie_goal": calorie_goal or "not specified",
        "training_days": training_days,
        "session_time": session_time,
        "athlete_name": athlete_name,
    }

    if athlete_name:
        name_rule = f"Address the athlete by name as {athlete_name}. "
    else:
        name_rule = ""

    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config={"temperature": 0.7},
    )

    outputs = {}
    for t in TASKS:
        prompt = (
            name_rule +
            t["tpl"].format(**ctx) +
            "\n\nRules: Use simple language. Avoid placeholders. Keep it safe for youth."
        )

        try:
            resp = model.generate_content(prompt)
            text = resp.text
        except Exception as e:
            text = f"Error generating content: {e}"

        outputs[t["title"]] = text

    st.success("Plan generated! Review below:")

    tabs = st.tabs(list(outputs.keys()))

    for i, (title, content) in enumerate(outputs.items()):
        with tabs[i]:
            st.markdown(content)

            risks = detect_risks(content, injuries)
            if risks:
                st.error("\n".join(risks))

            if "nutrition" in title.lower():
                df = extract_macros(content)
                if df is not None:
                    st.dataframe(df)


    md = "\n\n---\n\n".join([f"## {t}\n\n{c}" for t, c in outputs.items()])
    st.download_button("Download Plan (Markdown)", md, "coachbot_plan.md")
``
