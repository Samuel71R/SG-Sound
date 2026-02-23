import sqlite3
import json
import smtplib
import random
import os
import tempfile
from fpdf import FPDF
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from flask import Flask, request, jsonify, send_from_directory, session, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, template_folder=basedir)
app.secret_key = "sgsoundserve_mfa_secret_2024"
CORS(app, supports_credentials=True)

DB_FILE = os.path.join(basedir, "sgsound.db")
UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# This part is vital: it creates the folder if it's missing on Render
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
otp_storage = {}
@app.route('/')
def home():
    # This tells Flask to look for index.html and show it to the user
    return render_template('index.html')

# Ensure upload directory exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- EMAIL CONFIGURATION ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
import os
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'sgsoundserve@gmail.com')
SENDER_PASSWORD = os.environ.get('SENDER_PASSWORD', 'buna dbuv tckx mhqy')
def get_db_connection():
    conn = sqlite3.connect(DB_FILE, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, password TEXT, username TEXT, mfa_otp TEXT)')
    
    # Check if mfa_otp column exists in users, if not add it
    try:
        c.execute('SELECT mfa_otp FROM users LIMIT 1')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE users ADD COLUMN mfa_otp TEXT')
    
    # Modified products table to include sample_url
    c.execute('''CREATE TABLE IF NOT EXISTS products 
                 (id INTEGER, cat TEXT, name TEXT, price INTEGER, icon TEXT, image TEXT, sample_url TEXT)''')
    
    c.execute('CREATE TABLE IF NOT EXISTS catalog (id INTEGER, cat TEXT, name TEXT, price INTEGER, image TEXT)')
    
    # Modified orders table to include booking_date
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                 (id INTEGER PRIMARY KEY, user TEXT, user_email TEXT, date TEXT, booking_date TEXT,
                  items TEXT, total INTEGER, is_read INTEGER)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS tickets 
                 (id INTEGER PRIMARY KEY, user TEXT, email TEXT, subject TEXT, desc TEXT, 
                  date TEXT, status TEXT, is_read INTEGER, reply TEXT)''')

    # Check if sample_url column exists in products, if not add it
    try:
        c.execute('SELECT sample_url FROM products LIMIT 1')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE products ADD COLUMN sample_url TEXT')
    
    # Check if booking_date column exists in orders, if not add it
    try:
        c.execute('SELECT booking_date FROM orders LIMIT 1')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE orders ADD COLUMN booking_date TEXT')

    # Clear existing products and insert comprehensive catalog
    c.execute('DELETE FROM products')
    c.executemany('INSERT INTO products (id, cat, name, price, icon, image, sample_url) VALUES (?,?,?,?,?,?,?)', [
        # DJ Services (Book Packages) - IDs 101-110
        (101, "DJ Services", "Basic Party DJ", 6500, "fas fa-music", "", ""),
        (102, "DJ Services", "Wedding Sangeet DJ", 13500, "fas fa-ring", "", ""),
        (103, "DJ Services", "Corporate Event DJ", 14000, "fas fa-briefcase", "", ""),
        (104, "DJ Services", "Celebrity/Club DJ", 95000, "fas fa-star", "", ""),
        (105, "DJ Services", "Birthday Bash Set", 7500, "fas fa-birthday-cake", "", ""),
        (106, "DJ Services", "Pool Party DJ", 9000, "fas fa-swimming-pool", "", ""),
        (107, "DJ Services", "Baraat DJ (Mobile)", 20000, "fas fa-truck", "", ""),
        (108, "DJ Services", "Dandiya/Folk Night", 12000, "fas fa-drum", "", ""),
        (109, "DJ Services", "School/College Culturals", 35000, "fas fa-graduation-cap", "", ""),
        (110, "DJ Services", "Karaoke & DJ Combo", 11000, "fas fa-microphone-alt", "", ""),
        
        # Rentals (Full Sets) - IDs 201-210
        (201, "Rentals", "Standard PA System", 2500, "fas fa-volume-up", "", ""),
        (202, "Rentals", "Premium Sound Set", 8000, "fas fa-speakers", "", ""),
        (203, "Rentals", "Full DJ Setup", 10000, "fas fa-compact-disc", "", ""),
        (204, "Rentals", "Conference Audio Set", 4500, "fas fa-user-tie", "", ""),
        (205, "Rentals", "Live Band Audio Rig", 15000, "fas fa-guitar", "", ""),
        (206, "Rentals", "LED Dance Floor Set", 18000, "fas fa-lightbulb", "", ""),
        (207, "Rentals", "Visual Rental Set", 12000, "fas fa-video", "", ""),
        (208, "Rentals", "Trussing & Lighting", 20000, "fas fa-project-diagram", "", ""),
        (209, "Rentals", "Compact Vlog Set", 1500, "fas fa-camera", "", ""),
        (210, "Rentals", "Silent Disco Set", 15000, "fas fa-headphones", "", ""),
        
        # Sales (Buy Equipment) - IDs 301-310
        (301, "Sales", "Pioneer DDJ-FLX4", 35000, "fas fa-compact-disc", "", ""),
        (302, "Sales", "Pioneer XDJ-XZ", 245000, "fas fa-sliders-h", "", ""),
        (303, "Sales", "JBL EON 715", 58000, "fas fa-volume-up", "", ""),
        (304, "Sales", "Shure SM58", 9500, "fas fa-microphone", "", ""),
        (305, "Sales", "Yamaha MG16XU", 42000, "fas fa-sliders-h", "", ""),
        (306, "Sales", "Sennheiser EW-D", 65000, "fas fa-broadcast-tower", "", ""),
        (307, "Sales", "KRK Rokit 5", 32000, "fas fa-music", "", ""),
        (308, "Sales", "Focusrite Scarlett", 16500, "fas fa-plug", "", ""),
        (309, "Sales", "RCF Sub 8003-AS", 145000, "fas fa-volume-down", "", ""),
        (310, "Sales", "Used CDJ-2000NXS2", 110000, "fas fa-recycle", "", "")
    ])
    
    # Clear existing catalog and insert comprehensive catalog
    c.execute('DELETE FROM catalog')
    c.executemany('INSERT INTO catalog (id, cat, name, price, image) VALUES (?,?,?,?,?)', [
        # Custom Catalog (Individual Items) - IDs 901-910
        (901, "Microphones", "Cordless Handheld Mic", 600, ""),
        (902, "Microphones", "Wireless Collar/Lapel", 1000, ""),
        (903, "Lighting", "Sharpy Moving Head", 1500, ""),
        (904, "Effects", "Smoke / Fog Machine", 1000, ""),
        (905, "Lighting", "LED Par Can Light", 400, ""),
        (906, "Power", "Silent Generator", 5500, ""),
        (907, "Visual", "LED TV (65 inch)", 4000, ""),
        (908, "Visual", "Projector (High Lumens)", 3500, ""),
        (909, "Monitors", "Stage Monitor (Wedge)", 1200, ""),
        (910, "Communication", "Walkie Talkie Set", 1000, "")
    ])

    conn.commit()
    conn.close()

# --- PDF GENERATOR ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'SG SOUND SERVE', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, 'Professional Audio & Event Production', 0, 1, 'C')
        self.line(10, 30, 200, 30)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_invoice(order_data):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"INVOICE #: {order_data['id']}", ln=True)
    pdf.cell(0, 10, f"Date: {order_data['date']}", ln=True)
    pdf.cell(0, 10, f"Booking Date: {order_data.get('booking_date', 'N/A')}", ln=True)
    pdf.cell(0, 10, f"Bill To: {order_data['user']}", ln=True)
    pdf.ln(10)
    
    pdf.set_fill_color(200, 220, 255)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(100, 10, "Item Description", 1, 0, 'L', 1)
    pdf.cell(40, 10, "Price", 1, 0, 'R', 1)
    pdf.cell(50, 10, "Total", 1, 1, 'R', 1)
    
    pdf.set_font("Arial", size=11)
    for item in order_data['items']:
        name = item.get('name', 'Item')
        price = str(item.get('price', 0))
        total = str(item.get('total', 0))
        pdf.cell(100, 10, name, 1)
        pdf.cell(40, 10, f"Rs. {price}", 1, 0, 'R')
        pdf.cell(50, 10, f"Rs. {total}", 1, 1, 'R')
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(140, 10, "Grand Total", 1, 0, 'R')
    pdf.cell(50, 10, f"Rs. {order_data['total']}", 1, 1, 'R')
    
    pdf.ln(20)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 10, "Thank you for your business!", ln=True, align='C')
    
    temp_dir = tempfile.gettempdir()
    filename = os.path.join(temp_dir, f"invoice_{order_data['id']}.pdf")
    pdf.output(filename)
    return filename

# --- UNIVERSAL EMAIL SENDER ---
def send_email(to_email, subject, body_text, attachment_path=None):
    if "your-email" in SENDER_EMAIL:
        return

    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = f"SG Sound Serve <{SENDER_EMAIL}>"
        msg['To'] = to_email
        msg['Subject'] = subject

        html_content = f"""
        <html>
            <body style="font-family: sans-serif; color: #333;">
                <div style="padding: 20px; border: 1px solid #eee; max-width: 600px;">
                    <h2 style="color: #d32f2f;">SG Sound Serve</h2>
                    <p style="font-size: 15px;">{body_text.replace('\\n', '<br>')}</p>
                    <hr style="border: none; border-top: 1px solid #eee;">
                    <p style="font-size: 11px; color: #999;">Professional Audio & Event Production</p>
                </div>
            </body>
        </html>
        """
        msg.attach(MIMEText(body_text, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))

        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
            msg.attach(part)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        server.quit()
        print(f"✅ Email sent to {to_email}")
    except Exception as e:
        print(f"❌ Email error: {e}")

# --- IMAGE UPLOAD ROUTE ---
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"success": False, "msg": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "msg": "No selected file"}), 400
    if file:
        filename = secure_filename(f"{random.randint(1000,9999)}_{file.filename}")
        file.save(os.path.join(UPLOAD_FOLDER, filename))
        return jsonify({"success": True, "filename": filename})

# --- DATA ROUTES ---
@app.route('/api/products', methods=['GET', 'POST'])
def products():
    conn = get_db_connection()
    if request.method == 'GET':
        rows = conn.execute('SELECT * FROM products').fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows])
    else:
        items = request.json
        conn.execute('DELETE FROM products')
        for i in items:
            img = i.get('image', '')
            sample = i.get('sample_url', '')
            conn.execute('INSERT INTO products (id, cat, name, price, icon, image, sample_url) VALUES (?,?,?,?,?,?,?)', 
                         (i['id'], i['cat'], i['name'], i['price'], i['icon'], img, sample))
        conn.commit()
        conn.close()
        return jsonify({"success": True})

# --- FEATURE 1: Availability Check Endpoint ---
@app.route('/api/available-products', methods=['GET'])
def available_products():
    booking_date = request.args.get('date')
    if not booking_date:
        return jsonify({"success": False, "msg": "Date parameter required"}), 400
    
    conn = get_db_connection()
    
    # Get all products
    all_products = conn.execute('SELECT * FROM products').fetchall()
    
    # Get orders for the specified date
    orders = conn.execute('SELECT items FROM orders WHERE booking_date = ?', (booking_date,)).fetchall()
    conn.close()
    
    # Extract booked product IDs
    booked_ids = set()
    for order in orders:
        try:
            items = json.loads(order['items'])
            for item in items:
                if 'id' in item:
                    booked_ids.add(item['id'])
        except:
            pass
    
    # Filter available products
    available_products = []
    for product in all_products:
        prod_dict = dict(product)
        if prod_dict['id'] not in booked_ids:
            available_products.append(prod_dict)
    
    return jsonify({"success": True, "products": available_products, "booked_count": len(booked_ids)})

@app.route('/api/catalog', methods=['GET', 'POST'])
def catalog():
    conn = get_db_connection()
    if request.method == 'GET':
        rows = conn.execute('SELECT * FROM catalog').fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows])
    else:
        items = request.json
        conn.execute('DELETE FROM catalog')
        for i in items:
            img = i.get('image', '')
            conn.execute('INSERT INTO catalog (id, cat, name, price, image) VALUES (?,?,?,?,?)', 
                         (i['id'], i['cat'], i['name'], i['price'], img))
        conn.commit()
        conn.close()
        return jsonify({"success": True})

# --- AUTH ROUTES ---
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email=? AND password=?', (data['email'], data['password'])).fetchone()
    if not user:
        conn.close()
        return jsonify({"success": False}), 401

    email = data['email']
    username = user['username']

    # Generate 6-digit OTP and store in DB + in-memory dict (cross-origin safe, no cookies needed)
    otp = str(random.randint(100000, 999999))
    conn.execute('UPDATE users SET mfa_otp=? WHERE email=?', (otp, email))
    conn.commit()
    conn.close()

    # Also keep in otp_storage with a "mfa:" prefix to distinguish from password-reset OTPs
    otp_storage['mfa:' + email] = {'otp': otp, 'username': username}

    # Email the OTP
    send_email(email, "SG Sound Serve \u2013 Your Login OTP",
        f"Hello {username},\n\nYour One-Time Password (OTP) for login is:\n\n{otp}\n\nThis OTP is valid for this session only. Do not share it with anyone.\n\nIf you did not attempt to login, please ignore this email.")

    # Return email back to frontend so it can include it in the verify request (no cookie/session needed)
    return jsonify({"success": True, "mfa_required": True, "email": email})

@app.route('/api/verify-mfa', methods=['POST'])
def verify_mfa():
    data = request.json
    email = data.get('email', '').strip()
    provided_otp = data.get('otp', '').strip()

    if not email or not provided_otp:
        return jsonify({"success": False, "msg": "Missing email or OTP."}), 400

    # Check in-memory store first (fast path)
    pending = otp_storage.get('mfa:' + email)
    if not pending or pending['otp'] != provided_otp:
        # Fallback: also check DB in case server restarted between login and verify
        conn = get_db_connection()
        user = conn.execute('SELECT username, mfa_otp FROM users WHERE email=?', (email,)).fetchone()
        conn.close()
        if not user or user['mfa_otp'] != provided_otp:
            return jsonify({"success": False, "msg": "Invalid OTP. Please try again."}), 401
        username = user['username']
    else:
        username = pending['username']

    # OTP correct — clear from both stores (single-use)
    otp_storage.pop('mfa:' + email, None)
    conn = get_db_connection()
    conn.execute('UPDATE users SET mfa_otp=NULL WHERE email=?', (email,))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "user": username, "email": email})

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO users VALUES (?,?,?,NULL)', (data['email'], data['password'], data['username']))
        conn.commit()
        
        welcome_msg = f"Hello {data['username']}, Welcome to SG SOUND SERVE! You have successfully registered as a partner. You can now log in to the portal to request quotes and manage orders."
        send_email(data['email'], "Welcome to SG Sound Serve", welcome_msg)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "msg": "User already exists"}), 400
    finally:
        conn.close()

# --- FORGOT PASSWORD ---
@app.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    data = request.json
    email = data.get('email')
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
    conn.close()
    if not user: return jsonify({"success": False, "msg": "Email not found"})
    otp = str(random.randint(100000, 999999))
    otp_storage[email] = otp
    send_email(email, "Password Reset OTP", f"Your OTP is: {otp}")
    return jsonify({"success": True})

@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    data = request.json
    email, otp, new_pass = data.get('email'), data.get('otp'), data.get('new_pass')
    if email in otp_storage and otp_storage[email] == otp:
        conn = get_db_connection()
        conn.execute('UPDATE users SET password=? WHERE email=?', (new_pass, email))
        conn.commit()
        conn.close()
        del otp_storage[email]
        return jsonify({"success": True})
    return jsonify({"success": False, "msg": "Invalid OTP"})

# --- ORDER ROUTES ---
@app.route('/api/orders', methods=['GET', 'POST', 'PUT'])
def orders():
    conn = get_db_connection()
    if request.method == 'GET':
        rows = conn.execute('SELECT * FROM orders').fetchall()
        conn.close()
        data = []
        for r in rows:
            d = dict(r)
            d['items'] = json.loads(d['items'])
            d['isRead'] = bool(d['is_read'])
            data.append(d)
        return jsonify(data)
    elif request.method == 'POST':
        data = request.json
        booking_date = data.get('booking_date', '')
        conn.execute('INSERT INTO orders VALUES (?,?,?,?,?,?,?,0)', 
                     (data['id'], data['user'], data['userEmail'], data['date'], 
                      booking_date, json.dumps(data['items']), data['total']))
        conn.commit()
        conn.close()
        
        # Generate invoice with booking date
        pdf_file = generate_invoice(data)
        item_list = "\\n".join([f"- {i['name']}: Rs. {i['total']}" for i in data['items']])
        email_body = f"Dear {data['user']}, Thank you for your order #{data['id']}. Booking Date: {booking_date}. Total: Rs. {data['total']}. Details: \\n{item_list}"
        send_email(data['userEmail'], f"Invoice #{data['id']}", email_body, pdf_file)
        if os.path.exists(pdf_file): os.remove(pdf_file)
        return jsonify({"success": True})
    elif request.method == 'PUT':
        conn.execute('UPDATE orders SET is_read = 1')
        conn.commit()
        conn.close()
        return jsonify({"success": True})

@app.route('/api/user/orders', methods=['GET'])
def user_orders():
    email = request.args.get('email')
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM orders WHERE user_email = ? ORDER BY id DESC', (email,)).fetchall()
    conn.close()
    data = []
    for r in rows:
        d = dict(r)
        d['items'] = json.loads(d['items'])
        data.append(d)
    return jsonify(data)

# --- NEW: ADMIN ANALYTICS ENDPOINT (Feature 5) ---
@app.route('/api/analytics', methods=['GET'])
def analytics():
    conn = get_db_connection()
    
    # Revenue by category
    orders = conn.execute('SELECT items, total, date, booking_date FROM orders').fetchall()
    category_revenue = {"DJ Services": 0, "Rentals": 0, "Sales": 0}
    
    for order in orders:
        try:
            items = json.loads(order['items'])
            for item in items:
                cat = item.get('cat', 'Unknown')
                if cat in category_revenue:
                    category_revenue[cat] += item.get('total', 0)
        except:
            pass
    
    # Orders over time (by order date)
    orders_by_date = {}
    for order in orders:
        date = order['date']
        orders_by_date[date] = orders_by_date.get(date, 0) + 1
    
    # Booking frequency by booking_date
    booking_dates = {}
    for order in orders:
        if order['booking_date']:
            date = order['booking_date']
            booking_dates[date] = booking_dates.get(date, 0) + 1
    
    conn.close()
    
    return jsonify({
        "success": True,
        "category_revenue": category_revenue,
        "orders_over_time": orders_by_date,
        "booking_frequency": booking_dates
    })

# --- SUPPORT TICKETS ---
@app.route('/api/tickets', methods=['GET', 'POST'])
def tickets():
    conn = get_db_connection()
    if request.method == 'GET':
        rows = conn.execute('SELECT * FROM tickets').fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows])
    else:
        data = request.json
        conn.execute('INSERT INTO tickets (id, user, email, subject, desc, date, status, is_read, reply) VALUES (?,?,?,?,?,?,?,0, "")', 
                     (data['id'], data['user'], data['email'], data['subject'], data['desc'], data['date'], "Open"))
        conn.commit()
        conn.close()
        return jsonify({"success": True})

@app.route('/api/tickets/<int:id>/resolve', methods=['PUT'])
def resolve_ticket(id):
    data = request.json
    reply_text = data.get('reply', '')
    conn = get_db_connection()
    ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (id,)).fetchone()
    if ticket:
        conn.execute('UPDATE tickets SET status = "Resolved", reply = ? WHERE id = ?', (reply_text, id))
        conn.commit()
        if ticket['email']:
            send_email(ticket['email'], f"Resolved: {ticket['subject']}", f"Hello {ticket['user']}, your ticket has been resolved. Reply: {reply_text}")
    conn.close()
    return jsonify({"success": True})

@app.route('/admin')
def admin_portal():
    return render_template('admin.html')

if __name__ == '__main__':
    init_db()
    print("SG Sound Serve Server Running on port 5001...")
    app.run(port=5001, debug=True)