import os
import json
import random
import string
import io
import math
import pandas as pd
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, session, send_from_directory, send_file, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'hermel_tech_school_shams_secret_key_2026'

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'xlsx', 'xls'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_FILE = 'database.json'

teachers_db = {}
admin_replies = []
admin_credentials = {'username': 'admin', 'password': '123456'}

# 1. نظام الأعوام الدراسية الممتدة
academic_years_db = ["2025-2026", "2026-2027", "2027-2028", "2028-2029"]
current_academic_year = "2026-2027"

# 2. قواعد بيانات الطلاب والجلسات الميدانية
students_db = []
field_sessions = []

# 3. قاعدة بيانات مواقع التدريب الميداني وإحداثيات الـ GPS ونطاق الأمان (بالأمتار)
TRAINING_LOCATIONS = {
    "مستشفى الهرمل الحكومي": {"lat": 34.381283, "lng": 36.424456, "radius_meters": 300},
    "مستشفى البتول": {"lat": 34.381283, "lng": 36.424456, "radius_meters": 300},
    "مستشفى دار الكرامة": {"lat": 34.403492, "lng": 36.396789, "radius_meters": 250},
    "مستشفى العاصي": {"lat": 34.398330, "lng": 36.406490, "radius_meters": 250},
    "مدرسة سانرايز": {"lat": 34.403492, "lng": 36.396789, "radius_meters": 200},
    "ثانوية الرشاد": {"lat": 34.403826, "lng": 36.391736, "radius_meters": 200},
    "مدرسة الإمام علي": {"lat": 34.395518, "lng": 36.386411, "radius_meters": 200}
}

def calculate_distance(lat1, lon1, lat2, lon2):
    """حساب المسافة بالمتر بين نقطتين جغرافيتين باستخدام معادلة Haversine"""
    R = 6371000  # نصف قطر الأرض بالمتر
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def save_to_disk():
    """حفظ قاعدة البيانات الكاملة في ملف JSON دائم"""
    try:
        data = {
            'teachers_db': teachers_db,
            'admin_replies': admin_replies,
            'admin_credentials': admin_credentials,
            'academic_years_db': academic_years_db,
            'current_academic_year': current_academic_year,
            'students_db': students_db,
            'field_sessions': field_sessions
        }
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving database: {e}")

def load_from_disk():
    """تحميل البيانات المحفوظة إن وجدت"""
    global teachers_db, admin_replies, admin_credentials, academic_years_db, current_academic_year, students_db, field_sessions
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                teachers_db = data.get('teachers_db', {})
                admin_replies = data.get('admin_replies', [])
                admin_credentials = data.get('admin_credentials', {'username': 'admin', 'password': '123456'})
                academic_years_db = data.get('academic_years_db', ["2025-2026", "2026-2027", "2027-2028"])
                current_academic_year = data.get('current_academic_year', "2026-2027")
                students_db = data.get('students_db', [])
                field_sessions = data.get('field_sessions', [])
                return True
        except Exception as e:
            print(f"Error loading database file: {e}")
    return False

def load_initial_teachers():
    """تحميل البيانات الأولية للأساتذة من الإكسل"""
    global teachers_db
    if load_from_disk():
        return

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
            save_to_disk()
    except Exception as e:
        print(f"Error loading excel: {e}")

load_initial_teachers()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

ICON_URL = "https://cdn-icons-png.flaticon.com/512/3135/3135755.png"

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

@app.route('/manifest.json')
def manifest():
    return jsonify({
        "short_name": "معهد الهرمل",
        "name": "معهد الهرمل الفني",
        "icons": [{"src": ICON_URL, "type": "image/png", "sizes": "512x512"}],
        "start_url": "/",
        "background_color": "#1a365d",
        "theme_color": "#1a365d",
        "display": "standalone",
        "orientation": "portrait"
    })

@app.route('/sw.js')
def service_worker():
    sw_code = "self.addEventListener('install', (e) => { self.skipWaiting(); }); self.addEventListener('activate', (e) => { e.waitUntil(self.clients.claim()); });"
    return app.response_class(sw_code, mimetype='application/javascript')

@app.route('/api/check_notifications')
def check_notifications():
    if session.get('role') == 'teacher':
        username = session.get('username')
        user_data = teachers_db.get(username, {})
        notifs = user_data.get('notifications', [])
        return jsonify({'count': len(notifs), 'latest': notifs[-1] if notifs else ''})
    return jsonify({'count': 0, 'latest': ''})

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ''
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '').strip()
        
        if username == admin_credentials['username'] and password == admin_credentials['password']:
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

