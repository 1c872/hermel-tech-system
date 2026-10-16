from flask import Flask, render_template_string, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'hermel_technical_institute_secret_key'

# قاعدة بيانات الأساتذة وحساباتهم (قابلة للتعديل والزيادة لاحقاً)
users_db = {
    'admin': {'password': '123456', 'role': 'admin', 'name': 'أستاذ محمد (مدير المعهد)'},
    'mohammed': {'password': '1234', 'role': 'teacher', 'name': 'محمد حسين شمص', 'subject': 'معلوماتية صناعية', 'hours': 45, 'rate': 10},
    'ahmed': {'password': '1234', 'role': 'teacher', 'name': 'أحمد علي', 'subject': 'إلكترونيات واتصالات', 'hours': 38, 'rate': 10}
}

# قائمة الأساتذة لعرضها في لوحة التحكم
teachers_list = [
    {"id": 1, "username": "mohammed", "name": "محمد حسين شمص", "subject": "معلوماتية صناعية", "hours": 45, "rate": 10},
    {"id": 2, "username": "ahmed", "name": "أحمد علي", "subject": "إلكترونيات واتصالات", "hours": 38, "rate": 10}
]

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ''
    if request.method == 'POST':
        username = request.form.get('username').strip().lower()
        password = request.form.get('password').strip()
        
        if username in users_db and users_db[username]['password'] == password:
            session['username'] = username
            session['role'] = users_db[username]['role']
            session['name'] = users_db[username]['name']
            
            if users_db[username]['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('teacher_dashboard'))
        else:
            error = 'اسم المستخدم أو كلمة المرور غير صحيحة'
            
    return f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>معهد الهرمل الفني - تسجيل الدخول</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }}
            .login-card {{ background: rgba(255, 255, 255, 0.95); padding: 40px 30px; border-radius: 16px; box-shadow: 0 15px 35px rgba(0,0,0,0.2); width: 90%; max-width: 380px; text-align: center; backdrop-filter: blur(10px); }}
            .logo-title {{ color: #1e3c72; font-size: 24px; font-weight: bold; margin-bottom: 5px; }}
            .sub-title {{ color: #718096; font-size: 14px; margin-bottom: 25px; }}
            input {{ width: 100%; padding: 12px 15px; margin: 8px 0; border: 1.5px solid #e2e8f0; border-radius: 8px; font-size: 15px; box-sizing: border-box; text-align: right; transition: all 0.3s; }}
            input:focus {{ border-color: #2a5298; outline: none; box-shadow: 0 0 0 3px rgba(42,82,152,0.15); }}
            button {{ width: 100%; padding: 12px; background: #2a5298; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; margin-top: 15px; transition: background 0.3s; }}
            button:hover {{ background: #1e3c72; }}
            .error {{ color: #e53e3e; margin-top: 12px; font-size: 14px; font-weight: bold; }}
            .demo-info {{ margin-top: 20px; padding: 10px; background: #edf2f7; border-radius: 8px; font-size: 12px; color: #4a5568; text-align: right; line-height: 1.5; }}
        </style>
    </head>
    <body>
        <div class="login-card">
            <div class="logo-title">معهد الهرمل الفني</div>
            <div class="sub-title">البوابة الإلكترونية الرسمية</div>
            <form method="POST">
                <input type="text" name="username" placeholder="اسم المستخدم" required>
                <input type="password" name="password" placeholder="كلمة المرور" required>
                <button type="submit">دخول النظام</button>
            </form>
            <div class="error">{error}</div>
            <div class="demo-info">
                💡 <b>بيانات التجربة:</b><br>
                • المدير: <code>admin</code> / <code>123456</code><br>
                • أستاذ تجريبي: <code>mohammed</code> / <code>1234</code>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        name = request.form.get('name')
        subject = request.form.get('subject')
        hours = int(request.form.get('hours', 0))
        username = request.form.get('username').strip().lower()
        password = request.form.get('password').strip()
        
        # إضافة الحساب
        users_db[username] = {'password': password, 'role': 'teacher', 'name': name, 'subject': subject, 'hours': hours, 'rate': 10}
        teachers_list.append({"id": len(teachers_list) + 1, "username": username, "name": name, "subject": subject, "hours": hours, "rate": 10})
        return redirect(url_for('admin_dashboard'))

    total_hours = sum(t['hours'] for t in teachers_list)
    total_amount = total_hours * 10
    
    rows = ""
    for t in teachers_list:
        total = t['hours'] * t['rate']
        rows += f"""
        <tr>
            <td><b>{t['name']}</b></td>
            <td><span class="badge">{t['subject']}</span></td>
            <td><code>{t['username']}</code></td>
            <td><b>{t['hours']}</b> ساعة</td>
            <td style="color:#2b6cb0; font-weight:bold;">${total}</td>
        </tr>
        """

    return f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>لوحة إدارة معهد الهرمل الفني</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f0f4f8; margin: 0; padding: 20px; color: #2d3748; }}
            .navbar {{ background: #1a365d; color: white; padding: 15px 25px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
            .navbar h2 {{ margin: 0; font-size: 20px; }}
            .logout-btn {{ background: #e53e3e; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 14px; }}
            .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 15px; margin-bottom: 25px; }}
            .stat-card {{ background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center; border-bottom: 4px solid #2b6cb0; }}
            .stat-card h3 {{ margin: 0; color: #718096; font-size: 14px; }}
            .stat-card p {{ margin: 10px 0 0 0; color: #1a365d; font-size: 24px; font-weight: bold; }}
            .card {{ background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 25px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
            th, td {{ border-bottom: 1px solid #e2e8f0; padding: 12px; text-align: center; font-size: 15px; }}
            th {{ background: #2b6cb0; color: white; font-weight: 600; }}
            .badge {{ background: #ebf8ff; color: #2b6cb0; padding: 4px 10px; border-radius: 20px; font-size: 13px; font-weight: 500; }}
            .form-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-top: 15px; }}
            input {{ padding: 10px; border: 1px solid #cbd5e0; border-radius: 6px; font-size: 14px; text-align: right; }}
            .add-btn {{ grid-column: 1 / -1; padding: 12px; background: #38a169; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 15px; }}
            .add-btn:hover {{ background: #2f855a; }}
        </style>
    </head>
    <body>
        <div class="navbar">
            <h2>معهد الهرمل الفني - لوحة إدارة المدير</h2>
            <a href="/logout" class="logout-btn">تسجيل الخروج</a>
        </div>

        <div class="stats-grid">
            <div class="stat-card"><h3>إجمالي الأساتذة</h3><p>{len(teachers_list)} أستاذ</p></div>
            <div class="stat-card"><h3>مجموع الساعات</h3><p>{total_hours} ساعة</p></div>
            <div class="stat-card"><h3>المستحقات الكلية</h3><p>${total_amount}</p></div>
        </div>

        <div class="card">
            <h3 style="margin-top:0; color:#1a365d;">جدول بيانات وساعات الأساتذة</h3>
            <table>
                <tr>
                    <th>اسم الأستاذ</th>
                    <th>المادة / الاختصاص</th>
                    <th>اسم المستخدم</th>
                    <th>الساعات المنفذة</th>
                    <th>المستحقات التقديرية</th>
                </tr>
                {rows}
            </table>
        </div>

        <div class="card">
            <h3 style="margin-top:0; color:#1a365d;">➕ إضافة أستاذ جديد وحساب دخول</h3>
            <form method="POST" class="form-grid">
                <input type="text" name="name" placeholder="الاسم الكامل" required>
                <input type="text" name="subject" placeholder="المادة / الاختصاص" required>
                <input type="number" name="hours" placeholder="عدد الساعات" required>
                <input type="text" name="username" placeholder="اسم المستخدم للتسجيل" required>
                <input type="password" name="password" placeholder="كلمة المرور" required>
                <button type="submit" class="add-btn">حفظ وإضافة الأستاذ للنظام</button>
            </form>
        </div>
    </body>
    </html>
    '''

@app.route('/teacher')
def teacher_dashboard():
    if session.get('role') != 'teacher':
        return redirect(url_for('login'))
        
    username = session.get('username')
    user_info = users_db.get(username, {})
    total = user_info.get('hours', 0) * user_info.get('rate', 10)

    return f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>معهد الهرمل الفني - بوابة الأستاذ</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f0f4f8; margin: 0; padding: 20px; }}
            .navbar {{ background: #1a365d; color: white; padding: 15px 25px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
            .logout-btn {{ background: #e53e3e; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 14px; }}
            .profile-card {{ background: white; padding: 30px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); max-width: 500px; margin: 0 auto; text-align: center; }}
            .avatar {{ width: 80px; height: 80px; background: #e2e8f0; color: #2b6cb0; font-size: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 15px auto; font-weight: bold; }}
            .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 25px; text-align: right; }}
            .info-box {{ background: #f7fafc; padding: 15px; border-radius: 10px; border-right: 4px solid #2b6cb0; }}
            .info-box span {{ display: block; color: #718096; font-size: 13px; margin-bottom: 5px; }}
            .info-box strong {{ color: #1a365d; font-size: 18px; }}
        </style>
    </head>
    <body>
        <div class="navbar">
            <h2 style="margin:0; font-size:18px;">معهد الهرمل الفني</h2>
            <a href="/logout" class="logout-btn">تسجيل الخروج</a>
        </div>

        <div class="profile-card">
            <div class="avatar">👨‍🏫</div>
            <h2 style="margin:0; color:#1a365d;">أهلاً بك، {user_info.get('name')}</h2>
            <p style="color:#718096; margin-top:5px;">حساب أستاذ رسمي - معهد الهرمل الفني</p>

            <div class="info-grid">
                <div class="info-box">
                    <span>المادة المخصصة:</span>
                    <strong>{user_info.get('subject')}</strong>
                </div>
                <div class="info-box">
                    <span>الساعات المنفذة:</span>
                    <strong>{user_info.get('hours')} ساعة</strong>
                </div>
                <div class="info-box" style="grid-column: 1 / -1; border-right-color: #38a169;">
                    <span>إجمالي المستحقات التقديرية:</span>
                    <strong style="color:#2f855a; font-size:22px;">${total}</strong>
                </div>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)