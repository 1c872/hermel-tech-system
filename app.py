import os
import json
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

DB_FILE = 'database.json'

teachers_db = {}
grades_db = {}            # { "student_name_subject_year": grade }
attendance_db = {}        # { "class_date_year": { "present": [], "absent": [] } }
teacher_classes_map = {}  # { "teacher_username": ["BP1 الكترونيك", "BT1 كهرباء"] }
classes_students = {
    "BP1 الكترونيك": ["علي أحمد شمص", "حسين محمد زعيتر", "حسن علي ناصرالدين", "عباس خليل علوه"],
    "BP2 معلوماتية": ["محمد حسين أمهز", "سارة يوسف دندش", "فاطمة أحمد طه", "جواد خضر خزعل"],
    "BT1 كهرباء": ["مهدي حسن مرتضى", "علي الرضا علوه", "زينب محمد شمص"],
    "BT2 الكترونيك": ["هادي أحمد ناصرالدين", "زين العابدين خزعل", "فاطمة علي أمهز"]
}

admin_replies = []
admin_credentials = {'username': 'admin', 'password': '123456'}

def save_to_disk():
    try:
        data = {
            'teachers_db': teachers_db,
            'grades_db': grades_db,
            'attendance_db': attendance_db,
            'teacher_classes_map': teacher_classes_map,
            'admin_replies': admin_replies,
            'admin_credentials': admin_credentials,
            'classes_students': classes_students
        }
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving database: {e}")

def load_from_disk():
    global teachers_db, grades_db, attendance_db, teacher_classes_map, admin_replies, admin_credentials, classes_students
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                teachers_db = data.get('teachers_db', {})
                grades_db = data.get('grades_db', {})
                attendance_db = data.get('attendance_db', {})
                teacher_classes_map = data.get('teacher_classes_map', {})
                admin_replies = data.get('admin_replies', [])
                admin_credentials = data.get('admin_credentials', {'username': 'admin', 'password': '123456'})
                classes_students = data.get('classes_students', classes_students)
                return True
        except Exception as e:
            print(f"Error loading database file: {e}")
    return False

def load_initial_teachers():
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
                    'job_status': str(row.get('الوضع الوظيفي', 'غير محدد')) if pd.notna(row.get('الوضع الوظيفي')) else 'غير محدد',
                    'subject': str(row.get('المادة التي يدرسها', 'غير محددة')) if pd.notna(row.get('المادة التي يدرسها')) else 'غير محددة',
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

@app.route('/manifest.json')
def manifest():
    return jsonify({
        "short_name": "معهد الهرمل",
        "name": "معهد الهرمل الفني",
        "icons": [{"src": ICON_URL, "type": "image/png", "sizes": "512x512"}],
        "start_url": "/",
        "background_color": "#0d47a1",
        "theme_color": "#0d47a1",
        "display": "standalone"
    })

@app.route('/sw.js')
def service_worker():
    return app.response_class("self.addEventListener('install', e => self.skipWaiting()); self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));", mimetype='application/javascript')

@app.route('/api/get_students/<class_name>')
def get_students(class_name):
    students = classes_students.get(class_name, ["طالب 1", "طالب 2", "طالب 3", "طالب 4"])
    return jsonify({'students': students})

# مسارات تنزيل نماذج الإكسل الفارغة
@app.route('/download_template/students')
def download_students_template():
    df = pd.DataFrame(columns=['الاسم الثلاثي', 'الصف'])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='الطلاب')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='نموذج_الطلاب_والصفوف.xlsx')

@app.route('/download_template/teachers')
def download_teachers_template():
    df = pd.DataFrame(columns=['الاسم الثلاثي', 'المادة', 'الصفوف'])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='مواد_الأساتذة')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='نموذج_مواد_صفوف_الأساتذة.xlsx')

@app.route('/download_template/monthly')
def download_monthly_template():
    df = pd.DataFrame(columns=['الاسم الثلاثي', 'عدد الحصص', 'عدد أيام النقل'])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='الحصص_والدوام')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='نموذج_الساعات_والدوام.xlsx')

PWA_HEAD = f'''
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#0d47a1">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <link rel="apple-touch-icon" href="{ICON_URL}">
    <script>if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js');</script>
'''