@app.route('/admin/add_year', methods=['POST'])
def add_academic_year():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    new_y = request.form.get('new_year', '').strip()
    if new_y and new_y not in academic_years_db:
        academic_years_db.append(new_y)
        save_to_disk()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/switch_year', methods=['POST'])
def switch_academic_year():
    global current_academic_year
    if session.get('role') != 'admin': return redirect(url_for('login'))
    sel_y = request.form.get('academic_year')
    if sel_y in academic_years_db:
        current_academic_year = sel_y
        save_to_disk()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/download_students_template')
def download_students_template():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    df_temp = pd.DataFrame({
        'name': ['علي أحمد', 'حسن محمد', 'ميرا شمص'],
        'class': ['سنة ثالثة', 'سنة ثالثة', 'سنة ثالثة'],
        'major': ['عناية تمريضية', 'عناية تمريضية', 'عناية تمريضية']
    })
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_temp.to_excel(output, index=False, sheet_name='الطلاب')
    output.seek(0)
    return send_file(output, download_name="قالب_رفع_الطلاب.xlsx", as_attachment=True)

@app.route('/admin/upload_students_excel', methods=['POST'])
def upload_students_excel():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    file = request.files.get('students_excel')
    if file and allowed_file(file.filename):
        try:
            df = pd.read_excel(file)
            added = 0
            for _, row in df.iterrows():
                s_name = str(row.get('name', row.get('اسم الطالب', ''))).strip()
                s_class = str(row.get('class', row.get('الصف', ''))).strip()
                s_major = str(row.get('major', row.get('الاختصاص', ''))).strip()
                
                if s_name and s_name != 'nan':
                    students_db.append({
                        "id": len(students_db) + 1,
                        "name": s_name,
                        "class": s_class,
                        "major": s_major,
                        "academic_year": current_academic_year
                    })
                    added += 1
            save_to_disk()
            session['msg'] = f"تم رفع واستيراد {added} طالب بنجاح للعام الدراسي {current_academic_year}!"
        except Exception as e:
            session['msg'] = f"خطأ أثناء قراءة ملف الإكسل: {e}"
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/create_field_session', methods=['POST'])
def create_field_session():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    
    p_teacher = request.form.get('primary_teacher')
    s_teacher = request.form.get('secondary_teacher')
    
    new_s = {
        "id": len(field_sessions) + 1,
        "academic_year": current_academic_year,
        "class_name": request.form.get('class_name'),
        "major": request.form.get('major'),
        "location": request.form.get('location'),
        "primary_teacher": p_teacher if p_teacher else "غير محدد",
        "secondary_teacher": s_teacher if s_teacher and s_teacher != 'none' else None,
        "attendance": {},
        "submitted_by": None,
        "status": "قيد التدريب",
        "created_at": datetime.now().strftime('%Y-%m-%d %H:%M')
    }
    field_sessions.append(new_s)
    save_to_disk()
    session['msg'] = "تم إنشاء وتكليف جلسة التدريب الميداني بنجاح!"
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/download_template')
def download_template():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    names = [t['name'] for u, t in teachers_db.items()]
    df_template = pd.DataFrame({
        'الاسم الثلاثي': names,
        'عدد الحصص': [0] * len(names),
        'عدد أيام النقل': [0] * len(names)
    })
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_template.to_excel(output, index=False, sheet_name='الحصص والنقل الشهري')
    output.seek(0)
    return send_file(output, download_name="نموذج_الحصص_والنقل_الشهري.xlsx", as_attachment=True)

@app.route('/admin/delete_reply/<int:reply_id>', methods=['POST'])
def delete_reply(reply_id):
    if session.get('role') == 'admin' and 0 <= reply_id < len(admin_replies):
        admin_replies.pop(reply_id)
        save_to_disk()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_teacher/<username>', methods=['POST'])
