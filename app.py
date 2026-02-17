import re
import time
from typing import List, Dict, Optional, Tuple

import streamlit as st
import pandas as pd
import plotly.express as px
import google.generativeai as genai

# ===================== API KEY & MODEL =========================
GENAI_API_KEY = "YOUR_API_KEY_HERE"  # <-- Replace with your real Gemini key (starts with AIza...)
MODEL_ID = "gemini-1.5-flash"        # Good free-tier quota; change if needed
genai.configure(api_key=GENAI_API_KEY.strip())
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

def extract_macros(text: str) -> Optional[pd.DataFrame]:
    """Extract 'Day N ... #### kcal ... P g ... C g ... F g' lines -> DataFrame."""
    rows: List[Dict[str, int]] = []
    for line in text.splitlines():
        m = re.search(r"day\s*(\d+).*?(\d{3,4})\s*kcal.*?(\d{2,3})\s*g.*?(\d{2,3})\s*g.*?(\d{2,3})\s*g", line, re.I)
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

def build_context_block(ctx: Dict[str, str | int]) -> str:
    """Reusable context block for prompts and chat."""
    return (
        "CONTEXT\n"
        f"- Sport: {ctx['sport']}\n"
        f"- Position: {ctx['position']}\n"
        f"- Age: {ctx['age']} | Fitness: {ctx['fitness_level']}\n"
        f"- Training days/week: {ctx['training_days']} | Session: {ctx['session_time']} min\n"
        f"- Goals: {ctx['goals']}\n"
        f"- Injuries: {ctx['injuries']}\n"
        f"- Constraints: {ctx['constraints']}\n"
        f"- Diet: {ctx['diet']} | Allergies: {ctx['allergies']} | Calorie goal: {ctx['calorie_goal']}\n"
    )

def make_single_call_prompt(ctx: Dict[str, str | int], selected: List[Dict[str, str]]) -> str:
    """Ask Gemini to produce all selected sections at once with clear markers."""
    name_rule = f"Address the athlete by name as {ctx['athlete_name']}. " if ctx.get("athlete_name") else ""
    header = (
        f"{name_rule}"
        f"You are a youth {ctx['sport']} coach. Use simple language suitable for a teenager. "
        f"Keep all advice conservative and age-appropriate. If unsure, say so.\n\n"
        + build_context_block(ctx)
        + "\nOUTPUT FORMAT\n"
          "For each section below, start with a heading EXACTLY like:\n"
          "### [[Section Title]]\n"
          "If you include daily nutrition targets, use lines like: 'Day 1 — 2300 kcal — 140 g protein — 300 g carbs — 70 g fat'.\n\n"
          "SECTIONS TO PRODUCE\n"
    )
    body = "".join([f"- {s['title']}: {s['tpl'].format(**ctx)}\n" for s in selected])
    rules = "\nRULES\n- No placeholders like [your name] or [coach's name].\n- Prioritize safety for youth and listed injuries.\n"
    return header + body + rules

def split_sections(text: str) -> Dict[str, str]:
    """Split single-call output into {title: content} using ### [[Title]] markers."""
    pattern = re.compile(r"^### \[\[(.+?)\]\]\s*$", re.M)
    parts = pattern.split(text)
    if len(parts) < 3:
        return {"Full Plan": text.strip()}
    result: Dict[str, str] = {}
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        result[title] = content
    return result

def call_gemini_once(model_id: str, prompt: str, temperature: float = 0.7, max_attempts: int = 2) -> str:
    """Call Gemini once; if rate-limited, wait 'retry in Xs' (parsed from message) and retry once."""
    model = genai.GenerativeModel(model_name=model_id, generation_config={"temperature": temperature})
    delay_pattern = re.compile(r"(?:retry in|retry_delay\s*\{\s*seconds:\s*)(\d+)", re.I)
    last_err = None
    for attempt in range(max_attempts):
        try:
            resp = model.generate_content(prompt)
            return resp.text if hasattr(resp, "text") else str(resp)
        except Exception as e:
            msg = str(e)
            last_err = msg
            m = delay_pattern.search(msg)
            if m and attempt + 1 < max_attempts:
                wait_s = min(int(m.group(1)) + 1, 60)
                time.sleep(wait_s)
                continue
            break
    return f"Error generating content: {last_err or 'unknown error'}"

