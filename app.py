from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd

app = Flask(__name__)
app.secret_key = 'Lets_predict'  # Set a secret key for session management

# Configure SQLAlchemy with SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'  # Use SQLite for simplicity
db = SQLAlchemy(app)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)


@app.route('/reviews')
def show_reviews():
    # Fetch all feedback from the database
    reviews = Feedback.query.all()
    return render_template('reviews.html', reviews=reviews)


# Feedback model
class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    feedback_text = db.Column(db.Text, nullable=False)
# Initialize the database (Run this once manually, not on every request)
with app.app_context():
    db.create_all()

def delete_feedback(feedback_id):
    feedback = Feedback.query.get(feedback_id)
    if feedback:
        db.session.delete(feedback)
        db.session.commit()
        print(f"Feedback with ID {feedback_id} deleted successfully.")
    else:
        print("Feedback not found.")

if __name__ == "__main__":
    with app.app_context():
        delete_feedback(4)  # Replace '1' with the ID of the feedback you want to delete


# Load the datasets
data = pd.read_csv('Project Dataset .csv')
college_data = pd.read_csv('college dataset.csv')  # College code to college name mapping
department_data = pd.read_csv('department.csv')  # Department code to department name mapping

# Ensure correct data types and normalize
data['cutoff_score'] = pd.to_numeric(data['cutoff_score'], errors='coerce')
data['community'] = data['community'].astype(str).str.lower().str.strip()
data['college'] = data['college'].astype(str).str.strip().str.lower()
data['department'] = data['department'].astype(str).str.strip().str.lower()
college_data['college'] = college_data['college'].astype(str).str.strip().str.lower()
department_data['department'] = department_data['department'].astype(str).str.strip().str.lower()
college_data['college_name'] = college_data['college_name'].str.strip().astype(str).str.lower()
department_data['department_name'] = department_data['department_name'].str.strip().astype(str).str.lower()

# Merge both department and college data into the main dataset
data = data.merge(department_data, on='department', how='left')
data = data.merge(college_data, on='college', how='left')

# Filter dataset by community, college, department, and cut-off
def predict_allocation(community, cutoff_score, college, department):
    # Normalize the input values
    community = str(community).strip().lower()
    college = str(college).strip().lower()
    department = str(department).strip().lower()
    cutoff_score = float(cutoff_score)
    
    filtered_data = data[(data['community'] == community) &
                         (data['college'] == college) &
                         (data['department'] == department)]

    if filtered_data.empty:
        return 0  # No matching records
    
    min_cutoff = filtered_data['cutoff_score'].min()
    max_cutoff = filtered_data['cutoff_score'].max()

    if pd.isna(min_cutoff) or pd.isna(max_cutoff):
        return 0  # No valid data

    if cutoff_score < min_cutoff:
        return 0  # No chance of seat allotment
    elif cutoff_score >= max_cutoff:
        return 100  # Guaranteed seat allotment

    probability = (cutoff_score - min_cutoff) / (max_cutoff - min_cutoff)
    return round(probability * 100, 2)

# Recommend colleges based on cut-off and department
def recommend_colleges(community, cutoff_score, department):
    community = str(community).strip().lower()
    department = str(department).strip().lower()
    cutoff_score = float(cutoff_score)

    filtered_data = data[(data['community'] == community) &
                         (data['department'] == department) &
                         (data['cutoff_score'] <= cutoff_score)]

    if filtered_data.empty:
        return pd.DataFrame()

    recommended_colleges = filtered_data[['college', 'college_name']].drop_duplicates().sort_values(by='college')

    return recommended_colleges

# Recommend other departments in the same college based on community and cutoff score
def recommend_departments(community, cutoff_score, college):
    community = str(community).strip().lower()
    college = str(college).strip().lower()
    cutoff_score = float(cutoff_score)

    filtered_data = data[(data['community'] == community) &
                         (data['college'] == college) &
                         (data['cutoff_score'] <= cutoff_score)]

    if filtered_data.empty:
        return pd.DataFrame()

    recommended_departments = filtered_data[['department', 'department_name']].drop_duplicates().sort_values(by='department')

    return recommended_departments

# Route for the welcome page
@app.route('/welcome')
def welcome():
    return render_template('welcome.html')  # No need to pass feedback data here


@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('welcome'))  # Redirect to the welcome page if not logged in
    colleges = data[['college', 'college_name']].drop_duplicates().to_dict(orient='records')
    departments = data[['department', 'department_name']].drop_duplicates().to_dict(orient='records')
    return render_template('index.html', colleges=colleges, departments=departments)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return render_template('signup.html', error='Username already exists. Please choose another.')

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))  # Redirect to login after successful signup
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['username'] = username
            return redirect(url_for('dashboard'))  # Redirect to the index page
        else:
            return render_template('login.html', error='Invalid credentials. Please try again.')

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')  # Create a dashboard page


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('welcome'))  # Redirect to the welcome page

@app.route('/feedback', methods=['GET'])
def feedback():
    feedback_data = Feedback.query.order_by(Feedback.id.desc()).limit(5).all()
    feedback_data = [{'username': feedback.username, 'feedback_text': feedback.feedback_text} for feedback in feedback_data]
    return render_template('feedback.html', feedback_data=feedback_data)

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    if 'username' not in session:
        return redirect(url_for('login'))

    feedback_text = request.form['feedback_text']
    username = session['username']

    new_feedback = Feedback(username=username, feedback_text=feedback_text)
    db.session.add(new_feedback)
    db.session.commit()
    flash('Feedback submitted successfully!', 'success')

    return redirect(url_for('feedback'))

@app.route('/college_list')
def college_list():
    # Create a dictionary to group departments by college
    college_departments = {}
    
    # Iterate over the data and populate the dictionary
    for _, row in data.iterrows():
        college_code = row['college']
        college_name = row['college_name']
        department_code = row['department']
        department_name = row['department_name']

        # If the college isn't already in the dictionary, add it
        if college_code not in college_departments:
            college_departments[college_code] = {
                'college_name': college_name,
                'departments': []
            }
        
        # Append the department to the college's department list
        college_departments[college_code]['departments'].append({
            'department_code': department_code,
            'department_name': department_name
        })
    
    return render_template('college_list.html', college_departments=college_departments)



@app.route('/predict', methods=['POST'])
def predict():
    if 'username' not in session:
        return redirect(url_for('login'))
    community = str.lower(request.form['community']).strip()
    cutoff_score = float(request.form['cutoff_score'])
    college_input = request.form['college']
    college = college_input.split(' - ')[0].strip().lower()
    department_input = request.form['department']
    department = department_input.split(' - ')[0].strip().lower()

    probability = predict_allocation(community, cutoff_score, college, department)
    recommended_colleges = recommend_colleges(community, cutoff_score, department)
    recommended_departments = recommend_departments(community, cutoff_score, college)

    return render_template('result.html', probability=probability,
                           recommended_colleges=recommended_colleges.to_dict(orient='records'),
                           recommended_departments=recommended_departments.to_dict(orient='records'))

if __name__ == '__main__':
    app.run(debug=True)
