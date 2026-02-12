import re
from typing import List, Dict

import streamlit as st
import pandas as pd
import plotly.express as px
import google.generativeai as genai

# ===================== API KEY & MODEL =========================
GENAI_API_KEY = "AIzaSyDTVSEtVpDB9egL0h-yoZFRNqF3xTr9VVE"       # <-- Replace with your real Gemini key
MODEL_ID = "gemini-1.5-flash"             # If you see 404/429 for this model, try: "gemini-2.0-flash" or "gemini-1.0-pro"
genai.configure(api_key=GENAI_API_KEY)
# ==============================================================


# ---------------------- TASK DEFINITIONS -----------------------
TASKS: List[Dict[str, str]] = [
    {"key": "workout_full", "title": "Full-body Workout Plan",
     "tpl": "Create a 7-day progressive full-body plan for a {age}-year-old {sport} {position}. Fitness: {fitness_level}. Goals: {goals}. Injuries: {injuries}. Constraints: {constraints}. Include sets x reps, rest, RPE, warm-up and cooldown."},
    {"key": "recovery_schedule", "title": "Safe Recovery Training",
     "tpl": "Create a 5-day low-impact recovery plan for a youth {sport} {position} with injuries: {injuries}. Emphasize mobility, flexibility, tissue tolerance, and pain-free ranges. Avoid unsafe exercises."},
    {"key": "tactical_coaching", "title": "Tactical Coaching",
     "tpl": "Provide tactical coaching for {sport}. Role: {position}. Priority skills: {goals}. Give 6 drills with tactical cues, constraints-led variations, and session objectives."},
    {"key": "nutrition_week", "title": "Week-long Nutrition Guide",
     "tpl": "Create a 7-day nutrition plan for a {age}-year-old youth athlete in {sport}. Diet: {diet}. Allergies: {allergies}. Calorie goal: {calorie_goal}. Include hydration and daily macro estimates."},
    {"key": "warmup_cooldown", "title": "Warm-up & Cooldown",
     "tpl": "Create a dynamic warm-up and cooldown for {sport} {position}. Avoid movements unsafe for: {injuries}."},
    {"key": "hydration_strategy", "title": "Hydration and Electrolytes",
     "tpl": "Provide a hydration and electrolyte strategy for a {sport} athlete training {training_days} days/week."},
    {"key": "mental_routine", "title": "Mental Focus Routine",
     "tpl": "Write a mental routine for a youth {sport} {position}. Include breath work, focus cues, and pre-match steps."},
    {"key": "visualization_drills", "title": "Visualization Drills",
     "tpl": "Write 3 short visualization drills for {sport} {position} to rehearse key decisions and goals: {goals}."},
    {"key": "post_injury_mobility", "title": "Post-injury Mobility",
     "tpl": "Create a 30-min mobility session safe for injuries: {injuries}. Include tempo, dosage, and safety cues."},
    {"key": "matchday_plan", "title": "Match-day Plan",
     "tpl": "Create a match-day checklist for a {sport} {position}. Include meals, hydration, warm-up timing, pacing, recovery."},
]

# ---------------------- REFERENCE DATA -------------------------
SPORT_POSITIONS: Dict[str, List[str]] = {
    "cricket": ["batter", "bowler", "fast bowler", "spinner", "wicketkeeper", "all-rounder"],
    "football": ["goalkeeper", "defender", "fullback", "midfielder", "winger", "striker"],
    "basketball": ["point guard", "shooting guard", "small forward", "power forward", "center"],
    "athletics": ["sprinter", "middle distance", "long distance", "jumps", "throws"],
    "badminton": ["singles", "doubles"],
    "tennis": ["baseline player", "serve-and-volley"],
    "hockey": ["goalkeeper", "defender", "midfielder", "forward"],
}

SAFETY_RULES: Dict[str, List[str]] = {
    "knee": ["box jumps", "deep lunges", "full-depth squat", "plyometric jumps"],
    "ankle": ["cutting drills", "high-impact jumps"],
    "shoulder": ["overhead pressing", "snatch", "kipping"],
    "hamstring": ["max sprinting", "heavy good mornings"],
    "back": ["heavy deadlifts", "loaded back extensions"],
}

# --------------------------- HELPERS ---------------------------
def detect_risks(text: str, injuries: List[str]) -> List[str]:
    flags: List[str] = []
    t = text.lower()
    for inj in injuries:
        for risk in SAFETY_RULES.get(inj, []):
            if risk in t:
                flags.append(f"⚠️ Risk for {inj}: includes '{risk}'")
    return flags

def extract_macros(text: str) -> pd.DataFrame | None:
    """Extract 'Day N ... #### kcal ... P g ... C g ... F g' lines -> DataFrame."""
    rows: List[Dict[str, int]] = []
    for line in text.splitlines():
        m = re.search(
            r"day\s*(\d+).*?(\d{3,4})\s*kcal.*?(\d{2,3})\s*g.*?(\d{2,3})\s*g.*?(\d{2,3})\s*g",
            line, re.I
        )
        if m:
            d, kcal, p, c, f = m.groups()
            rows.append({"Day": int(d), "Calories": int(kcal), "Protein(g)": int(p), "Carbs(g)": int(c), "Fat(g)": int(f)})
    return pd.DataFrame(rows).sort_values("Day") if rows else None

def plot_macros(df: pd.DataFrame):
    if df is None or df.empty:
        return None
    long_df = df.melt(id_vars="Day", var_name="Metric", value_name="Value")
    fig = px.line(long_df, x="Day", y="Value", color="Metric", markers=True, title="Nutrition Plan — Daily Targets")
    fig.update_layout(legend_title_text="Metric", height=420)
    return fig

