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

# جدول الحصص الرسمية المعتمد في المعهد
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

# نطاق الوقت المسموح به للتدريب الميداني الـ GPS
FIELD_START_TIME = time(7, 50)
FIELD_END_TIME = time(13, 30)

teachers_db = {}
supervisors_db = {}
general_supervisors = {}
grades_db = {}
attendance_db = {}
teacher_classes_map = {}
classes_students = {}

admin_replies = []
admin_credentials = {'username': 'admin', 'password': '123456'}
current_academic_year = "2026-2027"
field_sessions = []
teacher_absences_log = []   
student_exit_permissions = [] 
teacher_exits_log = []

def save_to_disk():
    try:
        data = {
            'teachers_db': teachers_db,
            'supervisors_db': supervisors_db,
            'general_supervisors': general_supervisors,
            'grades_db': grades_db,
            'attendance_db': attendance_db,
            'teacher_classes_map': teacher_classes_map,
            'admin_replies': admin_replies,
            'admin_credentials': admin_credentials,
            'classes_students': classes_students,
            'field_sessions': field_sessions,
            'teacher_absences_log': teacher_absences_log,
            'student_exit_permissions': student_exit_permissions,
            'teacher_exits_log': teacher_exits_log
        }
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        shutil.copyfile(DB_FILE, BACKUP_FILE)
    except Exception as e:
        print(f"Error saving database: {e}")

def load_from_disk():
    global teachers_db, supervisors_db, general_supervisors, grades_db, attendance_db, teacher_classes_map
    global admin_replies, admin_credentials, classes_students, field_sessions, teacher_absences_log, student_exit_permissions, teacher_exits_log
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                teachers_db = data.get('teachers_db', {})
                supervisors_db = data.get('supervisors_db', {})
                general_supervisors = data.get('general_supervisors', {})
                grades_db = data.get('grades_db', {})
                attendance_db = data.get('attendance_db', {})
                teacher_classes_map = data.get('teacher_classes_map', {})
                admin_replies = data.get('admin_replies', [])
                admin_credentials = data.get('admin_credentials', {'username': 'admin', 'password': '123456'})
                classes_students = data.get('classes_students', {})
                field_sessions = data.get('field_sessions', [])
                teacher_absences_log = data.get('teacher_absences_log', [])
                student_exit_permissions = data.get('student_exit_permissions', [])
                teacher_exits_log = data.get('teacher_exits_log', [])
                return True
        except Exception as e:
            print(f"Error loading database: {e}")
    return False

load_from_disk()

ICON_URL = "https://cdn-icons-png.flaticon.com/512/3135/3135755.png"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# حساب المسافة الجغرافية بالكيلومتر
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371.0 # نصف قطر الأرض بالكيلومتر
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

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
            
            # حماية الجهاز وبصمة المتصفح (Device Binding)
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

