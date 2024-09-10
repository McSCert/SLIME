from flask import Flask, request

app = Flask(__name__)

HOST = '0.0.0.0'
PORT = 9000

session = {
    'balance': 0,
    'amount': 0,
    'pending_order': False
}

def place_deposit(session):
    # session['pending_deposit'] = True
    return 'DEPOSIT_PENDING'

def deposit_balance(session):
    session['balance'] += session['amount']
    session['amount'] = 0
    return 'DEPOSIT_OK'

def place_order(session):
    session['pending_order'] = True
    return 'ORDER_PENDING'

def confirm_order(session):
    session['pending_order'] = False
    session['balance'] -= session['amount']
    return 'ORDER_CONFIRMED'

def handle_client_request(data):
    if data.startswith('DEPOSIT:'):
        if session['pending_order']:
            return 'INVALID_REQUEST'
        session['amount'] = int(data.split(':')[1])
        return place_deposit(session)
    elif data.startswith('CONFIRM_DEPOSIT'):
        return deposit_balance(session)
    elif data.startswith('PLACE_ORDER:'):
        if session['pending_order']:
            return 'INVALID_REQUEST'
        session['amount'] = int(data.split(':')[1])
        if session['balance'] - session['amount'] >= 0:
            session['pending_order'] = True
            return place_order(session)
        else:
            return 'INSUFFICIENT_FUNDS'
    elif data.startswith('CONFIRM_ORDER'):
            if session['pending_order']:
                return confirm_order(session)
            else:
                return 'NO_PENDING_ORDER'
    return 'INVALID_REQUEST'

@app.route('/', methods=['POST'])
def listen():
    data = request.data.decode('utf-8')
    response = handle_client_request(data)
    return response

if __name__ == '__main__':
    print(f'Server running on {HOST}:{PORT}...')
    app.run(host=HOST, port=PORT)
