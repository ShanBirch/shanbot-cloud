from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class ExerciseDefinition(BaseModel):
    name: str
    sets: str
    reps: str


class WorkoutDefinition(BaseModel):
    day_type: str = Field(..., description="Type of workout day. Supported values: 'back', 'chest_tris', 'shoulders_core', 'legs', 'arms_core'.")
    exercises_list: List[ExerciseDefinition]


class BuildProgramRequest(BaseModel):
    client_name: str
    program_name: str
    workout_definitions: List[WorkoutDefinition]

# Analytics Models


class MacroTracking(BaseModel):
    daily_target: int
    consumed: int
    remaining: int


class MacrosData(BaseModel):
    protein: MacroTracking
    carbs: MacroTracking
    fats: MacroTracking


class MealEntry(BaseModel):
    time: str
    calories: int
    protein: int
    carbs: int
    fats: int


class CalorieTracking(BaseModel):
    daily_target: int = 2000
    current_date: str
    calories_consumed: int = 0
    remaining_calories: int = 2000
    macros: MacrosData
    meals_today: List[MealEntry] = []
