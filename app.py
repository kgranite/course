import streamlit as st
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash

st.set_page_config(page_title="EireCourse Hub")

def get_db_conn():
    return psycopg2.connect(st.secrets["DATABASE_URL"])

if 'user_pps' not in st.session_state:
    st.session_state.user_pps = None

st.title("EireCourse Hub")

# Connect to database
conn = get_db_conn()
cursor = conn.cursor()

# --- MAIN PAGE: SEARCH & REGISTER ---
search_query = st.text_input("Search courses by name, town, or county:")

query = """
    SELECT c.course_id, c.course_name, c.description, l.town, l.county 
    FROM courses c
    JOIN course_locations l ON c.location_id = l.location_id
"""
if search_query:
    query += f" WHERE c.course_name ILIKE '%{search_query}%' OR l.town ILIKE '%{search_query}%' OR l.county ILIKE '%{search_query}%'"

cursor.execute(query)
courses = cursor.fetchall()

st.subheader("Available Courses")
for row in courses:
    st.write(f"**{row[1]}** — {row[3]}, Co. {row[4]}")
    st.write(row[2])
    
    if st.session_state.user_pps:
        if st.button(f"Register for {row[1]}", key=row[0]):
            try:
                cursor.execute("INSERT INTO registrations (pps_number, course_id) VALUES (%s, %s)", (st.session_state.user_pps, row[0]))
                conn.commit()
                st.success("Successfully registered!")
            except psycopg2.IntegrityError:
                conn.rollback()
                st.warning("You are already registered.")
    else:
        st.write("*Log in via the sidebar to register.*")
    st.divider()

# --- SIDEBAR: ROS-STYLE LOGIN / REGISTRATION ---
st.sidebar.title("Account Dashboard")

if st.session_state.user_pps:
    st.sidebar.write(f"Logged in as: **{st.session_state.user_pps}**")
    if st.sidebar.button("Log Out"):
        st.session_state.user_pps = None
        cursor.close()
        conn.close()
        st.rerun()
else:
    login_tab, register_tab = st.sidebar.tabs(["Sign In", "Create Account"])
    
    # 1. ROS-Style Dual Gateway
    with login_tab:
        st.write("Sign In Gateway")
        auth_method = st.radio("Method:", ["PPSN & DOB", "GovID"])
        
        if auth_method == "PPSN & DOB":
            pps_input = st.text_input("PPS Number")
            dob_input = st.date_input("Date of Birth")
            pass_input = st.text_input("Password", type="password")
            
            if st.button("Sign In"):
                cursor.execute("SELECT pps_number, date_of_birth, password_hash FROM users WHERE pps_number = %s", (pps_input,))
                user = cursor.fetchone()
                
                if user and str(user[1]) == str(dob_input) and check_password_hash(user[2], pass_input):
                    st.session_state.user_pps = user[0]
                    cursor.close()
                    conn.close()
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
                
        else:
            govid_input = st.text_input("GovID")
            if st.button("Sign In via GovID"):
                cursor.execute("SELECT pps_number FROM users WHERE govid = %s", (govid_input,))
                user = cursor.fetchone()
                if user:
                    st.session_state.user_pps = user[0]
                    cursor.close()
                    conn.close()
                    st.rerun()
                else:
                    st.error("GovID not found.")

    # 2. 5-Column Address Registration
    with register_tab:
        st.write("New Account")
        with st.form("register_form"):
            new_pps = st.text_input("PPS Number (Required)")
            new_dob = st.date_input("Date of Birth")
            new_pass = st.text_input("Password (Required)", type="password")
            new_govid = st.text_input("GovID (Optional)")
            
            st.write("Address (5 Columns)")
            line1 = st.text_input("Line 1")
            line2 = st.text_input("Line 2")
            town = st.text_input("Town (3rd Column)")
            county = st.text_input("County (4th Column)")
            eircode = st.text_input("Eircode (5th Column)")
            
            submit = st.form_submit_button("Register")
            
            if submit:
                hashed_pw = generate_password_hash(new_pass)
                try:
                    cursor.execute("""
                        INSERT INTO users (pps_number, date_of_birth, password_hash, govid, line1, line2, town, county, eircode)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (new_pps, new_dob, hashed_pw, new_govid or None, line1, line2, town, county, eircode))
                    conn.commit()
                    st.success("Registered! You can now sign in.")
                except psycopg2.Error:
                    conn.rollback()
                    st.error("Registration failed. PPS may already exist.")

# Clean up connection
try:
    cursor.close()
    conn.close()
except:
    pass