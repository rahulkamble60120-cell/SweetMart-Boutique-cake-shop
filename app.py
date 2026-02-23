import os
import urllib.parse
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --- CONFIGURATION ---
app.secret_key = "rahul_cake_shop_secret"
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:root@localhost:8889/cake_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Image Upload Configuration
UPLOAD_FOLDER = 'static/images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db = SQLAlchemy(app)

# --- MODELS ---
class User(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    address = db.Column(db.Text) 

class Cake(db.Model):
    __tablename__ = 'cakes'
    cake_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    discount_price = db.Column(db.Float, default=0.0) 
    image_file = db.Column(db.String(255))
    description = db.Column(db.Text) 
    category = db.Column(db.String(50), default='General')
    is_active = db.Column(db.Boolean, default=True)

class Order(db.Model):
    __tablename__ = 'orders'
    order_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    cake_id = db.Column(db.Integer, db.ForeignKey('cakes.cake_id')) 
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(500), default='Pending')
    payment_method = db.Column(db.String(100), nullable=False)
    cake_size = db.Column(db.String(50))
    cake_shape = db.Column(db.String(50))
    cake_message = db.Column(db.String(255))
    delivery_date = db.Column(db.String(50)) 
    order_date = db.Column(db.DateTime, default=datetime.utcnow)

# --- CONTEXT PROCESSOR ---
@app.context_processor
def inject_user():
    user = None
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
    return dict(user=user, datetime=datetime)

# --- CUSTOMER ROUTES ---

@app.route('/')
def home():
    search_query = request.args.get('search', '').strip()
    cat_filter = request.args.get('category', '').strip()
    query = Cake.query.filter_by(is_active=True)
    if search_query: query = query.filter(Cake.name.contains(search_query))
    if cat_filter: query = query.filter_by(category=cat_filter)
    cakes = query.all()
    categories = ["Premium Cakes", "Chocolate Delight", "Fruit Special", "Wedding Collection"]
    return render_template('index.html', cakes=cakes, categories=categories)

@app.route('/cake/<int:cake_id>')
def cake_details(cake_id):
    cake = db.session.get(Cake, cake_id)
    if not cake or not cake.is_active:
        return "Cake not found or no longer available", 404
    return render_template('cake_details.html', cake=cake)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email, password = request.form.get('email', '').strip().lower(), request.form.get('password')
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session.clear()
            session.update({'user_id': user.user_id, 'user_name': user.name, 'user_email': user.email.lower(), 'wishlist': [], 'cart': []})
            if user.email.lower() == 'rahulkamble0522@gmail.com':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('home'))
        flash("Invalid Credentials", "danger")
    return render_template('login.html')

