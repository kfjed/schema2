import streamlit as st
import json
import os
from collections import defaultdict
from itertools import combinations
from datetime import datetime, timedelta

# -----------------------------------
# CONFIGURATION
# -----------------------------------

HISTORY_FILE = "history.json"

employee_skills = {
    "ALX": {"101", "205", "131"},
    "JSM": {"101", "205", "131"},
    "TRN": {"205", "131"},
    "KIM": {"101", "131"},
    "ROB": {"205", "131"},
    "LIA": {"101", "131"},
    "ELI": {"001", "131"},
    "MFN": {"001", "205", "131"},
}

ALL_TASKS = ["001", "101", "205"]

OVERFLOW_TASK = "131"


# -----------------------------------
# LOAD / SAVE HISTORY
# -----------------------------------

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r") as f:
        return json.load(f)


def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)


# -----------------------------------
# HISTORY HELPERS
# -----------------------------------

def get_recent_history(history, days=30):
    cutoff = datetime.today() - timedelta(days=days)
    recent = []
    for entry in history:
        date = datetime.strptime(entry["date"], "%Y-%m-%d")
        if date >= cutoff:
            recent.append(entry)
    return recent


def build_statistics(history):
    task_count = defaultdict(lambda: defaultdict(int))
    cowork_count = defaultdict(lambda: defaultdict(int))

    daily = defaultdict(list)
    for entry in history:
        daily[entry["date"]].append((entry["employee"], entry["task"]))

    for entries in daily.values():
        employees_today = [emp for emp, _ in entries]

        for emp, task in entries:
            task_count[emp][task] += 1

        for e1, e2 in combinations(employees_today, 2):
            cowork_count[e1][e2] += 1
            cowork_count[e2][e1] += 1

    return task_count, cowork_count


def assignment_score(employee, task, current_group, task_count, cowork_count):
    task_score = task_count[employee][task] * 3
    cowork_score = sum(cowork_count[employee][e] for e in current_group)
    return task_score + cowork_score


# -----------------------------------
# SCHEDULER
# -----------------------------------

def generate_schedule(task_counts, present_employees, history):

    recent_history = get_recent_history(history)
    task_count, cowork_count = build_statistics(recent_history)

    schedule = {}
    available = set(present_employees)

    for task, required in task_counts.items():

        schedule[task] = []

        qualified = {
            emp for emp in available
            if task in employee_skills.get(emp, set())
        }

        if len(qualified) < required:
            raise ValueError(f"Not enough trained employees for task {task}")

        for _ in range(required):

            best_employee = min(
                qualified,
                key=lambda emp: assignment_score(
                    emp, task, schedule[task], task_count, cowork_count
                ),
            )

            schedule[task].append(best_employee)
            available.remove(best_employee)
            qualified.remove(best_employee)

    # Overflow
    overflow = []
    for emp in available:
        if OVERFLOW_TASK in employee_skills.get(emp, set()):
            overflow.append(emp)
        else:
            raise ValueError(f"{emp} cannot be assigned to overflow task {OVERFLOW_TASK}")

    schedule[OVERFLOW_TASK] = overflow

    return schedule


# -----------------------------------
# UI
# -----------------------------------

st.title("Work Scheduler")

history = load_history()

st.subheader("Select Tasks")
selected_tasks = st.multiselect("Tasks for today", ALL_TASKS)

task_counts = {}
for task in selected_tasks:
    task_counts[task] = st.number_input(
        f"Number of workers for {task}",
        min_value=1,
        step=1,
        key=task
    )

st.subheader("Select Available Employees")
present_employees = st.multiselect(
    "Employees present",
    list(employee_skills.keys())
)

if "generated_schedule" not in st.session_state:
    st.session_state.generated_schedule = None


if st.button("Generate Schedule"):

    try:
        schedule = generate_schedule(task_counts, present_employees, history)
        st.session_state.generated_schedule = schedule
    except Exception as e:
        st.error(str(e))


if st.session_state.generated_schedule:

    st.subheader("Generated Schedule")

    for task, emps in st.session_state.generated_schedule.items():
        st.text(f"{task} → {', '.join(emps) if emps else 'None'}")

    col1, col2 = st.columns(2)

    if col1.button("Accept Schedule"):

        today = datetime.today().strftime("%Y-%m-%d")

        for task, emps in st.session_state.generated_schedule.items():
            for emp in emps:
                history.append({
                    "date": today,
                    "employee": emp,
                    "task": task
                })

        save_history(history)
        st.success("Schedule added to history.")
        st.session_state.generated_schedule = None

    if col2.button("Delete Schedule"):
        st.session_state.generated_schedule = None
        st.warning("Schedule discarded.")