# لوحة المدير الشاملة
@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    msg = session.pop('msg', '')
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        # رفع ملف الإكسل واستخراج الأساتذة والصفوف
        if action == 'upload_excel':
            if 'excel_file' in request.files:
                file = request.files['excel_file']
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

        elif action == 'add_teacher':
            u_name = request.form.get('username').strip().lower()
            pwd = request.form.get('password').strip()
            full_name = request.form.get('full_name').strip()
            subject = request.form.get('subject').strip()
            
            teachers_db[u_name] = {
                'name': full_name,
                'password': pwd,
                'subject': subject,
                'is_supervisor': False,
                'is_general_supervisor': False,
                'device_id': ''
            }
            save_to_disk()
            msg = f"تم إضافة الأستاذ ({full_name}) وتوليد بيانات الدخول بنجاح!"

        elif action == 'reset_teacher_device':
            target_user = request.form.get('target_user')
            if target_user in teachers_db:
                teachers_db[target_user]['device_id'] = ''
                save_to_disk()
                msg = f"تم مسح بصمة الجهاز للأستاذ ({teachers_db[target_user]['name']}) بنجاح. أصبح بإمكانه الدخول من جهازه الجديد!"

        elif action == 'assign_supervisor':
            target_user = request.form.get('target_user')
            role_type = request.form.get('role_type')
            floor = request.form.get('floor', 'الطابق الأول')
            selected_classes = request.form.getlist('classes')
            
            if target_user in teachers_db:
                if role_type == 'floor':
                    teachers_db[target_user]['is_supervisor'] = True
                    teachers_db[target_user]['floor'] = floor
                    teachers_db[target_user]['supervisor_classes'] = selected_classes
                elif role_type == 'general':
                    teachers_db[target_user]['is_general_supervisor'] = True
                save_to_disk()
                msg = f"تم تحديث صلاحيات الأستاذ ({teachers_db[target_user]['name']}) وتكليفه بالصفوف بنجاح!"

    teacher_opts = "".join([f"<option value='{u}'>{t['name']} ({u})</option>" for u, t in teachers_db.items()])
    class_checks = "".join([f"<label style='display:inline-block; margin:6px; background:#e3f2fd; padding:6px 10px; border-radius:4px;'><input type='checkbox' name='classes' value='{c}'> {c}</label>" for c in classes_students.keys()])

    return render_template_string('''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>معهد الهرمل الفني - لوحة الإدارة الرئيسية</title>
        <style>
            body { font-family: system-ui, sans-serif; background: #f4f6f9; margin: 0; padding-bottom: 30px; }
            .header { background:#0d47a1; color:white; padding:12px 20px; display:flex; justify-content:space-between; align-items:center; }
            .container { padding: 20px; }
            .card { background: white; padding: 20px; border-radius: 8px; margin-top: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); border-top: 4px solid #0d47a1; }
            input[type=text], input[type=password], select, button { width: 100%; padding: 10px; margin-top: 6px; box-sizing: border-box; border:1px solid #ccc; border-radius:4px; }
            button { background: #0d47a1; color: white; border: none; font-weight: bold; cursor: pointer; }
            .btn { display:inline-block; background: #1565c0; color: white; padding: 10px 15px; text-decoration:none; border-radius: 5px; font-weight: bold; margin-top: 8px; margin-left: 8px; }
            .msg { background: #e8f5e9; color: #2e7d32; padding: 12px; border-radius: 6px; margin-bottom: 15px; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="header">
            <div>
                <div style="font-weight:bold; font-size:18px;">معهد الهرمل الفني - لوحة المدير الرئيسية</div>
                <div style="font-size:12px; color:#bbdefb;">رقم المعهد: 84 | العام الدراسي الحالي: 2026-2027</div>
            </div>
            <div><a href="/logout" style="color:#ffcdd2; text-decoration:none; font-weight:bold; font-size:13px; background:#c62828; padding:6px 12px; border-radius:4px;">خروج</a></div>
        </div>

        <div class="container">
            {% if msg %}<div class="msg">{{ msg }}</div>{% endif %}
            
            <div class="card">
                <h3 style="color:#0d47a1; margin-top:0;">🔗 التنقل السريع بين اللوحات:</h3>
                <a href="/general_supervisor" class="btn" style="background:#2e7d32;">🏛️ الناظر العام</a>
                <a href="/supervisor" class="btn">📋 ناظر الصفوف</a>
                <a href="/teacher" class="btn" style="background:#1565c0;">👨‍🏫 صفحة الأساتذة</a>
            </div>

            <div class="card" style="border-top-color: #2e7d32;">
                <h3 style="color:#2e7d32; margin-top:0;">📊 رفع جداول المعهد عبر ملف Excel:</h3>
                <form method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="action" value="upload_excel">
                    <input type="file" name="excel_file" accept=".xlsx, .xls" required style="margin-bottom:10px;">
                    <button type="submit" style="background:#2e7d32;">رفع الملف وتحديث الصفوف والأساتذة</button>
                </form>
            </div>

            <div class="card" style="border-top-color: #d32f2f; background: #fff8f8;">
                <h3 style="color:#c62828; margin-top:0;">📱 إدارة أجهزة الأساتذة (السماح بالدخول من هاتف جديد):</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="reset_teacher_device">
                    <label><b>اختر الأستاذ من القائمة:</b></label>
                    <select name="target_user" required>
                        <option value="">-- اختر الأستاذ --</option>
                        {{ teacher_opts | safe }}
                    </select>
                    <button type="submit" style="margin-top:10px; background:#c62828;">🔓 السماح بتسجيل الجهاز الجديد للأستاذ</button>
                </form>
            </div>

            <div class="card">
                <h3 style="color:#0d47a1; margin-top:0;">👤 إضافة أستاذ جديد وتوليد بيانات الدخول:</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="add_teacher">
                    <input type="text" name="full_name" placeholder="اسم الأستاذ الثلاثي" required>
                    <input type="text" name="subject" placeholder="المادة" required>
                    <input type="text" name="username" placeholder="اسم المستخدم (Username)" required>
                    <input type="text" name="password" placeholder="كلمة المرور (Password)" required>
                    <button type="submit" style="margin-top:10px; background:#2e7d32;">حفظ وإنشاء الحساب</button>
                </form>
            </div>

            <div class="card">
                <h3 style="color:#0d47a1; margin-top:0;">🎖️ تكليف أستاذ (ناظر طابق) وتحديد صفوفه من الإكسل:</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="assign_supervisor">
                    <label><b>اختر الأستاذ:</b></label>
                    <select name="target_user" required>
                        <option value="">-- اختر الأستاذ المُراد تكليفه --</option>
                        {{ teacher_opts | safe }}
                    </select>

                    <label style="margin-top:10px; display:block;"><b>نوع التكليف:</b></label>
                    <select name="role_type" required>
                        <option value="floor">ناظر طابق / صفوف معينة</option>
                        <option value="general">ناظر عام على سجل الدوام</option>
                    </select>

                    <label style="margin-top:10px; display:block;"><b>الطابق الموكل إليه:</b></label>
                    <input type="text" name="floor" value="الطابق الأول">

                    <label style="margin-top:12px; display:block; font-weight:bold; color:#0d47a1;">حدد الصفوف الموكلة إليه (المستخرجة من الإكسل):</label>
                    <div style="max-height: 180px; overflow-y: auto; border: 1px solid #bbdefb; padding: 8px; border-radius: 6px; background: #f1f8e9;">
                        {{ class_checks | safe if class_checks else 'لم يتم رفع أي صفوف عبر الإكسل بعد' }}
                    </div>

                    <button type="submit" style="margin-top:15px; background:#1565c0;">حفظ وتطبيق التكليف</button>
                </form>
            </div>
        </div>
        <div style="text-align:center; margin-top:30px; color:#666; font-size:12.5px;">🛠️ تم تصميم وتطوير البرنامج من قبل الأستاذ محمد حسين شمص</div>
    </body>
    </html>
    ''', teacher_opts=teacher_opts, class_checks=class_checks, msg=msg)

