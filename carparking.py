from flask import Flask, render_template, request, redirect, session, flash, jsonify, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit

import pymysql
from flask_bcrypt import Bcrypt

import eventlet
eventlet.monkey_patch()

import os

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
app.secret_key = "your_secret_key"  
bcrypt = Bcrypt(app)


def get_db_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="#mysql123", 
        database="Registeration",
        cursorclass=pymysql.cursors.DictCursor
    )


GUARD_CREDENTIALS = {
    "email": "guard@gmail.com",
    "password": "guard123"
}

# ✅ Home Route
@app.route("/")
def index():
    return render_template("first1.html") 

@app.route("/home")  
def home_page():
    return render_template("first1.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect("/register")

        connection = get_db_connection()
        cursor = connection.cursor()

       
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash("Email already registered! Please login.", "warning")
            return redirect("/register")

        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        cursor.execute("INSERT INTO users (email, password) VALUES (%s, %s)", (email, hashed_password))
        connection.commit()
        cursor.close()
        connection.close()

        flash("Registration successful! Please login.", "success")
        return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        
        if email == GUARD_CREDENTIALS["email"] and password == GUARD_CREDENTIALS["password"]:
            session['email'] = email  
            session['role'] = "guard"  
            flash("Guard login successful!", "success")
            return redirect("/guard_parking_slots")  

       
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        cursor.close()
        connection.close()

        if user and bcrypt.check_password_hash(user["password"], password):
            session["user"] = user["email"]
            flash("User login successful!", "success")
            return redirect("/user_parking_slots")
        
        else:
            flash("Invalid email or password!", "danger")
            return redirect("/login")

    return render_template("login.html")


@app.route('/guard_parking_slots')
def guard_parking_slots():
    if session.get('role') == "guard":
        return render_template('guard_parking_slots.html') 
    else:
        flash("Unauthorized Access!", "danger")
        return redirect("/login")


@app.route("/user_parking_slots")
def parking_slots():
    if "user" not in session:
        flash("Please log in first!", "warning")
        return redirect("/login")

    return render_template("user_parking_slots.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect("/login")


@app.route("/guard_bookings")
def guard_bookings():
    if session.get('role') != "guard":
        flash("Unauthorized Access!", "danger")
        return redirect("/login")

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM bookings")
    all_bookings = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template("guard_bookings.html", bookings=all_bookings)


@app.route("/my_bookings")
def my_bookings():
    if "user" not in session:
        return redirect("/login")

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT slot_number, booking_date, checkin_time, checkout_time FROM advance_bookings WHERE user_email = %s", (session["user"],))
    bookings = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template("my_bookings.html", bookings=bookings)


@socketio.on("update_parking_slots")
def handle_parking_update():
    emit("refresh_slots", broadcast=True) 


# ✅ Save Booking Data
@app.route("/save_advance_booking", methods=["POST"])
def save_advance_booking():
    if "user" not in session:
        return jsonify({"status": "error", "message": "User not logged in"})

    data = request.json
    print("Received Booking Data:", data)  

    try:
        user_email = session["user"]
        slot_number = data.get("slot_number")
        booking_date = data.get("booking_date")
        checkin_time = data.get("checkin_time")
        checkout_time = data.get("checkout_time")
        payment_status = data.get("payment_status", "pending")

        if not all([slot_number, booking_date, checkin_time, checkout_time]):
            return jsonify({"status": "error", "message": "Missing required booking data"})

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO advance_bookings (user_email, slot_number, booking_date, checkin_time, checkout_time, payment_status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_email, slot_number, booking_date, checkin_time, checkout_time, payment_status))

        connection.commit()
        cursor.close()
        connection.close()

      
        socketio.emit("refresh_slots")
        
        return jsonify({"status": "success", "message": "Advance booking saved successfully!"})

    except Exception as e:
        print("Error inserting booking:", e)  
        return jsonify({"status": "error", "message": "Database error", "error": str(e)}), 500

@app.route("/get_smallest_available_slot", methods=["GET"])
def get_smallest_available_slot():
    connection = get_db_connection()
    cursor = connection.cursor()

   
    cursor.execute("SELECT slot_number FROM advance_bookings")
    booked_slots = {row["slot_number"] for row in cursor.fetchall()} 

    cursor.close()
    connection.close()

  
    for slot in range(1, 101):  
        if slot not in booked_slots:
            return jsonify({"smallest_slot": slot})  

    return jsonify({"error": "No slots available"}), 400  


@app.route("/get_booked_slots", methods=["GET"])
def get_booked_slots():
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT slot_number FROM advance_bookings WHERE booking_date >= CURDATE()")
    booked_slots = [row[0] for row in cursor.fetchall()]

    cursor.close()
    connection.close()

    return jsonify(booked_slots)  


@app.route("/all_bookings")
def all_bookings():
    if session.get('role') != "guard":
        flash("Unauthorized Access!", "danger")
        return redirect("/login")

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT user_email, slot_number, booking_date, checkin_time, checkout_time, payment_status FROM advance_bookings")
    bookings = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template("all_bookings.html", bookings=bookings)



@app.route("/register_owner", methods=["GET", "POST"])
def register_owner():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if not all([name, email, phone, password, confirm_password]):
            flash("All fields are required!", "danger")
            return redirect("/register_owner")

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect("/register_owner")

        connection = get_db_connection()
        cursor = connection.cursor()

        
        cursor.execute("SELECT * FROM owners WHERE email = %s", (email,))
        existing_owner = cursor.fetchone()

        if existing_owner:
            flash("Email already registered! Please login.", "warning")
            return redirect("/register_owner")

        
        hashed_password = generate_password_hash(password)

        cursor.execute("INSERT INTO owners (name, email, phone, password) VALUES (%s, %s, %s, %s)", 
                       (name, email, phone, hashed_password))
        connection.commit()
        cursor.close()
        connection.close()

        flash("Registration successful! Please login.", "success")
        return redirect("/login_owner")

    return render_template("register_owner.html")


@app.route("/login_owner", methods=["GET", "POST"])
def login_owner():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)  
        cursor.execute("SELECT id, password FROM owners WHERE email = %s", (email,))
        owner = cursor.fetchone()
        cursor.close()
        connection.close()

        if owner and check_password_hash(owner["password"], password):
            session["owner_id"] = owner["id"] 
            flash("Owner login successful!", "success")
            return redirect("/rental_space_form")  
        
        else:
            flash("Invalid email or password!", "danger")
            return redirect("/login_owner")

    return render_template("login_owner.html")

