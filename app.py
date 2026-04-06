import os
from flask import Flask, request, jsonify, render_template
from src.orchestrator import run_orchestrator
from src.storage import init_db

app = Flask(__name__)

# Initialize DB tables for runs alongside prices on boot
init_db()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/backtest', methods=['POST'])
def backtest():
    try:
        config = request.json
        if not config:
            return jsonify({"error": "No configuration provided"}), 400
            
        # Dispatch to orchestrator bridging constraints, pricing, validation and strategy logic
        payload = run_orchestrator(config)
        return jsonify(payload)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Guarantee static and templates folders exist
    os.makedirs(os.path.join(os.path.dirname(__file__), "templates"), exist_ok=True)
    # Changed port to 8080 because macOS Monterey+ reserves port 5000 for AirPlay Receiver (causing Access Denied)
    app.run(debug=True, port=8080)