# لوحة الناظر العام
@app.route('/general_supervisor', methods=['GET', 'POST'])
def general_supervisor_dashboard():
    if session.get('role') not in ['general_supervisor', 'admin', 'teacher']: 
        return redirect(url_for('login'))
    
    username = session.get('username')
    user_info = teachers_db.get(username, {})
    selected_date = request.form.get('filter_date', datetime.now().strftime('%Y-%m-%d'))
    msg = ''

    if request.method == 'POST' and request.form.get('action') == 'log_teacher_absence':
        t_name = request.form.get('teacher_name')
        log_date = request.form.get('log_date')
        missed_periods = request.form.getlist('periods')
        notes = request.form.get('notes', '')
        teacher_absences_log.append({'date': log_date, 'teacher_name': t_name, 'missed_periods': [int(p) for p in missed_periods], 'notes': notes})
        save_to_disk()
        msg = "تم تسجيل غياب الحصص بنجاح!"

    day_absences = [a for a in teacher_absences_log if a['date'] == selected_date]
    abs_rows = "".join([f"<tr><td><b>{a['teacher_name']}</b></td><td>الحصص: {a['missed_periods']}</td><td>{a['notes']}</td></tr>" for a in day_absences])
    teacher_opts = "".join([f"<option value='{t['name']}'>{t['name']}</option>" for u, t in teachers_db.items()])

    return render_template_string('''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>سجل الدوام - الناظر العام</title>
        <style>
            body { font-family: system-ui, sans-serif; background: #f4f6f9; margin: 0; padding: 20px; }
            .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); border-top: 4px solid #0d47a1; margin-top: 15px; }
            input, select, button { width: 100%; padding: 10px; margin-top: 6px; box-sizing: border-box; }
            button { background: #0d47a1; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; }
            .nav-bar { background:#1565c0; padding:10px; border-radius:6px; margin-bottom:15px; display:flex; gap:10px; }
            .nav-bar a { color:white; text-decoration:none; font-weight:bold; padding:6px 12px; background:#0d47a1; border-radius:4px; font-size:13px; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: center; font-size: 13px; }
            th { background: #0d47a1; color: white; }
        </style>
    </head>
    <body>
        <div style="background:#0d47a1; color:white; padding:12px 20px; display:flex; justify-content:space-between; align-items:center; border-radius:8px;">
            <h3 style="margin:0;">🏛️ صفحة الناظر العام: {{ user_info.get('name', 'الإدارة') }}</h3>
            <a href="/logout" style="color:white; background:#c62828; padding:6px 12px; border-radius:4px; text-decoration:none;">خروج</a>
        </div>
        <div class="nav-bar" style="margin-top:10px;">
            <span style="color:white; font-weight:bold; align-self:center;">الانتقال بين الأدوار:</span>
            <a href="/teacher">👨‍🏫 واجهة الأستاذ</a>
            {% if user_info.get('is_supervisor') or session.get('username') == 'admin' %}<a href="/supervisor">📋 ناظر الصفوف</a>{% endif %}
            {% if session.get('username') == 'admin' %}<a href="/admin" style="background:#2e7d32;">🏠 واجهة المدير</a>{% endif %}
        </div>
        {% if msg %}<div style="background:#e8f5e9; color:#2e7d32; padding:10px; border-radius:6px; margin-top:15px;">{{ msg }}</div>{% endif %}
        <div class="card">
            <h3 style="color:#0d47a1; margin-top:0;">📅 تقويم رصد غياب الحصص للأساتذة:</h3>
            <form method="POST">
                <input type="hidden" name="action" value="log_teacher_absence">
                <input type="date" name="log_date" value="{{ selected_date }}" required>
                <select name="teacher_name" required>
                    <option value="">-- اختر الأستاذ من بيانات المعهد --</option>
                    {{ teacher_opts | safe }}
                </select>
                <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:8px;">
                    {% for i in range(1, 10) %}<label style="background:#e3f2fd; padding:6px 10px; border-radius:4px;"><input type="checkbox" name="periods" value="{{ i }}"> الحصة {{ i }}</label>{% endfor %}
                </div>
                <input type="text" name="notes" placeholder="ملاحظات أو سبب الغياب">
                <button type="submit" style="background:#c62828; margin-top:10px;">تسجيل غياب الحصص</button>
            </form>
        </div>
        <div class="card">
            <h3 style="color:#0d47a1; margin-top:0;">📊 غياب الحصص الموثق ليوم ({{ selected_date }})</h3>
            <table>
                <tr><th>الأستاذ</th><th>الحصص المتغيب عنها</th><th>الملاحظات</th></tr>
                {{ abs_rows | safe if abs_rows else '<tr><td colspan="3">لا يوجد غياب حصص موثق لهذا اليوم</td></tr>' }}
            </table>
        </div>
    </body>
    </html>
    ''', selected_date=selected_date, teacher_opts=teacher_opts, abs_rows=abs_rows, user_info=user_info, msg=msg)

