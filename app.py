from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import pyodbc
import os

app = Flask(__name__)
# Oturum (session) verilerini şifreleyerek güvenlik arttırıldı
app.secret_key = os.urandom(24) 

def get_connection():
    
    server = session.get('server')
    database = session.get('database')
    
    return pyodbc.connect(
        f"Driver={{SQL Server}};"
        f"Server={server};"
        f"Database={database};"
        f"Trusted_Connection=yes;"
    )

#Oturumun açılmadığı durum
@app.route('/')
def index():
    return render_template('index.html', connected=session.get('connected'), error=request.args.get('error'))


@app.route('/connect', methods=['POST'])
def connect():
    server = request.form.get('server')
    database = request.form.get('database')
    
    try:
        # Bağlantıyı test et
        conn = pyodbc.connect(
            f"Driver={{SQL Server}};"
            f"Server={server};"
            f"Database={database};"
            f"Trusted_Connection=yes;"
        )
        conn.close()
        
        # Başarılıysa oturuma kaydet
        session['server'] = server
        session['database'] = database
        session['connected'] = True
        return redirect(url_for('index'))

    # Hata varsa giriş ekranına geri dön ve hatayı göster
    except Exception as e:
        return redirect(url_for('index', error="Bağlantı başarısız. Lütfen bilgileri kontrol edin."))

@app.route('/disconnect')
def disconnect():
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/schema')
def schema():
    if not session.get('connected'):
        return jsonify({})
        
    conn = get_connection()
    cursor = conn.cursor()  #Veri tabanının içerisinde dolaşmamıza yardımcı yapı
    
    cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
    tables = [row[0] for row in cursor.fetchall()]  #Veri tabanındaki tüm tablo isimlerini aldık
    
    schema_data = {}
    for table in tables:
        cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ?", (table,))
        schema_data[table] = [row[0] for row in cursor.fetchall()]  #Tabloların içerisindeki stunları aldık
        
    cursor.close()
    conn.close()
    return jsonify(schema_data)


@app.route('/api/values', methods=['POST'])
def get_values():
    if not session.get('connected'):
        return jsonify([])
        
    data = request.json
    table = data.get('table')
    column = data.get('column')
    
    if not table or not column:
        return jsonify([])
        
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        sql = f"SELECT DISTINCT TOP 100 [{column}] FROM [{table}] WHERE [{column}] IS NOT NULL"
        #Veri tekrarı yaşanmaması için DISTINCT kullanıldı
        cursor.execute(sql)
        
        values = []
        for row in cursor.fetchall():
            val = row[0]
            if isinstance(val, bytes):
                values.append("<Binary Veri>")
            else:
                values.append(str(val))
        
        cursor.close()
        conn.close()
        return jsonify(values)
    
    except Exception as e:
        print(f"Değer okuma hatası: {e}")
        return jsonify([])

@app.route('/api/execute', methods=['POST'])
def execute():
    if not session.get('connected'):
        return jsonify({"error": "Oturum kapalı."})
        
    data = request.json
    table = data.get('table')
    filters = data.get('filters', [])
    
    sql = f"SELECT * FROM [{table}]"
    params = []
    
    if filters:
        conditions = []
        for f in filters:
            conditions.append(f"[{f['column']}] {f['operator']} ?")
            params.append(f['value'])
        sql += " WHERE " + " AND ".join(conditions)
        
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        
        columns = [column[0] for column in cursor.description]
        
        results = []
        for row in cursor.fetchall():
            row_dict = {}
            for col_name, value in zip(columns, row):
                if isinstance(value, bytes):
                    row_dict[col_name] = "<Binary Veri>"
                else:
                    row_dict[col_name] = value
            results.append(row_dict)
        
        cursor.close()
        conn.close()
        return jsonify({"sql": sql, "params": params, "results": results, "error": None})
    except Exception as e:
        return jsonify({"sql": sql, "params": params, "results": [], "error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)