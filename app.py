import re
from typing import List, Dict
import streamlit as st
import pandas as pd
import google.generativeai as genai

# ===================== API KEY (HARDCODED) =====================
GENAI_API_KEY = "AIzaSyA9OQMnlQm92Dp63QGDjXHv7I6WG3a5Aq0"  # <-- Replace with your real Gemini key
genai.configure(api_key=GENAI_API_KEY)
MODEL_ID = "gemini-1.5-flash"  # Use a widely available model
# ==============================================================


# ---------------------- TASK DEFINITIONS -----------------------
TASKS: List[Dict[str, str]] = [
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
            "Emphasize mobility, flexibility, and pain-free progressions. Avoid unsafe exercises."
        ),
    },
    {
        "key": "tactical_coaching",
        "title": "Tactical Coaching",
        "tpl": (
            "Provide tactical coaching for {sport}. Role: {position}. Priority skills: {goals}. "
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
            "Create a dynamic warm-up and cooldown for {sport} {position}. Avoid movements unsafe for: {injuries}."
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
        "tpl": }
