from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy

# --- Basic Setup ---
app = Flask(__name__)
# Configure the database. SQLite is a simple file-based database, perfect for starting.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///alerts.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Database Model ---
# This class defines the table in our database that will store the alerts.
class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), nullable=False)
    ticker = db.Column(db.String(10), nullable=False)
    target_price = db.Column(db.Float, nullable=False)
    condition = db.Column(db.String(10), nullable=False) # 'above' or 'below'
    alert_sent = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<Alert for {self.phone_number}: {self.ticker} {self.condition} {self.target_price}>"

# --- API Endpoints ---
# This endpoint will be called by our frontend to create a new alert.
@app.route('/api/add_alert', methods=['POST'])
def add_alert():
    data = request.get_json()
    if not all(k in data for k in ['phone_number', 'ticker', 'target_price', 'condition']):
        return jsonify({'error': 'Missing data'}), 400

    new_alert = Alert(
        phone_number=data['phone_number'],
        ticker=f"{data['ticker'].upper()}.NS", # Automatically add .NS suffix
        target_price=float(data['target_price']),
        condition=data['condition']
    )
    db.session.add(new_alert)
    db.session.commit()
    return jsonify({'message': f"Alert for {new_alert.ticker} created successfully!"}), 201

# This endpoint lets the frontend get all alerts for a specific phone number.
@app.route('/api/get_alerts/<phone_number>')
def get_alerts(phone_number):
    alerts = Alert.query.filter_by(phone_number=phone_number).all()
    alerts_data = [{
        'id': alert.id,
        'ticker': alert.ticker,
        'target_price': alert.target_price,
        'condition': alert.condition,
        'alert_sent': alert.alert_sent
    } for alert in alerts]
    return jsonify(alerts_data)

if __name__ == '__main__':
    # This command creates the database file and table if they don't exist
    with app.app_context():
        db.create_all()
    app.run(debug=True) # Run the Flask server for testing