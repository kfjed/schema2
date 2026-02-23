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
    "KDN": {"171", "172", "132", "134", "108", "068"},
    "MFN": {"171", "172", "132", "134", "108", "068", "101", "001"},
    "ALM": {"171", "172", "132", "134", "108", "068", "101"},
    "LHK": {"171", "172", "132", "134", "108", "068", "101"},
    "DBU": {"171", "172", "132", "134", "108", "068", "101"},
    "GSS": {"171", "172", "132", "134", "108", "068", "101"},
    "AGZ": {"171", "172", "132", "134", "108", "068"},
    "ELI": {"171", "172", "132", "134", "108", "068", "101", "001"},
    "RPN": {"171", "172", "132", "134", "068"},
    "SEN": {"171", "132", "068"},
    "KLR": {"068"},
}

import streamlit as st

# Initialize session state for employee checkboxes
for emp in employee_skills.keys():
    if f"emp_{emp}" not in st.session_state:
        st.session_state[f"emp_{emp}"] = False
        
ALL_TASKS = ["001", #granskning
             "172", #montering
             "171", #packning
             "134", #kapning
             "132", #extrudering
             "108", #formspuruta
             "101", #alupåsar
             "068", #testmontering
            ]

OVERFLOW_TASK = "172"

task_descriptions = {
    "001": "Granskning",
    "171": "Syning/Packning",
    "172": "Montering",
    "134": "Kapning/Vägning",
    "132": "Extrudering",
    "108": "Formspruta",
    "101": "Alupåsar",
    "068": "Testmontering",
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
    """
    Generate a schedule for selected tasks and employees.
    Guarantees all present employees are assigned somewhere if qualified.
    """
    # Track assignments and available employees
    schedule = {task: [] for task in task_counts.keys()}
    available = list(present_employees)  # Use list for predictable order

    # Optional: you can include task_count / cowork_count stats for scoring
    recent_history = get_recent_history(history)
    task_count, cowork_count = build_statistics(recent_history)

    # Assign employees to each task
    for task, required in task_counts.items():
        # Employees trained for this task and still available
        qualified = [emp for emp in available if task in employee_skills.get(emp, set())]

        if not qualified:
            # No qualified employees left for this task
            continue

        # Assign employees up to the required number
        for _ in range(required):
            if not qualified:
                break  # no more qualified employees

            # Pick best employee (lowest assignment_score)
            best_employee = min(
                qualified,
                key=lambda emp: assignment_score(emp, task, schedule[task], task_count, cowork_count)
            )

            schedule[task].append(best_employee)
            available.remove(best_employee)
            qualified.remove(best_employee)

    # Overflow task: assign any remaining available employees who are trained for 172
    overflow_task = "172"
    if overflow_task not in schedule:
        schedule[overflow_task] = []

    for emp in available[:]:  # copy to avoid modifying list while iterating
        if overflow_task in employee_skills.get(emp, set()):
            schedule[overflow_task].append(emp)
            available.remove(emp)

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

# "Select All" button
if st.button("Select All Employees"):
    for emp in employee_skills.keys():
        st.session_state[f"emp_{emp}"] = True

# Display checkboxes in 2 columns
present_employees = []
cols = st.columns(2)
for i, emp in enumerate(employee_skills.keys()):
    if cols[i % 2].checkbox(emp, key=f"emp_{emp}", value=st.session_state[f"emp_{emp}"]):
        present_employees.append(emp)

if "generated_schedule" not in st.session_state:
    st.session_state.generated_schedule = None


if st.button("Generate Schedule"):
    # Generate the schedule
    schedule = generate_schedule(task_counts, present_employees, history)

    # Display schedule
    for task, emps in schedule.items():
        st.text(f"{task} → {', '.join(emps) if emps else 'None'}")

    # Show unassigned employees
    assigned_employees = [emp for emps in schedule.values() for emp in emps]
    unassigned = set(present_employees) - set(assigned_employees)
    if unassigned:
        st.warning(f"The following employees could not be assigned to any task: {', '.join(unassigned)}")

    # ✅ Place Accept / Discard buttons HERE
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Accept Schedule"):
            # Save schedule to history
            save_schedule_to_history(schedule)
            st.success("Schedule saved to history!")

    with col2:
        if st.button("Discard Schedule"):
            st.info("Schedule discarded")
        

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
