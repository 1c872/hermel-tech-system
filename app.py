import os
import json
import io
import math
import shutil
import pandas as pd
from datetime import datetime, time
from flask import Flask, render_template_string, request, redirect, url_for, session, send_from_directory, send_file, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'hermel_tech_school_shams_secret_key_2026'

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'xlsx', 'xls'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_FILE = 'database.json'
BACKUP_FILE = 'database_backup.json'

# قاعدة بيانات مواقع التدريب الميداني وإحداثيات الـ GPS ونطاق الأمان (بالأمتار)
TRAINING_LOCATIONS = {
    "مستشفى الهرمل الحكومي": {"lat": 34.381283, "lng": 36.424456, "radius_meters": 300},
    "مستشفى البتول": {"lat": 34.381283, "lng": 36.424456, "radius_meters": 300},
    "مستشفى دار الكرامة": {"lat": 34.403492, "lng": 36.396789, "radius_meters": 250},
    "مستشفى العاصي": {"lat": 34.398330, "lng": 36.406490, "radius_meters": 250},
    "مدرسة سانرايز": {"lat": 34.403492, "lng": 36.396789, "radius_meters": 200},
    "ثانوية الرشاد": {"lat": 34.403826, "lng": 36.391736, "radius_meters": 200},
    "مدرسة الإمام علي": {"lat": 34.395518, "lng": 36.386411, "radius_meters": 200}
}

teachers_db = {}
grades_db = {}            
attendance_db = {}        
teacher_classes_map = {}  
classes_students = {}
admin_replies = []
admin_credentials = {'username': 'admin', 'password': '123456'}

academic_years_db = ["2025-2026", "2026-2027", "2027-2028", "2028-2029"]
current_academic_year = "2026-2027"

students_db = []
field_sessions = []
teacher_absences_log = []

def calculate_distance(lat1, lon1, lat2, lon2):
    """حساب المسافة بالمتر بين نقطتين جغرافيتين باستخدام معادلة Haversine"""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def save_to_disk():
    try:
        data = {
            'teachers_db': teachers_db,
            'grades_db': grades_db,
            'attendance_db': attendance_db,
            'teacher_classes_map': teacher_classes_map,
            'admin_replies': admin_replies,
            'admin_credentials': admin_credentials,
            'classes_students': classes_students,
            'academic_years_db': academic_years_db,
            'current_academic_year': current_academic_year,
            'students_db': students_db,
            'field_sessions': field_sessions,
            'teacher_absences_log': teacher_absences_log
        }
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        shutil.copyfile(DB_FILE, BACKUP_FILE)
    except Exception as e:
        print(f"Error saving database: {e}")

def load_from_disk():
    global teachers_db, grades_db, attendance_db, teacher_classes_map, admin_replies, admin_credentials, classes_students
    global academic_years_db, current_academic_year, students_db, field_sessions, teacher_absences_log
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
                classes_students = data.get('classes_students', {})
                academic_years_db = data.get('academic_years_db', academic_years_db)
                current_academic_year = data.get('current_academic_year', current_academic_year)
                students_db = data.get('students_db', [])
                field_sessions = data.get('field_sessions', [])
                teacher_absences_log = data.get('teacher_absences_log', [])
                return True
        except Exception as e:
            print(f"Error loading database file: {e}")
    return False

if not load_from_disk():
    # بيانات أولية افتراضية في حال عدم وجود ملف قاعدة بيانات لتسهيل التجربة فوراً
    classes_students = {
        "سنة ثالثة عناية تمريضية": ["علي أحمد شمص", "حسن محمد زعيتر", "ميرا شمص", "سيلا شمص"],
        "سنة ثانية معلوماتية": ["محمد حسين أمهز", "سارة يوسف دندش"]
    }
    teachers_db = {
        "teacher_1": {"name": "أحمد خضر", "password": "123", "subject": "تمريض", "device_id": "", "notifications": [], "monthly_data": {"كانون الأول": {"hours": 40, "days": 12}}, "contract_hours": 300, "schedule_pdf": None},
        "teacher_2": {"name": "علي ناصرالدين", "password": "123", "subject": "إ معلوماتية", "device_id": "", "notifications": [], "monthly_data": {"كانون الأول": {"hours": 35, "days": 10}}, "contract_hours": 300, "schedule_pdf": None}
    }
    teacher_classes_map = {"teacher_1": ["سنة ثالثة عناية تمريضية"], "teacher_2": ["سنة ثانية معلوماتية"]}
    save_to_disk()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