def reset_app():
    st.session_state.clear()
    st.rerun()

def make_single_call_prompt(ctx: Dict[str, str | int], selected: List[Dict[str, str]]) -> str:
    """Builds one prompt that asks Gemini to produce all sections with clear delimiters."""
    name_rule = f"Address the athlete by name as {ctx['athlete_name']}. " if ctx.get("athlete_name") else ""
    header = (
        f"{name_rule}"
        f"You are a youth {ctx['sport']} coach. Use simple language suitable for a teenager. "
        f"Keep all advice conservative and age-appropriate. If unsure, say so.\n\n"
        "CONTEXT\n"
        f"- Sport: {ctx['sport']}\n"
        f"- Position: {ctx['position']}\n"
        f"- Age: {ctx['age']} | Fitness: {ctx['fitness_level']}\n"
        f"- Training days/week: {ctx['training_days']} | Session duration: {ctx['session_time']} min\n"
        f"- Goals: {ctx['goals']}\n"
        f"- Injuries: {ctx['injuries']}\n"
        f"- Constraints: {ctx['constraints']}\n"
        f"- Diet: {ctx['diet']} | Allergies: {ctx['allergies']} | Calorie goal: {ctx['calorie_goal']}\n\n"
        "OUTPUT FORMAT\n"
        "For each section below, start with a heading line EXACTLY like:\n"
        "### [[Section Title]]\n"
        "Then write the content for that section.\n"
        "If you include daily nutrition targets, use lines like: 'Day 1 — 2300 kcal — 140 g protein — 300 g carbs — 70 g fat'.\n\n"
        "SECTIONS TO PRODUCE\n"
    )
    body = ""
    for s in selected:
        body += f"- {s['title']}: {s['tpl'].format(**ctx)}\n"
    rules = "\nRULES\n- No placeholders like [your name] or [coach's name].\n- Prioritize safety for youth and injuries listed.\n"
    return header + body + rules

def split_sections(text: str) -> Dict[str, str]:
    """Splits the single-call output into {title: content} using ### [[Title]] markers."""
    # Ensure the first marker is found; otherwise return the whole thing as a single section
    pattern = re.compile(r"^### \[\[(.+?)\]\]\s*$", re.M)
    parts = pattern.split(text)
    # parts -> [preface, title1, content1, title2, content2, ...]
    if len(parts) < 3:
        return {"Full Plan": text.strip()}
    result: Dict[str, str] = {}
    preface = parts[0]  # discard preface
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        result[title] = content
    return result

# --------------------------- UI SETUP ---------------------------
st.set_page_config(page_title="CoachBot AI", page_icon="🏅", layout="wide")
st.title("🏅 CoachBot AI — Youth Athlete Fitness Assistant")

# Reset
st.button("🔄 Reset", on_click=reset_app)

# 0) Name
st.subheader("0) Athlete Details")
athlete_name = st.text_input("Athlete Name (optional):", "")

# 1) Profile
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

goals = st.multiselect("Goals", ["stamina", "strength", "speed", "agility", "tactics", "mobility", "injury prevention"], default=["stamina"])
injuries = st.multiselect("Injury History", ["knee", "ankle", "shoulder", "hamstring", "back", "none"], default=["none"])
if "none" in injuries and len(injuries) > 1:
    injuries.remove("none")
constraints = st.text_input("Training Constraints", "Limited equipment")

# 2) Nutrition
st.subheader("2) Nutrition Preferences")
diet = st.selectbox("Diet Preference", ["veg", "non-veg", "vegan"])
allergies = st.text_input("Allergies", "none")
calorie_goal = st.text_input("Calorie Goal (optional)", "")

# Features to include
st.markdown("---")
st.write("Select features to include (single API call will produce all selected sections):")
selected_keys: List[str] = []
for t in TASKS:
    if st.checkbox(t["title"], value=True):
        selected_keys.append(t["key"])

# ------------------------ GENERATE PLAN --------------------------
if st.button("Generate Plan 🚀"):
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
        "athlete_name": athlete_name.strip(),
    }

    # Pick selected sections
    selected_sections = [t for t in TASKS if t["key"] in selected_keys]

    # Build one prompt and call Gemini ONCE
    full_prompt = make_single_call_prompt(ctx, selected_sections)

    model = genai.GenerativeModel(model_name=MODEL_ID, generation_config={"temperature": 0.7})

    try:
        resp = model.generate_content(full_prompt)
        combined_text = resp.text if hasattr(resp, "text") else str(resp)
    except Exception as e:
        combined_text = f"Error generating content: {e}"

    sections = split_sections(combined_text)

    st.success("Plan generated! Review below:")
    if ctx["athlete_name"]:
        st.markdown(f"**Plan for:** {ctx['athlete_name']}")

    tabs = st.tabs(list(sections.keys()))
    for i, (title, content) in enumerate(sections.items()):
        with tabs[i]:
            st.markdown(content)

            # Safety flags
            flags = detect_risks(content, injuries)
            if flags:
                st.error("\n".join(flags))

            # Nutrition table + chart if macros detected
            if "nutrition" in title.lower():
                df = extract_macros(content)
                if df is not None:
                    st.markdown("**Estimated macros from the plan (table):**")
                    st.dataframe(df, use_container_width=True)
                    fig = plot_macros(df)
                    if fig is not None:
                        st.markdown("**Daily calorie & macro trends (chart):**")
                        st.plotly_chart(fig, use_container_width=True)

    # Download full plan
    md = "\n\n---\n\n".join([f"## {t}\n\n{c}" for t, c in sections.items()])
    st.download_button("Download Plan (Markdown)", data=md, file_name="coachbot_plan.md", mime="text/markdown")
