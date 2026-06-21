import os
import psycopg2
from flask import Flask, render_template, request, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash

# Get the absolute, exact path of the current folder on the server
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Force Flask to look in this exact folder for your HTML files
app = Flask(__name__, template_folder=BASE_DIR)
app.secret_key = os.environ.get('SECRET_KEY', 'super_secret_dev_key')

def get_db_conn():
    db_url = os.environ.get('DATABASE_URL')
    return psycopg2.connect(db_url)

@app.route('/')
def index():
    search_query = request.args.get('search', '')
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        
        if search_query:
            cursor.execute("""
                SELECT c.course_id, c.course_name, c.description, l.town, l.county 
                FROM courses c
                JOIN course_locations l ON c.location_id = l.location_id
                WHERE c.course_name ILIKE %s OR l.town ILIKE %s OR l.county ILIKE %s
            """, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
        else:
            cursor.execute("""
                SELECT c.course_id, c.course_name, c.description, l.town, l.county 
                FROM courses c
                JOIN course_locations l ON c.location_id = l.location_id
            """)
        
        courses = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('index.html', courses=courses, search_query=search_query)
    except Exception as e:
        return f"Database Error: {str(e)}"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        auth_method = request.form.get('auth_method')
        conn = get_db_conn()
        cursor = conn.cursor()
        
        if auth_method == 'govid':
            govid = request.form.get('govid')
            cursor.execute("SELECT pps_number FROM users WHERE govid = %s", (govid,))
            user = cursor.fetchone()
            if user:
                session['user_pps'] = user[0]
                return redirect(url_for('index'))
        else:
            pps = request.form.get('pps')
            dob = request.form.get('dob')
            password = request.form.get('password')
            
            cursor.execute("SELECT pps_number, date_of_birth, password_hash FROM users WHERE pps_number = %s", (pps,))
            user = cursor.fetchone()
            
            if user and str(user[1]) == dob and check_password_hash(user[2], password):
                session['user_pps'] = user[0]
                return redirect(url_for('index'))
                
        return "Authentication Failed. <a href='/login'>Try again</a>", 401
        
    return render_template('login.html')

@app.route('/register_account', methods=['GET', 'POST'])
def register_account():
    if request.method == 'POST':
        pps = request.form.get('pps')
        dob = request.form.get('dob')
        password = generate_password_hash(request.form.get('password'))
        govid = request.form.get('govid') or None
        
        line1 = request.form.get('line1')
        line2 = request.form.get('line2')
        town = request.form.get('town')      
        county = request.form.get('county')  
        eircode = request.form.get('eircode')
        
        conn = get_db_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (pps_number, date_of_birth, password_hash, govid, line1, line2, town, county, eircode)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (pps, dob, password, govid, line1, line2, town, county, eircode))
            conn.commit()
            session['user_pps'] = pps
            return redirect(url_for('index'))
        except Exception as e:
            return f"Registration Error: {str(e)}", 400
        finally:
            cursor.close()
            conn.close()
            
    return render_template('register_account.html')

@app.route('/enroll/<int:course_id>', methods=['POST'])
def enroll(course_id):
    if 'user_pps' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO registrations (pps_number, course_id) 
            VALUES (%s, %s)
        """, (session['user_pps'], course_id))
        conn.commit()
        return "Successfully Registered! <a href='/'>Go Home</a>"
    except:
        return "Already registered for this course. <a href='/'>Go Home</a>"
    finally:
        cursor.close()
        conn.close()

@app.route('/logout')
def logout():
    session.pop('user_pps', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
