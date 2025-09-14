import streamlit as st
import json
import os
import random
import time
import pandas as pd
from datetime import timedelta

# --- CONSTANTS ---
USERS_FILE = 'users.json'
JUNIORS_QUESTIONS_FILE = 'juniors.json'
SENIORS_QUESTIONS_FILE = 'seniors.json'
LEADERBOARD_FILE = 'leaderboard.json'
QUIZ_DURATION_SECONDS = 15 * 60  # 15 minutes
NUM_QUESTIONS_TO_SELECT = 5
STAFF_PASSWORD = "admin"  # Hardcoded staff password

# --- DATA MANAGEMENT FUNCTIONS ---


def initialize_file(filepath, default_content):
    """Creates a file with default content if it doesn't exist."""
    if not os.path.exists(filepath):
        with open(filepath, 'w') as f:
            json.dump(default_content, f, indent=4)


def load_data(filepath):
    """Loads data from a JSON file."""
    initialize_file(filepath, [])  # Ensure file exists
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        st.error(f"Error reading {
                 filepath}. Please ensure it's a valid JSON file.")
        return {} if 'users' in filepath else []


def save_data(filepath, data):
    """Saves data to a JSON file."""
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
    except IOError as e:
        st.error(f"Could not save data to {filepath}: {e}")

# --- HELPER FUNCTIONS ---


def get_participant_category(participant_id, users_data):
    """Determines if a participant is 'junior' or 'senior'."""
    year = users_data.get(participant_id, {}).get('year')
    if year in [1, 2]:
        return 'junior'
    elif year in [3, 4]:
        return 'senior'
    return None


def calculate_score(correct_answers, time_taken):
    """Calculates the final score based on accuracy and speed."""
    score = (correct_answers * 100) - (time_taken / 2)
    return round(score, 2)

# --- PAGE RENDERING FUNCTIONS ---