@app.route("/rental_space_form")
def rental_space():
    if "owner_id" not in session:  
        flash("Please log in to access this page.", "warning")
        return redirect("/login_owner")  

    return render_template("rental_space_form.html")  

@app.route("/submit_space", methods=["POST"])
def submit_space():
    if "owner_id" not in session:
        flash("Please log in to list a parking space.", "warning")
        return redirect(url_for("login_owner"))  

    owner_id = session["owner_id"]
    owner_name = request.form["owner_name"]
    aadhaar_number = request.form["aadhaar_number"]
    phone_number = request.form["phone_number"]
    location = request.form["location"]
    description = request.form["description"]
    price = request.form["price"]
    total_slots = int(request.form["total_slots"])  

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            INSERT INTO rental_spaces (owner_id, owner_name, aadhaar_number, phone_number, location, description, price) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (owner_id, owner_name, aadhaar_number, phone_number, location, description, price))

        space_id = cursor.lastrowid  

        for slot in range(1, total_slots + 1):
            cursor.execute("""
                INSERT INTO parking_slots (space_id, slot_number, status) VALUES (%s, %s, 'available')
            """, (space_id, slot))

        connection.commit()
        flash("Your parking space has been listed successfully!", "success")

        
        return redirect(url_for("view_parking_slots", space_id=space_id))


    except pymysql.err.IntegrityError:
        flash("Aadhaar number already exists. Please use a unique Aadhaar number.", "danger")
        return redirect("/rental_space_form")

    finally:
        cursor.close()
        connection.close()
        
@app.route("/view_parking_slots/<int:space_id>")
def view_parking_slots(space_id):
    connection = get_db_connection()
    cursor = connection.cursor()

  
    cursor.execute("SELECT * FROM rental_spaces WHERE id = %s", (space_id,))
    parking_space = cursor.fetchone()

    cursor.execute("SELECT * FROM parking_slots WHERE space_id = %s", (space_id,))
    slots = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template("rental_parking_slots.html", parking_space=parking_space, slots=slots)
        
@app.route("/book_parking_slot", methods=["POST"])
def book_parking_slot():
    if "user" not in session:
        return jsonify({"status": "error", "message": "Please log in first!"})

    data = request.json
    slot_id = data.get("slot_id")

    connection = get_db_connection()
    cursor = connection.cursor()

   
    cursor.execute("SELECT status FROM parking_slots WHERE id = %s", (slot_id,))
    slot = cursor.fetchone()

    if not slot or slot["status"] != "available":
        return jsonify({"status": "error", "message": "Slot not available!"})

   
    cursor.execute("UPDATE parking_slots SET status = 'booked', booked_by = %s WHERE id = %s", (session["user"], slot_id))
    
    connection.commit()
    cursor.close()
    connection.close()

    socketio.emit("update_slots") 
    return jsonify({"status": "success", "message": "Slot booked successfully!"})
    
        
 

@app.route('/update_slot/<int:slot>/<int:status>')
def update_slot(slot, status):
    socketio.emit('slot_update', {'slot': slot, 'status': status})
    return f"Slot {slot} updated to status {status}"
 
@socketio.on('connect')
def test_connection():
    print("A user connected")
    socketio.emit('slot_update', {'slot': 1, 'status': 1}) 


parking_slots = {}

@socketio.on("instant_booking")
def handle_instant_booking(data):
    slot = data["slot"]
    car = data["car"]
    parking_slots[slot] = car
    socketio.emit("update_slot", {"slot": slot, "car": car})

@socketio.on("cancel_slot_request")
def handle_cancel_slot(data):
    slot_number = data["slot"]
   
    socketio.emit("cancel_slot", {"slot": slot_number})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  
    socketio.run(app, host='0.0.0.0', port=port)