import os
import random
import string
import pandas as pd
from flask import Flask, render_template_string, request, redirect, url_for, session, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'hermel_tech_school_shams_secret_key'

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# قراءة كافة أعمدة ملف الإكسل تلقائياً
teachers_db = {}
try:
    df = pd.read_excel('بطاقات الاساتذة.xlsx', sheet_name=0)
    for index, row in df.iterrows():
        name = str(row.get('الاسم الثلاثي', f'أستاذ_{index}')).strip()
        if not name or name == 'nan':
            continue
        username = f"teacher_{index+1}"
        password = str(int(row.get('الرقم الآلي', 123456))) if pd.notna(row.get('الرقم الآلي')) else "123456"
        
        # استخراج كافة الحقول من الإكسل
        job_status = str(row.get('الوضع الوظيفي', 'غير محدد')) if pd.notna(row.get('الوضع الوظيفي')) else 'غير محدد'
        degree = str(row.get('الشهادة', 'غير محددة')) if pd.notna(row.get('الشهادة')) else 'غير محددة'
        subject = str(row.get('المادة التي يدرسها', 'غير محددة')) if pd.notna(row.get('المادة التي يدرسها')) else 'غير محددة'
        teaching_degree = str(row.get('الشهادة التي يدرسها', 'غير محددة')) if pd.notna(row.get('الشهادة التي يدرسها')) else 'غير محددة'
        
        teachers_db[username] = {
            'password': password,
            'name': name,
            'job_status': job_status,
            'degree': degree,
            'subject': subject,
            'teaching_degree': teaching_degree,
            'contract_hours': int(row.get('مجموع ساعات العقود', 0)) if pd.notna(row.get('مجموع ساعات العقود')) else 0,
            'phone': str(row.get('رقم الهاتف', 'غير متوفر')) if pd.notna(row.get('رقم الهاتف')) else 'غير متوفر',
            'bank': str(row.get('اسم البنك', 'غير متوفر')) if pd.notna(row.get('اسم البنك')) else 'غير متوفر',
            'iban': str(row.get('Iban Number', 'غير متوفر')) if pd.notna(row.get('Iban Number')) else 'غير متوفر',
            'schedule_pdf': None,
            'notifications': [],
            'monthly_hours': {}, # { 'تشرين الأول': 40, 'تشرين الثاني': 48 }
            'absence_requests': [],
            'uploaded_images': []
        }
except Exception as e:
    teachers_db = {}

