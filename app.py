import os
import re
from typing import List, Dict

import streamlit as st
import pandas as pd
import google.generativeai as genai

# ───────────────────────────────────────────────
#  HARDCODE YOUR GEMINI API KEY HERE
# ───────────────────────────────────────────────
GENAI_API_KEY = "YOUR_API_KEY_HERE"    # ← Replace with your real key

genai.configure(api_key=GENAI_API_KEY)
# ───────────────────────────────────────────────


# ----------------------------- Prompt Definitions -----------------------------
class Task:
    def __init__(self, key: str, title: str, description: str, prompt_template: str):
        self.key = key
        self.title = title
        self.description = description
        self.prompt_template = prompt_template

TASKS: List[Task] = [
    Task(
        key="workout_full",
        title="Full-body Workout Plan",
        description="7-day full-body plan with sets×reps, rest, RPE.",
        prompt_template=(
            "Act as an elite youth {sport} coach. Create a 7-day full-body plan for a "
            "{age}-year-old {position}. Fitness: {fitness_level}. Goals: {goals}. "
            "Injuries: {injuries}. Constraints: {constraints}. Include warm-up and cooldown."
        ),
    ),
    Task(
        key="recovery_schedule",
        title="Safe Recovery Training",
        description="5-day low-impact rehabilitation plan.",
        prompt_template=(
            "Create a 5-day low-impact recovery plan for a youth {sport} {position} with injuries: {injuries}. "
            "Focus on mobility, flexibility, and pain-free progressions."
        ),
    ),
    Task(
        key="tactical_coaching",
        title="Tactical Coaching",
        description="6 tactical drills with objectives.",
        prompt_template=(
            "Provide tactical coaching for {sport}. Role: {position}. Goals: {goals}. "
            "Include 6 drills and tactical cues."
        ),
    ),
    Task(
        key="nutrition_week",
        title="Week-long Nutrition Guide",
        description="7-day nutrition plan with hydration.",
        prompt_template=(
            "Create a 7-day nutrition plan for a {age}-year-old {sport} athlete. Diet: {diet}. "
            "Allergies: {allergies}. Calories: {calorie_goal}. Include hydration and macros/day."
        ),
    ),
    Task(
        key="warmup_cooldown",
        title="Warm-up & Cooldown",
        description="Position-specific warm-up and cooldown.",
        prompt_template=(
            "Generate a warm-up (10–15 min) and cooldown for {sport} {position}. "
            "Avoid movements unsafe for injuries: {injuries}."
        ),
    ),
    Task(
        key="hydration_strategy",
        title="Hydration & Electrolytes",
        description="Daily and match hydration guidelines.",
        prompt_template=(
            "Provide a hydration and electrolyte strategy for a {sport} athlete training {training_days} days/week."
        ),
    ),
    Task(
        key="mental_routine",
        title="Mental Focus Routine",
        description="Mindset routine for young athletes.",
        prompt_template=(
            "Provide a mental skills routine for a youth {sport} {position}. Include breathwork, focus cues, imagery."
        ),
    ),
    Task(
        key="visualization_drills",
        title="Visualization Drills",
        description="Three pre-match scripts.",
        prompt_template=(
            "Write 3 short visualization scripts for a {sport} {position} focused on {goals}."
        ),
    ),
    Task(
        key="post_injury_mobility",
        title="Post-Injury Mobility",
        description="30-min safe mobility session.",
        prompt_template=(
            "Write a 30-min mobility session safe for these injuries: {injuries}. Include dosage and tempo."
        ),
    ),
    Task(
        key="matchday_plan",
        title="Match-day Plan",
        description="Fueling, warm-up, and recovery checklist.",
        prompt_template=(
            "Create a match-day checklist for a {sport} {position}. Meals, hydration, warm-up, pacing."
        ),
    ),
]

# ------------------------------- Helper Data ---------------------------------
SPORT_POSITIONS = {
    "cricket": ["batter", "bowler", "fast bowler", "spinner", "wicketkeeper", "all-rounder"],
    "football": ["goalkeeper", "defender", "midfielder", "winger", "striker"],
    "basketball": ["point guard", "shooting guard", "small forward", "power forward", "center"],
}

SAFETY_RULES = {
    "knee": ["box jumps", "plyometric jumps"],
    "ankle": ["cutting drills"],
    "shoulder": ["overhead pressing"],
}

def detect_risks(text, injuries):
    flags = []
    lt = text.lower()
    for inj in injuries:
        for risk in SAFETY_RULES.get(inj, []):
            if risk in lt:
                flags.append(f"Risk for {inj}: contains '{risk}'")
    return flags

def extract_macros(text):
    days = []
    for line in text.splitlines():
        m = re.search(r"day (\d+).*?(\d{3,4}) kcal.*?(\d{2,3}) g.*?(\d{2,3}) g.*?(\d{2,3}) g", line, re.I)
        if m:
            d, kcal, p, c, f = m.groups()
            days.append({"Day": int(d), "Calories": int(kcal), "Protein(g)": int(p), "Carbs(g)": int(c), "Fat(g)": int(f)})
    if days:
        return pd.DataFrame(days)
    return None


# --------------------------------- UI -----------------------------------------
st.title("🏅 CoachBot AI — Smart Fitness Assistant")
st.caption("AI-generated fitness, recovery, tactics, and nutrition for youth athletes.")

with st.sidebar:
    st.header("⚙️ Settings")
    temperature = st.slider("Temperature", 0.0, 1.0, 0.7)
    top_p = st.slider("Top-p", 0.0, 1.0, 0.9)
    top_k = st.slider("Top-k", 1, 64, 32)
    st.markdown("### Select features:")
    selected_keys = [t.key for t in TASKS if st.checkbox(t.title, True)]

sport = st.selectbox("Sport", list(SPORT_POSITIONS.keys()))
position = st.selectbox("Position", SPORT_POSITIONS[sport])
age = st.number_input("Age", 8, 19, 15)
fitness = st.selectbox("Fitness Level", ["beginner", "intermediate", "advanced"])
injuries = st.multiselect("Injury history", ["knee", "ankle", "shoulder", "none"], ["none"])
if "none" in injuries and len(injuries) > 1:
    injuries.remove("none")

goals = st.multiselect("Goals", ["stamina", "strength", "speed", "tactics", "mobility"], ["stamina"])
diet = st.selectbox("Diet", ["veg", "non-veg", "vegan"])
allergies = st.text_input("Allergies", "none")
cal_goal = st.text_input("Calorie Goal", "not specified")
constraints = st.text_area("Training Constraints", "Limited equipment")

if st.button("Generate Plan 🚀"):
    ctx = {
        "sport": sport,
        "position": position,
        "age": age,
        "fitness_level": fitness,
        "goals": ", ".join(goals),
        "injuries": ", ".join(injuries),
        "constraints": constraints,
        "diet": diet,
        "allergies": allergies,
        "calorie_goal": cal_goal,
    }

    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        generation_config={"temperature": temperature, "top_p": top_p, "top_k": top_k},
    )

    outputs = {}

    for task in TASKS:
        if task.key in selected_keys:
            prompt = task.prompt_template.format(**ctx)
            resp = model.generate_content(prompt)
            outputs[task.title] = resp.text

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

st.markdown("---")
st.caption("Educational use only — not medical advice.")