# لوحة ناظر الصفوف
@app.route('/supervisor', methods=['GET', 'POST'])
def supervisor_dashboard():
    if session.get('role') not in ['supervisor', 'admin', 'teacher']: 
        return redirect(url_for('login'))
    
    username = session.get('username')
    user_info = teachers_db.get(username, {})
    
    if username == 'admin':
        sup_data = {"name": "مدير المعهد", "floor": "الإدارة العامة", "classes": list(classes_students.keys())}
    else:
        sup_data = {
            "name": user_info.get('name', 'ناظر'),
            "floor": user_info.get('floor', 'الطابق الأول'),
            "classes": user_info.get('supervisor_classes', list(classes_students.keys()))
        }
        
    msg = ''

    if request.method == 'POST' and request.form.get('action') == 'submit_supervisor_attendance':
        c_name = request.form.get('class_name')
        period_num = request.form.get('period_num')
        present_sts = request.form.getlist('attendance_check')
        teacher_status = request.form.get('teacher_status')
        attendance_db[f"ناظر - {c_name} - الحصة {period_num}"] = {'present': present_sts, 'teacher_status': teacher_status}
        save_to_disk()
        msg = "تم تسجيل تقرير الحصة بنجاح!"

    class_opts = "".join([f'<option value="{c}">{c}</option>' for c in sup_data.get('classes', [])])
    period_opts = "".join([f'<option value="{k}">{v["label"]}</option>' for k, v in PERIODS_SCHEDULE.items()])

    return render_template_string('''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>لوحة الناظر - معهد الهرمل الفني</title>
        <style>
            body { font-family: system-ui, sans-serif; background: #f4f6f9; margin: 0; padding: 20px; }
            .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); border-top: 4px solid #0d47a1; margin-top: 15px; }
            select, input, button { width: 100%; padding: 10px; margin-top: 8px; box-sizing: border-box; }
            button { background: #0d47a1; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; }
            .nav-bar { background:#1565c0; padding:10px; border-radius:6px; margin-bottom:15px; display:flex; gap:10px; }
            .nav-bar a { color:white; text-decoration:none; font-weight:bold; padding:6px 12px; background:#0d47a1; border-radius:4px; font-size:13px; }
            .student-row { display: flex; justify-content: space-between; padding: 8px; border-bottom: 1px solid #eee; }
        </style>
    </head>
    <body>
        <div style="background:#0d47a1; color:white; padding:12px 20px; display:flex; justify-content:space-between; align-items:center; border-radius:8px;">
            <h3 style="margin:0;">صفحة الناظر: {{ sup_name }}</h3>
            <a href="/logout" style="color:white; background:#c62828; padding:6px 12px; border-radius:4px; text-decoration:none;">خروج</a>
        </div>
        <div class="nav-bar" style="margin-top:10px;">
            <span style="color:white; font-weight:bold; align-self:center;">الانتقال بين الأدوار:</span>
            <a href="/teacher">👨‍🏫 واجهة الأستاذ</a>
            {% if user_info.get('is_general_supervisor') or session.get('username') == 'admin' %}<a href="/general_supervisor">🏛️ الناظر العام</a>{% endif %}
            {% if session.get('username') == 'admin' %}<a href="/admin" style="background:#2e7d32;">🏠 واجهة المدير</a>{% endif %}
        </div>
        {% if msg %}<div style="background:#e8f5e9; color:#2e7d32; padding:10px; border-radius:6px; margin-top:15px;">{{ msg }}</div>{% endif %}
        <div class="card">
            <h3 style="color:#0d47a1; margin-top:0;">📋 رصد الحصص ومتابعة التزام الأساتذة والطلاب</h3>
            <form method="POST">
                <input type="hidden" name="action" value="submit_supervisor_attendance">
                <label><b>1. اختر الحصة الدراسية:</b></label>
                <select name="period_num" required>{{ period_opts | safe }}</select>

                <label style="margin-top:10px; display:block;"><b>2. اختر الصف (من الصفوف الموكلة إليك):</b></label>
                <select name="class_name" id="supClassSelect" onchange="loadSupStudents()" required>
                    <option value="">-- اختر الصف --</option>
                    {{ class_opts | safe }}
                </select>

                <div id="supStudentsContainer" style="margin-top:15px;"></div>

                <div style="margin-top:15px; background:#fff3e0; padding:15px; border-radius:6px;">
                    <label style="font-weight:bold; color:#e65100;">التزام أستاذ هذه الحصة:</label><br>
                    <input type="radio" name="teacher_status" value="present" checked style="width:auto;"> ✅ حاضر ويدرس بالحصة<br>
                    <input type="radio" name="teacher_status" value="absent" style="width:auto;"> ❌ متغيب تماماً<br>
                    <input type="radio" name="teacher_status" value="escaped" style="width:auto;"> 🚨 تهرب ومغادرة الصف
                </div>
                <button type="submit" id="supSubmitBtn" style="display:none; margin-top:15px; background:#2e7d32;">حفظ تقرير الحصة</button>
            </form>
        </div>

        <script>
            function loadSupStudents() {
                let cName = document.getElementById('supClassSelect').value;
                let container = document.getElementById('supStudentsContainer');
                let submitBtn = document.getElementById('supSubmitBtn');
                container.innerHTML = '';

                if (!cName) { submitBtn.style.display = 'none'; return; }

                fetch('/api/get_students/' + encodeURIComponent(cName))
                    .then(res => res.json())
                    .then(data => {
                        let html = '<p style="font-size:13px; color:#0d47a1; font-weight:bold;">حدد الطلاب الحاضرين لهذه الحصة:</p>';
                        if(data.students.length === 0) {
                            html += '<p style="color:#777;">لا يوجد طلاب موثقين لهذا الصف في الإكسل بعد.</p>';
                        } else {
                            data.students.forEach(st => {
                                html += `
                                <div class="student-row">
                                    <span>${st}</span>
                                    <input type="checkbox" name="attendance_check" value="${st}" checked style="width:auto;">
                                </div>`;
                            });
                        }
                        container.innerHTML = html;
                        submitBtn.style.display = 'block';
                    });
            }
        </script>
    </body>
    </html>
    ''', sup_name=sup_data.get('name'), class_opts=class_opts, period_opts=period_opts, user_info=user_info, msg=msg)

