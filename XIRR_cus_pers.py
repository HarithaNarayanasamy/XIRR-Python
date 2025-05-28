from flask import Flask, render_template, request
from pymongo import MongoClient
from scipy.optimize import newton
from datetime import datetime
from functools import lru_cache
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Flask app setup
app = Flask(__name__)

# Function to get Mongo collection safely
@lru_cache()
def get_collection():
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("MONGO_URI not found in environment variables.")
    client = MongoClient(mongo_uri)
    db = client['MyData']
    return db['DataMine']

# XIRR Calculation Function
def xirr(cashflows, dates):
    def npv(rate):
        return sum(cf / (1 + rate) ** ((date - dates[0]).days / 365.0) for cf, date in zip(cashflows, dates))
    try:
        result = newton(npv, 0.1)
        return result
    except (RuntimeError, OverflowError, ValueError):
        return None

@app.route('/')
def index():
    collection = get_collection()
    member_ids = collection.distinct('MemberIDNew')
    return render_template('index.html', member_ids=member_ids)

@app.route('/calculate', methods=['POST'])
def calculate():
    collection = get_collection()
    member_id = int(request.form['member_id'])
    records = list(collection.find({'MemberIDNew': member_id}).sort('InstallmentDate', 1))

    if not records or len(records) < 2:
        return render_template('result.html', member_id=member_id, xirr=None, error="Insufficient data for XIRR calculation.")

    try:
        cashflows = [float(record['InstallmentAmount']) for record in records]
        dates = [record['InstallmentDate'] if isinstance(record['InstallmentDate'], datetime) else datetime.strptime(record['InstallmentDate'], "%Y-%m-%d") for record in records]
    except Exception as e:
        return render_template('result.html', member_id=member_id, xirr=None, error=f"Data Error: {str(e)}")

    if len(set(dates)) == 1 or all(cf >= 0 for cf in cashflows) or all(cf <= 0 for cf in cashflows):
        return render_template('result.html', member_id=member_id, xirr=None, error="Invalid data for XIRR calculation. Need both inflows & outflows.")

    irr = xirr(cashflows, dates)
    if irr is not None:
        xirr_value = f"{irr * 100:.2f}%"
        return render_template('result.html', member_id=member_id, xirr=xirr_value, error=None)
    else:
        return render_template('result.html', member_id=member_id, xirr=None, error="Error calculating XIRR.")

@app.route('/calculate_all', methods=['GET'])
def calculate_all():
    collection = get_collection()
    member_ids = collection.distinct('MemberIDNew')
    results = []

    for member_id in member_ids:
        records = list(collection.find({'MemberIDNew': member_id}).sort('InstallmentDate', 1))

        if not records or len(records) < 2:
            results.append({'member_id': member_id, 'xirr': None, 'error': "Insufficient data"})
            continue

        cashflows = [float(record['InstallmentAmount']) for record in records]
        dates = [record['InstallmentDate'] if isinstance(record['InstallmentDate'], datetime) else datetime.strptime(record['InstallmentDate'], "%Y-%m-%d") for record in records]

        if len(set(dates)) == 1 or all(cf >= 0 for cf in cashflows) or all(cf <= 0 for cf in cashflows):
            results.append({'member_id': member_id, 'xirr': None, 'error': "Invalid data"})
            continue

        irr = xirr(cashflows, dates)
        if irr is not None:
            xirr_value = f"{irr * 100:.2f}%"
            results.append({'member_id': member_id, 'xirr': xirr_value, 'error': None})
        else:
            results.append({'member_id': member_id, 'xirr': None, 'error': "Error calculating XIRR"})

    return render_template('all_results.html', results=results)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # Use the port Render provides
    app.run(host='0.0.0.0', port=port, debug=True)
