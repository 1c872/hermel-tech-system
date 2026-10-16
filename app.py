from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)

# قاعدة بيانات مؤقتة لتخزين الأساتذة والساعات (يمكننا ربطها بـ SQLite لاحقاً)
teachers_db = [
    {"id": 1, "name": "أستاذ محمد", "subject": "معلوماتية صناعية", "hours": 45, "rate": 10},
    {"id": 2, "name": "أستاذ أحمد", "subject": "إلكترونيات واتصالات", "hours": 38, "rate": 10}
]

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ''
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == '123456':
            return redirect(url_for('admin_dashboard'))
        else:
            error = 'اسم المستخدم أو كلمة المرور غير صحيحة'
            
    return f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>معهد الهرمل الفني - تسجيل الدخول</title>
        <style>
            body {{ font-family: system-ui, sans-serif; background: #f0f4f8; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
            .card {{ background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); width: 100%; max-width: 380px; text-align: center; }}
            h2 {{ color: #1a365d; margin-bottom: 25px; }}
            input {{ width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #cbd5e0; border-radius: 6px; box-sizing: border-box; text-align: right; }}
            button {{ width: 100%; padding: 12px; background: #2b6cb0; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; margin-top: 15px; }}
            button:hover {{ background: #1a365d; }}
            .error {{ color: #e53e3e; margin-top: 10px; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>معهد الهرمل الفني</h2>
            <form method="POST">
                <input type="text" name="username" placeholder="اسم المستخدم (admin)" required><br>
                <input type="password" name="password" placeholder="كلمة المرور (123456)" required><br>
                <button type="submit">دخول النظام</button>
            </form>
            <div class="error">{error}</div>
        </div>
    </body>
    </html>
    '''

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if request.method == 'POST':
        name = request.form.get('name')
        subject = request.form.get('subject')
        hours = int(request.form.get('hours', 0))
        teachers_db.append({"id": len(teachers_db) + 1, "name": name, "subject": subject, "hours": hours, "rate": 10})
        return redirect(url_for('admin_dashboard'))

    rows = ""
    for t in teachers_db:
        total = t['hours'] * t['rate']
        rows += f"""
        <tr>
            <td>{t['name']}</td>
            <td>{t['subject']}</td>
            <td>{t['hours']} ساعة</td>
            <td>${total}</td>
        </tr>
        """

    return f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>لوحة تحكم معهد الهرمل الفني</title>
        <style>
            body {{ font-family: system-ui, sans-serif; background: #f7fafc; margin: 0; padding: 20px; }}
            .container {{ max-width: 900px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
            h1, h2 {{ color: #1a365d; text-align: center; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ border: 1px solid #e2e8f0; padding: 12px; text-align: center; }}
            th {{ background: #2b6cb0; color: white; }}
            form {{ background: #edf2f7; padding: 20px; border-radius: 8px; margin-top: 20px; display: grid; grid-template-columns: 1fr 1fr 1fr auto; gap: 10px; align-items: center; }}
            input {{ padding: 10px; border: 1px solid #cbd5e0; border-radius: 5px; }}
            button {{ padding: 10px 20px; background: #38a169; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; }}
            button:hover {{ background: #2f855a; }}
            .logout {{ display: inline-block; margin-top: 20px; color: #e53e3e; text-decoration: none; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>معهد الهرمل الفني</h1>
            <h2>لوحة إدارة الأساتذة والساعات التعليمية</h2>
            
            <table>
                <tr>
                    <th>اسم الأستاذ</th>
                    <th>المادة / الاختصاص</th>
                    <th>الساعات المنفذة</th>
                    <th>المستحقات التقديرية</th>
                </tr>
                {rows}
            </table>

            <form method="POST">
                <input type="text" name="name" placeholder="اسم الأستاذ الجديد" required>
                <input type="text" name="subject" placeholder="المادة" required>
                <input type="number" name="hours" placeholder="عدد الساعات" required>
                <button type="submit">إضافة أستاذ</button>
            </form>
            
            <a href="/login" class="logout">تسجيل الخروج</a>
        </div>
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)