def render_login_page():
    """Renders the participant login UI and handles authentication."""
    st.header("Participant Login")

    with st.form("login_form"):
        participant_id = st.text_input("Participant ID")
        otp = st.text_input("One-Time Password (OTP)", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            users_data = load_data(USERS_FILE)
            user_info = users_data.get(participant_id)

            if not user_info:
                st.error("Invalid Participant ID.")
            elif user_info['has_logged_in']:
                st.warning(
                    "This ID has already been used to complete the quiz.")
            elif str(user_info['otp']) != otp:
                st.error("Invalid OTP. Please check with the staff.")
            else:
                # Successful login
                user_info['has_logged_in'] = True
                save_data(USERS_FILE, users_data)

                st.session_state.logged_in = True
                st.session_state.participant_id = participant_id
                st.session_state.category = get_participant_category(
                    participant_id, users_data)
                st.session_state.quiz_started = False
                st.success("Login successful! The contest will begin now.")
                time.sleep(1)
                st.rerun()


def render_staff_page():
    """Renders the staff admin dashboard for participant registration and OTP generation."""
    st.header("Staff Administration")
    password = st.text_input("Enter Staff Password", type="password")

    if password == STAFF_PASSWORD:
        st.success("Access Granted")

        st.subheader("Register New Participant")

        with st.form("register_form"):
            new_participant_id = st.text_input("New Participant ID")
            register_button = st.form_submit_button(
                "Register Participant & Generate OTP")

            if register_button:
                users_data = load_data(USERS_FILE)
                leaderboard_data = load_data(LEADERBOARD_FILE)

                if not new_participant_id:
                    st.warning("Please enter a Participant ID.")
                elif not new_participant_id.isdigit() or len(new_participant_id) < 2:
                    st.error(
                        "Participant ID must be a number with at least 2 digits.")

                elif new_participant_id in users_data:
                    # Participant already exists, check if they are on the leaderboard
                    leaderboard_ids = [entry['id']
                                       for entry in leaderboard_data]
                    if new_participant_id in leaderboard_ids:
                        st.error(f"Participant '{
                                 new_participant_id}' has already completed the quiz and is on the leaderboard. Cannot generate a new OTP.")
                    else:
                        # Regenerate OTP for existing, non-competed user
                        new_otp = random.randint(100000, 999999)
                        users_data[new_participant_id]['otp'] = new_otp
                        # Reset login status
                        users_data[new_participant_id]['has_logged_in'] = False
                        save_data(USERS_FILE, users_data)
                        st.success(f"Successfully regenerated OTP for existing participant '{
                                   new_participant_id}'.")
                        st.info(f"New OTP: **{new_otp}**")

                else:
                    # New participant registration logic
                    try:
                        # Assumes the current year is 2025.
                        # The first two digits of the ID represent the admission year.
                        # e.g., '25xxx' -> year 1, '24xxx' -> year 2, etc.
                        current_year_prefix = 25
                        id_prefix = int(new_participant_id[:2])

                        participant_year = current_year_prefix - id_prefix + 1

                        if not 1 <= participant_year <= 4:
                            st.error(
                                f"Could not determine a valid year (1-4) from the ID prefix '{id_prefix}'.")
                        else:
                            new_otp = random.randint(100000, 999999)
                            users_data[new_participant_id] = {
                                "year": participant_year,
                                "has_logged_in": False,
                                "otp": new_otp
                            }
                            save_data(USERS_FILE, users_data)
                            st.success(f"Successfully registered participant '{
                                       new_participant_id}' as Year {participant_year}.")
                            st.info(f"Generated OTP: **{new_otp}**")
                    except (ValueError, IndexError):
                        st.error(
                            "Invalid Participant ID format. It must start with two digits representing the admission year.")

    elif password:
        st.error("Incorrect password.")


def render_leaderboard_page():
    """Renders the public leaderboard."""
    st.header("Leaderboard")
    leaderboard_data = load_data(LEADERBOARD_FILE)

    if not leaderboard_data:
        st.info("The leaderboard is currently empty. Results will appear here after participants complete the quiz.")
    else:
        df = pd.DataFrame(leaderboard_data)
        # Sort by score descending, then by time ascending
        df_sorted = df.sort_values(
            by=['score', 'time_taken'], ascending=[False, True])
        df_sorted.reset_index(drop=True, inplace=True)
        df_sorted.index += 1  # Start ranking from 1
        df_sorted.index.name = "Rank"

        st.dataframe(
            df_sorted[['id', 'score', 'time_taken']],
            use_container_width=True
        )


def render_contest_page():
    """Renders the quiz interface, timer, and handles submission."""
    st.header(f"Quiz Contest - {st.session_state.category.title()}")

    # Initialize quiz state once
    if not st.session_state.quiz_started:
        question_file = JUNIORS_QUESTIONS_FILE if st.session_state.category == 'junior' else SENIORS_QUESTIONS_FILE
        questions = load_data(question_file)
        st.session_state.quiz_questions = random.sample(
            questions, NUM_QUESTIONS_TO_SELECT)
        st.session_state.answers = {}
        st.session_state.start_time = time.time()
        st.session_state.quiz_started = True

    # Timer logic
    elapsed_time = time.time() - st.session_state.start_time
    time_left = QUIZ_DURATION_SECONDS - elapsed_time

    if time_left <= 0:
        st.warning("Time's up! Submitting your answers automatically.")
        # Trigger automatic submission
        submit_quiz()
        st.rerun()

    timer_placeholder = st.empty()
    timer_placeholder.metric("Time Remaining", str(
        timedelta(seconds=int(time_left))))

    # Display questions and collect answers
    with st.form("quiz_form"):
        for i, q in enumerate(st.session_state.quiz_questions):
            st.subheader(f"Question {i+1}: {q['question']}")
            # Use a unique key for each radio button based on question index
            st.session_state.answers[i] = st.radio(
                "Options:", q['options'], key=f"q_{i}", label_visibility="collapsed", index=None
            )
            st.markdown("---")

        submitted = st.form_submit_button("Submit Answers")
        if submitted:
            submit_quiz()
            st.rerun()

    # This is needed to update the timer continuously
    time.sleep(1)
    st.rerun()


def submit_quiz():
    """Grades the quiz, calculates score, and saves the result."""
    end_time = time.time()
    time_taken = round(end_time - st.session_state.start_time)

    correct_answers = 0
    for i, q in enumerate(st.session_state.quiz_questions):
        if st.session_state.answers.get(i) == q['answer']:
            correct_answers += 1

    final_score = calculate_score(correct_answers, time_taken)

    result = {
        "id": st.session_state.participant_id,
        "category": st.session_state.category,
        "score": final_score,
        "time_taken": time_taken,
        "correct_answers": correct_answers,
    }

    leaderboard_data = load_data(LEADERBOARD_FILE)
    leaderboard_data.append(result)
    save_data(LEADERBOARD_FILE, leaderboard_data)

    st.session_state.quiz_submitted = True
    st.session_state.final_score = final_score
    st.session_state.correct_answers = correct_answers
    st.session_state.time_taken = time_taken


def render_results_page():
    """Displays the participant's final score and quiz summary."""
    st.balloons()
    st.header("Quiz Completed!")
    st.success("Your results have been submitted successfully.")

    st.metric("Your Final Score", st.session_state.final_score)
    st.write(
        f"**Correct Answers:** {st.session_state.correct_answers} / {NUM_QUESTIONS_TO_SELECT}")
    st.write(
        f"**Time Taken:** {str(timedelta(seconds=int(st.session_state.time_taken)))}")

    st.info("You can now view the main Leaderboard from the navigation sidebar.")


# --- MAIN APPLICATION LOGIC ---

def main():
    """Main function to run the Streamlit app."""
    st.set_page_config(page_title="Online Quiz Platform", layout="wide")

    # Sidebar for navigation
    st.sidebar.title("Navigation")
    page_options = ["Home", "Leaderboard", "Staff Admin"]
    selection = st.sidebar.radio("Go to", page_options)

    # Initialize session state variables
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'quiz_submitted' not in st.session_state:
        st.session_state.quiz_submitted = False

    # Page routing logic
    if selection == "Home":
        if not st.session_state.logged_in:
            render_login_page()
        elif st.session_state.logged_in and not st.session_state.quiz_submitted:
            render_contest_page()
        else:  # Logged in and quiz submitted
            render_results_page()

    elif selection == "Leaderboard":
        render_leaderboard_page()

    elif selection == "Staff Admin":
        render_staff_page()


if __name__ == "__main__":
    # Create dummy data files if they don't exist on first run
    initialize_file(USERS_FILE, {
        "23001": {"year": 1, "has_logged_in": False, "otp": None},
        "23002": {"year": 2, "has_logged_in": False, "otp": None},
        "22001": {"year": 3, "has_logged_in": False, "otp": None},
        "21001": {"year": 4, "has_logged_in": False, "otp": None}
    })
    initialize_file(JUNIORS_QUESTIONS_FILE, [
        {"question": "What is the capital of France?", "options": [
            "Berlin", "Madrid", "Paris", "Rome"], "answer": "Paris"},
        {"question": "Which planet is known as the Red Planet?", "options": [
            "Earth", "Mars", "Jupiter", "Venus"], "answer": "Mars"},
        {"question": "What is 2 + 2 * 2?",
            "options": ["8", "6", "4", "2"], "answer": "6"},
        {"question": "Who wrote 'Hamlet'?", "options": [
            "Charles Dickens", "J.K. Rowling", "William Shakespeare", "Leo Tolstoy"], "answer": "William Shakespeare"},
        {"question": "What is the largest ocean on Earth?", "options": [
            "Atlantic", "Indian", "Arctic", "Pacific"], "answer": "Pacific"},
        {"question": "How many continents are there?",
            "options": ["5", "6", "7", "8"], "answer": "7"}
    ])
    initialize_file(SENIORS_QUESTIONS_FILE, [
        {"question": "What is the powerhouse of the cell?", "options": [
            "Nucleus", "Ribosome", "Mitochondrion", "Golgi apparatus"], "answer": "Mitochondrion"},
        {"question": "In Python, what does the 'yield' keyword do?", "options": [
            "Ends the function", "Returns a generator object", "Prints to console", "Raises an exception"], "answer": "Returns a generator object"},
        {"question": "What is the value of 'e' (Euler's number) approximately?", "options": [
            "3.141", "1.618", "2.718", "9.81"], "answer": "2.718"},
        {"question": "Who is credited with discovering penicillin?", "options": [
            "Marie Curie", "Albert Einstein", "Isaac Newton", "Alexander Fleming"], "answer": "Alexander Fleming"},
        {"question": "What is the time complexity of a binary search algorithm?",
            "options": ["O(n)", "O(log n)", "O(n^2)", "O(1)"], "answer": "O(log n)"},
        {"question": "What does SQL stand for?", "options": [
            "Strong Question Language", "Structured Query Language", "Simple Query Logic", "Standardized Question Lexicon"], "answer": "Structured Query Language"}
    ])
    initialize_file(LEADERBOARD_FILE, [])

    main()