ICON_URL = "https://cdn-icons-png.flaticon.com/512/3135/3135755.png"

# القائمة المنسدلة الاحترافية والمنظمة للإدارة
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
            <a href="javascript:void(0)" onclick="showSection('teachersListSec')">👨‍🏫 سجل الأساتذة والجدول</a>
        </div>
    </div>

    <div class="dropdown">
        <button class="dropbtn">التدريب الميداني والـ GPS ▾</button>
        <div class="dropdown-content">
            <a href="javascript:void(0)" onclick="showSection('fieldSessionSec')">🏥 إضافة وإدارة الجلسات الميدانية</a>
        </div>
    </div>

    <div class="dropdown">
        <button class="dropbtn">إعدادات وإدارة ▾</button>
        <div class="dropdown-content">
            <a href="javascript:void(0)" onclick="showSection('uploadStudentsSec')">👨‍🎓 رفع ملف الطلاب (Excel)</a>
            <a href="javascript:void(0)" onclick="showSection('deviceBindingSec')">📱 إدارة أجهزة الأساتذة (فك الربط)</a>
            <a href="javascript:void(0)" onclick="showSection('sendNotifSec')">📢 إرسال تعميم / تنبيه</a>
            <a href="javascript:void(0)" onclick="showSection('teacherRepliesSec')">📩 الرسائل والأعذار الواردة</a>
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
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '').strip()
        current_device_fingerprint = request.headers.get('User-Agent', 'unknown_device')
        
        if username == admin_credentials['username'] and password == admin_credentials['password']:
            session['username'] = 'admin'
            session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))
        elif username in teachers_db and teachers_db[username]['password'] == password:
            t_data = teachers_db[username]
            
            # نظام حماية الجهاز (Device Binding)
            if not t_data.get('device_id'):
                t_data['device_id'] = current_device_fingerprint
                save_to_disk()
            elif t_data.get('device_id') != current_device_fingerprint:
                error = 'عذراً، هذا الحساب مرتبط بهاتف آخر. يراجع مدير المعهد لإعادة ضبط الجهاز.'
                return render_template_string(login_template, error=error)

            session['username'] = username
            session['role'] = 'teacher'
            return redirect(url_for('teacher_dashboard'))
        else:
            error = 'اسم المستخدم أو كلمة المرور غير صحيحة'
            
    return render_template_string(login_template, error=error)

login_template = '''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>معهد الهرمل الفني - تسجيل الدخول</title>
        <style>
            body { font-family: system-ui, sans-serif; background: #e3f2fd; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; flex-direction: column; }
            .card { background: white; padding: 35px 25px; border-radius: 12px; width: 90%; max-width: 380px; text-align: center; box-shadow: 0 8px 20px rgba(13,71,161,0.15); border-top: 5px solid #0d47a1; }
            h2 { color: #0d47a1; margin-bottom: 20px; font-size: 22px; }
            input { width: 100%; padding: 12px; margin: 8px 0; border: 1.5px solid #bbdefb; border-radius: 6px; box-sizing: border-box; text-align: right; font-size: 14px; }
            button { width: 100%; padding: 12px; background: #0d47a1; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; margin-top: 10px; font-size: 15px; }
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
            <div style="color:#d32f2f; margin-top:12px; font-weight:bold; font-size:13px;">{{ error }}</div>
        </div>
        <div style="margin-top: 25px; color: #5c6bc0; font-size: 12px;">🛠️ تم تصميم وتطوير البرنامج من قبل الأستاذ محمد حسين شمص</div>
    </body>
    </html>
'''

