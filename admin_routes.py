from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from sqlalchemy import func

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/')
def dashboard():
    # Local imports inside the function prevent "Circular Import" crashes
    from app import db, User, Cake, Order 
    
    # 1. Security Check
    user_email = session.get('user_email', '').strip().lower()
    if 'user_id' not in session or user_email != 'rahulkamble0522@gmail.com':
        flash("Unauthorized Access!")
        return redirect(url_for('home'))

    # 2. Fix the RuntimeError by using the app_context
    with current_app.app_context():
        stats = {
            'orders': db.session.query(Order).count(),
            'revenue': db.session.query(func.sum(Order.total_amount)).scalar() or 0,
            'customers': db.session.query(User).filter(User.email != 'rahulkamble0522@gmail.com').count(),
            'pending': db.session.query(Order).filter_by(status='Pending').count()
        }
        
        orders = db.session.query(Order).order_by(Order.order_date.desc()).all()
        cakes = db.session.query(Cake).all()
    
    return render_template('admin_dashboard.html', stats=stats, orders=orders, cakes=cakes)

@admin_bp.route('/update_order/<int:order_id>', methods=['POST'])
def update_order(order_id):
    from app import db, Order
    with current_app.app_context():
        order = db.session.get(Order, order_id)
        if order:
            order.status = request.form.get('status')
            db.session.commit()
    return redirect(url_for('admin.dashboard'))