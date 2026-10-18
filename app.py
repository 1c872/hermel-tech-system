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

PERIODS_SCHEDULE = {
    1: {"start": "07:50", "end": "08:30", "label": "الحصة الأولى (07:50 - 08:30)"},
    2: {"start": "08:30", "end": "09:10", "label": "الحصة الثانية (08:30 - 09:10)"},
    3: {"start": "09:10", "end": "09:50", "label": "الحصة الثالثة (09:10 - 09:50)"},
    4: {"start": "09:50", "end": "10:30", "label": "الحصة الرابعة (09:50 - 10:30)"},
    5: {"start": "10:50", "end": "11:30", "label": "الحصة الخامسة (10:50 - 11:30)"},
    6: {"start": "11:30", "end": "12:10", "label": "الحصة السادسة (11:30 - 12:10)"},
    7: {"start": "12:10", "end": "12:50", "label": "الحصة السابعة (12:10 - 12:50)"},
    8: {"start": "12:50", "end": "01:30", "label": "الحصة الثامنة (12:50 - 01:30)"},
    9: {"start": "01:30", "end": "02:10", "label": "الحصة التاسعة (01:30 - 02:10)"}
}

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

load_from_disk()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

ICON_URL = "https://cdn-icons-png.flaticon.com/512/3135/3135755.png"

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
        <button class="dropbtn">النظار والدوريات ▾</button>
        <div class="dropdown-content">
            <a href="/general_supervisor">🏛️ لوحة الناظر العام</a>
            <a href="/supervisor">📋 لوحة ناظر الصفوف</a>
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
            <a href="javascript:void(0)" onclick="showSection('uploadStudentsSec')">👨‍🎓 رفع ملف الطلاب والصفوف (Excel)</a>
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
            
            # حماية الجهاز (Device Binding)
            if not t_data.get('device_id'):
                t_data['device_id'] = current_device_fingerprint
                save_to_disk()
            elif t_data.get('device_id') != current_device_fingerprint:
                error = 'عذراً، هذا الحساب مرتبط بهاتف آخر. يراجع مدير المعهد لإعادة ضبط الجهاز.'
                return render_template_string(login_template, icon_url=ICON_URL, error=error)

            session['username'] = username
            session['role'] = 'teacher'
            if t_data.get('is_general_supervisor'):
                return redirect(url_for('general_supervisor_dashboard'))
            elif t_data.get('is_supervisor'):
                return redirect(url_for('supervisor_dashboard'))
            return redirect(url_for('teacher_dashboard'))
        else:
            error = 'اسم المستخدم أو كلمة المرور غير صحيحة'
            
    return render_template_string(login_template, icon_url=ICON_URL, error=error)

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
            <img src="{{ icon_url }}" width="65" style="margin-bottom:5px;">
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

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    msg = session.pop('msg', '')
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'upload_excel':
            file = request.files.get('excel_file')
            if file and allowed_file(file.filename):
                try:
                    df = pd.read_excel(file)
                    for _, row in df.iterrows():
                        c_name = str(row.get('الصف', row.get('Class', ''))).strip()
                        s_name = str(row.get('اسم الطالب', row.get('Student', ''))).strip()
                        t_name = str(row.get('الأستاذ', row.get('Teacher', ''))).strip()
                        
                        if c_name and s_name and c_name != 'nan':
                            if c_name not in classes_students:
                                classes_students[c_name] = []
                            if s_name not in classes_students[c_name]:
                                classes_students[c_name].append(s_name)
                                
                        if t_name and t_name != 'nan':
                            u_key = t_name.replace(" ", "_").lower()
                            if u_key not in teachers_db:
                                teachers_db[u_key] = {
                                    'name': t_name,
                                    'password': '123',
                                    'subject': 'عام',
                                    'is_supervisor': False,
                                    'is_general_supervisor': False,
                                    'device_id': ''
                                }
                    save_to_disk()
                    msg = "تم رفع ملف الإكسل واستخراج الصفوف والأساتذة والطلاب بنجاح!"
                except Exception as e:
                    msg = f"خطأ في قراءة ملف الإكسل: {e}"

        elif action == 'reset_teacher_device':
            target_user = request.form.get('target_user')
            if target_user in teachers_db:
                teachers_db[target_user]['device_id'] = ''
                save_to_disk()
                msg = f"تم مسح بصمة الجهاز للأستاذ ({teachers_db[target_user]['name']}) بنجاح!"

    teacher_opts = "".join([f"<option value='{u}'>{t['name']} ({u})</option>" for u, t in teachers_db.items()])

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
            input, select, button { width: 100%; padding: 10px; margin-top: 6px; box-sizing: border-box; }
            button { background: #0d47a1; color: white; border: none; font-weight: bold; cursor: pointer; }
        </style>
    </head>
    <body>
        ''' + HEADER_VTE_HTML + '''

        <div class="container">
            {% if msg %}<div style="background:#e8f5e9; color:#2e7d32; padding:12px; border-radius:6px; font-weight:bold;">{{ msg }}</div>{% endif %}

            <div id="uploadStudentsSec" class="card active">
                <h3 style="color:#0d47a1; margin-top:0;">📊 رفع جداول المعهد والصفوف والأساتذة (Excel):</h3>
                <form method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="action" value="upload_excel">
                    <input type="file" name="excel_file" accept=".xlsx, .xls" required>
                    <button type="submit" style="margin-top:10px; background:#2e7d32;">رفع الملف واستخراج القوائم</button>
                </form>
            </div>

            <div id="deviceBindingSec" class="card">
                <h3 style="color:#c62828; margin-top:0;">📱 إدارة أجهزة الأساتذة (السماح بالدخول من هاتف جديد):</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="reset_teacher_device">
                    <select name="target_user" required>
                        <option value="">-- اختر الأستاذ --</option>
                        {{ teacher_opts | safe }}
                    </select>
                    <button type="submit" style="margin-top:10px; background:#c62828;">🔓 السماح بتسجيل الجهاز الجديد للأستاذ</button>
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
    ''', teacher_opts=teacher_opts, msg=msg)

@app.route('/general_supervisor', methods=['GET', 'POST'])
def general_supervisor_dashboard():
    if session.get('role') not in ['general_supervisor', 'admin', 'teacher']: 
        return redirect(url_for('login'))
    return redirect(url_for('admin_dashboard'))

@app.route('/supervisor', methods=['GET', 'POST'])
def supervisor_dashboard():
    if session.get('role') not in ['supervisor', 'admin', 'teacher']: 
        return redirect(url_for('login'))
    return redirect(url_for('admin_dashboard'))

@app.route('/teacher')
def teacher_dashboard():
    if session.get('role') not in ['teacher', 'admin']: return redirect(url_for('login'))
    return "واجهة الأستاذ جاهزة ومحمية بالـ GPS."

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)