teachers_db['admin'] = {
    'password': 'admin_secure_password',
    'name': 'مدير المعهد',
    'job_status': 'الإدارة',
    'degree': '',
    'subject': '',
    'teaching_degree': '',
    'contract_hours': 0,
    'phone': '',
    'bank': '',
    'iban': '',
    'schedule_pdf': None,
    'notifications': [],
    'monthly_hours': {},
    'absence_requests': [],
    'uploaded_images': []
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_random_password(length=6):
    return ''.join(random.choice(string.digits) for _ in range(length))

# 1. تسجيل الدخول
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ''
    if request.method == 'POST':
        username = request.form.get('username').strip().lower()
        password = request.form.get('password').strip()
        
        if username == 'admin' and password == '123456':
            session['username'] = 'admin'
            session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))
        elif username in teachers_db and teachers_db[username]['password'] == password:
            session['username'] = username
            session['role'] = 'teacher'
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
            body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background: #1a202c; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; flex-direction: column; }}
            .card {{ background: white; padding: 40px 30px; border-radius: 16px; width: 90%; max-width: 380px; text-align: center; box-shadow: 0 15px 35px rgba(0,0,0,0.3); }}
            h2 {{ color: #1a365d; margin-bottom: 25px; font-size: 24px; font-weight: bold; }}
            input {{ width: 100%; padding: 12px; margin: 10px 0; border: 1.5px solid #cbd5e0; border-radius: 8px; box-sizing: border-box; text-align: right; font-size: 15px; }}
            button {{ width: 100%; padding: 12px; background: #2b6cb0; color: white; border: none; border-radius: 8px; font-weight: bold; font-size: 16px; cursor: pointer; margin-top: 15px; }}
            button:hover {{ background: #1a365d; }}
            .error {{ color: #e53e3e; margin-top: 12px; font-weight: bold; font-size: 14px; }}
            .designer-tag {{ margin-top: 25px; color: #a0aec0; font-size: 13px; font-weight: 500; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>معهد الهرمل الفني</h2>
            <form method="POST">
                <input type="text" name="username" placeholder="اسم المستخدم" required>
                <input type="password" name="password" placeholder="كلمة المرور" required>
                <button type="submit">دخول النظام</button>
            </form>
            <div class="error">{error}</div>
        </div>
        <div class="designer-tag">🛠️ تم تصميم وتطوير البرنامج من قبل الأستاذ محمد حسين شمص</div>
    </body>
    </html>
    '''

# 2. لوحة المدير
@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    msg = ''
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_hours':
            target_user = request.form.get('target_user')
            month = request.form.get('month_name')
            hours = request.form.get('hours_count')
            if target_user in teachers_db and month and hours:
                teachers_db[target_user]['monthly_hours'][month] = hours
                msg = f"تم تسجيل {hours} حصة للأستاذ لشهر ({month}) بنجاح."

        elif action == 'add_teacher':
            name = request.form.get('name').strip()
            subject = request.form.get('subject').strip()
            username = f"user_{random.randint(100, 999)}"
            generated_pwd = generate_random_password(6)
            
            teachers_db[username] = {
                'password': generated_pwd,
                'name': name,
                'job_status': 'استاذ جديد',
                'degree': 'غير محدد',
                'subject': subject,
                'teaching_degree': 'غير محدد',
                'contract_hours': 0,
                'phone': '',
                'bank': '',
                'iban': '',
                'schedule_pdf': None,
                'notifications': [],
                'monthly_hours': {},
                'absence_requests': [],
                'uploaded_images': []
            }
            msg = f"تم إضافة الأستاذ بنجاح! اسم المستخدم: ({username}) | كلمة المرور: ({generated_pwd})"

        elif action == 'send_notification':
            target_user = request.form.get('target_user')
            notif = request.form.get('notification_text')
            if target_user in teachers_db and notif:
                teachers_db[target_user]['notifications'].append(notif)
                msg = "تم إرسال الإشعار بنجاح."

        elif action == 'upload_pdf':
            target_user = request.form.get('target_user')
            file = request.files.get('pdf_file')
            if target_user in teachers_db and file and allowed_file(file.filename):
                filename = secure_filename(f"schedule_{target_user}.pdf")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                teachers_db[target_user]['schedule_pdf'] = filename
                msg = "تم رفع جدول التدريس PDF."

    rows = ""
    for username, t in teachers_db.items():
        if username == 'admin': continue
        pdf_status = f"<a href='/uploads/{t['schedule_pdf']}' target='_blank'>📄 عرض PDF</a>" if t['schedule_pdf'] else "غير مرفوع"
        
        # استعراض الحصص الشهرية
        m_hours_list = [f"<b>{m}:</b> {h} حصة/ساعة" for m, h in t['monthly_hours'].items()]
        m_hours_str = "<br>".join(m_hours_list) if m_hours_list else "لم تُسجّل بعد"

        rows += f"""
        <tr>
            <td>
                <b>{t['name']}</b><br>
                <small style='color:#4a5568;'>مادة: {t['subject']}</small><br>
                <code>حساب: {username} | سر: {t['password']}</code>
            </td>
            <td><b>{t['contract_hours']} ساعة</b></td>
            <td style="background:#f7fafc; color:#2b6cb0; font-size:13px;">{m_hours_str}</td>
            <td>{pdf_status}</td>
        </tr>
        """

    active_teachers_opts = "".join([f'<option value="{u}">{t["name"]}</option>' for u,t in teachers_db.items() if u != 'admin'])

    return f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>معهد الهرمل الفني - لوحة المدير</title>
        <style>
            body {{ font-family: system-ui, sans-serif; background: #edf2f7; margin: 0; padding: 15px; }}
            .navbar {{ background: #1a365d; color: white; padding: 18px 25px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }}
            .navbar h2 {{ margin:0; font-size: 20px; }}
            .card {{ background: white; padding: 20px; border-radius: 12px; margin-top: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
            th, td {{ border: 1px solid #e2e8f0; padding: 10px; text-align: center; font-size: 13px; }}
            th {{ background: #2b6cb0; color: white; }}
            form {{ display: flex; flex-direction: column; gap: 10px; margin-top: 10px; }}
            input, select, button {{ padding: 10px; border: 1px solid #cbd5e0; border-radius: 6px; text-align: right; font-size: 14px; }}
            button {{ background: #38a169; color: white; border: none; font-weight: bold; cursor: pointer; }}
            .msg {{ background: #c6f6d5; color: #22543d; padding: 12px; border-radius: 8px; margin-top: 15px; font-weight: bold; text-align: center; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 15px; }}
            .designer-tag {{ margin-top: 30px; color: #718096; font-size: 13px; font-weight: 500; text-align: center; border-top: 1px solid #cbd5e0; padding-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="navbar">
            <h2>معهد الهرمل الفني - الإدارة</h2>
            <a href="/logout" style="color:white; font-weight:bold; text-decoration:none; background:#e53e3e; padding:8px 15px; border-radius:6px;">تسجيل الخروج</a>
        </div>

        {f'<div class="msg">{msg}</div>' if msg else ''}

        <div class="grid">
            <div class="card" style="border-top: 4px solid #2b6cb0;">
                <h4>⏱️ إدخال الساعات / الحصص الشهرية لأستاذ:</h4>
                <form method="POST">
                    <input type="hidden" name="action" value="add_hours">
                    <select name="target_user" required>{active_teachers_opts}</select>
                    <input type="text" name="month_name" placeholder="اسم الشهر (مثال: كانون الثاني)" required>
                    <input type="number" name="hours_count" placeholder="عدد الحصص/الساعات المنفذة" required>
                    <button type="submit" style="background:#2b6cb0;">حفظ الحصص الشهرية</button>
                </form>
            </div>

            <div class="card">
                <h4>📄 رفع جدول التدريس (PDF)</h4>
                <form method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="action" value="upload_pdf">
                    <select name="target_user" required>{active_teachers_opts}</select>
                    <input type="file" name="pdf_file" accept=".pdf" required>
                    <button type="submit" style="background:#4a5568;">رفع ملف PDF</button>
                </form>
            </div>

            <div class="card">
                <h4>📢 إرسال إشعار</h4>
                <form method="POST">
                    <input type="hidden" name="action" value="send_notification">
                    <select name="target_user" required>{active_teachers_opts}</select>
                    <input type="text" name="notification_text" placeholder="نص الرسالة" required>
                    <button type="submit" style="background:#dd6b20;">إرسال التنبيه</button>
                </form>
            </div>
        </div>

        <div class="card">
            <h3 style="margin-top:0; color:#1a365d;">سجل الأساتذة والحصص الشهرية</h3>
            <table>
                <tr>
                    <th>بيانات الأستاذ</th>
                    <th>مجموع العقود</th>
                    <th>الحصص الشهرية المنفذة</th>
                    <th>جدول PDF</th>
                </tr>
                {rows}
            </table>
        </div>

        <div class="designer-tag">🛠️ تم تصميم وتطوير البرنامج من قبل الأستاذ محمد حسين شمص</div>
    </body>
    </html>
    '''

# 3. لوحة الأستاذ
@app.route('/teacher', methods=['GET', 'POST'])
def teacher_dashboard():
    if session.get('role') != 'teacher':
        return redirect(url_for('login'))
        
    username = session.get('username')
    user_data = teachers_db.get(username, {})
    msg = ''

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'request_absence':
            abs_date = request.form.get('absence_date')
            reason = request.form.get('absence_reason')
            file = request.files.get('medical_report')
            report_filename = None
            if file and allowed_file(file.filename):
                report_filename = secure_filename(f"report_{username}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], report_filename))
            
            user_data['absence_requests'].append({
                'date': abs_date,
                'reason': reason,
                'report': report_filename
            })
            msg = "تم إرسال طلب التغيب والتقرير الطبي للإدارة بنجاح!"

    notifs_html = "".join([f"<div class='notif-box'>⚠️ {n}</div>" for n in user_data['notifications']])
    pdf_html = f"<a href='/uploads/{user_data['schedule_pdf']}' class='btn-pdf' target='_blank'>📄 فتح/تحميل جدول الحصص الأسبوعي PDF</a>" if user_data['schedule_pdf'] else "لم يتم رفع جدول الحصص بعد."
    
    # جدول الساعات الشهرية للأستاذ
    monthly_rows = ""
    for m, h in user_data['monthly_hours'].items():
        monthly_rows += f"<tr><td><b>{m}</b></td><td><span style='color:#2b6cb0; font-weight:bold;'>{h} حصة / ساعة</span></td></tr>"
    if not monthly_rows:
        monthly_rows = "<tr><td colspan='2'>لم يتدخل المدير أي حصص شهرية بعد.</td></tr>"

    return f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>معهد الهرمل الفني - ملف الأستاذ</title>
        <style>
            body {{ font-family: system-ui, sans-serif; background: #f7fafc; margin: 0; padding: 15px; color: #2d3748; }}
            .navbar {{ background: #1a365d; color: white; padding: 15px; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; }}
            .card {{ background: white; padding: 20px; border-radius: 12px; margin-top: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }}
            .info-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 10px; }}
            .info-item {{ background: #edf2f7; padding: 10px 14px; border-radius: 8px; font-size: 14px; }}
            .info-item b {{ color: #1a365d; }}
            .notif-box {{ background: #fffaf0; border-right: 4px solid #dd6b20; color: #9c4221; padding: 12px; margin-bottom: 8px; border-radius: 6px; font-weight: bold; }}
            .btn-pdf {{ display: inline-block; background: #2b6cb0; color: white; padding: 10px 15px; border-radius: 6px; text-decoration: none; font-weight: bold; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ border: 1px solid #e2e8f0; padding: 10px; text-align: center; font-size: 14px; }}
            th {{ background: #2b6cb0; color: white; }}
            button {{ background: #38a169; color: white; border: none; padding: 10px 15px; border-radius: 6px; font-weight: bold; cursor: pointer; }}
            .designer-tag {{ margin-top: 30px; color: #718096; font-size: 13px; font-weight: 500; text-align: center; border-top: 1px solid #cbd5e0; padding-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="navbar">
            <h3 style="margin:0;">معهد الهرمل الفني</h3>
            <span style="font-size:14px;">أهلاً بك أستاذ: {user_data['name']} | <a href="/logout" style="color:#feb2b2; text-decoration:none; font-weight:bold;">خروج</a></span>
        </div>

        {f'<div style="background:#c6f6d5; color:#22543d; padding:10px; border-radius:6px; margin-top:10px; font-weight:bold;">{msg}</div>' if msg else ''}

        {f'<div class="card"><h4>🔔 رسائل وإشعارات الإدارة:</h4>{notifs_html}</div>' if user_data['notifications'] else ''}

        <div class="card">
            <h4 style="margin-top:0; color:#1a365d; border-bottom:2px solid #edf2f7; padding-bottom:8px;">📋 البطاقة الشخصية والمعلومات العامة (من الإكسل):</h4>
            <div class="info-grid">
                <div class="info-item"><b>الاسم الثلاثي:</b> {user_data['name']}</div>
                <div class="info-item"><b>الوضع الوظيفي:</b> {user_data['job_status']}</div>
                <div class="info-item"><b>الشهادة:</b> {user_data['degree']}</div>
                <div class="info-item"><b>المادة التي يدرّسها:</b> {user_data['subject']}</div>
                <div class="info-item"><b>الشهادة التي يدرّسها:</b> {user_data['teaching_degree']}</div>
                <div class="info-item"><b>مجموع ساعات العقود:</b> {user_data['contract_hours']} ساعة</div>
                <div class="info-item"><b>رقم الهاتف:</b> {user_data['phone']}</div>
                <div class="info-item"><b>اسم البنك:</b> {user_data['bank']}</div>
                <div class="info-item"><b>رقم الـ IBAN:</b> {user_data['iban']}</div>
            </div>
        </div>

        <div class="card">
            <h4 style="margin-top:0; color:#1a365d;">📊 الحصص/الساعات الشهرية المسجلة من الإدارة:</h4>
            <table>
                <tr>
                    <th>الشهر</th>
                    <th>عدد الحصص / الساعات المنفذة</th>
                </tr>
                {monthly_rows}
            </table>
        </div>

        <div class="card">
            <h4 style="margin-top:0; color:#1a365d;">📅 جدول التدريس الأسبوعي:</h4>
            {pdf_html}
        </div>

        <div class="card">
            <h4 style="margin-top:0; color:#1a365d;">📝 تقديم طلب تغيب مسبق مع تقرير طبي:</h4>
            <form method="POST" enctype="multipart/form-data">
                <input type="hidden" name="action" value="request_absence">
                <label>تاريخ التغيب المطلوب:</label>
                <input type="date" name="absence_date" required style="padding:8px; margin:5px 0;"><br>
                <input type="text" name="absence_reason" placeholder="سبب الغياب بالتفصيل..." required style="width:100%; padding:8px; margin:5px 0; box-sizing:border-box;"><br>
                <label>رفع تقرير طبي أو عذر رسمياً (صورة/PDF):</label>
                <input type="file" name="medical_report" accept=".pdf,.png,.jpg,.jpeg" style="margin:5px 0;"><br>
                <button type="submit" style="background:#e53e3e; margin-top:10px;">إرسال طلب التغيب للإدارة</button>
            </form>
        </div>

        <div class="designer-tag">🛠️ تم تصميم وتطوير البرنامج من قبل الأستاذ محمد حسين شمص</div>
    </body>
    </html>
    '''

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)