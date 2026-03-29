from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from datetime import datetime, date, timedelta
from functools import wraps
from decimal import Decimal
import json

# ─── DECIMAL / TYPE SAFETY ────────────────────────────────────
def to_float(val, default=0.0):
    """Safely convert Decimal, str, int, float to float."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return float(default)

app = Flask(__name__)
app.secret_key = "laundry_pro_secret_2024"

# Inject datetime helpers into all templates
@app.context_processor
def inject_globals():
    return {'now': datetime.now, 'date': date}

# ─── DB CONNECTION ────────────────────────────────────────────
def db_conn():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Dharani@321",
        database="laundry_db"
    )

# ─── AUTH DECORATORS ─────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'loggedin' not in session:
            flash('Please login first.', 'warning')
            return redirect('/')
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect('/')
        return f(*args, **kwargs)
    return decorated

# ─── HELPERS ─────────────────────────────────────────────────
def format_time(td):
    """Convert MySQL timedelta or time to HH:MM AM/PM string."""
    if td is None:
        return None
    if hasattr(td, 'total_seconds'):
        total = int(td.total_seconds())
        hours = (total // 3600) % 24
        minutes = (total % 3600) // 60
    else:
        hours = td.hour
        minutes = td.minute
    period = 'AM' if hours < 12 else 'PM'
    h12 = hours % 12 or 12
    return f"{h12:02d}:{minutes:02d} {period}"

def get_settings():
    conn = db_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM settings WHERE id=1")
    s = cur.fetchone()
    conn.close()
    if s:
        s["opening_time_str"] = format_time(s.get("opening_time")) or "08:00 AM"
        s["closing_time_str"] = format_time(s.get("closing_time")) or "08:00 PM"
        # also store raw HH:MM for input[type=time] fields
        if s.get("opening_time"):
            td = s["opening_time"]
            total = int(td.total_seconds()) if hasattr(td, "total_seconds") else 0
            h = (total // 3600) % 24 if hasattr(td, "total_seconds") else td.hour
            m = (total % 3600) // 60 if hasattr(td, "total_seconds") else td.minute
            s["opening_time_hm"] = f"{h:02d}:{m:02d}"
            td2 = s["closing_time"]
            total2 = int(td2.total_seconds()) if hasattr(td2, "total_seconds") else 0
            h2 = (total2 // 3600) % 24 if hasattr(td2, "total_seconds") else td2.hour
            m2 = (total2 % 3600) // 60 if hasattr(td2, "total_seconds") else td2.minute
            s["closing_time_hm"] = f"{h2:02d}:{m2:02d}"
        else:
            s["opening_time_hm"] = "08:00"
            s["closing_time_hm"] = "20:00"
    return s

def unread_notifications(user_id):
    conn = db_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT COUNT(*) AS cnt FROM notifications WHERE user_id=%s AND is_read=0", (user_id,))
    r = cur.fetchone()
    conn.close()
    return r['cnt'] if r else 0

# ─── PUBLIC PAGES ─────────────────────────────────────────────
@app.route('/')
def index():
    settings = get_settings()
    today_name = datetime.now().strftime('%A')
    is_open = today_name in (settings['working_days'] or '')
    conn = db_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM services WHERE is_active=1")
    services = cur.fetchall()
    conn.close()
    return render_template('index.html', settings=settings, is_open=is_open, services=services)

# ─── AUTH ─────────────────────────────────────────────────────
@app.route('/login', methods=['POST'])
def login():
    user = request.form.get('username', '').strip()
    pw   = request.form.get('password', '').strip()
    conn = db_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (user, pw))
    account = cur.fetchone()
    conn.close()
    if account:
        if account['status'] == 'disabled':
            flash('Your account has been disabled. Contact admin.', 'danger')
            return redirect('/')
        session['loggedin']  = True
        session['id']        = account['id']
        session['username']  = account['username']
        session['full_name'] = account['full_name'] or account['username']
        session['role']      = account['role']
        flash(f"Welcome back, {session['full_name']}!", 'success')
        return redirect(url_for('admin_dashboard' if account['role'] == 'admin' else 'user_dashboard'))
    flash('Invalid username or password.', 'danger')
    return redirect('/')

@app.route('/register', methods=['POST'])
def register():
    username  = request.form.get('username', '').strip()
    password  = request.form.get('password', '').strip()
    full_name = request.form.get('full_name', '').strip()
    email     = request.form.get('email', '').strip()
    phone     = request.form.get('phone', '').strip()
    address   = request.form.get('address', '').strip()
    if not username or not password:
        flash('Username and password are required.', 'danger')
        return redirect('/')
    conn = db_conn()
    cur  = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, password, full_name, email, phone, address) VALUES (%s,%s,%s,%s,%s,%s)",
            (username, password, full_name, email, phone, address)
        )
        conn.commit()
        flash('Registration successful! Please login.', 'success')
    except mysql.connector.IntegrityError:
        flash('Username already exists. Try another.', 'danger')
    finally:
        conn.close()
    return redirect('/')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect('/')

# ─── USER DASHBOARD ───────────────────────────────────────────
@app.route('/dashboard')
@login_required
def user_dashboard():
    conn = db_conn()
    cur  = conn.cursor(dictionary=True, buffered=True)

    # All orders with service info
    cur.execute("""SELECT o.*, s.name AS service_name
                   FROM orders o LEFT JOIN services s ON o.service_id=s.id
                   WHERE o.user_id=%s ORDER BY o.order_date DESC""", (session['id'],))
    orders = cur.fetchall()

    # Active services for order form
    cur.execute("SELECT * FROM services WHERE is_active=1")
    services = cur.fetchall()

    # Notifications
    notif_count = unread_notifications(session['id'])
    cur.execute("SELECT * FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT 15", (session['id'],))
    notifications = cur.fetchall()

    # Stats
    total_spent   = to_float(sum(o['amount'] for o in orders))
    total_orders  = len(orders)
    pending_count = sum(1 for o in orders if o['status'] == 'Pending')
    delivered_count = sum(1 for o in orders if o['status'] == 'Delivered')
    active_count  = sum(1 for o in orders if o['status'] not in ('Delivered','Cancelled'))

    # Most used service
    from collections import Counter
    svc_counts = Counter(o['service_type'] for o in orders if o['service_type'])
    fav_service = svc_counts.most_common(1)[0][0] if svc_counts else 'None'

    # Monthly spend (last 6 months)
    cur.execute("""SELECT DATE_FORMAT(MIN(order_date),'%b') AS month,
                          DATE_FORMAT(order_date,'%Y-%m') AS month_key,
                          SUM(amount) AS total
                   FROM orders WHERE user_id=%s
                     AND order_date >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
                   GROUP BY DATE_FORMAT(order_date,'%Y-%m')
                   ORDER BY month_key""", (session['id'],))
    monthly_spend = cur.fetchall()

    # Recent (last 3 active) orders
    active_orders = [o for o in orders if o['status'] not in ('Delivered','Cancelled')][:3]

    # User profile
    cur.execute("SELECT * FROM users WHERE id=%s", (session['id'],))
    user_profile = cur.fetchone()

    settings = get_settings()
    conn.close()
    return render_template('user_dashboard.html',
                           orders=orders, services=services,
                           notif_count=notif_count, notifications=notifications,
                           total_spent=total_spent, total_orders=total_orders,
                           pending_count=pending_count, delivered_count=delivered_count,
                           active_count=active_count, fav_service=fav_service,
                           monthly_spend=json.dumps([{"month":m["month"],"total":to_float(m["total"])} for m in monthly_spend]),
                           active_orders=active_orders, user_profile=user_profile,
                           settings=settings)

@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    full_name = request.form.get('full_name','').strip()
    phone     = request.form.get('phone','').strip()
    address   = request.form.get('address','').strip()
    email     = request.form.get('email','').strip()
    conn = db_conn()
    cur  = conn.cursor()
    cur.execute("UPDATE users SET full_name=%s, phone=%s, address=%s, email=%s WHERE id=%s",
                (full_name, phone, address, email, session['id']))
    conn.commit()
    conn.close()
    session['full_name'] = full_name or session['full_name']
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('user_dashboard'))

@app.route('/upi_qr')
@login_required
def upi_qr():
    amount  = request.args.get('amount', '0')
    note    = request.args.get('note', 'LaundryPro Payment')
    settings = get_settings()
    return render_template('upi_qr.html', amount=amount, note=note, settings=settings)

@app.route('/cancel_order/<int:order_id>', methods=['POST'])
@login_required
def cancel_order(order_id):
    conn = db_conn()
    cur  = conn.cursor(dictionary=True, buffered=True)
    # Fetch order — make sure it belongs to this user
    cur.execute("SELECT * FROM orders WHERE id=%s AND user_id=%s", (order_id, session['id']))
    order = cur.fetchone()
    if not order:
        flash('Order not found.', 'danger')
        conn.close()
        return redirect(url_for('user_dashboard'))
    # Only allow cancel if not Delivered or already Cancelled
    if order['status'] in ('Delivered', 'Cancelled'):
        flash(f'Order #{order_id} cannot be cancelled (status: {order["status"]}).', 'warning')
        conn.close()
        return redirect(url_for('user_dashboard'))
    # Cancel the order — set payment_status to Cancelled if still Pending
    if order['payment_status'] == 'Pending':
        cur.execute(
            "UPDATE orders SET status='Cancelled', payment_status='Cancelled' WHERE id=%s AND user_id=%s",
            (order_id, session['id'])
        )
    else:
        cur.execute(
            "UPDATE orders SET status='Cancelled' WHERE id=%s AND user_id=%s",
            (order_id, session['id'])
        )
    # Notify admin
    cur.execute(
        "INSERT INTO notifications (user_id, message) SELECT id, %s FROM users WHERE role='admin' LIMIT 1",
        (f"Order #{order_id} cancelled by {session['full_name']}",)
    )
    conn.commit()
    conn.close()
    flash(f'Order #{order_id} has been cancelled successfully.', 'success')
    return redirect(url_for('user_dashboard'))

@app.route('/place_order', methods=['POST'])
@login_required
def place_order():
    service_id     = request.form.get('service_id')
    cloth_type     = request.form.get('cloth_type', '')
    weight         = float(request.form.get('weight', 1))
    payment_method = request.form.get('payment_method', 'Cash')
    notes          = request.form.get('notes', '')
    pickup_date    = request.form.get('pickup_date')
    conn = db_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM services WHERE id=%s", (service_id,))
    svc = cur.fetchone()
    amount = round(float(svc['price']) * float(weight), 2) if svc else 0
    cur2 = conn.cursor()
    cur2.execute(
        "INSERT INTO orders (user_id, service_id, service_type, cloth_type, weight_kg, amount, payment_method, notes, pickup_date) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (session['id'], service_id, svc['name'], cloth_type, weight, amount, payment_method, notes, pickup_date or None)
    )
    order_id = cur2.lastrowid
    # Notify admin
    cur2.execute(
        "INSERT INTO notifications (user_id, message) SELECT id, %s FROM users WHERE role='admin' LIMIT 1",
        (f"New order #{order_id} from {session['full_name']} - {svc['name']}",)
    )
    conn.commit()
    conn.close()
    flash(f'Order #{order_id} placed successfully!', 'success')
    if payment_method == 'UPI':
        return redirect(url_for('payment_page', order_id=order_id, amount=amount))
    return redirect(url_for('user_dashboard'))

@app.route('/payment/<int:order_id>')
@login_required
def payment_page(order_id):
    amount = request.args.get('amount', 0)
    settings = get_settings()
    return render_template('payment.html', order_id=order_id, amount=amount, settings=settings)

@app.route('/confirm_payment/<int:order_id>', methods=['POST'])
@login_required
def confirm_payment(order_id):
    conn = db_conn()
    cur  = conn.cursor()
    cur.execute("UPDATE orders SET payment_status='Paid' WHERE id=%s AND user_id=%s", (order_id, session['id']))
    conn.commit()
    conn.close()
    flash('Payment confirmed!', 'success')
    return redirect(url_for('user_dashboard'))

@app.route('/notifications/read', methods=['POST'])
@login_required
def mark_notifications_read():
    conn = db_conn()
    cur  = conn.cursor()
    cur.execute("UPDATE notifications SET is_read=1 WHERE user_id=%s", (session['id'],))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/admin/notifications/read_all', methods=['POST'])
@login_required
@admin_required
def admin_mark_all_read():
    conn = db_conn()
    cur  = conn.cursor(buffered=True)
    # Mark all notifications for admin user as read
    cur.execute("UPDATE notifications SET is_read=1 WHERE user_id=(SELECT id FROM users WHERE role='admin' LIMIT 1)")
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

# ─── ADMIN DASHBOARD ──────────────────────────────────────────
@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    conn = db_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT o.*, u.username, u.full_name FROM orders o JOIN users u ON o.user_id=u.id ORDER BY o.order_date DESC")
    orders = cur.fetchall()
    cur.execute("SELECT COUNT(*) AS cnt FROM orders WHERE status='Pending'")
    pending_count = cur.fetchone()['cnt']
    cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE role='user'")
    user_count = cur.fetchone()['cnt']
    cur.execute("SELECT SUM(amount) AS total FROM orders WHERE payment_status='Paid' AND MONTH(order_date)=MONTH(NOW())")
    monthly_revenue = to_float(cur.fetchone()['total'])
    cur.execute("SELECT COUNT(*) AS cnt FROM orders WHERE DATE(order_date)=CURDATE()")
    today_orders = cur.fetchone()['cnt']
    notif_count = unread_notifications(session['id'])
    cur.execute("SELECT n.*, u.username FROM notifications n JOIN users u ON n.user_id=u.id WHERE n.user_id=(SELECT id FROM users WHERE role='admin' LIMIT 1) ORDER BY n.created_at DESC LIMIT 15")
    notifications = cur.fetchall()
    conn.close()
    return render_template('admin_dashboard.html', orders=orders,
                           pending_count=pending_count, user_count=user_count,
                           monthly_revenue=monthly_revenue, today_orders=today_orders,
                           notif_count=notif_count, notifications=notifications)

@app.route('/admin/update_order', methods=['POST'])
@login_required
@admin_required
def update_order():
    order_id       = request.form.get('order_id')
    status         = request.form.get('status')
    payment_status = request.form.get('payment_status', '').strip()  # from admin modal
    pickup_date    = request.form.get('pickup_date') or None
    delivery_date  = request.form.get('delivery_date') or None
    conn = db_conn()
    cur = conn.cursor(dictionary=True, buffered=True)

    # 1. Fetch current order
    cur.execute("SELECT user_id, amount, payment_status AS cur_pay FROM orders WHERE id=%s", (order_id,))
    order = cur.fetchone()

    # 2. Determine final payment_status
    # Admin can override via modal; if not sent, auto-set based on status
    if payment_status in ('Pending', 'Paid', 'Cancelled'):
        final_pay = payment_status
    elif status == 'Delivered':
        final_pay = 'Paid'
    elif status == 'Cancelled':
        final_pay = 'Cancelled'
    else:
        final_pay = order['cur_pay'] if order else 'Pending'

    # 3. Update order
    cur.execute(
        "UPDATE orders SET status=%s, pickup_date=%s, delivery_date=%s, payment_status=%s WHERE id=%s",
        (status, pickup_date, delivery_date, final_pay, order_id)
    )

    if order:
        # 4. Notify customer
        if status == 'Delivered':
            msg = f"Your order #{order_id} has been DELIVERED and marked as Paid. Thank you!"
        elif status == 'Cancelled':
            msg = f"Your order #{order_id} has been cancelled by admin."
        else:
            msg = f"Your order #{order_id} status updated to: {status}"
        cur.execute(
            "INSERT INTO notifications (user_id, message) VALUES (%s, %s)",
            (order['user_id'], msg)
        )
        # 5. Auto-log credit when delivered and payment is Paid
        if status == 'Delivered' and final_pay == 'Paid':
            cur.execute(
                "INSERT INTO expenses (type, category, amount, description, entry_date) "
                "VALUES ('credit', 'Order Payment', %s, %s, CURDATE())",
                (float(order['amount']), f"Order #{order_id} delivered - payment received")
            )

    conn.commit()
    conn.close()
    flash(f'Order #{order_id} updated to {status}.', 'success')
    return redirect(url_for('admin_dashboard'))

# ─── ADMIN USERS ──────────────────────────────────────────────
@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    conn = db_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users ORDER BY created_at DESC")
    users = cur.fetchall()
    notif_count = unread_notifications(session['id'])
    conn.close()
    return render_template('admin_users.html', users=users, notif_count=notif_count)

@app.route('/admin/users/update', methods=['POST'])
@login_required
@admin_required
def update_user():
    uid      = request.form.get('user_id')
    role     = request.form.get('role')
    status   = request.form.get('status')
    password = request.form.get('password', '').strip()
    conn = db_conn()
    cur  = conn.cursor()
    if password:
        cur.execute("UPDATE users SET role=%s, status=%s, password=%s WHERE id=%s", (role, status, password, uid))
    else:
        cur.execute("UPDATE users SET role=%s, status=%s WHERE id=%s", (role, status, uid))
    conn.commit()
    conn.close()
    flash('User updated successfully.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/delete/<int:uid>', methods=['POST'])
@login_required
@admin_required
def delete_user(uid):
    if uid == session['id']:
        flash("You can't delete yourself.", 'danger')
        return redirect(url_for('admin_users'))
    conn = db_conn()
    cur  = conn.cursor(buffered=True)
    # Delete child records first to satisfy FK constraints
    cur.execute("DELETE FROM notifications WHERE user_id=%s", (uid,))
    cur.execute("DELETE FROM orders WHERE user_id=%s", (uid,))
    cur.execute("DELETE FROM users WHERE id=%s", (uid,))
    conn.commit()
    conn.close()
    flash('User and all related records deleted.', 'success')
    return redirect(url_for('admin_users'))

# ─── ADMIN EXPENSES ───────────────────────────────────────────
@app.route('/admin/expenses')
@login_required
@admin_required
def admin_expenses():
    conn = db_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM expenses ORDER BY entry_date DESC")
    expenses = cur.fetchall()
    cur.execute("SELECT SUM(amount) AS total FROM expenses WHERE type='credit'")
    total_credit = to_float(cur.fetchone()['total'])
    cur.execute("SELECT SUM(amount) AS total FROM expenses WHERE type='debit'")
    total_debit  = to_float(cur.fetchone()['total'])
    notif_count = unread_notifications(session['id'])
    conn.close()
    return render_template('admin_expenses.html', expenses=expenses,
                           total_credit=total_credit, total_debit=total_debit,
                           balance=round(total_credit - total_debit, 2),
                           notif_count=notif_count)

@app.route('/admin/expenses/add', methods=['POST'])
@login_required
@admin_required
def add_expense():
    etype       = request.form.get('type')
    category    = request.form.get('category')
    amount      = float(request.form.get('amount', 0))
    description = request.form.get('description', '')
    entry_date  = request.form.get('entry_date') or date.today().isoformat()
    conn = db_conn()
    cur  = conn.cursor()
    cur.execute("INSERT INTO expenses (type, category, amount, description, entry_date) VALUES (%s,%s,%s,%s,%s)",
                (etype, category, amount, description, entry_date))
    conn.commit()
    conn.close()
    flash('Expense entry added.', 'success')
    return redirect(url_for('admin_expenses'))

@app.route('/admin/expenses/delete/<int:eid>', methods=['POST'])
@login_required
@admin_required
def delete_expense(eid):
    conn = db_conn()
    cur  = conn.cursor()
    cur.execute("DELETE FROM expenses WHERE id=%s", (eid,))
    conn.commit()
    conn.close()
    flash('Entry deleted.', 'success')
    return redirect(url_for('admin_expenses'))

# ─── ADMIN REPORTS ────────────────────────────────────────────
@app.route('/admin/reports')
@login_required
@admin_required
def admin_reports():
    conn = db_conn()
    cur  = conn.cursor(dictionary=True)
    # Monthly revenue last 6 months — fully aggregated, no non-grouped cols
    cur.execute("""
        SELECT
            DATE_FORMAT(MIN(order_date), '%b %Y') AS month,
            DATE_FORMAT(order_date, '%Y-%m')      AS month_key,
            SUM(amount)                           AS revenue,
            COUNT(*)                              AS orders
        FROM orders
        WHERE order_date >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(order_date, '%Y-%m')
        ORDER BY month_key
    """)
    monthly = cur.fetchall()
    # Daily last 14 days — DATE() is deterministic so safe to group by
    cur.execute("""
        SELECT
            DATE(order_date)  AS day,
            SUM(amount)       AS revenue,
            COUNT(*)          AS orders
        FROM orders
        WHERE order_date >= DATE_SUB(NOW(), INTERVAL 14 DAY)
        GROUP BY DATE(order_date)
        ORDER BY DATE(order_date)
    """)
    daily = cur.fetchall()
    # Service breakdown
    cur.execute("""
        SELECT service_type, COUNT(*) AS cnt, SUM(amount) AS total
        FROM orders
        GROUP BY service_type
        ORDER BY SUM(amount) DESC
    """)
    service_stats = cur.fetchall()
    # Payment stats
    cur.execute("""
        SELECT payment_method, COUNT(*) AS cnt, SUM(amount) AS total
        FROM orders
        GROUP BY payment_method
    """)
    payment_stats = cur.fetchall()
    # Status summary
    cur.execute("SELECT status, COUNT(*) AS cnt FROM orders GROUP BY status")
    status_stats = cur.fetchall()
    notif_count = unread_notifications(session['id'])
    conn.close()
    # Convert Decimal -> float for JSON serialization
    def safe_row(row):
        return {k: float(v) if isinstance(v, Decimal) else (str(v) if hasattr(v, 'strftime') else v) for k, v in row.items()}

    return render_template('admin_reports.html',
                           monthly=json.dumps([{**safe_row(m), 'revenue': to_float(m['revenue'])} for m in monthly]),
                           daily=json.dumps([{**safe_row(d), 'revenue': to_float(d['revenue']), 'day': str(d['day'])} for d in daily]),
                           service_stats=[{**r, 'total': to_float(r['total'])} for r in service_stats],
                           payment_stats=json.dumps([{**safe_row(p), 'total': to_float(p['total'])} for p in payment_stats]),
                           status_stats=json.dumps([dict(s) for s in status_stats]),
                           notif_count=notif_count)

# ─── ADMIN SETTINGS ───────────────────────────────────────────
@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_settings():
    if request.method == 'POST':
        shop_name    = request.form.get('shop_name')
        working_days = ','.join(request.form.getlist('working_days'))
        opening_time = request.form.get('opening_time')
        closing_time = request.form.get('closing_time')
        upi_id       = request.form.get('upi_id')
        conn = db_conn()
        cur  = conn.cursor()
        cur.execute("UPDATE settings SET shop_name=%s, working_days=%s, opening_time=%s, closing_time=%s, upi_id=%s WHERE id=1",
                    (shop_name, working_days, opening_time, closing_time, upi_id))
        conn.commit()
        conn.close()
        flash('Settings saved.', 'success')
        return redirect(url_for('admin_settings'))
    settings = get_settings()
    notif_count = unread_notifications(session['id'])
    # Services
    conn = db_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM services ORDER BY id")
    services = cur.fetchall()
    conn.close()
    return render_template('admin_settings.html', settings=settings, services=services, notif_count=notif_count)

@app.route('/admin/services/save', methods=['POST'])
@login_required
@admin_required
def save_service():
    sid   = request.form.get('service_id')
    name  = request.form.get('name')
    price = float(request.form.get('price', 0))
    unit  = request.form.get('unit')
    desc  = request.form.get('description', '')
    active = 1 if request.form.get('is_active') else 0
    conn = db_conn()
    cur  = conn.cursor()
    if sid:
        cur.execute("UPDATE services SET name=%s, price=%s, unit=%s, description=%s, is_active=%s WHERE id=%s",
                    (name, price, unit, desc, active, sid))
    else:
        cur.execute("INSERT INTO services (name, price, unit, description, is_active) VALUES (%s,%s,%s,%s,%s)",
                    (name, price, unit, desc, active))
    conn.commit()
    conn.close()
    flash('Service saved.', 'success')
    return redirect(url_for('admin_settings'))

# ─── API ──────────────────────────────────────────────────────
@app.route('/api/notifications')
@login_required
def api_notifications():
    count = unread_notifications(session['id'])
    return jsonify({'count': count})

if __name__ == '__main__':
    # host='0.0.0.0' makes the server accessible on all network interfaces
    # so any device on the same LAN can reach it via http://<your-ip>:5000
    app.run(host='0.0.0.0', port=5000, debug=True)