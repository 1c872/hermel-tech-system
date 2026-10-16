import os
import random
import string
import io
import pandas as pd
from flask import Flask, render_template_string, request, redirect, url_for, session, send_from_directory, send_file, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'hermel_tech_school_shams_secret_key_2026'

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'xlsx', 'xls'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

teachers_db = {}
admin_replies = []

def load_initial_teachers():
    global teachers_db
    try:
        if os.path.exists('بطاقات الاساتذة.xlsx'):
            df = pd.read_excel('بطاقات الاساتذة.xlsx', sheet_name=0)
            for index, row in df.iterrows():
                name = str(row.get('الاسم الثلاثي', f'أستاذ_{index}')).strip()
                if not name or name == 'nan':
                    continue
                username = f"teacher_{index+1}"
                password = str(int(row.get('الرقم الآلي', 123456))) if pd.notna(row.get('الرقم الآلي')) else "123456"
                
                teachers_db[username] = {
                    'password': password,
                    'name': name,
                    'dob': str(row.get('تاريخ الميلاد', 'غير محدد')) if pd.notna(row.get('تاريخ الميلاد')) else 'غير محدد',
                    'register_no': str(row.get('رقم السجل', 'غير محدد')) if pd.notna(row.get('رقم السجل')) else 'غير محدد',
                    'district': str(row.get('القضاء', 'غير محدد')) if pd.notna(row.get('القضاء')) else 'غير محدد',
                    'town': str(row.get('بلدة النفوس', 'غير محدد')) if pd.notna(row.get('بلدة النفوس')) else 'غير محدد',
                    'address': str(row.get('العنوان الحالي', 'غير محدد')) if pd.notna(row.get('العنوان الحالي')) else 'غير محدد',
                    'marital_status': str(row.get('الوضع العائلي', 'غير محدد')) if pd.notna(row.get('الوضع العائلي')) else 'غير محدد',
                    'children_count': str(row.get('عدد الأولاد', '0')) if pd.notna(row.get('عدد الأولاد')) else '0',
                    'start_date': str(row.get('تاريخ المباشرة', 'غير محدد')) if pd.notna(row.get('تاريخ المباشرة')) else 'غير محدد',
                    'job_status': str(row.get('الوضع الوظيفي', 'غير محدد')) if pd.notna(row.get('الوضع الوظيفي')) else 'غير محدد',
                    'degree': str(row.get('الشهادة', 'غير محددة')) if pd.notna(row.get('الشهادة')) else 'غير محددة',
                    'subject': str(row.get('المادة التي يدرسها', 'غير محددة')) if pd.notna(row.get('المادة التي يدرسها')) else 'غير محددة',
                    'teaching_degree': str(row.get('الشهادة التي يدرسها', 'غير محددة')) if pd.notna(row.get('الشهادة التي يدرسها')) else 'غير محددة',
                    'contract_hours': int(row.get('مجموع ساعات العقود', 0)) if pd.notna(row.get('مجموع ساعات العقود')) else 0,
                    'phone': str(row.get('رقم الهاتف', 'غير متوفر')) if pd.notna(row.get('رقم الهاتف')) else 'غير متوفر',
                    'bank': str(row.get('اسم البنك', 'غير متوفر')) if pd.notna(row.get('اسم البنك')) else 'غير متوفر',
                    'iban': str(row.get('Iban Number', 'غير متوفر')) if pd.notna(row.get('Iban Number')) else 'غير متوفر',
                    'schedule_pdf': None,
                    'notifications': [],
                    'monthly_data': {}
                }
    except Exception as e:
        print(f"Error loading excel: {e}")

load_initial_teachers()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

ICON_URL = "https://cdn-icons-png.flaticon.com/512/3135/3135755.png"

@app.route('/manifest.json')
def manifest():
    return jsonify({
        "short_name": "معهد الهرمل",
        "name": "معهد الهرمل الفني",
        "icons": [
            {
                "src": ICON_URL,
                "type": "image/png",
                "sizes": "512x512"
            }
        ],
        "start_url": "/",
        "background_color": "#1a365d",
        "theme_color": "#1a365d",
        "display": "standalone",
        "orientation": "portrait"
    })