HEADER_VTE_HTML = '''
<div style="background:#0d47a1; color:white; padding:12px 20px; display:flex; justify-content:space-between; align-items:center; border-bottom:3px solid #1565c0;">
    <div style="display:flex; align-items:center; gap:12px;">
        <img src="https://cdn-icons-png.flaticon.com/512/3135/3135755.png" width="38" height="38" style="background:white; border-radius:50%; padding:2px;">
        <div>
            <div style="font-weight:bold; font-size:18px;">معهد الهرمل الفني</div>
            <div style="font-size:12px; color:#bbdefb;">رقم المعهد: 84 | العام الدراسي الحالي: 2026-2027</div>
        </div>
    </div>
    <div>
        <a href="/logout" style="color:#ffcdd2; text-decoration:none; font-weight:bold; font-size:13px; background:#c62828; padding:6px 12px; border-radius:4px;">تسجيل الخروج</a>
    </div>
</div>

<div style="background:#1565c0; padding:0 20px; display:flex; gap:5px; border-bottom:1px solid #1976d2; flex-wrap:wrap;">
    <a href="/admin" style="color:white; text-decoration:none; padding:12px 16px; font-weight:bold; font-size:14px; background:#0d47a1;">🏠 الرئيسية</a>
    
    <div class="dropdown">
        <button class="dropbtn">الطلاب ▾</button>
        <div class="dropdown-content">
            <a href="javascript:void(0)" onclick="showSection('studentAttendanceSec')">📋 حضور وغياب الطلاب</a>
            <a href="javascript:void(0)" onclick="showSection('studentGradesSec')">📝 علامات ونتائج الطلاب</a>
        </div>
    </div>

    <div class="dropdown">
        <button class="dropbtn">الأساتذة والدوام ▾</button>
        <div class="dropdown-content">
            <a href="javascript:void(0)" onclick="showSection('teacherHoursSec')">⏱️ الساعات المنفذة للأساتذة</a>
            <a href="javascript:void(0)" onclick="showSection('teacherDaysSec')">📅 أيام الحضور للأساتذة</a>
            <a href="javascript:void(0)" onclick="showSection('teacherScheduleSec')">📄 جدول الحصص PDF</a>
        </div>
    </div>

    <div class="dropdown">
        <button class="dropbtn">إعدادات وإدارة ▾</button>
        <div class="dropdown-content">
            <a href="javascript:void(0)" onclick="showSection('uploadStudentsSec')">👨‍🎓 رفع ملف الطلاب والصفوف (Excel)</a>
            <a href="javascript:void(0)" onclick="showSection('uploadTeacherClassesSec')">📚 رفع صفوف ومواد الأساتذة (Excel)</a>
            <a href="javascript:void(0)" onclick="showSection('importExcelSec')">📊 استيراد ملفات الحصص (Excel)</a>
            <a href="javascript:void(0)" onclick="showSection('sendNotifSec')">📢 إرسال تعميم / تنبيه</a>
            <a href="javascript:void(0)" onclick="showSection('changePassSec')">🔑 تغيير كلمة السر</a>
        </div>
    </div>
</div>

<style>
    .dropdown { position: relative; display: inline-block; }
    .dropbtn { background-color: #1565c0; color: white; padding: 12px 16px; font-size: 14px; border: none; cursor: pointer; font-weight: bold; font-family: inherit; }
    .dropdown:hover .dropbtn { background-color: #0d47a1; }
    .dropdown-content { display: none; position: absolute; background-color: #ffffff; min-width: 230px; box-shadow: 0px 8px 16px rgba(0,0,0,0.2); z-index: 100; border-radius: 0 0 6px 6px; }
    .dropdown-content a { color: #333; padding: 10px 15px; text-decoration: none; display: block; font-size: 13.5px; border-bottom: 1px solid #f0f0f0; }
    .dropdown-content a:hover { background-color: #e3f2fd; color: #0d47a1; font-weight: bold; }
    .dropdown:hover .dropdown-content { display: block; }
</style>
'''

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ''
    if request.method == 'POST':
        username = request.form.get('username').strip().lower()
        password = request.form.get('password').strip()
        
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
        <title>معهد الهرمل الفني - دخول النظام</title>
        {PWA_HEAD}
        <style>
            body {{ font-family: system-ui, sans-serif; background: #e3f2fd; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; flex-direction: column; }}
            .card {{ background: white; padding: 35px 25px; border-radius: 12px; width: 90%; max-width: 380px; text-align: center; box-shadow: 0 8px 20px rgba(13,71,161,0.15); border-top: 5px solid #0d47a1; }}
            h2 {{ color: #0d47a1; margin-bottom: 20px; font-size: 22px; margin-top: 10px; }}
            input {{ width: 100%; padding: 12px; margin: 8px 0; border: 1.5px solid #bbdefb; border-radius: 6px; box-sizing: border-box; text-align: right; font-size: 14px; }}
            button {{ width: 100%; padding: 12px; background: #0d47a1; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; margin-top: 10px; font-size: 15px; }}
            button:hover {{ background: #1565c0; }}
            .designer-tag {{ margin-top: 25px; color: #5c6bc0; font-size: 12px; font-weight: 500; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="card">
            <img src="https://cdn-icons-png.flaticon.com/512/3135/3135755.png" width="65" style="margin-bottom:5px;">
            <h2>معهد الهرمل الفني</h2>
            <form method="POST">
                <input type="text" name="username" placeholder="اسم المستخدم" required>
                <input type="password" name="password" placeholder="كلمة المرور" required>
                <button type="submit">دخول النظام</button>
            </form>
            <div style="color:#d32f2f; margin-top:12px; font-weight:bold; font-size:13px;">{error}</div>
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
        
        if action == 'upload_students':
            file = request.files.get('students_excel')
            if file and allowed_file(file.filename):
                try:
                    df_st = pd.read_excel(file)
                    new_classes = {}
                    for _, row in df_st.iterrows():
                        s_name = str(row.get('الاسم الثلاثي', row.get('اسم الطالب', ''))).strip()
                        c_name = str(row.get('الصف', row.get('الشعبة', ''))).strip()
                        if s_name and c_name and s_name != 'nan' and c_name != 'nan':
                            if c_name not in new_classes:
                                new_classes[c_name] = []
                            new_classes[c_name].append(s_name)
                    if new_classes:
                        classes_students.update(new_classes)
                        save_to_disk()
                        msg = "تم استيراد قائمة الطلاب والصفوف من ملف الإكسل بنجاح!"
                    else:
                        msg = "يرجى التأكد من أن الملف يحتوي على أعمدة (الاسم الثلاثي) و (الصف)."
                except Exception as e:
                    msg = f"خطأ في قراءة ملف الطلاب: {e}"

        elif action == 'upload_teacher_classes':
            file = request.files.get('teacher_classes_excel')
            if file and allowed_file(file.filename):
                try:
                    df_tc = pd.read_excel(file)
                    updated_count = 0
                    for _, row in df_tc.iterrows():
                        t_name = str(row.get('الاسم الثلاثي', row.get('اسم الأستاذ', ''))).strip()
                        subject = str(row.get('المادة', '')).strip()
                        classes_str = str(row.get('الصفوف', '')).strip()
                        
                        if not t_name: continue
                        classes_list = [c.strip() for c in classes_str.replace('،', ',').split(',') if c.strip()]
                        
                        for u, t_data in teachers_db.items():
                            if t_data['name'] == t_name or t_name in t_data['name']:
                                if subject: t_data['subject'] = subject
                                teacher_classes_map[u] = classes_list
                                updated_count += 1
                    save_to_disk()
                    msg = f"تم ربط المواد والصفوف لعدد ({updated_count}) أستاذ بنجاح!"
                except Exception as e:
                    msg = f"خطأ في الملف! يجب أن يحتوي على الأعمدة: (الاسم الثلاثي، المادة، الصفوف)."

        elif action == 'change_admin_password':
            new_pass = request.form.get('new_password').strip()
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
                                if 'monthly_data' not in t_data:
                                    t_data['monthly_data'] = {}
                                t_data['monthly_data'][month_name] = {'hours': hours, 'days': days}
                                updated_count += 1
                    save_to_disk()
                    msg = f"تم استيراد ملف الإكسل لشهر ({month_name}) بنجاح لعدد ({updated_count}) أستاذ!"
                except Exception as e:
                    msg = f"حدث خطأ أثناء قراءة الملف: {e}"

        elif action == 'send_notification':
            target_user = request.form.get('target_user')
            notif = request.form.get('notification_text')
            if target_user == 'all':
                for u, t in teachers_db.items():
                    t['notifications'].append(f"📢 تعميم إداري: {notif}")
                msg = "تم إرسال التعميم لجميع الأساتذة بنجاح!"
            elif target_user in teachers_db:
                teachers_db[target_user]['notifications'].append(notif)
                msg = f"تم إرسال التنبيه للأستاذ {teachers_db[target_user]['name']}!"
            save_to_disk()

        elif action == 'upload_pdf':
            target_user = request.form.get('target_user')
            file = request.files.get('pdf_file')
            if target_user in teachers_db and file and allowed_file(file.filename):
                filename = secure_filename(f"schedule_{target_user}.pdf")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                teachers_db[target_user]['schedule_pdf'] = filename
                save_to_disk()
                msg = f"تم رفع جدول التدريس PDF للأستاذ {teachers_db[target_user]['name']}!"

    hours_rows = ""
    days_rows = ""
    for username, t in teachers_db.items():
        m_hours = [f"<b>{m}:</b> {v.get('hours', 0)} حصة" for m, v in t.get('monthly_data', {}).items()]
        m_days = [f"<b>{m}:</b> {v.get('days', 0)} يوم" for m, v in t.get('monthly_data', {}).items()]
        assigned_cls = ", ".join(teacher_classes_map.get(username, [])) or "لم تحدد صفوفه بعد"
        
        hours_rows += f"<tr><td><b>{t['name']}</b><br><small>المادة: {t['subject']}</small><br><small style='color:#0d47a1;'>الصفوف: {assigned_cls}</small></td><td><b>{t['contract_hours']} ساعة</b></td><td>{' | '.join(m_hours) if m_hours else 'لم يرفع'}</td></tr>"
        days_rows += f"<tr><td><b>{t['name']}</b></td><td>{' | '.join(m_days) if m_days else 'لم يرفع'}</td></tr>"

    attendance_rows = ""
    for k, v in attendance_db.items():
        absent_str = ", ".join(v.get('absent', [])) if v.get('absent') else "حضور كامل (لا يوجد غياب)"
        attendance_rows += f"<tr><td><b>{k}</b></td><td style='color:#c62828; font-weight:bold;'>{absent_str}</td></tr>"

    return f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>معهد الهرمل الفني - لوحة الإدارة</title>
        {PWA_HEAD}
        <style>
            body {{ font-family: system-ui, sans-serif; background: #f4f6f9; margin: 0; padding-bottom: 30px; }}
            .container {{ padding: 20px; }}
            .card {{ background: white; padding: 20px; border-radius: 8px; margin-top: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); border-top: 4px solid #0d47a1; display: none; }}
            .card.active {{ display: block; }}
            input, select, textarea, button {{ padding: 10px; border: 1px solid #ccc; border-radius: 5px; text-align: right; font-size: 14px; width: 100%; box-sizing: border-box; margin-top: 8px; font-family: inherit; }}
            button {{ background: #0d47a1; color: white; font-weight: bold; cursor: pointer; border: none; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
            th, td {{ border: 1px solid #e0e0e0; padding: 10px; text-align: center; font-size: 13.5px; }}
            th {{ background: #0d47a1; color: white; }}
            .msg {{ background: #e8f5e9; color: #2e7d32; padding: 12px; border-radius: 6px; margin-bottom: 15px; font-weight: bold; border-right: 4px solid #2e7d32; }}
            .vte-box {{ background: #e3f2fd; padding: 15px; border-radius: 8px; border-right: 4px solid #1565c0; margin-bottom: 15px; font-size: 14px; line-height: 1.6; }}
            .excel-guide {{ background: #fff3e0; padding: 10px; border-radius: 6px; border-right: 4px solid #ff9800; font-size: 13px; margin-bottom: 10px; }}
            .btn-download {{ display: inline-block; background: #2e7d32; color: white; padding: 10px 15px; border-radius: 5px; text-decoration: none; font-weight: bold; font-size: 13.5px; text-align: center; margin-top: 8px; }}
            .btn-download:hover {{ background: #1b5e20; }}
        </style>
    </head>
    <body>
        {HEADER_VTE_HTML}

        <div class="container">
            {f'<div class="msg">{msg}</div>' if msg else ''}

            <div class="vte-box">
                🏛️ <b>بوابة معهد الهرمل الفني:</b> يمكنك تحميل نموذج إكسل فارغ بالأعمدة المطلوبة، تعبئته من ملفات المديرية، ثم رفعه لتحديث البيانات تلقائياً.
            </div>

            <!-- رفع ملف الطلاب -->
            <div id="uploadStudentsSec" class="card active">
                <h3 style="margin-top:0; color:#0d47a1;">👨‍🎓 رفع ملف إكسل الطلاب والصفوف (2026-2027)</h3>
                <div class="excel-guide">📌 الأعمدة المطلوبة في الإكسل: <code>الاسم الثلاثي</code> | <code>الصف</code></div>
                <a href="/download_template/students" class="btn-download">📥 تحميل نموذج إكسل فارغ (الطلاب)</a>
                <form method="POST" enctype="multipart/form-data" style="margin-top:10px;">
                    <input type="hidden" name="action" value="upload_students">
                    <input type="file" name="students_excel" accept=".xlsx,.xls" required>
                    <button type="submit" style="background:#2e7d32;">رفع واستيراد طلاب المعهد</button>
                </form>
            </div>

            <!-- رفع صفوف ومواد الأساتذة -->
            <div id="uploadTeacherClassesSec" class="card">
                <h3 style="margin-top:0; color:#0d47a1;">📚 رفع ملف إكسل مواد وصفوف الأساتذة (2026-2027)</h3>
                <div class="excel-guide">📌 الأعمدة المطلوبة في الإكسل: <code>الاسم الثلاثي</code> | <code>المادة</code> | <code>الصفوف</code></div>
                <a href="/download_template/teachers" class="btn-download">📥 تحميل نموذج إكسل فارغ (مواد الأساتذة)</a>
                <form method="POST" enctype="multipart/form-data" style="margin-top:10px;">
                    <input type="hidden" name="action" value="upload_teacher_classes">
                    <input type="file" name="teacher_classes_excel" accept=".xlsx,.xls" required>
                    <button type="submit" style="background:#2e7d32;">رفع وتأكيد توزيع الصفوف</button>
                </form>
            </div>

            <!-- حضور وغياب الطلاب -->
            <div id="studentAttendanceSec" class="card">
                <h3 style="margin-top:0; color:#0d47a1;">📋 سجل حضور وغياب الطلاب اليومي الموثق</h3>
                <table>
                    <tr><th>الصف والتاريخ والعام</th><th>الطلاب المتغيبون</th></tr>
                    {attendance_rows if attendance_rows else '<tr><td colspan="2">لم يتم تسجيل غياب بعد</td></tr>'}
                </table>
            </div>

            <!-- علامات ونتائج الطلاب -->
            <div id="studentGradesSec" class="card">
                <h3 style="margin-top:0; color:#0d47a1;">📝 علامات ونتائج الطلاب (من 20)</h3>
                <table>
                    <tr><th>اسم الطالب والمادة والعام</th><th>العلامة المعتمدة</th></tr>
                    {''.join([f'<tr><td><b>{k}</b></td><td><b style="color:#0d47a1;">{v} / 20</b></td></tr>' for k,v in grades_db.items()]) if grades_db else '<tr><td colspan="2">لم تُدخل علامات بعد</td></tr>'}
                </table>
            </div>

            <!-- الساعات المنفذة -->
            <div id="teacherHoursSec" class="card">
                <h3 style="margin-top:0; color:#0d47a1;">⏱️ الساعات المنفذة للأساتذة والصفوف الموكلة</h3>
                <table>
                    <tr><th>اسم الأستاذ والصفوف</th><th>عقد الساعات</th><th>الساعات المنفذة شهرياً</th></tr>
                    {hours_rows}
                </table>
            </div>

            <!-- أيام الحضور -->
            <div id="teacherDaysSec" class="card">
                <h3 style="margin-top:0; color:#0d47a1;">📅 أيام الحضور والدوام للأساتذة</h3>
                <table>
                    <tr><th>اسم الأستاذ</th><th>أيام بدل النقل والحضور شهرياً</th></tr>
                    {days_rows}
                </table>
            </div>

            <!-- رفع الجدول PDF -->
            <div id="teacherScheduleSec" class="card">
                <h3 style="margin-top:0; color:#0d47a1;">📄 رفع جدول التدريس الأسبوعي (PDF)</h3>
                <form method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="action" value="upload_pdf">
                    <select name="target_user" required>
                        {''.join([f'<option value="{u}">{t["name"]} ({t["subject"]})</option>' for u,t in teachers_db.items()])}
                    </select>
                    <input type="file" name="pdf_file" accept=".pdf" required>
                    <button type="submit">رفع ملف جدول PDF</button>
                </form>
            </div>

            <!-- استيراد ملف الحصص الشهري -->
            <div id="importExcelSec" class="card">
                <h3 style="margin-top:0; color:#0d47a1;">📊 استيراد ملف إكسل الحصص والدوام الشهري</h3>
                <div class="excel-guide">📌 الأعمدة المطلوبة: <code>الاسم الثلاثي</code> | <code>عدد الحصص</code> | <code>عدد أيام النقل</code></div>
                <a href="/download_template/monthly" class="btn-download">📥 تحميل نموذج إكسل فارغ (الحصص والدوام)</a>
                <form method="POST" enctype="multipart/form-data" style="margin-top:10px;">
                    <input type="hidden" name="action" value="upload_monthly_excel">
                    <input type="text" name="month_name" placeholder="اسم الشهر (مثال: تشرين الأول)" required>
                    <input type="file" name="monthly_excel" accept=".xlsx,.xls" required>
                    <button type="submit" style="background:#2e7d32;">تحديث الحصص وأيام الحضور</button>
                </form>
            </div>

            <!-- إرسال تعميم -->
            <div id="sendNotifSec" class="card">
                <h3 style="margin-top:0; color:#0d47a1;">📢 إرسال تعميم إداري أو تنبيه خاص</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="send_notification">
                    <select name="target_user" required>
                        <option value="all">📢 تعميم عام لكل الأساتذة</option>
                        {''.join([f'<option value="{u}">{t["name"]}</option>' for u,t in teachers_db.items()])}
                    </select>
                    <textarea name="notification_text" placeholder="اكتب نص التعميم الإداري..." required style="height:80px;"></textarea>
                    <button type="submit">إرسال التعميم</button>
                </form>
            </div>

            <!-- تغيير كلمة السر -->
            <div id="changePassSec" class="card">
                <h3 style="margin-top:0; color:#0d47a1;">🔑 تغيير كلمة مرور الإدارة</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="change_admin_password">
                    <input type="password" name="new_password" placeholder="كلمة المرور الجديدة" required>
                    <button type="submit" style="background:#c62828;">تحديث كلمة المرور</button>
                </form>
            </div>
        </div>

        <div style="text-align:center; margin-top:30px; color:#666; font-size:12.5px;">🛠️ تم تصميم وتطوير البرنامج من قبل الأستاذ محمد حسين شمص</div>

        <script>
            function showSection(secId) {{
                document.querySelectorAll('.card').forEach(el => el.classList.remove('active'));
                let target = document.getElementById(secId);
                if(target) target.classList.add('active');
            }}
        </script>
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
        
        if action == 'submit_class_grades':
            class_name = request.form.get('class_name')
            subject = user_data.get('subject', 'مادة عامة')
            students = classes_students.get(class_name, [])
            
            saved_count = 0
            for student in students:
                grade_val = request.form.get(f"grade_{student}")
                if grade_val:
                    grades_db[f"{student} - {class_name} ({subject}) [2026-2027]"] = grade_val
                    saved_count += 1
            save_to_disk()
            msg = f"تم رصد وحفظ علامات ({saved_count}) طلاب لصف ({class_name}) للعام الحالي (2026-2027) بنجاح!"

        elif action == 'submit_class_attendance':
            class_name = request.form.get('class_name')
            students = classes_students.get(class_name, [])
            present_students = request.form.getlist('attendance_check')
            
            absent_students = [s for s in students if s not in present_students]
            date_key = pd.Timestamp.now().strftime('%Y-%m-%d')
            
            attendance_db[f"صف: {class_name} ({date_key}) [2026-2027]"] = {
                'present': present_students,
                'absent': absent_students
            }
            save_to_disk()
            msg = f"تم توثيق الحضور والغياب لصف ({class_name}) للعام الحالي (2026-2027): عدد المتغيبين ({len(absent_students)}) طالب!"

    notifs_list = user_data.get('notifications', [])
    notifs_html = "".join([f"<div style='background:#e3f2fd; border-right:4px solid #1565c0; padding:10px; margin-bottom:6px; font-weight:bold; color:#0d47a1;'>🔔 {n}</div>" for n in notifs_list])
    
    total_hours = sum([v.get('hours', 0) for v in user_data.get('monthly_data', {}).values()])
    total_days = sum([v.get('days', 0) for v in user_data.get('monthly_data', {}).values()])
    contract_total = user_data.get('contract_hours', 0)
    remaining_hours = max(0, contract_total - total_hours)

    pdf_link = f"<a href='/uploads/{user_data['schedule_pdf']}' target='_blank' style='background:#0d47a1; color:white; padding:8px 12px; border-radius:5px; text-decoration:none; font-weight:bold;'>📄 عرض جدول الحصص PDF</a>" if user_data.get('schedule_pdf') else "لم يرفع الجدول بعد"

    my_classes = teacher_classes_map.get(username, list(classes_students.keys()))
    class_options = "".join([f'<option value="{c}">{c}</option>' for c in my_classes])

    return f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>صفحة الأستاذ - معهد الهرمل الفني</title>
        {PWA_HEAD}
        <style>
            body {{ font-family: system-ui, sans-serif; background: #f4f6f9; margin: 0; padding-bottom:30px; }}
            .card {{ background: white; padding: 18px; border-radius: 8px; margin-top: 15px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); border-top: 4px solid #0d47a1; }}
            input, select, textarea, button {{ padding: 10px; border: 1px solid #ccc; border-radius: 5px; text-align: right; font-size: 14px; width: 100%; box-sizing: border-box; margin-top: 6px; font-family: inherit; }}
            button {{ background: #0d47a1; color: white; font-weight: bold; cursor: pointer; border: none; }}
            .sum-card {{ flex: 1; background: #e3f2fd; padding: 12px; border-radius: 6px; text-align: center; border:1px solid #bbdefb; }}
            .student-row {{ display: flex; justify-content: space-between; align-items: center; padding: 10px; border-bottom: 1px solid #eee; background: #fafafa; margin-top: 5px; border-radius: 4px; }}
            @media print {{ body {{ background: white; }} .no-print {{ display: none !important; }} }}
        </style>
    </head>
    <body>
        <div style="background:#0d47a1; color:white; padding:12px 20px; display:flex; justify-content:space-between; align-items:center;" class="no-print">
            <div>
                <h3 style="margin:0; font-size:18px;">معهد الهرمل الفني</h3>
                <small style="color:#bbdefb;">الأستاذ: {user_data.get('name')} ({user_data.get('subject')})</small>
            </div>
            <a href="/logout" style="color:#ffcdd2; text-decoration:none; font-weight:bold; background:#c62828; padding:6px 12px; border-radius:4px; font-size:12px;">خروج</a>
        </div>

        <div style="padding:15px;">
            {f'<div style="background:#e8f5e9; color:#2e7d32; padding:10px; border-radius:6px; margin-bottom:10px; font-weight:bold;" class="no-print">{msg}</div>' if msg else ''}

            <div class="card no-print">
                <h4 style="margin-top:0; color:#0d47a1;">📢 التعاميم والتنبيهات الواردة:</h4>
                {notifs_html if notifs_html else '<p style="color:#666;">لا توجد تعاميم جديدة.</p>'}
            </div>

            <!-- اختيار العام لاستخراج السجلات فقط -->
            <div class="card no-print" style="border-top: 4px solid #f57c00;">
                <h4 style="margin-top:0; color:#e65100;">📊 استخراج معلومات وسجلات الأعوام الدراسية:</h4>
                <p style="font-size:12px; color:#666; margin-bottom:4px;">تنبيه: إدخال البيانات الجديدة يتم حصراً للعام الحالي (2026-2027).</p>
                <select id="academicYearSelect" style="font-weight:bold; color:#0d47a1;">
                    <option value="2026-2027">العام الحالي (2026-2027)</option>
                    <option value="2025-2026">سجلات العام السابق (2025-2026)</option>
                    <option value="2027-2028">سجلات العام القادم (2027-2028)</option>
                </select>
            </div>

            <div class="card no-print">
                <h4 style="margin-top:0; color:#0d47a1;">📊 الساعات المنفذة وأيام الدوام:</h4>
                <div style="display:flex; gap:10px; flex-wrap:wrap;">
                    <div class="sum-card">الساعات المنفذة: <br><b style="font-size:18px; color:#0d47a1;">{total_hours} حصة</b></div>
                    <div class="sum-card">أيام الحضور: <br><b style="font-size:18px; color:#2e7d32;">{total_days} يوم</b></div>
                    <div class="sum-card">المتبقي من العقد: <br><b style="font-size:18px; color:#c62828;">{remaining_hours} ساعة</b></div>
                </div>
            </div>

            <div class="card no-print">
                <h4 style="margin-top:0; color:#0d47a1;">📅 جدول الحصص الأسبوعي:</h4>
                {pdf_link}
            </div>

            <!-- توثيق حضور وغياب الطلاب -->
            <div class="card no-print">
                <h4 style="margin-top:0; color:#0d47a1;">📋 توثيق حضور وغياب الطلاب (للعام الحالي 2026-2027):</h4>
                <form method="POST">
                    <input type="hidden" name="action" value="submit_class_attendance">
                    <label style="font-size:13px; font-weight:bold;">1. اختر الصف والشعبة:</label>
                    <select name="class_name" id="attendanceClassSelect" onchange="loadAttendanceStudents()" required>
                        <option value="">-- اختر صفاً من صفوفك --</option>
                        {class_options}
                    </select>

                    <div id="attendanceStudentsContainer" style="margin-top:15px;"></div>
                    <button type="submit" id="attendanceSubmitBtn" style="display:none; background:#2e7d32; margin-top:15px;">حفظ وتأكيد الحضور والغياب</button>
                </form>
            </div>

            <!-- إدخال العلامات واستخراج التقرير -->
            <div class="card">
                <h4 style="margin-top:0; color:#0d47a1;" class="no-print">📝 إدخال علامات الطلاب ورصدها (مادة: {user_data.get('subject')} - عام 2026-2027):</h4>
                <form method="POST">
                    <input type="hidden" name="action" value="submit_class_grades">
                    <label style="font-size:13px; font-weight:bold;" class="no-print">1. اختر الصف والشعبة:</label>
                    <select name="class_name" id="gradesClassSelect" onchange="loadGradesStudents()" required class="no-print">
                        <option value="">-- اختر صفاً من صفوفك --</option>
                        {class_options}
                    </select>

                    <div id="gradesStudentsContainer" style="margin-top:15px;"></div>
                    <div style="display:flex; gap:10px;">
                        <button type="submit" id="gradesSubmitBtn" style="display:none; background:#0d47a1; margin-top:15px; flex:2;">حفظ ورصد علامات الصف</button>
                        <button type="button" id="printReportBtn" onclick="window.print()" style="display:none; background:#2e7d32; margin-top:15px; flex:1;">📄 استخراج تقرير علامات الصف (طباعة / PDF)</button>
                    </div>
                </form>
            </div>
        </div>

        <div style="text-align:center; margin-top:20px; color:#666; font-size:12.5px;" class="no-print">🛠️ تم تصميم وتطوير البرنامج من قبل الأستاذ محمد حسين شمص</div>

        <script>
            function loadAttendanceStudents() {{
                let className = document.getElementById('attendanceClassSelect').value;
                let container = document.getElementById('attendanceStudentsContainer');
                let submitBtn = document.getElementById('attendanceSubmitBtn');
                container.innerHTML = '';

                if (!className) {{
                    submitBtn.style.display = 'none';
                    return;
                }}

                fetch('/api/get_students/' + encodeURIComponent(className))
                    .then(res => res.json())
                    .then(data => {{
                        let html = '<p style="font-size:13px; color:#0d47a1; font-weight:bold;">جميع الطلاب محددون كـ "حاضر" ✅. أزل علامة الصح عن الطالب المتغيب:</p>';
                        data.students.forEach(student => {{
                            html += `
                            <div class="student-row">
                                <span style="font-weight:bold;">${{student}}</span>
                                <label style="cursor:pointer; font-size:13px; color:#2e7d32; font-weight:bold;">
                                    <input type="checkbox" name="attendance_check" value="${{student}}" checked style="width:auto; transform:scale(1.3); margin-left:8px;"> حاضر
                                </label>
                            </div>`;
                        }});
                        container.innerHTML = html;
                        submitBtn.style.display = 'block';
                    }});
            }}

            function loadGradesStudents() {{
                let className = document.getElementById('gradesClassSelect').value;
                let container = document.getElementById('gradesStudentsContainer');
                let submitBtn = document.getElementById('gradesSubmitBtn');
                let printBtn = document.getElementById('printReportBtn');
                container.innerHTML = '';

                if (!className) {{
                    submitBtn.style.display = 'none';
                    printBtn.style.display = 'none';
                    return;
                }}

                fetch('/api/get_students/' + encodeURIComponent(className))
                    .then(res => res.json())
                    .then(data => {{
                        let html = '<h3 style="text-align:center; color:#0d47a1;">معهد الهرمل الفني - كشف علامات صف (' + className + ') للعام الدراسي 2026-2027<br><small style="color:#555;">المادة: {user_data.get('subject')}</small></h3>';
                        html += '<p style="font-size:13px; color:#0d47a1; font-weight:bold;" class="no-print">أدخل علامة كل طالب من 20:</p>';
                        data.students.forEach(student => {{
                            html += `
                            <div class="student-row">
                                <span style="font-weight:bold; flex:1;">${{student}}</span>
                                <input type="number" step="0.5" min="0" max="20" name="grade_${{student}}" placeholder="العلامة من 20" style="width:120px; margin:0;" required>
                            </div>`;
                        }});
                        container.innerHTML = html;
                        submitBtn.style.display = 'block';
                        printBtn.style.display = 'block';
                    }});
            }}
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
    return redirect(url_for('logout'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)