def verify_key(model_id: str, api_key: str) -> Tuple[bool, str]:
    """Tiny probe to validate the key before generating the full plan or chatting."""
    try:
        genai.configure(api_key=api_key.strip())
        model = genai.GenerativeModel(model_name=model_id, generation_config={"temperature": 0})
        resp = model.generate_content("ping")
        _ = resp.text
        genai.configure(api_key=GENAI_API_KEY.strip())  # restore
        return True, "OK"
    except Exception as e:
        genai.configure(api_key=GENAI_API_KEY.strip())
        return False, str(e)


# --------------------------- UI SETUP ---------------------------
st.set_page_config(page_title="CoachBot AI", page_icon="🏅", layout="wide")
st.title("🏅 CoachBot AI — Youth Athlete Fitness Assistant")

# Reset (full app)
st.button("🔄 Reset App", on_click=reset_app)

# 0) Athlete name
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
    ok, msg = verify_key(MODEL_ID, GENAI_API_KEY)
    if not ok:
        st.error(
            "Your Gemini API key didn’t validate.\n\n"
            f"**Details:** {msg}\n\n"
            "Tips: paste a fresh key (starts with AIza…), remove extra spaces, or rotate the key in Google AI Studio."
        )
        st.stop()

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

    selected_sections = [t for t in TASKS if t["key"] in selected_keys]
    full_prompt = make_single_call_prompt(ctx, selected_sections)
    combined_text = call_gemini_once(MODEL_ID, full_prompt, temperature=0.7, max_attempts=2)
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


# ====================== 3) CHAT — ASK ANYTHING ======================
st.markdown("---")
st.subheader("3) Chat — Ask Anything")

# Initialize chat state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []  # list of {"role": "user"/"assistant", "content": str}

col_left, col_right = st.columns([3, 1])
with col_right:
    include_context = st.checkbox(
        "Use current athlete context",
        value=True,
        help="When ON, your chat prompt includes the profile & nutrition details above."
    )
    if st.button("🧹 Clear Chat"):
        st.session_state.chat_history = []
        st.experimental_rerun()

with col_left:
    # Display history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    user_msg = st.chat_input("Type your prompt…")
    if user_msg:
        # Push user message
        st.session_state.chat_history.append({"role": "user", "content": user_msg})

        # Build a single prompt string for Gemini (stateless API)
        context_text = ""
        if include_context:
            ctx_for_chat = {
                "sport": sport, "position": position, "age": age,
                "fitness_level": fitness_level, "training_days": training_days,
                "session_time": session_time, "goals": ", ".join(goals) if goals else "general development",
                "injuries": ", ".join(injuries) if injuries else "none",
                "constraints": constraints, "diet": diet, "allergies": allergies,
                "calorie_goal": calorie_goal or "not specified", "athlete_name": athlete_name.strip(),
            }
            context_text = (
                "You are a friendly, safety-first youth sports coach.\n"
                + build_context_block(ctx_for_chat)
                + "Rules: Use simple language; avoid risky advice; do not include placeholders.\n\n"
            )

        # Include brief conversation transcript (last few turns) to keep continuity
        transcript_lines = []
        recent = st.session_state.chat_history[-6:]  # last 6 messages max
        for m in recent:
            who = "User" if m["role"] == "user" else "CoachBot"
            transcript_lines.append(f"{who}: {m['content']}")
        transcript = "\n".join(transcript_lines)

        chat_prompt = f"{context_text}Conversation (most recent messages first):\n{transcript}\n\nCoachBot:"

        # Validate key quickly (first time)
        ok, msg = verify_key(MODEL_ID, GENAI_API_KEY)
        if not ok:
            err = (
                "Your Gemini API key didn’t validate in Chat.\n\n"
                f"**Details:** {msg}\n\n"
                "Paste a fresh key (starts with AIza…) and try again."
            )
            st.session_state.chat_history.append({"role": "assistant", "content": err})
            st.experimental_rerun()

        # Call Gemini once for this chat turn (with brief retry)
        reply = call_gemini_once(MODEL_ID, chat_prompt, temperature=0.7, max_attempts=2)
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        st.experimental_rerun()
# ===================================================================

st.markdown("---")
st.caption("Disclaimer: CoachBot AI is for educational purposes only and does not replace qualified medical or coaching advice.")