def delete_teacher(username):
    if session.get('role') == 'admin' and username in teachers_db:
        del teachers_db[username]
        save_to_disk()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))
        
    msg = session.pop('msg', '')
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'change_admin_password':
            new_pass = request.form.get('new_password', '').strip()
            if new_pass:
                admin_credentials['password'] = new_pass
                save_to_disk()
                msg = "تم تغيير كلمة مرور الإدارة بنجاح!"

        elif action == 'upload_monthly_excel':
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
                                if 'monthly_data' not in t_data: t_data['monthly_data'] = {}
                                t_data['monthly_data'][month_name] = {'hours': hours, 'days': days}
                                updated_count += 1
                    save_to_disk()
                    msg = f"تم استيراد بيانات شهر ({month_name}) بنجاح لعدد ({updated_count}) أستاذ!"
                except Exception as e:
                    msg = f"حدث خطأ أثناء قراءة الملف: {e}"

        elif action == 'send_notification':
            target_user = request.form.get('target_user')
            notif = request.form.get('notification_text')
            if target_user == 'all':
                for u, t_data in teachers_db.items():
                    t_data['notifications'].append(f"📢 تعميم إداري: {notif}")
                save_to_disk()
                msg = "تم إرسال التعميم لجميع الأساتذة بنجاح!"
            elif target_user in teachers_db and notif:
                teachers_db[target_user]['notifications'].append(notif)
                save_to_disk()
                msg = f"تم إرسال الإشعار للأستاذ {teachers_db[target_user]['name']} بنجاح!"

        elif action == 'upload_pdf':
            target_user = request.form.get('target_user')
            file = request.files.get('pdf_file')
            if target_user in teachers_db and file and allowed_file(file.filename):
                filename = secure_filename(f"schedule_{target_user}.pdf")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                teachers_db[target_user]['schedule_pdf'] = filename
                save_to_disk()
                msg = f"تم رفع جدول التدريس PDF للأستاذ {teachers_db[target_user]['name']}."

    replies_html = ""
    for idx, r in enumerate(reversed(admin_replies)):
        real_idx = len(admin_replies) - 1 - idx
        report_link = f"<a href='/uploads/{r['report']}' target='_blank'>📎 عرض العذر</a>" if r.get('report') else "لا يوجد مرفق"
        replies_html += f"""
        <div style="background:#fffaf0; border-right:4px solid #dd6b20; padding:12px; margin-bottom:10px; border-radius:6px; display:flex; justify-content:space-between; align-items:center;">
            <div>
                <span style="color:#2b6cb0; font-weight:bold;">📩 من: {r['teacher_name']}</span> | <small>{r.get('date', '')}</small><br>
                <b>الرسالة:</b> {r['message']}<br>
                <small>{report_link}</small>
            </div>
            <form method="POST" action="/admin/delete_reply/{real_idx}" style="margin:0;">
                <button type="submit" style="background:#e53e3e; color:white; border:none; padding:5px 10px; border-radius:4px; font-size:12px; cursor:pointer;">✖️ إزالة</button>
            </form>
        </div>
        """
    if not replies_html: replies_html = "<p style='color:#718096;'>لا توجد إجابات ورسائل جديدة.</p>"

    active_field_sessions = [s for s in field_sessions if s.get('academic_year') == current_academic_year]
    field_rows = ""
    for fs in reversed(active_field_sessions):
        sec_t = f" / {fs['secondary_teacher']}" if fs['secondary_teacher'] else ""
        att_info = ""
        if fs['status'] == 'مكتملة':
            absents = [st for st, stt in fs['attendance'].items() if stt == 'غائب']
            abs_str = ", ".join(absents) if absents else "لا يوجد غياب"
            att_info = f"<span style='color:#38a169; font-weight:bold;'>مكتملة بواسطة ({fs['submitted_by']})</span><br><small style='color:#e53e3e;'>الغائبون: {abs_str}</small>"
        else:
            att_info = "<span style='color:#dd6b20; font-weight:bold;'>⏳ قيد انتظار الأستاذ</span>"

        field_rows += f"""
        <tr>
            <td><b>{fs['location']}</b><br><small>{fs['class_name']} - {fs['major']}</small></td>
            <td><b>{fs['primary_teacher']}</b>{sec_t}</td>
            <td>{att_info}</td>
        </tr>
        """
    if not field_rows: field_rows = "<tr><td colspan='3'>لا توجد جلسات ميدانية مضافة لهذا العام بعد.</td></tr>"

    rows = ""
    for username, t in teachers_db.items():
        pdf_status = f"<a href='/uploads/{t['schedule_pdf']}' target='_blank'>📄 عرض PDF</a>" if t['schedule_pdf'] else "غير مرفوع"
        m_data_list = [f"<b>{m}:</b> {val.get('hours', 0)} حصة | {val.get('days', 0)} أيام" for m, val in t.get('monthly_data', {}).items()]
        m_str = "<br>".join(m_data_list) if m_data_list else "لم تُرفع بعد"

        rows += f"""
        <tr>
            <td><b>{t['name']}</b><br><small style='color:#4a5568;'>مادة: {t['subject']}</small><br><code>حساب: {username} | سر: {t['password']}</code></td>
            <td><b>{t['contract_hours']} ساعة</b></td>
            <td style="background:#f7fafc; color:#2b6cb0; font-size:12px;">{m_str}</td>
            <td>{pdf_status}</td>
            <td>
                <form method="POST" action="/admin/delete_teacher/{username}" onsubmit="return confirm('حذف الأستاذ؟');" style="margin:0;">
                    <button type="submit" style="background:#e53e3e; color:white; border:none; padding:6px 10px; border-radius:4px; font-size:12px; cursor:pointer;">🗑️ حذف</button>
                </form>
            </td>
        </tr>
        """

    years_options = "".join([f"<option value='{y}' {'selected' if y==current_academic_year else ''}>{y}</option>" for y in academic_years_db])
    teachers_options = "".join([f"<option value='{t['name']}'>{t['name']}</option>" for u, t in teachers_db.items()])
    locations_options = "".join([f"<option value='{loc}'>{loc}</option>" for loc in TRAINING_LOCATIONS.keys()])

    return f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>معهد الهرمل الفني - لوحة الإدارة</title>
        {PWA_HEAD}
        <style>
            body {{ font-family: system-ui, sans-serif; background: #edf2f7; margin: 0; padding: 15px; }}
            .navbar {{ background: #1a365d; color: white; padding: 18px 25px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 10px rgba(0,0,0,0.1); flex-wrap: wrap; gap:10px; }}
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
            .autocomplete-container {{ position: relative; width: 100%; }}
            .suggestionsList {{ position: absolute; top: 100%; left: 0; right: 0; background: white; border: 1px solid #cbd5e0; border-radius: 0 0 6px 6px; max-height: 180px; overflow-y: auto; z-index: 1000; display: none; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }}
            .suggestion-item {{ padding: 10px; cursor: pointer; border-bottom: 1px solid #edf2f7; font-size: 14px; text-align: right; }}
            .suggestion-item:hover {{ background: #ebf8ff; color: #2b6cb0; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="navbar">
            <div>
                <h2 style="margin:0;">معهد الهرمل الفني - لوحة الإدارة</h2>
                <small>العام الدراسي النشط حالياً: <b>{current_academic_year}</b></small>
            </div>
            <div style="display:flex; gap:10px; align-items:center;">
                <form action="/admin/switch_year" method="POST" style="margin:0; flex-direction:row;">
                    <select name="academic_year" onchange="this.form.submit()" style="background:#2b6cb0; color:white; font-weight:bold;">
                        {years_options}
                    </select>
                </form>
                <a href="/logout" style="color:white; font-weight:bold; text-decoration:none; background:#e53e3e; padding:8px 15px; border-radius:6px;">تسجيل الخروج</a>
            </div>
        </div>

        {f'<div class="msg">{msg}</div>' if msg else ''}

        <div class="grid">
            <div class="card" style="border-top: 4px solid #319795;">
                <h4 style="margin-top:0; color:#2c7a7b;">📅 إدارة الأعوام الدراسية الممتدة:</h4>
                <form action="/admin/add_year" method="POST" style="flex-direction:row; gap:5px;">
                    <input type="text" name="new_year" placeholder="مثال: 2029-2030" required style="flex:1;">
                    <button type="submit" style="background:#319795;">إضافة عام جديد</button>
                </form>
            </div>

            <div class="card" style="border-top: 4px solid #d69e2e;">
                <h4 style="margin-top:0; color:#b7791f;">📥 استيراد طلاب للعام ({current_academic_year}):</h4>
                <a href="/admin/download_students_template" style="background:#742a2a; color:white; text-decoration:none; padding:6px 10px; border-radius:6px; font-size:12px; text-align:center; display:inline-block; margin-bottom:5px;">📥 تحميل قالب إكسل للطلاب</a>
                <form action="/admin/upload_students_excel" method="POST" enctype="multipart/form-data">
                    <input type="file" name="students_excel" accept=".xlsx,.xls" required>
                    <button type="submit" style="background:#d69e2e;">رفع واستيراد الطلاب</button>
                </form>
            </div>
        </div>

        <div class="card" style="border-top: 4px solid #805ad5;">
            <h3 style="margin-top:0; color:#553c9a;">🏥 إضافة جلسة تدريب ميداني (مستشفيات / مدارس):</h3>
            <form action="/admin/create_field_session" method="POST" class="grid" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));">
                <div>
                    <label style="font-size:12px;">المكان المعتمد:</label>
                    <select name="location" required style="width:100%;">
                        {locations_options}
                    </select>
                </div>
                <div>
                    <label style="font-size:12px;">الصف:</label>
                    <input type="text" name="class_name" placeholder="سنة ثالثة" required style="width:100%;">
                </div>
                <div>
                    <label style="font-size:12px;">الاختصاص:</label>
                    <input type="text" name="major" placeholder="عناية تمريضية" required style="width:100%;">
                </div>
                <div>
                    <label style="font-size:12px;">الأستاذ الرئيسي:</label>
                    <select name="primary_teacher" required style="width:100%;">
                        {teachers_options}
                    </select>
                </div>
                <div>
                    <label style="font-size:12px;">الأستاذ المساعد:</label>
                    <select name="secondary_teacher" style="width:100%;">
                        <option value="none">-- أستاذ واحد فقط --</option>
                        {teachers_options}
                    </select>
                </div>
                <div style="grid-column: 1 / -1;">
                    <button type="submit" style="background:#805ad5; width:100%;">حفظ وتكليف الجلسة الميدانية</button>
                </div>
            </form>

            <h4 style="margin-top:20px;">سجل الحضور والغياب الميداني للعام النشط:</h4>
            <table>
                <tr>
                    <th>المكان والصف</th>
                    <th>الأستاذ المشرف</th>
                    <th>حالة إرسال الغياب</th>
                </tr>
                {field_rows}
            </table>
        </div>

        <div class="card" style="border-top: 4px solid #805ad5;">
            <h4 style="margin-top:0; color:#553c9a;">🔑 تغيير كلمة مرور الإدارة:</h4>
            <form method="POST">
                <input type="hidden" name="action" value="change_admin_password">
                <input type="password" name="new_password" placeholder="كلمة المرور الإدارية الجديدة" required>
                <button type="submit" style="background:#805ad5;">تحديث كلمة المرور</button>
            </form>
        </div>

        <div class="card" style="border-top: 4px solid #dd6b20;">
            <h3 style="margin-top:0; color:#c05621;">📥 إجابات ورسائل الأساتذة الواردة:</h3>
            {replies_html}
        </div>

        <div class="grid">
            <div class="card" style="border-top: 4px solid #38a169;">
                <h4>📊 رفع إكسل الحصص وأيام النقل الشهرية:</h4>
                <a href="/admin/download_template" style="display:inline-block; background:#4a5568; color:white; text-decoration:none; padding:8px 12px; border-radius:6px; font-size:13px; font-weight:bold; margin-bottom:10px; text-align:center;">📥 تنزيل نموذج الحصص والنقل</a>
                <form method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="action" value="upload_monthly_excel">
                    <input type="text" name="month_name" placeholder="اسم الشهر (مثال: كانون الثاني)" required>
                    <input type="file" name="monthly_excel" accept=".xlsx,.xls" required>
                    <button type="submit" style="background:#38a169;">استيراد بيانات الشهر وتحديث الأساتذة</button>
                </form>
            </div>

            <div class="card" style="border-top: 4px solid #2b6cb0;">
                <h4>📢 إرسال إشعار / تعليمات للأساتذة:</h4>
                <form method="POST">
                    <input type="hidden" name="action" value="send_notification">
                    <div class="autocomplete-container">
                        <input type="text" id="notifSearchBox" placeholder="اكتب للبحث عن اسم أستاذ..." oninput="onNotifSearch()" autocomplete="off">
                        <div id="notifSuggestions" class="suggestionsList"></div>
                    </div>
                    <input type="hidden" name="target_user" id="notifTargetUser" value="all" required>
                    <div id="notifTargetDisplay" style="background:#edf2f7; padding:8px; border-radius:6px; font-size:13px; color:#2b6cb0; font-weight:bold; text-align:center;">🎯 المستهدف: إرسال لجميع الأساتذة</div>
                    <textarea name="notification_text" placeholder="اكتب التعليمات..." required style="width:100%; height:70px; padding:10px; border:1px solid #cbd5e0; border-radius:6px; font-family:inherit;"></textarea>
                    <button type="submit" style="background:#2b6cb0;">📢 إرسال التنبيه</button>
                </form>
            </div>

            <div class="card" style="border-top: 4px solid #4a5568;">
                <h4>📄 رفع جدول التدريس (PDF):</h4>
                <form method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="action" value="upload_pdf">
                    <div class="autocomplete-container">
                        <input type="text" id="pdfSearchBox" placeholder="اكتب اسم الأستاذ..." oninput="onPdfSearch()" autocomplete="off">
                        <div id="pdfSuggestions" class="suggestionsList"></div>
                    </div>
                    <input type="hidden" name="target_user" id="pdfTargetUser" required>
                    <div id="pdfTargetDisplay" style="background:#edf2f7; padding:8px; border-radius:6px; font-size:13px; color:#4a5568; font-weight:bold; text-align:center;">⚠️ اختر أستاذاً أولاً</div>
                    <input type="file" name="pdf_file" accept=".pdf" required>
                    <button type="submit" style="background:#4a5568;">رفع ملف PDF للأستاذ</button>
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
                    <th>إدارة</th>
                </tr>
                {rows}
            </table>
        </div>

        <div class="designer-tag">🛠️ تم تصميم وتطوير البرنامج من قبل الأستاذ محمد حسين شمص</div>

        <script>
            const allTeachers = [
                {{"username": "all", "name": "📢 إرسال لجميع الأساتذة (تعميم عام)", "subject": "الجميع"}},
                {','.join([f'{{"username": "{u}", "name": "{t["name"]}", "subject": "{t["subject"]}"}}' for u, t in teachers_db.items()])}
            ];
            const teachersOnly = allTeachers.filter(t => t.username !== 'all');

            function onNotifSearch() {{
                let query = document.getElementById('notifSearchBox').value.trim().toLowerCase();
                let listDiv = document.getElementById('notifSuggestions');
                listDiv.innerHTML = '';
                if (query === '') {{
                    listDiv.style.display = 'none';
                    document.getElementById('notifTargetUser').value = 'all';
                    document.getElementById('notifTargetDisplay').innerText = "🎯 المستهدف: إرسال لجميع الأساتذة";
                    return;
                }}
                let filtered = allTeachers.filter(t => t.name.toLowerCase().includes(query) || t.subject.toLowerCase().includes(query));
                filtered.forEach(t => {{
                    let item = document.createElement('div');
                    item.className = 'suggestion-item';
                    item.innerHTML = `<b>${{t.name}}</b> <small>(${{t.subject}})</small>`;
                    item.onclick = function() {{
                        document.getElementById('notifSearchBox').value = t.name;
                        document.getElementById('notifTargetUser').value = t.username;
                        document.getElementById('notifTargetDisplay').innerText = "🎯 المستهدف: " + t.name;
                        listDiv.style.display = 'none';
                    }};
                    listDiv.appendChild(item);
                }});
                listDiv.style.display = 'block';
            }}

            function onPdfSearch() {{
                let query = document.getElementById('pdfSearchBox').value.trim().toLowerCase();
                let listDiv = document.getElementById('pdfSuggestions');
                listDiv.innerHTML = '';
                if (query === '') {{
                    listDiv.style.display = 'none';
                    document.getElementById('pdfTargetUser').value = '';
                    document.getElementById('pdfTargetDisplay').innerText = "⚠️ اختر أستاذاً أولاً";
                    return;
                }}
                let filtered = teachersOnly.filter(t => t.name.toLowerCase().includes(query) || t.subject.toLowerCase().includes(query));
                filtered.forEach(t => {{
                    let item = document.createElement('div');
                    item.className = 'suggestion-item';
                    item.innerHTML = `<b>${{t.name}}</b> <small>(${{t.subject}})</small>`;
                    item.onclick = function() {{
                        document.getElementById('pdfSearchBox').value = t.name;
                        document.getElementById('pdfTargetUser').value = t.username;
                        document.getElementById('pdfTargetDisplay').innerText = "✅ الأستاذ المختار: " + t.name;
                        listDiv.style.display = 'none';
                    }};
                    listDiv.appendChild(item);
                }});
                listDiv.style.display = 'block';
            }}

            document.addEventListener('click', function(e) {{
                if (!e.target.closest('.autocomplete-container')) {{
                    document.querySelectorAll('.suggestionsList').forEach(el => el.style.display = 'none');
                }}
            }});
        </script>
    </body>
    </html>
    '''

@app.route('/teacher', methods=['GET', 'POST'])
def teacher_dashboard():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
        
    username = session.get('username')
    user_data = teachers_db.get(username, {})
    t_name = user_data.get('name', '')
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
                'teacher_name': t_name,
                'message': reply_msg,
                'report': report_filename,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M')
            })
            save_to_disk()
            msg = "تم إرسال إجابتك/رسالتك لمدير المعهد بنجاح!"

    notifs_list = user_data.get('notifications', [])
    notifs_html = "".join([f"<div class='notif-box'>🔔 <b>إشعار/تعميم:</b> {n}</div>" for n in notifs_list])
    pdf_html = f"<a href='/uploads/{user_data['schedule_pdf']}' class='btn-pdf' target='_blank'>📄 فتح/تحميل جدول الحصص PDF</a>" if user_data.get('schedule_pdf') else "لم يتم رفع جدول الحصص بعد."
    
    my_sessions = [s for s in field_sessions if s.get('academic_year') == current_academic_year and (s['primary_teacher'] == t_name or s['secondary_teacher'] == t_name)]
    
    sessions_html = ""
    for s in my_sessions:
        if s['status'] == 'قيد التدريب':
            matching_students = [st for st in students_db if st.get('academic_year') == current_academic_year and st['class'] == s['class_name'] and st['major'] == s['major']]
            
            students_list_html = ""
            for st in matching_students:
                students_list_html += f'''
                <li style="display:flex; justify-content:space-between; align-items:center; padding:8px; border-bottom:1px solid #edf2f7;">
                    <span>{st['name']}</span>
                    <div>
                        <input type="checkbox" class="btn-check" id="st_{st['id']}" checked autocomplete="off">
                        <label class="btn btn-outline-success btn-sm" for="st_{st['id']}" onclick="toggleStatus(this)" style="padding:4px 12px; cursor:pointer;">حاضر</label>
                    </div>
                </li>
                '''
            if not students_list_html: students_list_html = "<p style='color:red; font-size:13px;'>لا توجد أسماء طلاب مرفوعة لهذا الصف والاختصاص عبر إكسل بعد.</p>"

            sessions_html += f'''
            <div style="background:#f7fafc; border:1.5px solid #cbd5e0; padding:15px; border-radius:8px; margin-bottom:15px;">
                <h4 style="margin:0 0 10px 0; color:#2b6cb0;">📍 مكان التدريب: {s['location']}</h4>
                <p style="font-size:14px; margin:5px 0;"><b>الصف:</b> {s['class_name']} | <b>الاختصاص:</b> {s['major']}</p>
                <p style="margin:5px 0;"><small style="color:#718096;">يرجى تفعيل الـ GPS والنقر على الطالب المتغيب فقط تحول إلى غائب:</small></p>
                <ul style="list-style:none; padding:0; max-height:200px; overflow-y:auto; background:white; border:1px solid #cbd5e0; border-radius:6px; margin-bottom:10px;">
                    {students_list_html}
                </ul>
                <button type="button" onclick="submitAttendance({s['id']}, '{t_name}', '{s['location']}')" style="background:#38a169; color:white; border:none; padding:10px; width:100%; border-radius:6px; font-weight:bold; cursor:pointer;">إرسال غياب الطلاب للإدارة عبر التحقق الجغرافي GPS</button>
            </div>
            '''
        else:
            sessions_html += f'''
            <div style="background:#f0fff4; border:1.5px solid #38a169; padding:15px; border-radius:8px; margin-bottom:15px;">
                <h4 style="margin:0; color:#22543d;">✔ تم إرسال تقرير التدريب لـ ({s['location']}) مسبقاً</h4>
                <small>بواسطة الأستاذ: <b>{s['submitted_by']}</b></small>
            </div>
            '''

    if not sessions_html: sessions_html = "<p style='color:#718096;'>لا توجد جلسات تدريب ميداني مكلف بها حالياً لهذا العام.</p>"

    total_hours_executed = 0
    total_days_executed = 0
    monthly_rows = ""
    for m, val in user_data.get('monthly_data', {}).items():
        h = val.get('hours', 0)
        d = val.get('days', 0)
        total_hours_executed += h
        total_days_executed += d
        monthly_rows += f"<tr><td><b>{m}</b></td><td><span style='color:#2b6cb0; font-weight:bold;'>{h} حصة</span></td><td><span style='color:#38a169; font-weight:bold;'>{d} أيام</span></td></tr>"
    if not monthly_rows: monthly_rows = "<tr><td colspan='3'>لم تُرفع بيانات شهرية بعد.</td></tr>"

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
            #smoothBanner {{ display: none; background: linear-gradient(90deg, #1e3a8a, #2563eb); color: white; padding: 12px 18px; border-radius: 10px; margin-top: 12px; box-shadow: 0 4px 12px rgba(37,99,235,0.25); font-size: 14px; line-height: 1.5; }}
        </style>
    </head>
    <body>
        <div class="navbar">
            <h3 style="margin:0;">معهد الهرمل الفني</h3>
            <span style="font-size:14px;">أهلاً بك أستاذ: {user_data.get('name')} | <a href="/logout" style="color:#feb2b2; text-decoration:none; font-weight:bold;">خروج</a></span>
        </div>

        <div id="smoothBanner">
            ⚡ <b>رسالة جديدة من مدير المعهد:</b> <span id="bannerText"></span>
        </div>

        {f'<div style="background:#c6f6d5; color:#22543d; padding:10px; border-radius:6px; margin-top:10px; font-weight:bold;">{msg}</div>' if msg else ''}

        <div class="card" id="notifArea">
            <h4>📩 التنبيهات والتعاميم الواردة:</h4>
            <div id="notifContent">{notifs_html if notifs_html else '<p style="color:#718096;">لا توجد تعاميم جديدة حالياً.</p>'}</div>
        </div>

        <div class="card" style="border-top: 4px solid #805ad5;">
            <h3 style="margin-top:0; color:#553c9a;">🏥 جلسات التدريب الميداني الخاص بك ({current_academic_year}):</h3>
            {sessions_html}
        </div>

        <div class="card" style="border-top: 4px solid #2b6cb0;">
            <h4 style="margin-top:0; color:#1a365d; border-bottom:2px solid #edf2f7; padding-bottom:8px;">📋 البطاقة الشخصية والمعلومات الإدارية الكاملة:</h4>
            <div class="info-grid">
                <div class="info-item"><b>الاسم الثلاثي:</b> {user_data.get('name')}</div>
                <div class="info-item"><b>تاريخ الميلاد:</b> {user_data.get('dob')}</div>
                <div class="info-item"><b>رقم السجل:</b> {user_data.get('register_no')}</div>
                <div class="info-item"><b>القضاء / بلدة النفوس:</b> {user_data.get('district')} / {user_data.get('town')}</div>
                <div class="info-item"><b>الوضع الوظيفي:</b> {user_data.get('job_status')}</div>
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

            function toggleStatus(label) {{
                setTimeout(() => {{
                    let checkbox = document.getElementById(label.getAttribute('for'));
                    if (checkbox.checked) {{
                        label.style.backgroundColor = "";
                        label.style.color = "";
                        label.innerText = "حاضر";
                    }} else {{
                        label.style.backgroundColor = "#e53e3e";
                        label.style.color = "white";
                        label.innerText = "غائب";
                    }}
                }}, 50);
            }}

            function submitAttendance(sessionId, teacherName, locationName) {{
                if (!navigator.geolocation) {{
                    alert("متصفحك لا يدعم تحديد الموقع الجغرافي GPS");
                    return;
                }}

                navigator.geolocation.getCurrentPosition(function(position) {{
                    let attendance = {{}};
                    document.querySelectorAll('input[id^="st_"]').forEach(cb => {{
                        let studentId = cb.id.replace('st_', '');
                        let label = document.querySelector(`label[for="st_${{studentId}}"]`);
                        let studentName = label.parentElement.previousElementSibling.innerText;
                        attendance[studentName] = cb.checked ? "حاضر" : "غائب";
                    }});

                    fetch('/teacher/submit_field_attendance', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{
                            session_id: sessionId,
                            sender_name: teacherName,
                            location: locationName,
                            attendance: attendance,
                            lat: position.coords.latitude,
                            lng: position.coords.longitude
                        }})
                    }})
                    .then(res => res.json())
                    .then(data => {{
                        alert(data.message);
                        if(data.success) location.reload();
                    }})
                    .catch(err => alert("حدث خطأ أثناء الاتصال."));
                }}, function(error) {{
                    alert("يجب تفعيل خدمة الـ GPS على هاتفك لتتمكن من إرسال الحضور وتأكيد تواجدك بالمستشفى/المدرسة.");
                }}, {{ enableHighAccuracy: true }});
            }}

            function playSubtleTone() {{
                try {{
                    if (!audioCtx) {{
                        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                    }}
                    let osc = audioCtx.createOscillator();
                    let gain = audioCtx.createGain();
                    osc.type = 'sine';
                    osc.frequency.setValueAtTime(659.25, audioCtx.currentTime);
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

@app.route('/teacher/submit_field_attendance', methods=['POST'])
def submit_field_attendance():
    if session.get('role') != 'teacher': return jsonify({"success": False, "message": "غير مصرح"}), 403
    
    data = request.json
    session_id = int(data.get('session_id'))
    sender_name = data.get('sender_name')
    location_name = data.get('location')
    attendance = data.get('attendance')
    user_lat = float(data.get('lat'))
    user_lng = float(data.get('lng'))

    # التحقق من الإحداثيات الجغرافية (Geofencing)
    if location_name in TRAINING_LOCATIONS:
        loc_data = TRAINING_LOCATIONS[location_name]
        distance = calculate_distance(user_lat, user_lng, loc_data['lat'], loc_data['lng'])
        if distance > loc_data['radius_meters']:
            return jsonify({
                "success": False, 
                "message": f"عذراً! أنت خارج نطاق موقع ({location_name}). المسافة الحالية عن الموقع هي {int(distance)} متر بينما النطاق المسموح هو {loc_data['radius_meters']} متر."
            }), 400

    session_item = next((s for s in field_sessions if s['id'] == session_id), None)
    if session_item:
        if session_item['status'] == "مكتملة":
            return jsonify({"success": False, "message": "تم إرسال تقرير الغياب لهذه الجلسة مسبقاً من قبل زميلك!"}), 400

        session_item['attendance'] = attendance
        session_item['submitted_by'] = sender_name
        session_item['status'] = "مكتملة"
        save_to_disk()
        return jsonify({"success": True, "message": "تم التحقق الجغرافي بالـ GPS بنجاح وحفظ حضور الطلاب وإرساله لمدير المعهد!"})
    
    return jsonify({"success": False, "message": "الجلسة غير متوفرة"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)