# NEW: Register Route added to fix BuildError
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone')
        password = request.form.get('password')
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash("Email already registered!", "danger")
            return redirect(url_for('register'))
            
        new_user = User(name=name, email=email, phone=phone, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash("Registration successful! Please login.", "success")
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/profile')
def profile():
    if 'user_id' not in session: return redirect(url_for('login'))
    user_orders = db.session.query(Order, Cake).join(Cake, Order.cake_id == Cake.cake_id)\
        .filter(Order.user_id == session['user_id'])\
        .order_by(Order.order_date.desc()).all()
    return render_template('profile.html', orders=user_orders)

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = db.session.get(User, session['user_id'])
    if user:
        user.phone = request.form.get('phone')
        user.address = request.form.get('address')
        db.session.commit()
        flash("Profile updated! ✨", "success")
    return redirect(url_for('profile'))

@app.route('/toggle_wishlist/<int:cake_id>', methods=['POST'])
def toggle_wishlist(cake_id):
    if 'user_id' not in session: return jsonify({'error': 'Login required'}), 401
    wishlist = list(session.get('wishlist', []))
    if cake_id in wishlist:
        wishlist.remove(cake_id)
        action = 'removed'
    else:
        wishlist.append(cake_id)
        action = 'added'
    session['wishlist'] = wishlist
    session.modified = True
    return jsonify({'action': action, 'wish_count': len(wishlist)})

@app.route('/wishlist')
def wishlist():
    if 'user_id' not in session: return redirect(url_for('login'))
    wishlist_ids = session.get('wishlist', [])
    cakes = Cake.query.filter(Cake.cake_id.in_(wishlist_ids), Cake.is_active == True).all() if wishlist_ids else []
    return render_template('wishlist.html', cakes=cakes)

@app.route('/add_to_cart/<int:cake_id>', methods=['POST'])
def add_to_cart(cake_id):
    if 'user_id' not in session: return jsonify({'error': 'Login required'}), 401
    cart = session.get('cart', [])
    cart.append(cake_id)
    session['cart'] = cart
    session.modified = True 
    return jsonify({'cart_count': len(session['cart'])})

@app.route('/remove_from_cart/<int:cake_id>', methods=['POST'])
def remove_from_cart(cake_id):
    cart = session.get('cart', [])
    if cake_id in cart:
        cart.remove(cake_id)
        session['cart'] = cart
        session.modified = True
    return redirect(url_for('cart'))

@app.route('/cart')
def cart():
    if 'user_id' not in session: return redirect(url_for('login'))
    cart_ids = session.get('cart', [])
    items = [db.session.get(Cake, cid) for cid in cart_ids if db.session.get(Cake, cid) and db.session.get(Cake, cid).is_active]
    total = sum(item.discount_price if item.discount_price > 0 else item.price for item in items)
    return render_template('cart.html', items=items, total=total)

@app.route('/checkout')
def checkout():
    if 'user_id' not in session: return redirect(url_for('login'))
    cart_ids = session.get('cart', [])
    items = [db.session.get(Cake, cid) for cid in cart_ids if db.session.get(Cake, cid) and db.session.get(Cake, cid).is_active]
    if not items: return redirect(url_for('home'))
    subtotal = sum(item.discount_price if item.discount_price > 0 else item.price for item in items)
    total = subtotal + 20 
    return render_template('checkout.html', items=items, total=total)

@app.route('/place_order', methods=['POST'])
def place_order():
    if 'user_id' not in session: return redirect(url_for('login'))
    cart_ids = session.get('cart', [])
    try:
        new_order = Order(
            user_id=session['user_id'], cake_id=cart_ids[0], 
            total_amount=float(request.form.get('final_amount')),
            status=f"Pending | Address: {request.form.get('address')}", 
            payment_method=request.form.get('payment_method'),
            cake_size=request.form.get('cake_size'), cake_shape=request.form.get('cake_shape'),
            cake_message=request.form.get('cake_message'), delivery_date=request.form.get('delivery_date')
        )
        db.session.add(new_order)
        db.session.commit()

        session['cart'] = []
        session.modified = True
        return redirect(url_for('order_success', order_id=new_order.order_id))
    except Exception:
        db.session.rollback()
        return redirect(url_for('home'))

@app.route('/order_success/<int:order_id>')
def order_success(order_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    order = db.session.get(Order, order_id)
    if not order: return redirect(url_for('home'))
    return render_template('thank_you.html', order=order)

# --- ADMIN ROUTES ---

@app.route('/admin/')
def admin_dashboard():
    if session.get('user_email') != 'rahulkamble0522@gmail.com': return redirect(url_for('login'))
    live_cake_count = Cake.query.filter_by(is_active=True).count()
    stats = {
        'orders': Order.query.count(),
        'revenue': db.session.query(func.sum(Order.total_amount)).scalar() or 0,
        'customers': User.query.filter(User.email != 'rahulkamble0522@gmail.com').count(),
        'pending': Order.query.filter(Order.status.contains('Pending')).count(),
        'live_cakes': live_cake_count
    }
    orders_with_users = db.session.query(Order, User).join(User, Order.user_id == User.user_id).order_by(Order.order_date.desc()).all()
    categories = ["Premium Cakes", "Chocolate Delight", "Fruit Special", "Wedding Collection"]
    return render_template('admin_dashboard.html', stats=stats, orders=orders_with_users, all_cakes=Cake.query.all(), categories=categories)

@app.route('/admin/add_cake', methods=['POST'])
def add_cake():
    if session.get('user_email') != 'rahulkamble0522@gmail.com': return redirect(url_for('login'))
    file = request.files.get('cake_image')
    filename = secure_filename(file.filename) if file else 'default_cake.jpg'
    if file: file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    new_cake = Cake(
        name=request.form.get('name'), 
        price=float(request.form.get('price')),
        discount_price=float(request.form.get('discount_price') or 0), 
        description=request.form.get('description'), 
        image_file='images/' + filename,
        category=request.form.get('category')
    )
    db.session.add(new_cake)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/update_order/<int:order_id>', methods=['POST'])
def update_order(order_id):
    if session.get('user_email') != 'rahulkamble0522@gmail.com': return redirect(url_for('login'))
    order = db.session.get(Order, order_id)
    user = db.session.get(User, order.user_id) if order else None
    
    if order and user:
        new_status = request.form.get('status')
        address_part = order.status.split('|')[1] if '|' in order.status else "Address: N/A"
        order.status = f"{new_status} | {address_part.strip()}"
        db.session.commit()

        hour = datetime.now().hour
        greeting = "Good Morning" if hour < 12 else "Good Afternoon" if hour < 17 else "Good Evening"
        msg = (
            f"{greeting} {user.name}! 🎂\n\n"
            f"Your SweetMart order *#{order.order_id}* has been updated to: *{new_status}*.\n\n"
            f"📦 Spec: {order.cake_size} Cake\n"
            f"✨ Msg: {order.cake_message}\n\n"
            f"Thank you for choosing us! ❤️"
        )
        encoded_msg = urllib.parse.quote(msg)
        phone = ''.join(filter(str.isdigit, user.phone))
        if not phone.startswith('91'): phone = '91' + phone
        whatsapp_url = f"https://wa.me/{phone}?text={encoded_msg}"
        return redirect(whatsapp_url)
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_cake/<int:cake_id>', methods=['POST'])
def delete_cake(cake_id):
    if session.get('user_email') != 'rahulkamble0522@gmail.com': return redirect(url_for('login'))
    cake = db.session.get(Cake, cake_id)
    if cake:
        has_orders = Order.query.filter_by(cake_id=cake_id).first()
        if has_orders: cake.is_active = False 
        else:
            if cake.image_file and 'default' not in cake.image_file:
                path = os.path.join('static', cake.image_file)
                if os.path.exists(path): os.remove(path)
            db.session.delete(cake)
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)