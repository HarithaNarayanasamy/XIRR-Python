from flask import Flask, render_template, request
from pymongo import MongoClient
from scipy.optimize import newton
from datetime import datetime

app = Flask(__name__)

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['MyData']
collection = db['DataMine']

# XIRR Calculation Function
def xirr(cashflows, dates):
    """ Calculate XIRR using Newton's method """

    def npv(rate):
        return sum(cf / (1 + rate) ** ((date - dates[0]).days / 365.0) for cf, date in zip(cashflows, dates))

    try:
        result = newton(npv, 0.1)  # Initial guess 0.1 (10%)
        return result
    except (RuntimeError, OverflowError, ValueError):
        return None


@app.route('/')
def index():
    """ Render index page with form """
    # Get unique MemberIDs from MongoDB for dropdown
    member_ids = collection.distinct('MemberIDNew')
    return render_template('index.html', member_ids=member_ids)


@app.route('/calculate', methods=['POST'])
def calculate():
    """ Calculate XIRR for the given MemberID """
    member_id = int(request.form['member_id'])

    # Get records for the selected MemberID
    records = list(collection.find({'MemberIDNew': member_id}).sort('InstallmentDate', 1))

    if not records or len(records) < 2:
        return render_template('result.html', member_id=member_id, xirr=None, error="Insufficient data for XIRR calculation.")

    # Extract cashflows and dates
    try:
        cashflows = [float(record['InstallmentAmount']) for record in records]  # Ensure numeric values
        dates = [record['InstallmentDate'] if isinstance(record['InstallmentDate'], datetime) else datetime.strptime(record['InstallmentDate'], "%Y-%m-%d") for record in records]  # Ensure datetime format
    except Exception as e:
        return render_template('result.html', member_id=member_id, xirr=None, error=f"Data Error: {str(e)}")

    # Validate data
    if len(set(dates)) == 1 or all(cf >= 0 for cf in cashflows) or all(cf <= 0 for cf in cashflows):
        return render_template('result.html', member_id=member_id, xirr=None, error="Invalid data for XIRR calculation. Need both inflows & outflows.")

    # Calculate XIRR
    irr = xirr(cashflows, dates)
    if irr is not None:
        xirr_value = f"{irr * 100:.2f}%"
        return render_template('result.html', member_id=member_id, xirr=xirr_value, error=None)
    else:
        return render_template('result.html', member_id=member_id, xirr=None, error="Error calculating XIRR.")

@app.route('/calculate_all', methods=['GET'])
def calculate_all():
    """ Calculate XIRR for all MemberIDs """
    member_ids = collection.distinct('MemberIDNew')
    results = []

    for member_id in member_ids:
        records = list(collection.find({'MemberIDNew': member_id}).sort('InstallmentDate', 1))

        if not records or len(records) < 2:
            results.append({'member_id': member_id, 'xirr': None, 'error': "Insufficient data"})
            continue

        cashflows = [record['InstallmentAmount'] for record in records]
        dates = [record['InstallmentDate'] for record in records]

        # Validate data
        if len(set(dates)) == 1 or all(cf >= 0 for cf in cashflows) or all(cf <= 0 for cf in cashflows):
            results.append({'member_id': member_id, 'xirr': None, 'error': "Invalid data"})
            continue

        # Calculate XIRR
        irr = xirr(cashflows, dates)
        if irr is not None:
            xirr_value = f"{irr * 100:.2f}%"
            results.append({'member_id': member_id, 'xirr': xirr_value, 'error': None})
        else:
            results.append({'member_id': member_id, 'xirr': None, 'error': "Error calculating XIRR"})

    return render_template('all_results.html', results=results)


if __name__ == '__main__':
    app.run(debug=True)