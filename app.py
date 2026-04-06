import os
from flask import Flask, request, jsonify, render_template
from src.orchestrator import run_orchestrator
from src.storage import init_db
from src.data_sources import get_catalog_for_ui

app = Flask(__name__)

# Initialize DB tables on boot
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

        payload = run_orchestrator(config)
        return jsonify(payload)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/instruments', methods=['GET'])
def instruments():
    """Return the full instrument catalog for dynamic UI population."""
    return jsonify(get_catalog_for_ui())

if __name__ == '__main__':
    os.makedirs(os.path.join(os.path.dirname(__file__), "templates"), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "static", "charts"), exist_ok=True)
    app.run(debug=True, port=8080)
