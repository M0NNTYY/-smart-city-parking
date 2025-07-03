import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, redirect, session, flash, jsonify, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit
from flask_bcrypt import Bcrypt

from firebase_admin import credentials, firestore, initialize_app
import os
from datetime import datetime

# Initialize Firebase
cred = credentials.Certificate("/etc/secrets/serviceAccountKey.json")
initialize_app(cred)
db = firestore.client()

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
app.secret_key = "your_secret_key"
bcrypt = Bcrypt(app)

# Guard Credentials
GUARD_CREDENTIALS = {
    "email": "guard@gmail.com",
    "password": "guard123"
}

# Home Routes
@app.route("/")
@app.route("/home")
def index():
    return render_template("first1.html")

# User Registration
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect("/register")

        existing_user = db.collection("users").where("email", "==", email).get()
        if existing_user:
            flash("Email already registered! Please login.", "warning")
            return redirect("/register")

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        db.collection("users").add({
            "email": email,
            "password": hashed_password
        })

        flash("Registration successful! Please login.", "success")
        return redirect("/login")

    return render_template("register.html")

# User Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        if email == GUARD_CREDENTIALS["email"] and password == GUARD_CREDENTIALS["password"]:
            session['email'] = email
            session['role'] = "guard"
            flash("Guard login successful!", "success")
            return redirect("/guard_bookings")

        user_docs = db.collection("users").where("email", "==", email).get()
        user = None
        for doc in user_docs:
            user = doc.to_dict()
            break

        if user and bcrypt.check_password_hash(user["password"], password):
            session["user"] = user["email"]
            flash("User login successful!", "success")
            return redirect("/user_parking_slots")
        else:
            flash("Invalid email or password!", "danger")
            return redirect("/login")

    return render_template("login.html")

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

    bookings = [doc.to_dict() for doc in db.collection("advance_bookings").get()]
    return render_template("guard_bookings.html", bookings=bookings)

@app.route("/my_bookings")
def my_bookings():
    if "user" not in session:
        return redirect("/login")

    bookings = [doc.to_dict() for doc in db.collection("advance_bookings").where("user_email", "==", session["user"]).get()]
    return render_template("my_bookings.html", bookings=bookings)

@socketio.on("update_parking_slots")
def handle_parking_update():
    emit("refresh_slots", broadcast=True)

@app.route("/save_advance_booking", methods=["POST"])
def save_advance_booking():
    if "user" not in session:
        return jsonify({"status": "error", "message": "User not logged in"})

    data = request.json
    user_email = session["user"]
    slot_number = data.get("slot_number")
    booking_date = data.get("booking_date")
    checkin_time = data.get("checkin_time")
    checkout_time = data.get("checkout_time")
    payment_status = data.get("payment_status", "pending")

    if not all([slot_number, booking_date, checkin_time, checkout_time]):
        return jsonify({"status": "error", "message": "Missing required booking data"})

    db.collection("advance_bookings").add({
        "user_email": user_email,
        "slot_number": slot_number,
        "booking_date": booking_date,
        "checkin_time": checkin_time,
        "checkout_time": checkout_time,
        "payment_status": payment_status
    })

    socketio.emit("refresh_slots")
    return jsonify({"status": "success", "message": "Advance booking saved successfully!"})

@app.route("/get_smallest_available_slot", methods=["GET"])
def get_smallest_available_slot():
    booked_slots = set()
    docs = db.collection("advance_bookings").get()
    for doc in docs:
        booked_slots.add(doc.to_dict()["slot_number"])
    for slot in range(1, 101):
        if slot not in booked_slots:
            return jsonify({"smallest_slot": slot})
    return jsonify({"error": "No slots available"}), 400

@app.route("/get_booked_slots", methods=["GET"])
def get_booked_slots():
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    booked = []
    docs = db.collection("advance_bookings").get()
    for doc in docs:
        d = doc.to_dict()
        if d["booking_date"] >= today_str:
            booked.append(d["slot_number"])
    return jsonify(booked)

@app.route("/all_bookings")
def all_bookings():
    if session.get('role') != "guard":
        flash("Unauthorized Access!", "danger")
        return redirect("/login")
    bookings = [doc.to_dict() for doc in db.collection("advance_bookings").get()]
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

        existing_owner = db.collection("owners").where("email", "==", email).get()
        if existing_owner:
            flash("Email already registered!", "warning")
            return redirect("/register_owner")

        hashed_password = generate_password_hash(password)
        db.collection("owners").add({
            "name": name,
            "email": email,
            "phone": phone,
            "password": hashed_password
        })

        flash("Registration successful!", "success")
        return redirect("/login_owner")

    return render_template("register_owner.html")

@app.route("/login_owner", methods=["GET", "POST"])
def login_owner():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        owner_docs = db.collection("owners").where("email", "==", email).get()
        owner = None
        owner_id = None
        for doc in owner_docs:
            owner = doc.to_dict()
            owner_id = doc.id
            break

        if owner and check_password_hash(owner["password"], password):
            session["owner_id"] = owner_id
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

    space_ref = db.collection("rental_spaces").add({
        "owner_id": owner_id,
        "owner_name": owner_name,
        "aadhaar_number": aadhaar_number,
        "phone_number": phone_number,
        "location": location,
        "description": description,
        "price": price
    })
    space_id = space_ref[1].id

    for slot in range(1, total_slots + 1):
        db.collection("rental_spaces").document(space_id).collection("parking_slots").add({
            "slot_number": slot,
            "status": "available"
        })

    flash("Your parking space has been listed successfully!", "success")
    return redirect(url_for("view_parking_slots", space_id=space_id))

@app.route("/view_parking_slots/<space_id>")
def view_parking_slots(space_id):
    space_doc = db.collection("rental_spaces").document(space_id).get()
    parking_space = space_doc.to_dict()
    slots = [doc.to_dict() for doc in db.collection("rental_spaces").document(space_id).collection("parking_slots").get()]
    return render_template("rental_parking_slots.html", parking_space=parking_space, slots=slots)

@socketio.on("instant_booking")
def handle_instant_booking(data):
    slot = data["slot"]
    car = data["car"]
    socketio.emit("update_slot", {"slot": slot, "car": car})

@socketio.on("cancel_slot_request")
def handle_cancel_slot(data):
    slot_number = data["slot"]
    socketio.emit("cancel_slot", {"slot": slot_number})

@socketio.on("connect")
def test_connection():
    print("A user connected")
    socketio.emit('slot_update', {"slot": 1, "status": 1})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