@app.route('/sw.js')
def service_worker():
    sw_code = """
    self.addEventListener('install', (e) => {
        self.skipWaiting();
    });
    self.addEventListener('activate', (e) => {
        e.waitUntil(self.clients.claim());
    });
    """
    return app.response_class(sw_code, mimetype='application/javascript')

@app.route('/api/check_notifications')
def check_notifications():
    if session.get('role') == 'teacher':
        username = session.get('username')
        user_data = teachers_db.get(username, {})
        notifs = user_data.get('notifications', [])
        return jsonify({'count': len(notifs), 'latest': notifs[-1] if notifs else ''})
    return jsonify({'count': 0, 'latest': ''})

@app.route('/admin/download_template')
def download_template():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    names = [t['name'] for u, t in teachers_db.items() if u != 'admin']
    df_template = pd.DataFrame({
        'الاسم الثلاثي': names,
        'عدد الحصص': [0] * len(names),
        'عدد أيام النقل': [0] * len(names)
    })
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_template.to_excel(writer, index=False, sheet_name='الحصص والنقل الشهري')
    output.seek(0)
    
    return send_file(
        output,
        download_name="نموذج_الحصص_والنقل_الشهري.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route('/admin/delete_reply/<int:reply_id>', methods=['POST'])
def delete_reply(reply_id):
    if session.get('role') == 'admin' and 0 <= reply_id < len(admin_replies):
        admin_replies.pop(reply_id)
    return redirect(url_for('admin_dashboard'))

PWA_HEAD = f'''
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#1a365d">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="معهد الهرمل">
    <link rel="apple-touch-icon" href="{ICON_URL}">
    <script>
        if ('serviceWorker' in navigator) {{
            window.addEventListener('load', () => {{
                navigator.serviceWorker.register('/sw.js');
            }});
        }}
    </script>
'''

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
        {PWA_HEAD}
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

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    msg = ''
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'upload_monthly_excel':
            month_name = request.form.get('month_name')
            file = request.files.get('monthly_excel')
            if file and allowed_file(file.filename):
                try:
                    df_m = pd.read_excel(file)
                    updated_count = 0
                    for _, row in df_m.iterrows():
                        t_name = str(row.get('الاسم الثلاثي', '')).strip()
                        hours = row.get('عدد الحصص', row.get('ساعات التدريس', 0))
                        days = row.get('عدد أيام النقل', row.get('عدد الايام', 0))
                        
                        try: hours = int(hours) if pd.notna(hours) else 0
                        except: hours = 0
                        try: days = int(days) if pd.notna(days) else 0
                        except: days = 0

                        for u, t_data in teachers_db.items():
                            if t_data['name'] == t_name or t_name in t_data['name']:
                                if 'monthly_data' not in t_data:
                                    t_data['monthly_data'] = {}
                                t_data['monthly_data'][month_name] = {
                                    'hours': hours,
                                    'days': days
                                }
                                updated_count += 1
                    msg = f"تم استيراد بيانات شهر ({month_name}) بنجاح لعدد ({updated_count}) أستاذ!"
                except Exception as e:
                    msg = f"حدث خطأ أثناء قراءة الملف: {e}"

        elif action == 'send_notification':
            target_user = request.form.get('target_user')
            notif = request.form.get('notification_text')
            if target_user in teachers_db and notif:
                teachers_db[target_user]['notifications'].append(notif)
                msg = f"تم إرسال الإشعار والتنبيه للأستاذ {teachers_db[target_user]['name']} بنجاح!"

        elif action == 'upload_pdf':
            target_user = request.form.get('target_user')
            file = request.files.get('pdf_file')
            if target_user in teachers_db and file and allowed_file(file.filename):
                filename = secure_filename(f"schedule_{target_user}.pdf")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                teachers_db[target_user]['schedule_pdf'] = filename
                msg = "تم رفع جدول التدريس PDF بنجاح."

    replies_html = ""
    for idx, r in enumerate(reversed(admin_replies)):
        real_idx = len(admin_replies) - 1 - idx
        report_link = f"<a href='/uploads/{r['report']}' target='_blank'>📎 عرض العذر/المرفق</a>" if r.get('report') else "لا يوجد مرفق"
        replies_html += f"""
        <div style="background:#fffaf0; border-right:4px solid #dd6b20; padding:12px; margin-bottom:10px; border-radius:6px; display:flex; justify-content:space-between; align-items:center;">
            <div>
                <span style="color:#2b6cb0; font-weight:bold;">📩 من الأستاذ: {r['teacher_name']}</span> | <small>{r.get('date', '')}</small><br>
                <b>الرسالة/الطلب:</b> {r['message']}<br>
                <small>{report_link}</small>
            </div>
            <form method="POST" action="/admin/delete_reply/{real_idx}" style="margin:0;">
                <button type="submit" style="background:#e53e3e; color:white; border:none; padding:5px 10px; border-radius:4px; font-size:12px; cursor:pointer;">✖️ إزالة</button>
            </form>
        </div>
        """
    if not replies_html:
        replies_html = "<p style='color:#718096;'>لا توجد إجابات أو رسائل جديدة حالياً.</p>"

    rows = ""
    for username, t in teachers_db.items():
        if username == 'admin': continue
        pdf_status = f"<a href='/uploads/{t['schedule_pdf']}' target='_blank'>📄 عرض PDF</a>" if t['schedule_pdf'] else "غير مرفوع"
        
        m_data_list = []
        for m, val in t.get('monthly_data', {}).items():
            m_data_list.append(f"<b>{m}:</b> {val.get('hours', 0)} حصة | {val.get('days', 0)} أيام نقل")
        m_str = "<br>".join(m_data_list) if m_data_list else "لم تُرفع بعد"

        rows += f"""
        <tr>
            <td>
                <b>{t['name']}</b><br>
                <small style='color:#4a5568;'>مادة: {t['subject']}</small><br>
                <code>حساب: {username} | سر: {t['password']}</code>
            </td>
            <td><b>{t['contract_hours']} ساعة</b></td>
            <td style="background:#f7fafc; color:#2b6cb0; font-size:12px;">{m_str}</td>
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
        {PWA_HEAD}
        <style>
            body {{ font-family: system-ui, sans-serif; background: #edf2f7; margin: 0; padding: 15px; }}
            .navbar {{ background: #1a365d; color: white; padding: 18px 25px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }}
            .card {{ background: white; padding: 20px; border-radius: 12px; margin-top: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
            th, td {{ border: 1px solid #e2e8f0; padding: 10px; text-align: center; font-size: 13px; }}
            th {{ background: #2b6cb0; color: white; }}
            form {{ display: flex; flex-direction: column; gap: 10px; margin-top: 10px; }}
            input, select, button {{ padding: 10px; border: 1px solid #cbd5e0; border-radius: 6px; text-align: right; font-size: 14px; }}
            button {{ background: #38a169; color: white; border: none; font-weight: bold; cursor: pointer; }}
            .msg {{ background: #c6f6d5; color: #22543d; padding: 12px; border-radius: 8px; margin-top: 15px; font-weight: bold; text-align: center; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; }}
            .designer-tag {{ margin-top: 30px; color: #718096; font-size: 13px; font-weight: 500; text-align: center; border-top: 1px solid #cbd5e0; padding-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="navbar">
            <h2 style="margin:0;">معهد الهرمل الفني - لوحة الإدارة</h2>
            <a href="/logout" style="color:white; font-weight:bold; text-decoration:none; background:#e53e3e; padding:8px 15px; border-radius:6px;">تسجيل الخروج</a>
        </div>

        {f'<div class="msg">{msg}</div>' if msg else ''}

        <div class="card" style="border-top: 4px solid #dd6b20;">
            <h3 style="margin-top:0; color:#c05621;">📥 إجابات ورسائل الأساتذة الواردة:</h3>
            {replies_html}
        </div>

        <div class="grid">
            <div class="card" style="border-top: 4px solid #38a169;">
                <h4>📊 رفع إكسل الحصص وأيام النقل الشهرية:</h4>
                <a href="/admin/download_template" style="display:inline-block; background:#4a5568; color:white; text-decoration:none; padding:8px 12px; border-radius:6px; font-size:13px; font-weight:bold; margin-bottom:10px; text-align:center;">📥 تنزيل ملف الإكسل الشهري الجاهز بالأسماء</a>
                <form method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="action" value="upload_monthly_excel">
                    <input type="text" name="month_name" placeholder="اسم الشهر (مثال: كانون الثاني)" required>
                    <label style="font-size:12px; color:#4a5568;">اختر ملف الإكسل بعد تعبئته:</label>
                    <input type="file" name="monthly_excel" accept=".xlsx,.xls" required>
                    <button type="submit" style="background:#38a169;">استيراد بيانات الشهر وتحديث الأساتذة</button>
                </form>
            </div>

            <div class="card">
                <h4>📢 إرسال إشعار / تنبيه لأستاذ:</h4>
                <form method="POST">
                    <input type="hidden" name="action" value="send_notification">
                    <select name="target_user" required>{active_teachers_opts}</select>
                    <input type="text" name="notification_text" placeholder="نص الرسالة والتنبيه..." required>
                    <button type="submit" style="background:#2b6cb0;">إرسال التنبيه الفوري</button>
                </form>
            </div>

            <div class="card">
                <h4>📄 رفع جدول التدريس (PDF):</h4>
                <form method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="action" value="upload_pdf">
                    <select name="target_user" required>{active_teachers_opts}</select>
                    <input type="file" name="pdf_file" accept=".pdf" required>
                    <button type="submit" style="background:#4a5568;">رفع ملف PDF</button>
                </form>
            </div>
        </div>

        <div class="card">
            <h3 style="margin-top:0; color:#1a365d;">سجل الأساتذة الكامل</h3>
            <table>
                <tr>
                    <th>بيانات الأستاذ</th>
                    <th>العقود</th>
                    <th>الحصص وأيام النقل الشهرية</th>
                    <th>جدول PDF</th>
                </tr>
                {rows}
            </table>
        </div>

        <div class="designer-tag">🛠️ تم تصميم وتطوير البرنامج من قبل الأستاذ محمد حسين شمص</div>
    </body>
    </html>
    '''

@app.route('/teacher', methods=['GET', 'POST'])
def teacher_dashboard():
    if session.get('role') != 'teacher':
        return redirect(url_for('login'))
        
    username = session.get('username')
    user_data = teachers_db.get(username, {})
    msg = ''

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'send_reply':
            reply_msg = request.form.get('reply_message')
            file = request.files.get('medical_report')
            report_filename = None
            if file and allowed_file(file.filename):
                report_filename = secure_filename(f"report_{username}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], report_filename))
            
            admin_replies.append({
                'teacher_name': user_data['name'],
                'message': reply_msg,
                'report': report_filename,
                'date': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')
            })
            msg = "تم إرسال إجابتك/رسالتك لمدير المعهد بنجاح!"

    notifs_list = user_data.get('notifications', [])
    notifs_html = "".join([f"<div class='notif-box'>🔔 <b>إشعار جديد:</b> {n}</div>" for n in notifs_list])
    pdf_html = f"<a href='/uploads/{user_data['schedule_pdf']}' class='btn-pdf' target='_blank'>📄 فتح/تحميل جدول الحصص PDF</a>" if user_data.get('schedule_pdf') else "لم يتم رفع جدول الحصص بعد."
    
    total_hours_executed = 0
    total_days_executed = 0
    monthly_rows = ""
    
    for m, val in user_data.get('monthly_data', {}).items():
        h = val.get('hours', 0)
        d = val.get('days', 0)
        total_hours_executed += h
        total_days_executed += d
        monthly_rows += f"<tr><td><b>{m}</b></td><td><span style='color:#2b6cb0; font-weight:bold;'>{h} حصة</span></td><td><span style='color:#38a169; font-weight:bold;'>{d} أيام</span></td></tr>"
    
    if not monthly_rows:
        monthly_rows = "<tr><td colspan='3'>لم تُرفع بيانات شهرية بعد.</td></tr>"

    contract_total = user_data.get('contract_hours', 0)
    remaining_hours = max(0, contract_total - total_hours_executed)

    initial_notif_count = len(notifs_list)

    return f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>معهد الهرمل الفني - بطاقة الأستاذ</title>
        {PWA_HEAD}
        <style>
            body {{ font-family: system-ui, sans-serif; background: #f7fafc; margin: 0; padding: 15px; color: #2d3748; }}
            .navbar {{ background: #1a365d; color: white; padding: 15px; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; }}
            .card {{ background: white; padding: 20px; border-radius: 12px; margin-top: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }}
            .info-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 10px; }}
            .info-item {{ background: #edf2f7; padding: 10px 14px; border-radius: 8px; font-size: 13.5px; line-height: 1.6; }}
            .info-item b {{ color: #1a365d; }}
            .notif-box {{ background: #ebf8ff; border-right: 4px solid #3182ce; color: #2b6cb0; padding: 12px; margin-bottom: 8px; border-radius: 6px; font-weight: bold; }}
            .btn-pdf {{ display: inline-block; background: #2b6cb0; color: white; padding: 10px 15px; border-radius: 6px; text-decoration: none; font-weight: bold; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ border: 1px solid #e2e8f0; padding: 10px; text-align: center; font-size: 14px; }}
            th {{ background: #2b6cb0; color: white; }}
            .summary-box {{ display: flex; flex-wrap: wrap; gap: 15px; margin-top: 15px; }}
            .sum-card {{ flex: 1; min-width: 150px; background: #f7fafc; border: 1.5px solid #cbd5e0; padding: 15px; border-radius: 8px; text-align: center; }}
            button {{ background: #38a169; color: white; border: none; padding: 10px 15px; border-radius: 6px; font-weight: bold; cursor: pointer; }}
            .designer-tag {{ margin-top: 30px; color: #718096; font-size: 13px; font-weight: 500; text-align: center; border-top: 1px solid #cbd5e0; padding-top: 15px; }}
            
            /* شريط التنبيه التقني المريح المدمج بدون إزعاج */
            #smoothBanner {{
                display: none;
                background: linear-gradient(90deg, #1e3a8a, #2563eb);
                color: white;
                padding: 12px 18px;
                border-radius: 10px;
                margin-top: 12px;
                box-shadow: 0 4px 12px rgba(37,99,235,0.25);
                font-size: 14px;
                line-height: 1.5;
            }}
        </style>
    </head>
    <body>
        <div class="navbar">
            <h3 style="margin:0;">معهد الهرمل الفني</h3>
            <span style="font-size:14px;">أهلاً بك أستاذ: {user_data.get('name')} | <a href="/logout" style="color:#feb2b2; text-decoration:none; font-weight:bold;">خروج</a></span>
        </div>

        <!-- شريط تنبيه أنيق وغير مزعج يظهر بالتدريج عند إضافة رسالة -->
        <div id="smoothBanner">
            ⚡ <b>رسالة جديدة من مدير المعهد:</b> <span id="bannerText"></span>
        </div>

        {f'<div style="background:#c6f6d5; color:#22543d; padding:10px; border-radius:6px; margin-top:10px; font-weight:bold;">{msg}</div>' if msg else ''}

        <div class="card" id="notifArea">
            <h4>📩 التنبيهات والإشعارات الواردة:</h4>
            <div id="notifContent">{notifs_html if notifs_html else '<p style="color:#718096;">لا توجد إشعارات جديدة حالياً.</p>'}</div>
        </div>

        <div class="card" style="border-top: 4px solid #2b6cb0;">
            <h4 style="margin-top:0; color:#1a365d; border-bottom:2px solid #edf2f7; padding-bottom:8px;">📋 البطاقة الشخصية والمعلومات الإدارية الكاملة:</h4>
            <div class="info-grid">
                <div class="info-item"><b>الاسم الثلاثي:</b> {user_data.get('name')}</div>
                <div class="info-item"><b>تاريخ الميلاد:</b> {user_data.get('dob')}</div>
                <div class="info-item"><b>رقم السجل:</b> {user_data.get('register_no')}</div>
                <div class="info-item"><b>القضاء / بلدة النفوس:</b> {user_data.get('district')} / {user_data.get('town')}</div>
                <div class="info-item"><b>العنوان الحالي:</b> {user_data.get('address')}</div>
                <div class="info-item"><b>الوضع العائلي:</b> {user_data.get('marital_status')} (الأولاد: {user_data.get('children_count')})</div>
                <div class="info-item"><b>الوضع الوظيفي:</b> {user_data.get('job_status')}</div>
                <div class="info-item"><b>تاريخ المباشرة:</b> {user_data.get('start_date')}</div>
                <div class="info-item"><b>الشهادة العلمية:</b> {user_data.get('degree')}</div>
                <div class="info-item"><b>المادة التي يدرّسها:</b> {user_data.get('subject')}</div>
                <div class="info-item"><b>مجموع ساعات العقود:</b> {contract_total} ساعة</div>
                <div class="info-item"><b>رقم الهاتف:</b> {user_data.get('phone')}</div>
                <div class="info-item"><b>البنك المعني:</b> {user_data.get('bank')}</div>
                <div class="info-item"><b>رقم الـ IBAN:</b> {user_data.get('iban')}</div>
            </div>
        </div>

        <div class="card">
            <h4 style="margin-top:0; color:#1a365d;">📊 سجل الحصص وأيام النقل والشهرية:</h4>
            <table>
                <tr>
                    <th>الشهر</th>
                    <th>عدد الحصص المنفذة</th>
                    <th>عدد أيام بدل النقل</th>
                </tr>
                {monthly_rows}
            </table>

            <div class="summary-box">
                <div class="sum-card" style="border-color:#2b6cb0;">
                    <span style="font-size:12px; color:#4a5568;">المجموع العام المنفذ:</span><br>
                    <b style="font-size:20px; color:#2b6cb0;">{total_hours_executed} حصة</b>
                </div>
                <div class="sum-card" style="border-color:#4a5568;">
                    <span style="font-size:12px; color:#4a5568;">العقد الكامل المحدد:</span><br>
                    <b style="font-size:20px; color:#2d3748;">{contract_total} ساعة</b>
                </div>
                <div class="sum-card" style="border-color:#e53e3e;">
                    <span style="font-size:12px; color:#4a5568;">المتبقي لإنجاز العقد:</span><br>
                    <b style="font-size:20px; color:#e53e3e;">{remaining_hours} ساعة</b>
                </div>
            </div>
        </div>

        <div class="card">
            <h4 style="margin-top:0; color:#1a365d;">📅 جدول التدريس الأسبوعي:</h4>
            {pdf_html}
        </div>

        <div class="card">
            <h4 style="margin-top:0; color:#1a365d;">💬 إرسال إجابة / طلب تغيب / عذر رسمي للإدارة:</h4>
            <form method="POST" enctype="multipart/form-data">
                <input type="hidden" name="action" value="send_reply">
                <textarea name="reply_message" placeholder="اكتب رسالتك أو سبب التغيب..." required style="width:100%; height:80px; padding:10px; border:1px solid #cbd5e0; border-radius:6px; box-sizing:border-box; margin-bottom:10px;"></textarea>
                <label style="font-size:13px; color:#4a5568;">إرفاق عذر رسمي / تقرير طبي (اختياري):</label><br>
                <input type="file" name="medical_report" accept=".pdf,.png,.jpg,.jpeg" style="margin:5px 0;"><br>
                <button type="submit" style="background:#2b6cb0; margin-top:10px;">إرسال الرد للإدارة</button>
            </form>
        </div>

        <div class="designer-tag">🛠️ تم تصميم وتطوير البرنامج من قبل الأستاذ محمد حسين شمص</div>

        <script>
            let currentNotifCount = {initial_notif_count};
            let audioCtx = null;

            // نغمة خفيفة وراقية لمرة واحدة فقط دون إزعاج
            function playSubtleTone() {{
                try {{
                    if (!audioCtx) {{
                        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                    }}
                    let osc = audioCtx.createOscillator();
                    let gain = audioCtx.createGain();

                    osc.type = 'sine';
                    osc.frequency.setValueAtTime(659.25, audioCtx.currentTime); // نغمة E5 هادئة

                    gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
                    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.3);

                    osc.connect(gain);
                    gain.connect(audioCtx.destination);

                    osc.start();
                    osc.stop(audioCtx.currentTime + 0.3);
                }} catch(e) {{}}
            }}

            function triggerQuietAlert(messageText) {{
                document.getElementById('bannerText').innerText = messageText;
                document.getElementById('smoothBanner').style.display = 'block';
                playSubtleTone();
            }}

            // فحص السيرفر بشكل صامت كل 10 ثوانٍ
            setInterval(() => {{
                fetch('/api/check_notifications')
                    .then(res => res.json())
                    .then(data => {{
                        if (data.count > currentNotifCount) {{
                            currentNotifCount = data.count;
                            triggerQuietAlert(data.latest);
                        }}
                    }});
            }}, 10000);
        </script>
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