# واجهة الأستاذ وتدريب الـ GPS
@app.route('/teacher', methods=['GET', 'POST'])
def teacher_dashboard():
    if session.get('role') not in ['teacher', 'admin']: 
        return redirect(url_for('login'))
        
    username = session.get('username')
    user_info = teachers_db.get(username, {})
    msg = ''

    # توثيق الحضور الجغرافي (GPS) للتدريب الميداني
    if request.method == 'POST' and request.form.get('action') == 'verify_gps_field':
        try:
            current_time = datetime.now().time()
            if not (FIELD_START_TIME <= current_time <= FIELD_END_TIME):
                msg = f"❌ عذراً، التوثيق مسموح به حصراً خلال ساعات الدوام الرسمي من ({FIELD_START_TIME.strftime('%H:%M')}) حتى ({FIELD_END_TIME.strftime('%H:%M')})!"
            else:
                lat = float(request.form.get('latitude', 0))
                lon = float(request.form.get('longitude', 0))
                center_name = request.form.get('center_name', 'موقع تدريب ميداني')
                
                # توثيق الجلسة الميدانية
                field_sessions.append({
                    'teacher': user_info.get('name', username),
                    'center': center_name,
                    'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'lat': lat,
                    'lon': lon
                })
                save_to_disk()
                msg = f"✅ تم توثيق موقع حضورك في ({center_name}) عبر الـ GPS بنجاح عند الساعة ({datetime.now().strftime('%H:%M')})!"
        except Exception as e:
            msg = f"خطأ في قراءة الموقع الجغرافي: {e}"

    return render_template_string('''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>صفحة الأستاذ - معهد الهرمل الفني</title>
        <style>
            body { font-family: system-ui, sans-serif; background: #f4f6f9; margin: 0; padding: 20px; }
            .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); border-top: 4px solid #0d47a1; margin-top: 15px; }
            button { background: #0d47a1; color: white; border: none; padding: 12px; border-radius: 5px; font-weight: bold; cursor: pointer; width: 100%; }
            .nav-bar { background:#1565c0; padding:10px; border-radius:6px; margin-bottom:15px; display:flex; gap:10px; }
            .nav-bar a { color:white; text-decoration:none; font-weight:bold; padding:6px 12px; background:#0d47a1; border-radius:4px; font-size:13px; }
        </style>
    </head>
    <body>
        <div style="background:#0d47a1; color:white; padding:12px 20px; display:flex; justify-content:space-between; align-items:center; border-radius:8px;">
            <h3 style="margin:0;">أهلاً بك الأستاذ: {{ user_info.get('name', 'مدير النظام') }}</h3>
            <a href="/logout" style="color:white; background:#c62828; padding:6px 12px; border-radius:4px; text-decoration:none;">خروج</a>
        </div>

        <div class="nav-bar" style="margin-top:10px;">
            <span style="color:white; font-weight:bold; align-self:center;">الانتقال بين الأدوار:</span>
            {% if user_info.get('is_supervisor') or session.get('username') == 'admin' %}<a href="/supervisor">📋 ناظر الصفوف</a>{% endif %}
            {% if user_info.get('is_general_supervisor') or session.get('username') == 'admin' %}<a href="/general_supervisor">🏛️ الناظر العام</a>{% endif %}
            {% if session.get('username') == 'admin' %}<a href="/admin" style="background:#2e7d32;">🏠 واجهة المدير</a>{% endif %}
        </div>

        {% if msg %}<div style="background:#e8f5e9; color:#2e7d32; padding:12px; border-radius:6px; margin-top:15px; font-weight:bold;">{{ msg }}</div>{% endif %}

        <div class="card" style="border-top-color: #e65100; background: #fffde7;">
            <h3 style="color:#e65100; margin-top:0;">📍 توثيق الحضور الميداني بالـ GPS (المستشفيات والمدارس):</h3>
            <p style="font-size:13px; color:#555;">ملاحظة: التوثيق متاح حصراً من الساعة <b>07:50 صباحاً حتى 01:30 ظهراً</b> عبر هاتفك المسجل برقم الجهاز.</p>
            
            <form method="POST" id="gpsForm">
                <input type="hidden" name="action" value="verify_gps_field">
                <input type="hidden" name="latitude" id="latInput">
                <input type="hidden" name="longitude" id="lonInput">
                
                <label><b>اسم مركز التدريب / المستشفى:</b></label>
                <input type="text" name="center_name" placeholder="مثال: مستشفى الهرمل الحكومي" required style="width:100%; padding:10px; margin:8px 0; box-sizing:border-box;">
                
                <button type="button" onclick="getLocation()" style="background:#e65100;">📡 اضغط هنا لتأكيد الموقع الجغرافي والوقت</button>
            </form>
        </div>

        <div class="card">
            <h3 style="color:#0d47a1; margin-top:0;">📚 واجهة التدريس</h3>
            <p>مرحباً بك أستاذنا العزيز. يمكنك استخدام هذه الصفحة لمتابعة الدروس ورصد غياب الطلاب والحصص.</p>
        </div>

        <script>
            function getLocation() {
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(showPosition, showError);
                } else {
                    alert("المتصفح لا يدعم تحديد الموقع الجغرافي GPS");
                }
            }
            function showPosition(position) {
                document.getElementById('latInput').value = position.coords.latitude;
                document.getElementById('lonInput').value = position.coords.longitude;
                document.getElementById('gpsForm').submit();
            }
            function showError(error) {
                alert("تعذر الحصول على الموقع الجغرافي. يرجى تفعيل الـ GPS في الهاتف والإذن للمتصفح.");
            }
        </script>
    </body>
    </html>
    ''', user_info=user_info, msg=msg)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)