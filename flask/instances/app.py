from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import mysql.connector
import configparser
import json
import os

app = Flask(__name__)
CORS(app)

# --- Načítanie konfigurácie ---
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(__file__), 'config.cfg'))

DB_CONFIG = {
    'host':     config['mysql']['host'],
    'user':     config['mysql']['user'],
    'password': config['mysql']['passwd'],
    'database': config['mysql']['database'],
}

print(**DB_CONFIG)

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def fmt_dt(dt):
    return dt.strftime('%Y-%m-%d %H:%M:%S') if dt else None


#  POST /dbdata/session
#  Uloží celý záznam po stlačení Stop
#  Body: { "temperatures": [...], "start_time": "2024-01-01 12:00:00" }

@app.route('/dbdata/session', methods=['POST'])
def save_session():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Očakávam JSON body'}), 400

    temperatures = data.get('temperatures')
    start_time   = data.get('start_time')

    if not temperatures or not isinstance(temperatures, list):
        return jsonify({'error': 'Pole "temperatures" musí byť neprázdny zoznam'}), 400
    if not start_time:
        return jsonify({'error': 'Pole "start_time" je povinné'}), 400

    temperatures_json = json.dumps(temperatures)

    try:
        conn   = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO temperature_session (temperatures, start_time) VALUES (%s, %s)",
            (temperatures_json, start_time)
        )
        conn.commit()
        new_id = cursor.lastrowid
        return jsonify({'message': 'Záznam uložený', 'id': new_id}), 201
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close(); conn.close()



#  GET /dbdata/session          → zoznam všetkých záznamov (bez temperatures JSON)
#  GET /dbdata/session/<id>     → detail jedného záznamu vrátane temperatures

@app.route('/dbdata/session', methods=['GET'])
def list_sessions():
    try:
        conn   = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, start_time, JSON_LENGTH(temperatures) AS count "
            "FROM temperature_session ORDER BY id DESC"
        )
        rows = cursor.fetchall()
        for row in rows:
            row['start_time'] = fmt_dt(row.get('start_time'))
        return jsonify({'sessions': rows}), 200
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close(); conn.close()


@app.route('/dbdata/session/<int:session_id>', methods=['GET'])
def get_session(session_id):
    try:
        conn   = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, temperatures, start_time FROM temperature_session WHERE id = %s",
            (session_id,)
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': f'Záznam ID {session_id} neexistuje'}), 404

        row['start_time']   = fmt_dt(row.get('start_time'))
        row['temperatures'] = json.loads(row['temperatures'])
        return jsonify(row), 200
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close(); conn.close()


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)