@app.route('/api/get_students/<path:class_name>')
def get_students(class_name):
    students = classes_students.get(class_name, [])
    return jsonify({'students': students})

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
    session['msg'] = "تم تكليف جلسة التدريب الميداني بنجاح!"
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_reply/<int:reply_id>', methods=['POST'])
def delete_reply(reply_id):
    if session.get('role') == 'admin' and 0 <= reply_id < len(admin_replies):
        admin_replies.pop(reply_id)
        save_to_disk()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    msg = session.pop('msg', '')
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'upload_students':
            file = request.files.get('excel_file')
            if file and allowed_file(file.filename):
                try:
                    df = pd.read_excel(file)
                    new_classes = {}
                    for _, row in df.iterrows():
                        c_name = str(row.get('الصف', row.get('Class', ''))).strip()
                        s_name = str(row.get('اسم الطالب', row.get('Student', ''))).strip()
                        if c_name and s_name and c_name != 'nan':
                            if c_name not in new_classes:
                                new_classes[c_name] = []
                            if s_name not in new_classes[c_name]:
                                new_classes[c_name].append(s_name)
                    if new_classes:
                        classes_students.update(new_classes)
                        save_to_disk()
                        msg = "تم استيراد الطلاب والصفوف بنجاح!"
                except Exception as e:
                    msg = f"خطأ في قراءة ملف الإكسل: {e}"

        elif action == 'reset_teacher_device':
            target_user = request.form.get('target_user')
            if target_user in teachers_db:
                teachers_db[target_user]['device_id'] = ''
                save_to_disk()
                msg = f"تم مسح بصمة الجهاز للأستاذ ({teachers_db[target_user]['name']}) بنجاح!"

        elif action == 'send_notification':
            target_user = request.form.get('target_user')
            notif = request.form.get('notification_text')
            if target_user == 'all':
                for u, t in teachers_db.items():
                    t['notifications'].append(f"📢 تعميم: {notif}")
                msg = "تم إرسال التعميم لجميع الأساتذة!"
            elif target_user in teachers_db:
                teachers_db[target_user]['notifications'].append(notif)
                msg = f"تم إرسال الإشعار للأستاذ بنجاح!"
            save_to_disk()

        elif action == 'change_admin_password':
            new_pass = request.form.get('new_password').strip()
            if new_pass:
                admin_credentials['password'] = new_pass
                save_to_disk()
                msg = "تم تغيير كلمة مرور الإدارة بنجاح!"

    attendance_rows = "".join([f"<tr><td><b>{k}</b></td><td style='color:#c62828;'>متغيبون: {v.get('absent', [])}</td></tr>" for k, v in attendance_db.items()])
    grades_rows = "".join([f"<tr><td><b>{k}</b></td><td><b style='color:#0d47a1;'>{v} / 20</b></td></tr>" for k, v in grades_db.items()])
    
    teachers_rows = "".join([f"<tr><td><b>{t['name']}</b><br><small>{t['subject']}</small></td><td>{t['contract_hours']} ساعة</td></tr>" for u, t in teachers_db.items()])
    
    field_rows = ""
    for fs in reversed(field_sessions):
        stat = "<span style='color:#2e7d32; font-weight:bold;'>مكتملة بالـ GPS</span>" if fs['status']=='مكتملة' else "<span style='color:#e65100;'>قيد الانتظار</span>"
        field_rows += f"<tr><td><b>{fs['location']}</b><br><small>{fs['class_name']}</small></td><td>{fs['primary_teacher']}</td><td>{stat}</td></tr>"

    replies_html = ""
    for idx, r in enumerate(reversed(admin_replies)):
        real_idx = len(admin_replies) - 1 - idx
        replies_html += f"""
        <div style="background:#fff3e0; border-right:4px solid #e65100; padding:10px; margin-bottom:8px; border-radius:6px; display:flex; justify-content:space-between; align-items:center;">
            <div><b>من: {r['teacher_name']}</b><br>{r['message']}</div>
            <form method="POST" action="/admin/delete_reply/{real_idx}" style="margin:0;"><button type="submit" style="background:#c62828; padding:5px 10px; width:auto;">مسح</button></form>
        </div>
        """

    teacher_opts = "".join([f"<option value='{u}'>{t['name']} ({u})</option>" for u, t in teachers_db.items()])
    locations_opts = "".join([f"<option value='{loc}'>{loc}</option>" for loc in TRAINING_LOCATIONS.keys()])

    return render_template_string('''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>لوحة الإدارة - معهد الهرمل الفني</title>
        <style>
            body { font-family: system-ui, sans-serif; background: #f4f6f9; margin: 0; padding-bottom: 30px; }
            .container { padding: 20px; }
            .card { background: white; padding: 20px; border-radius: 8px; margin-top: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); border-top: 4px solid #0d47a1; display: none; }
            .card.active { display: block; }
            input, select, textarea, button { width: 100%; padding: 10px; margin-top: 6px; box-sizing: border-box; font-family: inherit; }
            button { background: #0d47a1; color: white; border: none; font-weight: bold; cursor: pointer; border-radius: 5px; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { border: 1px solid #e0e0e0; padding: 9px; text-align: center; font-size: 13.5px; }
            th { background: #0d47a1; color: white; }
        </style>
    </head>
    <body>
        ''' + HEADER_VTE_HTML + '''

        <div class="container">
            {% if msg %}<div style="background:#e8f5e9; color:#2e7d32; padding:12px; border-radius:6px; font-weight:bold; margin-bottom:15px;">{{ msg }}</div>{% endif %}

            <!-- حضور وغياب الطلاب -->
            <div id="studentAttendanceSec" class="card active">
                <h3 style="color:#0d47a1; margin-top:0;">📋 سجل حضور وغياب الطلاب</h3>
                <table>
                    <tr><th>الصف والتاريخ</th><th>الطلاب المتغيبون</th></tr>
                    {{ attendance_rows | safe if attendance_rows else '<tr><td colspan="2">لا توجد بيانات غياب مسجلة</td></tr>' }}
                </table>
            </div>

            <!-- علامات ونتائج الطلاب -->
            <div id="studentGradesSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">📝 علامات ونتائج الطلاب (من 20)</h3>
                <table>
                    <tr><th>اسم الطالب والمادة</th><th>العلامة</th></tr>
                    {{ grades_rows | safe if grades_rows else '<tr><td colspan="2">لم تُدخل علامات بعد</td></tr>' }}
                </table>
            </div>

            <!-- سجل الأساتذة -->
            <div id="teachersListSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">👨‍🏫 سجل الأساتذة والجدول</h3>
                <table>
                    <tr><th>اسم الأستاذ والمادة</th><th>عقد الساعات</th></tr>
                    {{ teachers_rows | safe }}
                </table>
            </div>

            <!-- التدريب الميداني والـ GPS -->
            <div id="fieldSessionSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">🏥 تكليف وإدارة التدريب الميداني (GPS)</h3>
                <form action="/admin/create_field_session" method="POST">
                    <label>المكان:</label>
                    <select name="location" required>{{ locations_opts | safe }}</select>
                    <label>الصف:</label>
                    <input type="text" name="class_name" placeholder="سنة ثالثة عناية" required>
                    <label>الاختصاص:</label>
                    <input type="text" name="major" placeholder="تمريض" required>
                    <label>الأستاذ المشرف:</label>
                    <select name="primary_teacher" required>{{ teacher_opts | safe }}</select>
                    <button type="submit" style="background:#1565c0; margin-top:10px;">حفظ وتكليف الجلسة</button>
                </form>
                <h4 style="margin-top:20px; color:#0d47a1;">سجل الجلسات الميدانية:</h4>
                <table>
                    <tr><th>المكان والصف</th><th>المشرف</th><th>الحالة</th></tr>
                    {{ field_rows | safe if field_rows else '<tr><td colspan="3">لا توجد جلسات</td></tr>' }}
                </table>
            </div>

            <!-- رفع الطلاب Excel -->
            <div id="uploadStudentsSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">👨‍🎓 رفع ملف الطلاب والصفوف (Excel)</h3>
                <form method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="action" value="upload_students">
                    <input type="file" name="excel_file" accept=".xlsx, .xls" required>
                    <button type="submit" style="margin-top:10px; background:#2e7d32;">رفع واستيراد الطلاب</button>
                </form>
            </div>

            <!-- فك ربط أجهزة الأساتذة -->
            <div id="deviceBindingSec" class="card">
                <h3 style="color:#c62828; margin-top:0;">📱 إدارة أجهزة الأساتذة (فك ربط الجهاز)</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="reset_teacher_device">
                    <select name="target_user" required><option value="">-- اختر الأستاذ --</option>{{ teacher_opts | safe }}</select>
                    <button type="submit" style="margin-top:10px; background:#c62828;">🔓 السماح بتسجيل هاتف جديد للأستاذ</button>
                </form>
            </div>

            <!-- إرسال تعميم -->
            <div id="sendNotifSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">📢 إرسال تعميم إداري</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="send_notification">
                    <select name="target_user" required><option value="all">📢 إرسال للجميع</option>{{ teacher_opts | safe }}</select>
                    <textarea name="notification_text" placeholder="اكتب التعميم..." required style="height:70px;"></textarea>
                    <button type="submit" style="margin-top:10px;">إرسال</button>
                </form>
            </div>

            <!-- الرسائل والأعذار -->
            <div id="teacherRepliesSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">📩 الأعذار والرسائل الواردة</h3>
                {{ replies_html | safe if replies_html else '<p>لا توجد رسائل.</p>' }}
            </div>

            <!-- تغيير كلمة السر -->
            <div id="changePassSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">🔑 تغيير كلمة السر الإدارية</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="change_admin_password">
                    <input type="password" name="new_password" placeholder="كلمة المرور الجديدة" required>
                    <button type="submit" style="background:#c62828; margin-top:10px;">تحديث</button>
                </form>
            </div>
        </div>

        <script>
            function showSection(secId) {
                document.querySelectorAll('.card').forEach(el => el.classList.remove('active'));
                let target = document.getElementById(secId);
                if(target) target.classList.add('active');
            }
        </script>
    </body>
    </html>
    ''', attendance_rows=attendance_rows, grades_rows=grades_rows, teachers_rows=teachers_rows, field_rows=field_rows, replies_html=replies_html, teacher_opts=teacher_opts, locations_opts=locations_opts, msg=msg)

