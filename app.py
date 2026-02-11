import re
from typing import List, Dict

import streamlit as st
import pandas as pd
import google.generativeai as genai

# ─────────────────────────────────────────────────────
#  HARDCODE YOUR GEMINI API KEY HERE (as you requested)
# ─────────────────────────────────────────────────────
GENAI_API_KEY = "AIzaSyA9OQMnlQm92Dp63QGDjXHv7I6WG3a5Aq0"   # ← Replace with your real Gemini API key
genai.configure(api_key=GENAI_API_KEY)
# ─────────────────────────────────────────────────────

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
        description="7-day progressive full-body plan with sets×reps, rest, RPE, warm-up & cooldown.",
        prompt_template=(
            "Act as an elite youth {sport} coach. Create a 7-day progressive full-body training plan for a "
            "{age}-year-old {position}. Consider fitness level: {fitness_level}. Goals: {goals}. "
            "Account for injuries: {injuries}. Training constraints: {constraints}. Provide sets x reps, rest, "
            "RPE (1-10), and coaching cues. Include warm-up and cooldown for each day."
        ),
    ),
    Task(
        key="recovery_schedule",
        title="Safe Recovery Training",
        description="5-day low-impact recovery microcycle with regressions and pain-free ranges.",
        prompt_template=(
            "Design a 5-day low-impact recovery plan for a youth {sport} {position} with injury history: {injuries}. "
            "Emphasize mobility, tissue tolerance, flexibility, and pain-free ranges. Avoid contraindicated moves."
        ),
    ),
    Task(
        key="tactical_coaching",
        title="Tactical Coaching",
        description="6 evidence-informed drills with tactical cues and constraints-led variations.",
        prompt_template=(
            "Provide tactical coaching for {sport}. Role: {position}. Skill priority: {goals}. "
            "Include 6 evidence-informed drills with tactical cues, constraints-led variations, and session objectives."
        ),
    ),
    Task(
        key="nutrition_week",
        title="Week-long Nutrition Guide",
        description="7-day nutrition plan with hydration; macros/day if possible.",
        prompt_template=(
            "Create a 7-day nutrition plan for a {age}-year-old youth {sport} athlete. Diet preference: {diet}. "
            "Allergies: {allergies}. Calorie target: {calorie_goal} kcal/day if provided. Provide macros per day and hydration tips."
        ),
    ),
    Task(
        key="warmup_cooldown",
        title="Personalized Warm-up & Cooldown",
        description="Position-specific warm-up (10–15 min) and cooldown (10 min), injury-aware.",
        prompt_template=(
            "Generate a position-specific dynamic warm-up (10-15 min) and cooldown (10 min) for {sport} {position}. "
            "Avoid or regress movements contraindicated for {injuries}."
        ),
    ),
    Task(
        key="hydration_strategy",
        title="Hydration & Electrolytes",
        description="Daily hydration strategy and match-day plan.",
        prompt_template=(
            "Outline a hydration and electrolyte strategy for a {sport} athlete training {training_days} days/week in a warm climate. "
            "Include pre/during/post guidelines, and practical measures for school tournaments."
        ),
    ),
    Task(
        key="mental_routine",
        title="Mental Focus Routine",
        description="Mindset routine with breath work, focus cues, and pre-match routine.",
        prompt_template=(
            "Provide a mental skills routine for a youth {sport} player (role: {position}) including breath work, focus cues, imagery, and pre-match routines. Keep language coach-like."
        ),
    ),
    Task(
        key="visualization_drills",
        title="Pre-match Visualization Drills",
