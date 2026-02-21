import streamlit as st

# Set your password
PASSWORD = "plattfisk"

# Session state to track login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# Show password input if not logged in
if not st.session_state.logged_in:
    password_input = st.text_input("Enter password to access the scheduler:", type="password")
    if st.button("Login"):
        if password_input == PASSWORD:
            st.session_state.logged_in = True
            st.success("Logged in!")
        else:
            st.error("Incorrect password")
    st.stop()  # Stop execution until logged in


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
    "KDN": {"131", "132", "134", "130", "064"},
    "MFN": {"001", "131", "132", "134", "130", "064", "100"},
    "ALM": {"131", "132", "134", "130", "064", "100"},
    "GSS": {"131", "132", "134", "130", "064", "100"},
    "LHK": {"131", "132", "134", "130", "064", "100"},
    "DBU": {"131", "132", "134", "130", "064", "100"},
    "ELI": {"001", "131", "132", "134", "130", "064"},
    "AGZ": {"131", "132", "134", "130", "064"},
    "SUL": {"131", "134"},
}

import streamlit as st

# Initialize session state for employee checkboxes
for emp in employee_skills.keys():
    if f"emp_{emp}" not in st.session_state:
        st.session_state[f"emp_{emp}"] = False
        
ALL_TASKS = ["001", #granskning
             "131", #montering
             "132", #kapning
             "134", #extrudering
             "130", #packning
             "064", #formspuruta
             "100", #alupåsar
            ]

OVERFLOW_TASK = "131"

task_descriptions = {
    "001": "Granskning",
    "130": "Syning/Packning",
    "131": "Montering",
    "132": "Kapning/Vägning",
    "134": "Extrudering",
    "064": "Formspruta",
    "100": "Alupåsar",
}

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

st.title("Schema")

history = load_history()

st.subheader("Select Tasks")
selected_tasks = []

cols = st.columns(2)  # Change the number for more/fewer columns
for i, task in enumerate(ALL_TASKS):
    desc = task_descriptions.get(task, "")
    label = f"{task} — {desc}"
    if cols[i % 2].checkbox(label, key=f"task_{task}"):
        selected_tasks.append(task)

task_counts = {}
for task in selected_tasks:
    task_counts[task] = st.number_input(
        f"Number of workers for {task}",
        min_value=1,
        step=1,
        key=task
    )

st.subheader("Select Available Employees")

# "Select All" checkbox
select_all = st.checkbox("Select All")
# If select_all changed, update all individual employee checkboxes
if select_all:
    for emp in employee_skills.keys():
        st.session_state[f"emp_{emp}"] = True

present_employees = []

cols = st.columns(2)
for i, emp in enumerate(employee_skills.keys()):
    # Display checkbox with current value from session_state
    checked = st.session_state[f"emp_{emp}"]
    if cols[i % 2].checkbox(emp, key=f"emp_{emp}", value=checked):
        st.session_state[f"emp_{emp}"] = True
    else:
        st.session_state[f"emp_{emp}"] = False

    # Add to present_employees if checked
    if st.session_state[f"emp_{emp}"]:
        present_employees.append(emp)

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
