from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import csv
from flask.cli import with_appcontext
import click

# Initialize the Flask application
app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'  # Required for secure sessions and flashing messages

# Initialize database and migration
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Initialize login manager
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # Specify login route

# Define the User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    username = db.Column(db.String(50), unique=True)
    city = db.Column(db.String(50))
    state = db.Column(db.String(50))
    country = db.Column(db.String(50))
    zip = db.Column(db.String(10))
    password = db.Column(db.String(128))

    def __repr__(self):
        return f'<User {self.username}>'

# Medicine model
class Medicine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    is_discontinued = db.Column(db.Boolean, default=False)
    manufacturer_name = db.Column(db.String(100))
    type = db.Column(db.String(50))
    pack_size_label = db.Column(db.String(50))
    short_composition1 = db.Column(db.String(100))
    short_composition2 = db.Column(db.String(100))

    def __repr__(self):
        return f'<Medicine {self.name}>'

# MedicineOrder model
class MedicineOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicine.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='orders')
    medicine = db.relationship('Medicine', backref='orders')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/', methods=["GET", "POST"])
def home():
    return render_template('home.html')

@app.route('/find_doc', methods=["GET", "POST"])
def finddoc():
    return render_template('find_doc.html')

@app.route('/video_cons', methods=["GET", "POST"])
def video_cons():
    return render_template('video_cons.html')

from flask_sqlalchemy import pagination
from flask import request


@app.route('/meds', methods=['GET', 'POST'])
@login_required
def meds():
    # Handle search query
    search_query = request.args.get('search', '')
    
    # Determine the page number (default to 1 if not specified)
    page = request.args.get('page', 1, type=int)
    
    # Specify 12 entries per page
    per_page = 12
    
    if search_query:
        # Filter medicines based on the search query and paginate
        medicines = Medicine.query.filter(Medicine.name.contains(search_query)).paginate(page=page, per_page=per_page)
    else:
        # Fetch all medicines and paginate
        medicines = Medicine.query.paginate(page=page, per_page=per_page)

    # Basket functionality
    if 'basket' not in session:
        session['basket'] = []

    if request.method == 'POST':
        # Retrieve form data
        medicine_id = request.form.get('medicine_id')
        quantity = int(request.form.get('quantity'))
    
        # Check if the medicine_id is already in the basket
        found = False
        for item in session['basket']:
            if item['medicine_id'] == medicine_id:
                # If the item already exists, update the quantity
                item['quantity'] += quantity
                found = True
                break
    
        # If the item is not in the basket, add it as a new item
        if not found:
            session['basket'].append({
                'medicine_id': medicine_id,
                'quantity': quantity
            })

        # Flash a success message and redirect
        flash('Medicine added to basket!', 'success')
        return redirect(url_for('meds'))

    return render_template('meds.html', medicines=medicines)


@app.route('/basket')
@login_required
def basket():
    basket_items = []
    total_cost = 0

    # Fetch medicine details from the basket session
    for item in session['basket']:
        medicine_id = int(item['medicine_id'])
        quantity = int(item['quantity'])

        medicine = Medicine.query.get(medicine_id)
        cost = medicine.price * quantity
        total_cost += cost

        basket_items.append({
            'medicine': medicine,
            'quantity': quantity,
            'cost': cost
        })

    return render_template('basket.html', basket_items=basket_items, total_cost=total_cost)


@app.route('/order', methods=['POST'])
@login_required
def order():
    # Process the order and create MedicineOrder entries
    for item in session['basket']:
        medicine_id = int(item['medicine_id'])
        quantity = int(item['quantity'])

        # Create a new order
        order = MedicineOrder(
            user_id=current_user.id,
            medicine_id=medicine_id,
            quantity=quantity
        )
        db.session.add(order)

        # Update medicine quantity
        medicine = Medicine.query.get(medicine_id)
        medicine.quantity -= quantity

    db.session.commit()
    # Clear the basket
    session['basket'] = []
    flash('Order placed successfully!', 'success')
    return redirect(url_for('meds'))

@app.route('/dashboard', methods=["GET", "POST"])
@login_required
def dashboard():
    if not current_user.is_authenticated:
        flash('You need to log in to view this page.', 'warning')
        return redirect(url_for('login'))

    user = current_user

    if request.method == 'POST':
        # Update user data based on form submission
        user.first_name = request.form.get('first_name')
        user.last_name = request.form.get('last_name')
        user.username = request.form.get('username')
        user.city = request.form.get('city')
        user.state = request.form.get('state')
        user.country = request.form.get('country')
        user.zip = request.form.get('zip')

        db.session.commit()

        flash('Profile updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('dashboard.html', user=user)

@app.route('/consult', methods=["GET", "POST"])
def consult():
    return render_template('consult.html')

@app.route('/records', methods=['GET', 'POST'])
def records():
    return render_template('records.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')

        # Check if the username already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose a different one.', 'danger')
            return redirect(url_for('register'))

        # Create a new user
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        new_user = User(
            username=username,
            password=hashed_password,
            first_name=first_name,
            last_name=last_name
        )

        db.session.add(new_user)
        db.session.commit()

        flash('Account created successfully! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))

        flash('Invalid credentials. Please try again.', 'danger')
        return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have logged out successfully.', 'success')
    return redirect(url_for('login'))

# Add a CLI command to import medicines from a CSV file
@app.cli.command("import-medicines")
@click.argument("csv_file")
@with_appcontext
def import_medicines(csv_file):
    with open(csv_file, newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        # Skip the header row
        next(reader)

        # Process each row in the CSV file
        for row in reader:
            # Extract data from the row
            medicine_id = int(row[0])
            name = row[1]
            price = float(row[2])
            is_discontinued = row[3].lower() == 'true'
            manufacturer_name = row[4]
            medicine_type = row[5]
            pack_size_label = row[6]
            short_composition1 = row[7]
            short_composition2 = row[8]
            
            # Create a new Medicine instance
            medicine = Medicine(
                id=medicine_id,
                name=name,
                price=price,
                is_discontinued=is_discontinued,
                manufacturer_name=manufacturer_name,
                type=medicine_type,
                pack_size_label=pack_size_label,
                short_composition1=short_composition1,
                short_composition2=short_composition2
            )
            
            # Add the medicine instance to the database session
            db.session.add(medicine)

        # Commit the transaction to save the changes to the database
        db.session.commit()
        click.echo("Medicines imported successfully.")

if __name__ == '__main__':
    app.run(debug=True)