@app.route('/teacher', methods=['GET', 'POST'])
def teacher_dashboard():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    
    username = session.get('username')
    user_data = teachers_db.get(username, {})
    t_name = user_data.get('name', '')
    msg = ''

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'submit_class_grades':
            class_name = request.form.get('class_name')
            subject = user_data.get('subject', 'عام')
            students = classes_students.get(class_name, [])
            for st in students:
                val = request.form.get(f"grade_{st}")
                if val:
                    grades_db[f"{st} - {class_name} ({subject})"] = val
            save_to_disk()
            msg = "تم حفظ ورصد علامات الطلاب بنجاح!"

        elif action == 'submit_class_attendance':
            class_name = request.form.get('class_name')
            students = classes_students.get(class_name, [])
            present_sts = request.form.getlist('attendance_check')
            absent_sts = [s for s in students if s not in present_sts]
            date_key = datetime.now().strftime('%Y-%m-%d')
            attendance_db[f"{class_name} ({date_key})"] = {'present': present_sts, 'absent': absent_sts}
            save_to_disk()
            msg = "تم تسجيل حضور وغياب الطلاب بنجاح!"

        elif action == 'send_reply':
            reply_msg = request.form.get('reply_message')
            admin_replies.append({'teacher_name': t_name, 'message': reply_msg, 'report': None, 'date': datetime.now().strftime('%Y-%m-%d %H:%M')})
            save_to_disk()
            msg = "تم إرسال رسالتك للإدارة بنجاح!"

    my_classes = teacher_classes_map.get(username, list(classes_students.keys()))
    class_opts = "".join([f'<option value="{c}">{c}</option>' for c in my_classes])
    notifs = "".join([f"<div style='background:#e3f2fd; padding:8px; margin-bottom:5px; border-radius:4px; font-weight:bold;'>🔔 {n}</div>" for n in user_data.get('notifications', [])])

    my_sessions = [s for s in field_sessions if s['primary_teacher'] == t_name or s['secondary_teacher'] == t_name]
    field_html = ""
    for s in my_sessions:
        if s['status'] == 'قيد التدريب':
            field_html += f'''
            <div style="background:#f9fbe7; border:1px solid #c0ca33; padding:12px; border-radius:6px; margin-top:8px;">
                <b>📍 مكان التدريب الميداني: {s['location']} ({s['class_name']})</b>
                <button type="button" onclick="submitGps({s['id']}, '{t_name}', '{s['location']}')" style="background:#2e7d32; margin-top:8px;">📍 توثيق الحضور الجغرافي (GPS)</button>
            </div>
            '''
        else:
            field_html += f'''<div style="background:#e8f5e9; padding:8px; border-radius:6px; margin-top:8px; color:#2e7d32; font-weight:bold;">✔ تم توثيق الحضور الجغرافي لـ ({s['location']}) بنجاح!</div>'''

    return f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>واجهة الأستاذ - معهد الهرمل الفني</title>
        <style>
            body {{ font-family: system-ui, sans-serif; background: #f4f6f9; margin: 0; padding-bottom: 30px; }}
            .card {{ background: white; padding: 18px; border-radius: 8px; margin-top: 15px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); border-top: 4px solid #0d47a1; }}
            input, select, textarea, button {{ width: 100%; padding: 10px; margin-top: 6px; box-sizing: border-box; font-family: inherit; }}
            button {{ background: #0d47a1; color: white; border: none; font-weight: bold; cursor: pointer; border-radius: 5px; }}
            .student-row {{ display: flex; justify-content: space-between; align-items: center; padding: 8px; border-bottom: 1px solid #eee; background: #fafafa; margin-top: 5px; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <div style="background:#0d47a1; color:white; padding:12px 20px; display:flex; justify-content:space-between; align-items:center;">
            <div><h3 style="margin:0;">معهد الهرمل الفني</h3><small>الأستاذ: {user_data.get('name')}</small></div>
            <a href="/logout" style="color:#ffcdd2; background:#c62828; padding:6px 12px; border-radius:4px; text-decoration:none; font-size:12px;">خروج</a>
        </div>

        <div style="padding:15px;">
            {f'<div style="background:#e8f5e9; color:#2e7d32; padding:10px; border-radius:6px; margin-bottom:10px; font-weight:bold;">{msg}</div>' if msg else ''}

            {f'<div class="card"><h4 style="color:#0d47a1; margin-top:0;">🏥 التدريب الميداني والـ GPS:</h4>{field_html}</div>' if field_html else ''}

            <div class="card">
                <h4 style="color:#0d47a1; margin-top:0;">📢 التعاميم الواردة:</h4>
                {notifs if notifs else '<p style="color:#666;">لا توجد تعاميم جديدة.</p>'}
            </div>

            <!-- غياب الطلاب -->
            <div class="card">
                <h4 style="color:#0d47a1; margin-top:0;">📋 توثيق حضور وغياب الطلاب اليومي:</h4>
                <form method="POST">
                    <input type="hidden" name="action" value="submit_class_attendance">
                    <label>اختر الصف:</label>
                    <select name="class_name" id="attClass" onchange="loadStudentsForAtt()" required><option value="">-- اختر الصف --</option>{class_opts}</select>
                    <div id="attContainer" style="margin-top:10px;"></div>
                    <button type="submit" id="attBtn" style="display:none; background:#2e7d32; margin-top:10px;">حفظ الحضور والغياب</button>
                </form>
            </div>

            <!-- رصد العلامات -->
            <div class="card">
                <h4 style="color:#0d47a1; margin-top:0;">📝 إدخال ورصد علامات الطلاب (من 20):</h4>
                <form method="POST">
                    <input type="hidden" name="action" value="submit_class_grades">
                    <label>اختر الصف:</label>
                    <select name="class_name" id="gradeClass" onchange="loadStudentsForGrades()" required><option value="">-- اختر الصف --</option>{class_opts}</select>
                    <div id="gradeContainer" style="margin-top:10px;"></div>
                    <button type="submit" id="gradeBtn" style="display:none; margin-top:10px;">حفظ ورصد العلامات</button>
                </form>
            </div>

            <!-- إرسال عذر للإدارة -->
            <div class="card">
                <h4 style="color:#0d47a1; margin-top:0;">💬 إرسال رسالة أو عذر لإدارة المعهد:</h4>
                <form method="POST">
                    <input type="hidden" name="action" value="send_reply">
                    <textarea name="reply_message" placeholder="اكتب رسالتك..." required style="height:70px;"></textarea>
                    <button type="submit" style="background:#1565c0; margin-top:8px;">إرسال للإدارة</button>
                </form>
            </div>
        </div>

        <script>
            function loadStudentsForAtt() {
                let cls = document.getElementById('attClass').value;
                let cont = document.getElementById('attContainer');
                let btn = document.getElementById('attBtn');
                cont.innerHTML = '';
                if(!cls) { btn.style.display='none'; return; }
                fetch('/api/get_students/' + encodeURIComponent(cls)).then(res => res.json()).then(data => {
                    let html = '<p style="font-size:13px; color:#0d47a1; font-weight:bold;">الكل حاضر افتراضياً ✅ (أزل الصح عن المتغيب):</p>';
                    data.students.forEach(st => {
                        html += `<div class="student-row"><span>${{st}}</span><label style="color:#2e7d32; font-weight:bold; cursor:pointer;"><input type="checkbox" name="attendance_check" value="${{st}}" checked style="width:auto; transform:scale(1.2);"> حاضر</label></div>`;
                    });
                    cont.innerHTML = html;
                    btn.style.display = 'block';
                });
            }

            function loadStudentsForGrades() {
                let cls = document.getElementById('gradeClass').value;
                let cont = document.getElementById('gradeContainer');
                let btn = document.getElementById('gradeBtn');
                cont.innerHTML = '';
                if(!cls) { btn.style.display='none'; return; }
                fetch('/api/get_students/' + encodeURIComponent(cls)).then(res => res.json()).then(data => {
                    let html = '';
                    data.students.forEach(st => {
                        html += `<div class="student-row"><span style="flex:1; font-weight:bold;">${{st}}</span><input type="number" step="0.5" min="0" max="20" name="grade_${{st}}" placeholder="العلامة /20" style="width:110px; margin:0;" required></div>`;
                    });
                    cont.innerHTML = html;
                    btn.style.display = 'block';
                });
            }

            function submitGps(sessionId, teacherName, locationName) {
                if(!navigator.geolocation) { alert("الـ GPS غير مدعوم في متصفحك"); return; }
                navigator.geolocation.getCurrentPosition(function(pos) {
                    fetch('/teacher/submit_field_attendance', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({session_id: sessionId, sender_name: teacherName, location: locationName, lat: pos.coords.latitude, lng: pos.coords.longitude})
                    }).then(res => res.json()).then(data => {
                        alert(data.message);
                        if(data.success) location.reload();
                    });
                }, function(err) { alert("يرجى تفعيل الـ GPS لتأكيد الحضور."); }, {enableHighAccuracy: true});
            }
        </script>
    </body>
    </html>
    '''

@app.route('/teacher/submit_field_attendance', methods=['POST'])
def submit_field_attendance():
    if session.get('role') != 'teacher': return jsonify({"success": False, "message": "غير مصرح"}), 403
    data = request.json
    s_id = int(data.get('session_id'))
    loc_name = data.get('location')
    lat = float(data.get('lat'))
    lng = float(data.get('lng'))

    if loc_name in TRAINING_LOCATIONS:
        loc_data = TRAINING_LOCATIONS[loc_name]
        dist = calculate_distance(lat, lng, loc_data['lat'], loc_data['lng'])
        if dist > loc_data['radius_meters']:
            return jsonify({"success": False, "message": f"عذراً! أنت خارج نطاق موقع ({loc_name}). المسافة الحالية هي {int(dist)} متر والنطاق المسموح هو {loc_data['radius_meters']} متر."}), 400

    s_item = next((s for s in field_sessions if s['id'] == s_id), None)
    if s_item:
        s_item['status'] = "مكتملة"
        save_to_disk()
        return jsonify({"success": True, "message": "تم التحقق الجغرافي بالـ GPS بنجاح وتوثيق حضورك!"})
    return jsonify({"success": False, "message": "الجلسة غير متوفرة"}), 400

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)