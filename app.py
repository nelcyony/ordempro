from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload, selectinload
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'troque-esta-chave-antes-de-publicar')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'ordempro.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), default='admin')

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    document = db.Column(db.String(30))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(160))
    address = db.Column(db.String(240))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Technician(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    phone = db.Column(db.String(30))
    email = db.Column(db.String(160))
    active = db.Column(db.Boolean, default=True)

class ServiceOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(24), unique=True, nullable=False)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), default='Normal')
    status = db.Column(db.String(30), default='Aberta')
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    technician_id = db.Column(db.Integer, db.ForeignKey('technician.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    due_date = db.Column(db.Date)
    resolution = db.Column(db.Text)
    client = db.relationship('Client', backref='orders')
    technician = db.relationship('Technician', backref='orders')

class FinancialRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('service_order.id'), unique=True, nullable=False)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    order = db.relationship('ServiceOrder', backref=db.backref('financial', uselist=False))

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('service_order.id'), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    paid_at = db.Column(db.Date, nullable=False, default=lambda: datetime.utcnow().date())
    method = db.Column(db.String(30), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    order = db.relationship('ServiceOrder', backref=db.backref('payments', lazy=True))

class OrderHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('service_order.id'), nullable=False)
    event = db.Column(db.String(240), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    order = db.relationship('ServiceOrder', backref='history')

PAYMENT_METHODS = ['Pix', 'Dinheiro', 'Cartão de crédito', 'Cartão de débito', 'Transferência', 'Outro']


def parse_money(value):
    raw_value = (value or '').strip()
    if not raw_value:
        return None
    if ',' in raw_value:
        raw_value = raw_value.replace('.', '').replace(',', '.')
    try:
        amount = Decimal(raw_value)
        if not amount.is_finite() or amount < 0 or amount > Decimal('9999999999.99'):
            raise ValueError
        rounded = amount.quantize(Decimal('0.01'))
        if amount != rounded:
            raise ValueError
        return rounded
    except (InvalidOperation, ValueError):
        raise ValueError('Informe um valor válido, não negativo e com no máximo duas casas decimais.')


def financial_summary(order):
    paid = sum((payment.amount for payment in order.payments), Decimal('0.00'))
    record = order.financial
    if record is None:
        return {'total': None, 'paid': paid, 'balance': None, 'status': 'Sem orçamento'}
    total = record.total_amount
    if total == 0:
        status = 'Sem cobrança'
    elif paid >= total:
        status = 'Pago'
    elif paid > 0:
        status = 'Parcial'
    else:
        status = 'Pendente'
    return {'total': total, 'paid': paid, 'balance': max(total - paid, Decimal('0.00')), 'status': status}


@app.template_filter('brl')
def format_brl(value):
    if value is None:
        return '—'
    return 'R$ ' + format(value, ',.2f').replace(',', 'X').replace('.', ',').replace('X', '.')


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper

@app.context_processor
def inject_globals():
    return {'current_user_name': session.get('user_name')}

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email', '').strip().lower()).first()
        if user and check_password_hash(user.password_hash, request.form.get('password', '')):
            session['user_id'] = user.id
            session['user_name'] = user.name
            return redirect(url_for('dashboard'))
        flash('E-mail ou senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    total = ServiceOrder.query.count()
    open_count = ServiceOrder.query.filter(ServiceOrder.status == 'Aberta').count()
    progress = ServiceOrder.query.filter(ServiceOrder.status == 'Em andamento').count()
    completed = ServiceOrder.query.filter(ServiceOrder.status == 'Concluída').count()
    overdue = overdue_orders_query().count()
    recent = ServiceOrder.query.order_by(ServiceOrder.created_at.desc()).limit(4).all()

    labels = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
    week_values = []
    today = datetime.utcnow().date()
    monday = today - timedelta(days=today.weekday())
    for i in range(7):
        day = monday + timedelta(days=i)
        start = datetime.combine(day, datetime.min.time())
        end = start + timedelta(days=1)
        week_values.append(ServiceOrder.query.filter(
            ServiceOrder.created_at >= start,
            ServiceOrder.created_at < end
        ).count())
    return render_template(
        'dashboard.html',
        total=total,
        open_count=open_count,
        progress=progress,
        completed=completed,
        overdue=overdue,
        recent=recent,
        week_labels=labels,
        week_values=week_values
    )


def overdue_orders_query():
    return ServiceOrder.query.filter(or_(
        ServiceOrder.status == 'Atrasada',
        and_(
            ServiceOrder.status.notin_(['Concluída', 'Cancelada']),
            ServiceOrder.due_date.isnot(None),
            ServiceOrder.due_date < datetime.utcnow().date()
        )
    ))


@app.route('/agenda')
@login_required
def agenda():
    requested_week = request.args.get('semana')
    if requested_week:
        try:
            selected_day = datetime.strptime(requested_week, '%Y-%m-%d').date()
        except ValueError:
            abort(400)
    else:
        selected_day = datetime.utcnow().date()

    week_start = selected_day - timedelta(days=selected_day.weekday())
    week_end = week_start + timedelta(days=7)
    scheduled_orders = ServiceOrder.query.filter(
        ServiceOrder.due_date >= week_start,
        ServiceOrder.due_date < week_end,
        ServiceOrder.status != 'Cancelada'
    ).order_by(ServiceOrder.due_date, ServiceOrder.created_at).all()
    days = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        days.append({
            'date': day,
            'orders': [order for order in scheduled_orders if order.due_date == day]
        })
    unscheduled_orders = ServiceOrder.query.filter(
        ServiceOrder.due_date.is_(None),
        ServiceOrder.status != 'Cancelada'
    ).order_by(ServiceOrder.created_at.desc()).limit(10).all()

    return render_template(
        'agenda.html',
        days=days,
        unscheduled_orders=unscheduled_orders,
        week_start=week_start,
        week_end=week_end - timedelta(days=1),
        previous_week=week_start - timedelta(days=7),
        next_week=week_start + timedelta(days=7)
    )


@app.route('/financeiro')
@login_required
def finance():
    orders = ServiceOrder.query.options(
        joinedload(ServiceOrder.client),
        joinedload(ServiceOrder.financial),
        selectinload(ServiceOrder.payments)
    ).order_by(ServiceOrder.created_at.desc()).all()
    order_summaries = [
        {'order': order, **financial_summary(order)}
        for order in orders
    ]
    total_budgeted = sum(
        (item['total'] for item in order_summaries if item['total'] is not None),
        Decimal('0.00')
    )
    total_received = sum((item['paid'] for item in order_summaries), Decimal('0.00'))
    total_receivable = sum(
        (item['balance'] for item in order_summaries if item['balance'] is not None),
        Decimal('0.00')
    )
    recent_payments = Payment.query.options(
        joinedload(Payment.order).joinedload(ServiceOrder.client)
    ).order_by(Payment.paid_at.desc(), Payment.id.desc()).limit(10).all()
    return render_template(
        'finance.html',
        order_summaries=order_summaries,
        total_budgeted=total_budgeted,
        total_received=total_received,
        total_receivable=total_receivable,
        no_budget=sum(1 for item in order_summaries if item['total'] is None),
        recent_payments=recent_payments
    )


@app.route('/configuracoes', methods=['GET', 'POST'])
@login_required
def settings():
    user = User.query.get_or_404(session['user_id'])
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        new_password = request.form.get('new_password', '')
        current_password = request.form.get('current_password', '')

        if not name or not email:
            flash('Informe seu nome e e-mail.', 'warning')
        elif User.query.filter(User.email == email, User.id != user.id).first():
            flash('Este e-mail já está sendo usado por outra conta.', 'warning')
        elif new_password and not check_password_hash(user.password_hash, current_password):
            flash('Informe a senha atual correta para alterá-la.', 'warning')
        elif new_password and len(new_password) < 8:
            flash('A nova senha deve ter pelo menos 8 caracteres.', 'warning')
        else:
            user.name = name
            user.email = email
            if new_password:
                user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            session['user_name'] = user.name
            flash('Configurações da conta atualizadas.', 'success')
            return redirect(url_for('settings'))

    return render_template('settings.html', user=user)

@app.route('/clientes', methods=['GET', 'POST'])
@login_required
def clients():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Informe o nome do cliente.', 'warning')
        else:
            db.session.add(Client(name=name, document=request.form.get('document'), phone=request.form.get('phone'), email=request.form.get('email'), address=request.form.get('address')))
            db.session.commit(); flash('Cliente cadastrado com sucesso.', 'success')
            return redirect(url_for('clients'))
    q = request.args.get('q', '').strip()
    query = Client.query
    if q: query = query.filter(or_(Client.name.ilike(f'%{q}%'), Client.document.ilike(f'%{q}%'), Client.phone.ilike(f'%{q}%')))
    return render_template('clients.html', clients=query.order_by(Client.name).all(), q=q)

@app.route('/tecnicos', methods=['GET', 'POST'])
@login_required
def technicians():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name:
            db.session.add(Technician(name=name, phone=request.form.get('phone'), email=request.form.get('email')))
            db.session.commit(); flash('Técnico cadastrado.', 'success')
            return redirect(url_for('technicians'))
        flash('Informe o nome do técnico.', 'warning')
    return render_template('technicians.html', technicians=Technician.query.order_by(Technician.name).all())

@app.route('/ordens', methods=['GET', 'POST'])
@login_required
def orders():
    if request.method == 'POST':
        client_id = request.form.get('client_id', type=int)
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        try:
            total_amount = parse_money(request.form.get('total_amount'))
        except ValueError as error:
            flash(str(error), 'warning')
            total_amount = None
            price_invalid = True
        else:
            price_invalid = False
        if not price_invalid and (not client_id or not title or not description):
            flash('Preencha cliente, título e descrição.', 'warning')
        elif not price_invalid:
            order = ServiceOrder(code='OS-' + datetime.now().strftime('%y%m%d%H%M%S%f')[-10:], title=title, description=description,
                priority=request.form.get('priority', 'Normal'), client_id=client_id,
                technician_id=request.form.get('technician_id', type=int) or None,
                due_date=datetime.strptime(request.form['due_date'], '%Y-%m-%d').date() if request.form.get('due_date') else None)
            db.session.add(order); db.session.flush()
            db.session.add(OrderHistory(order_id=order.id, event='Ordem de serviço criada.'))
            if request.form.get('total_amount', '').strip():
                db.session.add(FinancialRecord(order_id=order.id, total_amount=total_amount))
            db.session.commit(); flash(f'Ordem {order.code} criada com sucesso.', 'success')
            return redirect(url_for('order_detail', order_id=order.id))
    q = request.args.get('q', '').strip(); status = request.args.get('status', '')
    query = ServiceOrder.query.join(Client)
    if q: query = query.filter(or_(ServiceOrder.code.ilike(f'%{q}%'), ServiceOrder.title.ilike(f'%{q}%'), Client.name.ilike(f'%{q}%')))
    if status: query = query.filter(ServiceOrder.status == status)
    return render_template('orders.html', orders=query.order_by(ServiceOrder.created_at.desc()).all(), clients=Client.query.order_by(Client.name).all(), technicians=Technician.query.filter_by(active=True).order_by(Technician.name).all(), q=q, selected_status=status)

@app.route('/ordens/<int:order_id>', methods=['GET', 'POST'])
@login_required
def order_detail(order_id):
    order = ServiceOrder.query.get_or_404(order_id)
    if request.method == 'POST':
        old_status = order.status
        new_status = request.form.get('status', order.status)
        if new_status not in ['Aberta', 'Em andamento', 'Aguardando cliente', 'Concluída', 'Atrasada', 'Cancelada']:
            abort(400)
        order.status = new_status
        order.technician_id = request.form.get('technician_id', type=int) or None
        order.resolution = request.form.get('resolution', '').strip()
        note = request.form.get('note', '').strip()
        if new_status != old_status: db.session.add(OrderHistory(order_id=order.id, event=f'Status alterado de {old_status} para {new_status}.'))
        if note: db.session.add(OrderHistory(order_id=order.id, event=note))
        db.session.commit(); flash('Ordem atualizada.', 'success')
        return redirect(url_for('order_detail', order_id=order.id))
    return render_template('order_detail.html', order=order, technicians=Technician.query.filter_by(active=True).order_by(Technician.name).all())


@app.route('/ordens/<int:order_id>/financeiro', methods=['GET', 'POST'])
@login_required
def order_finance(order_id):
    order = ServiceOrder.query.options(
        joinedload(ServiceOrder.financial),
        selectinload(ServiceOrder.payments),
        joinedload(ServiceOrder.client)
    ).get_or_404(order_id)
    today = datetime.now().date()

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'price':
            try:
                total_amount = parse_money(request.form.get('total_amount'))
            except ValueError as error:
                flash(str(error), 'warning')
            else:
                if total_amount is None:
                    flash('Informe o valor total do serviço.', 'warning')
                elif sum((payment.amount for payment in order.payments), Decimal('0.00')) > total_amount:
                    flash('O valor total não pode ser menor que os pagamentos já recebidos.', 'warning')
                else:
                    if order.financial is None:
                        db.session.add(FinancialRecord(order_id=order.id, total_amount=total_amount))
                    else:
                        order.financial.total_amount = total_amount
                    db.session.commit()
                    flash('Valor do serviço atualizado.', 'success')
                    return redirect(url_for('order_finance', order_id=order.id))
        elif action == 'payment':
            amount_raw = request.form.get('amount', '')
            try:
                amount = parse_money(amount_raw)
            except ValueError as error:
                flash(str(error), 'warning')
                amount = None

            payment_date_raw = request.form.get('paid_at', '')
            try:
                payment_date = datetime.strptime(payment_date_raw, '%Y-%m-%d').date()
            except ValueError:
                payment_date = None

            method = request.form.get('method', '')
            total_paid = sum((payment.amount for payment in order.payments), Decimal('0.00'))
            if amount is None:
                if not amount_raw.strip():
                    flash('Informe o valor do pagamento.', 'warning')
            elif amount <= 0:
                flash('O pagamento deve ser maior que zero.', 'warning')
            elif order.financial is None or order.financial.total_amount <= 0:
                flash('Defina um valor total maior que zero antes de registrar pagamentos.', 'warning')
            elif amount > order.financial.total_amount - total_paid:
                flash('O pagamento excede o saldo pendente da ordem.', 'warning')
            elif payment_date is None:
                flash('Informe uma data válida para o pagamento.', 'warning')
            elif payment_date > today:
                flash('A data do pagamento não pode estar no futuro.', 'warning')
            elif method not in PAYMENT_METHODS:
                flash('Selecione uma forma de pagamento válida.', 'warning')
            else:
                db.session.add(Payment(
                    order_id=order.id,
                    amount=amount,
                    paid_at=payment_date,
                    method=method
                ))
                db.session.commit()
                flash('Pagamento registrado.', 'success')
                return redirect(url_for('order_finance', order_id=order.id))
        else:
            abort(400)

    return render_template(
        'order_finance.html',
        order=order,
        summary=financial_summary(order),
        payment_methods=PAYMENT_METHODS,
        today=today.isoformat()
    )

@app.route('/relatorios')
@login_required
def reports():
    statuses = ['Aberta', 'Em andamento', 'Aguardando cliente', 'Concluída', 'Atrasada', 'Cancelada']
    counts = {s: ServiceOrder.query.filter_by(status=s).count() for s in statuses}
    return render_template('reports.html', counts=counts, total=sum(counts.values()), clients=Client.query.count(), technicians=Technician.query.count())

@app.route('/setup')
def setup():
    db.create_all()
    if not User.query.filter_by(email='admin@ordempro.local').first():
        db.session.add(User(name='Administrador', email='admin@ordempro.local', password_hash=generate_password_hash('Admin@123')))
        db.session.commit()
    return 'Banco inicializado. Acesse /login. Remova ou proteja esta rota antes de publicar o sistema.'

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
