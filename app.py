import os
import json
import io
import math
import shutil
import re
import pandas as pd
import psycopg2
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, session, send_from_directory, jsonify, send_file

app = Flask(__name__)
app.secret_key = 'hermel_tech_school_shams_secret_key_2026'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
except OSError:
    UPLOAD_FOLDER = '/tmp/uploads'
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'xlsx', 'xls', 'json'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DB_FILE = os.path.join(BASE_DIR, 'database.json')
BACKUP_FILE = os.path.join(BASE_DIR, 'database_backup.json')

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    if not DATABASE_URL:
        return None
    try:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    except Exception as e:
        print(f"PostgreSQL connection error: {e}")
        return None

def init_db_table():
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS app_storage (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            ''')
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Error creating table: {e}")

init_db_table()

# قواعد البيانات المتكاملة (مع الحفاظ على الحفظ والاسترجاع)
teachers_db = {}
grades_db = {}            
attendance_db = {}        
teacher_classes_map = {}  
classes_students = {}
students_contact_info = {}
admin_replies = []
admin_credentials = {'username': 'admin', 'password': '123456'}

academic_years_db = ["2025-2026", "2026-2027", "2027-2028"]
current_academic_year = "2025-2026"

field_sessions = []
teacher_absences_log = []

# قاعدة بيانات المستشفيات ومواقع GPS والخدمات المحفوظة
hospitals_gps_db = [
    {"name": "مستشفى الهرمل الحكومي", "type": "مستشفى رئيسي", "phone": "08-200111", "lat": 34.3901, "lng": 36.3822, "address": "الهرمل - الشارع العام"},
    {"name": "مستشفى البتول", "type": "مستشفى", "phone": "08-200222", "lat": 34.3850, "lng": 36.3800, "address": "الهرمل - الدورة"},
    {"name": "معهد الهرمل الفني الرسمي", "type": "مقر المعهد", "phone": "08-200333", "lat": 34.3880, "lng": 36.3810, "address": "طريق الدورة - الشارع الرئيسي"}
]

directorate_excel_tables = {
    "students_registered": {"title": "الطلاب المسجلون", "columns": [], "data": []},
    "teachers_cards": {"title": "بطاقات الاساتذة", "columns": [], "data": []},
    "personal_info": {"title": "المعلومات الشخصية", "columns": [], "data": []},
    "weekly_schedule": {"title": "برنامج اسبوعي مع الاساتذة والمواد", "columns": [], "data": [], "parsed_schedule": {}},
    "teachers_and_subjects": {"title": "الاستاذ والمواد (التوزيع الرسمي)", "columns": [], "data": [], "parsed_schedule": {}},
    "executed_hours": {"title": "الساعات المنفذة للاساتذة", "columns": [], "data": [], "monthly_hours": {}},
    "transport_days": {"title": "أيام النقل للاساتذة شهرياً", "columns": [], "data": [], "monthly_transport": {}}
}

def clean_column_name(col):
    col_str = str(col).strip().replace("&#x27;", "").replace("'", "").replace('"', '')
    col_str = re.sub(r'^ش\s*', '', col_str)
    if len(col_str) == 1 and col_str.isdigit():
        col_str = '0' + col_str
    return col_str

def clean_auto_id(val):
    if pd.isna(val) or val is None: return ""
    val_str = str(val).strip()
    if val_str.endswith('.0'): val_str = val_str[:-2]
    return val_str

def normalize_name(name):
    if not name: return ""
    n = str(name).strip()
    n = re.sub(r'[أإآ]', 'ا', n)
    n = re.sub(r'ى', 'ي', n)
    n = re.sub(r'ة', 'ه', n)
    n = re.sub(r'[\s_\-]+', ' ', n)
    return n.lower()

def smart_match(query, target):
    if not query or not target: return False
    return normalize_name(query) in normalize_name(target) or normalize_name(target) in normalize_name(query)

def save_to_disk():
    try:
        data = {
            'teachers_db': teachers_db,
            'grades_db': grades_db,
            'attendance_db': attendance_db,
            'teacher_classes_map': teacher_classes_map,
            'classes_students': classes_students,
            'students_contact_info': students_contact_info,
            'admin_replies': admin_replies,
            'admin_credentials': admin_credentials,
            'academic_years_db': academic_years_db,
            'current_academic_year': current_academic_year,
            'field_sessions': field_sessions,
            'hospitals_gps_db': hospitals_gps_db,
            'directorate_excel_tables': directorate_excel_tables
        }
        json_str = json.dumps(data, ensure_ascii=False)
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO app_storage (key, value) VALUES ('main_state', %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
            ''', (json_str,))
            conn.commit()
            cur.close()
            conn.close()
        else:
            with open(DB_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            shutil.copyfile(DB_FILE, BACKUP_FILE)
    except Exception as e:
        print(f"Error saving database: {e}")

def load_from_disk():
    global teachers_db, grades_db, attendance_db, teacher_classes_map, classes_students, students_contact_info
    global admin_replies, admin_credentials, academic_years_db, current_academic_year, field_sessions, hospitals_gps_db, directorate_excel_tables
    
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT value FROM app_storage WHERE key = 'main_state';")
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row and row[0]:
                data = json.loads(row[0])
                teachers_db = data.get('teachers_db', {})
                grades_db = data.get('grades_db', {})
                attendance_db = data.get('attendance_db', {})
                teacher_classes_map = data.get('teacher_classes_map', {})
                classes_students = data.get('classes_students', {})
                students_contact_info = data.get('students_contact_info', {})
                admin_replies = data.get('admin_replies', [])
                admin_credentials = data.get('admin_credentials', {'username': 'admin', 'password': '123456'})
                academic_years_db = data.get('academic_years_db', academic_years_db)
                current_academic_year = data.get('current_academic_year', current_academic_year)
                field_sessions = data.get('field_sessions', [])
                hospitals_gps_db = data.get('hospitals_gps_db', hospitals_gps_db)
                directorate_excel_tables = data.get('directorate_excel_tables', directorate_excel_tables)
                return True
        except Exception as e:
            print(f"Error loading from DB: {e}")

    target_file = DB_FILE if os.path.exists(DB_FILE) else (BACKUP_FILE if os.path.exists(BACKUP_FILE) else None)
    if target_file:
        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                teachers_db = data.get('teachers_db', {})
                grades_db = data.get('grades_db', {})
                attendance_db = data.get('attendance_db', {})
                teacher_classes_map = data.get('teacher_classes_map', {})
                classes_students = data.get('classes_students', {})
                students_contact_info = data.get('students_contact_info', {})
                admin_replies = data.get('admin_replies', [])
                admin_credentials = data.get('admin_credentials', {'username': 'admin', 'password': '123456'})
                academic_years_db = data.get('academic_years_db', academic_years_db)
                current_academic_year = data.get('current_academic_year', current_academic_year)
                field_sessions = data.get('field_sessions', [])
                hospitals_gps_db = data.get('hospitals_gps_db', hospitals_gps_db)
                directorate_excel_tables = data.get('directorate_excel_tables', directorate_excel_tables)
                return True
        except Exception as e:
            print(f"Error loading database: {e}")
    return False

load_from_disk()

def get_teacher_assignments(teacher_name):
    norm_t = normalize_name(teacher_name)
    assignments = []
    parsed_sub = directorate_excel_tables.get('teachers_and_subjects', {}).get('parsed_schedule', {})
    for t_key, items in parsed_sub.items():
        if smart_match(norm_t, t_key):
            for it in items: assignments.append({'class': it['class'], 'subject': it['subject']})
    parsed_sched = directorate_excel_tables.get('weekly_schedule', {}).get('parsed_schedule', {})
    for t_key, items in parsed_sched.items():
        if smart_match(norm_t, t_key):
            for it in items:
                item_dict = {'class': it['class'], 'subject': it['subject']}
                if item_dict not in assignments: assignments.append(item_dict)
    return assignments

def parse_teachers_and_subjects_smart(df):
    parsed_teachers = {}
    for _, row in df.iterrows():
        row_vals = [str(val).strip() for val in row.values if pd.notna(val) and str(val).strip() != 'nan']
        if len(row_vals) < 2: continue
        t_name = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
        c_name = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else ""
        s_name = str(row.iloc[2]).strip() if len(row) > 2 and pd.notna(row.iloc[2]) else ""
        s_type = str(row.iloc[3]).strip() if len(row) > 3 and pd.notna(row.iloc[3]) else "نظري"
        if t_name and s_name and c_name:
            norm_t = normalize_name(t_name)
            if norm_t not in parsed_teachers: parsed_teachers[norm_t] = []
            item = {"class": c_name, "subject": s_name, "type": s_type}
            if item not in parsed_teachers[norm_t]: parsed_teachers[norm_t].append(item)
    return parsed_teachers

HEADER_VTE_HTML = '''
<div style="background:#0d47a1; color:white; padding:12px 20px; display:flex; justify-content:space-between; align-items:center; border-bottom:3px solid #1565c0;">
    <div style="display:flex; align-items:center; gap:12px;">
        <img src="https://cdn-icons-png.flaticon.com/512/3135/3135755.png" width="38" height="38" style="background:white; border-radius:50%; padding:2px;">
        <div>
            <div style="font-weight:bold; font-size:18px;">معهد الهرمل الفني</div>
            <div style="font-size:12px; color:#bbdefb;">رقم المعهد: 84 | العام الدراسي النشط: <b>{{ current_academic_year }}</b></div>
        </div>
    </div>
    <div style="display:flex; gap:10px; align-items:center;">
        <button onclick="toggleDarkMode()" style="background:#37474f; color:white; border:none; padding:6px 12px; border-radius:4px; font-size:12px; cursor:pointer;">🌙 الوضع الداكن</button>
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
            <a href="javascript:void(0)" onclick="showSection('viewRegisteredStudents')">📂 جدول الطلاب المسجلون</a>
        </div>
    </div>

    <div class="dropdown">
        <button class="dropbtn">الأساتذة والدوام ▾</button>
        <div class="dropdown-content">
            <a href="javascript:void(0)" onclick="showSection('teachersListSec')">👨‍🏫 سجل الأساتذة وعقود الساعات</a>
            <a href="javascript:void(0)" onclick="showSection('viewTeachersCards')">📇 بطاقات الاساتذة والمعلومات الشخصية</a>
            <a href="javascript:void(0)" onclick="showSection('viewWeeklySchedule')">📅 البرنامج الأسبوعي والأساتذة والمواد</a>
        </div>
    </div>

    <div class="dropdown">
        <button class="dropbtn">التواصل الفوري (WhatsApp) 💬 ▾</button>
        <div class="dropdown-content">
            <a href="javascript:void(0)" onclick="showSection('whatsAppCenterSec')">💬 مراسلة طالب / صف كامل عبر الواتساب</a>
            <a href="javascript:void(0)" onclick="showSection('whatsAppTeacherSec')">📲 مراسلة أستاذ مباشرة وإرسال الحساب</a>
        </div>
    </div>

    <div class="dropdown">
        <button class="dropbtn">الخدمات والـ GPS 📍 ▾</button>
        <div class="dropdown-content">
            <a href="javascript:void(0)" onclick="showSection('gpsHospitalsSec')">🏥 دليل المستشفيات ومواقع GPS</a>
        </div>
    </div>

    <div class="dropdown">
        <button class="dropbtn">إعدادات وإدارة ▾</button>
        <div class="dropdown-content">
            <a href="javascript:void(0)" onclick="showSection('academicYearSec')">📅 التبديل بين الأعوام الدراسية</a>
            <a href="javascript:void(0)" onclick="showSection('uploadDirectorateFilesSec')">⚙️ رفع ملفات المديرية (Excel)</a>
            <a href="javascript:void(0)" onclick="showSection('deviceBindingSec')">📱 إدارة أجهزة الأساتذة (فك الربط)</a>
            <a href="javascript:void(0)" onclick="showSection('backupSec')">💾 النسخ الاحتياطي والاسترداد</a>
            <a href="javascript:void(0)" onclick="showSection('changePassSec')">🔑 تغيير كلمة السر الإدارية</a>
        </div>
    </div>
</div>

<style>
    body.dark-mode { background-color: #121212 !important; color: #e0e0e0 !important; }
    body.dark-mode .card { background-color: #1e1e1e !important; color: #ffffff !important; border-top-color: #2196f3 !important; }
    body.dark-mode table, body.dark-mode th, body.dark-mode td { border-color: #333 !important; }
    body.dark-mode th { background-color: #1565c0 !important; }
    body.dark-mode input, body.dark-mode select, body.dark-mode textarea { background-color: #2c2c2c !important; color: #fff !important; border-color: #555 !important; }

    .dropdown { position: relative; display: inline-block; }
    .dropbtn { background-color: #1565c0; color: white; padding: 12px 16px; font-size: 14px; border: none; cursor: pointer; font-weight: bold; font-family: inherit; }
    .dropdown:hover { background-color: #0d47a1; }
    .dropdown-content { display: none; position: absolute; background-color: #ffffff; min-width: 250px; box-shadow: 0px 8px 16px rgba(0,0,0,0.2); z-index: 100; border-radius: 0 0 6px 6px; }
    .dropdown-content a { color: #333; padding: 10px 15px; text-decoration: none; display: block; font-size: 13.5px; border-bottom: 1px solid #f0f0f0; }
    .dropdown-content a:hover { background-color: #e3f2fd; color: #0d47a1; font-weight: bold; }
    .dropdown:hover .dropdown-content { display: block; }
</style>
<script>
    function toggleDarkMode() {
        document.body.classList.toggle('dark-mode');
        localStorage.setItem('theme', document.body.classList.contains('dark-mode') ? 'dark' : 'light');
    }
    if (localStorage.getItem('theme') === 'dark') { document.body.classList.add('dark-mode'); }
</script>
'''

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ''
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = clean_auto_id(request.form.get('password', ''))
        user_agent = request.headers.get('User-Agent', '')
        
        is_pc = ("Windows" in user_agent or "Macintosh" in user_agent or "Linux" in user_agent) and not "Android" in user_agent
        device_category = "pc" if is_pc else "mobile"
        device_fingerprint = f"{'💻 لابتوب' if is_pc else '📱 هاتف'} ({user_agent[:40]})"
        
        if username == admin_credentials['username'] and password == admin_credentials['password']:
            session['username'] = 'admin'
            session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))
        elif username in teachers_db and clean_auto_id(teachers_db[username]['password']) == password:
            t_data = teachers_db[username]
            if device_category == "mobile":
                registered_dev = t_data.get('mobile_device', '')
                if not registered_dev:
                    t_data['mobile_device'] = device_fingerprint
                    save_to_disk()
                elif registered_dev != device_fingerprint:
                    error = 'عذراً! حسابك مرتبط بهاتف آخر. التواصل مع الإدارة لفك الربط.'
                    return render_template_string(login_template, error=error)
            else:
                registered_dev = t_data.get('pc_device', '')
                if not registered_dev:
                    t_data['pc_device'] = device_fingerprint
                    save_to_disk()
                elif registered_dev != device_fingerprint:
                    error = 'عذراً! حسابك مرتبط بلابتوب آخر. التواصل مع الإدارة لفك الربط.'
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
                <input type="password" name="password" placeholder="كلمة المرور (الرقم الآلي)" required>
                <button type="submit">دخول النظام</button>
            </form>
            <div style="color:#d32f2f; margin-top:12px; font-weight:bold; font-size:13px;">{{ error }}</div>
        </div>
        <div style="margin-top: 25px; color: #5c6bc0; font-size: 12px;">🛠️ معهد الهرمل الفني الرسمي</div>
    </body>
    </html>
'''

@app.route('/api/get_students/<path:class_name>')
def get_students(class_name):
    matched_students = []
    for c_key, sts in classes_students.items():
        if smart_match(class_name, c_key):
            matched_students = sts
            break
    if not matched_students: 
        matched_students = classes_students.get(class_name, [])
    
    student_details = []
    for st in matched_students:
        phone = students_contact_info.get(st, '')
        student_details.append({'name': st, 'phone': phone})
        
    return jsonify({'students': matched_students, 'details': student_details})

@app.route('/admin/set_academic_year', methods=['POST'])
def set_academic_year():
    global current_academic_year
    if session.get('role') != 'admin': return redirect(url_for('login'))
    selected_year = request.form.get('academic_year')
    if selected_year:
        current_academic_year = selected_year
        save_to_disk()
        session['msg'] = f"تم تحويل السنة الدراسية النشطة في النظام إلى: ({current_academic_year}) بنجاح!"
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/download_backup')
def download_backup():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    save_to_disk()
    if os.path.exists(DB_FILE):
        return send_file(DB_FILE, as_attachment=True, download_name=f"hermel_database_{datetime.now().strftime('%Y%m%d')}.json")
    return "ملف البيانات غير موجود", 404

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))
        
    msg = session.pop('msg', '')
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_hospital_gps':
            h_name = request.form.get('h_name', '').strip()
            h_type = request.form.get('h_type', '').strip()
            h_phone = request.form.get('h_phone', '').strip()
            h_address = request.form.get('h_address', '').strip()
            h_lat = request.form.get('h_lat', '34.3880').strip()
            h_lng = request.form.get('h_lng', '36.3810').strip()
            if h_name:
                try: lat_val = float(h_lat)
                except: lat_val = 34.3880
                try: lng_val = float(h_lng)
                except: lng_val = 36.3810
                
                hospitals_gps_db.append({
                    "name": h_name, "type": h_type, "phone": h_phone,
                    "lat": lat_val, "lng": lng_val, "address": h_address
                })
                save_to_disk()
                msg = "تم إضافة الموقع / المستشفى إلى الخريطة بنجاح! ✅"

        elif action == 'upload_directorate_file':
            file_key = request.form.get('file_key')
            file = request.files.get('excel_file')
            
            if file and file.filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS and file_key in directorate_excel_tables:
                try:
                    df = pd.read_excel(file)
                    col_mapping = {col: clean_column_name(col) for col in df.columns}
                    df_renamed = df.rename(columns=col_mapping)
                    rows_data = []
                    for _, row in df_renamed.iterrows():
                        r_dict = {col: ("" if pd.isna(row[col]) else clean_auto_id(row[col])) for col in df_renamed.columns}
                        rows_data.append(r_dict)
                    
                    if file_key in ['teachers_cards', 'personal_info']:
                        for r in rows_data:
                            t_raw_name = r.get('الاسم الثلاثي', r.get('اسم الاستاذ', r.get('الاسم', ''))).strip()
                            auto_id = clean_auto_id(r.get('الرقم الالي', r.get('الرقم الآلي', r.get('رقم الاستاذ', ''))))
                            phone_val = r.get('الهاتف', r.get('رقم الهاتف', r.get('خلوي', r.get('هاتف', ''))))
                            allowed_hrs = r.get('عدد الساعات المسموح بها', r.get('Maxhoures', '300'))
                            
                            if t_raw_name and len(t_raw_name.split()) >= 2:
                                user_id = next((u for u, t_info in teachers_db.items() if smart_match(t_info['name'], t_raw_name)), None)
                                if not user_id: user_id = f"teacher_{len(teachers_db) + 1}"
                                
                                try: c_val = int(float(allowed_hrs))
                                except: c_val = 300

                                teachers_db[user_id] = {
                                    "name": t_raw_name,
                                    "auto_id": auto_id,
                                    "phone": phone_val if phone_val else teachers_db.get(user_id, {}).get('phone', ''),
                                    "password": auto_id if auto_id else "123456",
                                    "subject": r.get('المادة', 'عام'),
                                    "mobile_device": teachers_db.get(user_id, {}).get('mobile_device', ''),
                                    "pc_device": teachers_db.get(user_id, {}).get('pc_device', ''),
                                    "notifications": teachers_db.get(user_id, {}).get('notifications', []),
                                    "monthly_hours": teachers_db.get(user_id, {}).get('monthly_hours', {}),
                                    "contract_hours": c_val
                                }

                    if file_key == 'teachers_and_subjects':
                        parsed_sub = parse_teachers_and_subjects_smart(df)
                        directorate_excel_tables['teachers_and_subjects']['parsed_schedule'] = parsed_sub

                    if file_key == 'students_registered':
                        new_classes = {}
                        for r in rows_data:
                            c_name = ""
                            s_name = ""
                            s_phone = ""
                            for k, v in r.items():
                                k_clean = str(k).strip()
                                if any(sub in k_clean for sub in ['الصف', 'Class', 'التخصص', 'الاختصاص', 'المستوى']):
                                    if v and str(v).strip() != 'nan': c_name = str(v).strip()
                                if any(sub in k_clean for sub in ['اسم الطالب', 'الاسم', 'الطالب', 'name']):
                                    if v and str(v).strip() != 'nan' and not s_name: s_name = str(v).strip()
                                if any(sub in k_clean for sub in ['هاتف', 'خلوي', 'رقم', 'phone', 'Mobile']):
                                    if v and str(v).strip() != 'nan' and not s_phone: s_phone = str(v).strip()
                            
                            if not c_name and len(r) > 1: c_name = str(list(r.values())[1]).strip()
                            if not s_name and len(r) > 0: s_name = str(list(r.values())[0]).strip()

                            if c_name and s_name and str(c_name) != 'nan' and str(s_name) != 'nan':
                                if c_name not in new_classes: new_classes[c_name] = []
                                if s_name not in new_classes[c_name]: new_classes[c_name].append(s_name)
                                if s_phone: students_contact_info[s_name] = s_phone
                        if new_classes: 
                            for cls_key, sts in new_classes.items():
                                if cls_key not in classes_students: classes_students[cls_key] = []
                                for st in sts:
                                    if st not in classes_students[cls_key]: classes_students[cls_key].append(st)

                    directorate_excel_tables[file_key] = {
                        "title": directorate_excel_tables[file_key]["title"],
                        "columns": list(df_renamed.columns),
                        "data": rows_data
                    }
                    save_to_disk()
                    msg = f"تم رفع وتحديث ملف ({directorate_excel_tables[file_key]['title']}) بنجاح!"
                except Exception as e: msg = f"خطأ في قراءة ملف الإكسل: {e}"

        elif action == 'create_auto_accounts':
            t_cards = directorate_excel_tables.get('teachers_cards', {}).get('data', [])
            count = 0
            for card in t_cards:
                name = card.get('الاسم الثلاثي', card.get('الاسم', '')).strip()
                auto_id = clean_auto_id(card.get('الرقم الالي', card.get('الرقم الآلي', card.get('رقم الاستاذ', ''))))
                phone = card.get('الهاتف', card.get('خلوي', card.get('هاتف', '')))
                allowed_hrs = card.get('عدد الساعات المسموح بها', card.get('Maxhoures', 300))
                try: c_hrs_val = int(float(allowed_hrs))
                except: c_hrs_val = 300

                if name and len(name.split()) >= 2:
                    user_id = f"teacher_{len(teachers_db) + 1}"
                    if not any(smart_match(t['name'], name) for t in teachers_db.values()):
                        teachers_db[user_id] = {
                            "name": name,
                            "auto_id": auto_id if auto_id else f"100{len(teachers_db)+1}",
                            "phone": phone,
                            "password": auto_id if auto_id else f"100{len(teachers_db)+1}",
                            "subject": card.get('المادة', 'عام'),
                            "mobile_device": "",
                            "pc_device": "",
                            "notifications": [],
                            "monthly_hours": {},
                            "contract_hours": c_hrs_val
                        }
                        count += 1
            save_to_disk()
            msg = f"تم توليد ({count}) حساب للأساتذة بنجاح!"

        elif action == 'reset_teacher_device':
            target_user = request.form.get('target_user')
            if target_user in teachers_db:
                teachers_db[target_user]['mobile_device'] = ''
                teachers_db[target_user]['pc_device'] = ''
                save_to_disk()
                msg = "تم فك ربط جهاز الأستاذ بنجاح!"

    sorted_teachers_list = sorted(teachers_db.items(), key=lambda x: x[1]['name'])
    
    teachers_rows = ""
    for u, t in sorted_teachers_list:
        auto_id_val = clean_auto_id(t.get('auto_id', 'غير محدد'))
        phone_val = t.get('phone', 'بدون رقم')
        pass_val = clean_auto_id(t.get('password', ''))
        
        clean_phone = re.sub(r'\D', '', str(phone_val))
        if clean_phone.startswith('0'): clean_phone = clean_phone[1:]
        if len(clean_phone) in [7, 8]: clean_phone = '961' + clean_phone
        
        teachers_rows += f"""
        <tr>
            <td><b>{t['name']}</b><br><small>الرقم الآلي: {auto_id_val}</small></td>
            <td><code style='color:#0d47a1; font-weight:bold; font-size:14px;'>{u}</code></td>
            <td><b style='color:#d32f2f; font-size:14px;'>{pass_val}</b></td>
            <td><b>{phone_val}</b></td>
            <td>
                {f'<a href="https://wa.me/{clean_phone}?text=' + f'مرحباً الاستاذ {t["name"]}، إليك بيانات حسابك في نظام معهد الهرمل الفني:\nاسم المستخدم: {u}\nكلمة المرور: {pass_val}" target="_blank" style="background:#25D366; color:white; padding:6px 12px; border-radius:4px; text-decoration:none; font-weight:bold; font-size:12px; display:inline-block;">📲 إرسال الحساب واتساب</a>' if clean_phone else '<span style="color:#777; font-size:12px;">لا يوجد رقم</span>'}
            </td>
        </tr>
        """

    hospitals_rows = ""
    for h in hospitals_gps_db:
        hospitals_rows += f"""
        <tr>
            <td><b>{h['name']}</b></td>
            <td>{h['type']}</td>
            <td>{h.get('phone', 'غير محدد')}</td>
            <td>{h.get('address', 'الهرمل')}</td>
            <td><a href="https://maps.google.com/?q={h['lat']},{h['lng']}" target="_blank" style="background:#1565c0; color:white; padding:5px 10px; border-radius:4px; text-decoration:none; font-size:12px;">🗺️ فتح عبر الخريطة (GPS)</a></td>
        </tr>
        """

    teachers_wa_opts = "".join([f"<option value='{t.get('phone', '')}'>{t['name']} - {t.get('phone', 'بدون رقم')}</option>" for u, t in sorted_teachers_list])
    classes_wa_opts = "".join([f"<option value='{c}'>{c}</option>" for c in classes_students.keys()])
    year_select_opts = "".join([f"<option value='{y}' {'selected' if y==current_academic_year else ''}>{y}</option>" for y in academic_years_db])

    admin_template = '''
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
            .wa-btn { background: #25D366; color: white; border: none; padding: 10px 15px; font-weight: bold; border-radius: 6px; cursor: pointer; display: inline-flex; align-items: center; gap: 8px; justify-content: center; text-decoration: none; font-size: 14px; }
        </style>
    </head>
    <body>
        ''' + HEADER_VTE_HTML + '''

        <div class="container">
            {% if msg %}<div style="background:#e8f5e9; color:#2e7d32; padding:12px; border-radius:6px; font-weight:bold; margin-bottom:15px;">{{ msg }}</div>{% endif %}

            <!-- مركز التواصل الفوري عبر الواتساب للطالب أو الصف -->
            <div id="whatsAppCenterSec" class="card active">
                <h3 style="color:#25D366; margin-top:0;">💬 مركز إرسال رسائل الواتساب (لطالب معين أو للصف كاملاً)</h3>
                <div style="background:#f1f8e9; padding:15px; border-radius:8px; border:1px solid #c8e6c9;">
                    <label><b>1. اختر الصف الدراسي:</b></label>
                    <select id="waClassSelect" onchange="loadStudentsForWhatsApp()">
                        <option value="">-- اختر الصف --</option>
                        ''' + classes_wa_opts + '''
                    </select>

                    <div style="margin-top:12px; display:flex; gap:15px; align-items:center;">
                        <label style="cursor:pointer; font-weight:bold; color:#0d47a1;"><input type="radio" name="waTargetMode" value="student" checked onchange="toggleWaMode()"> مراسلة طالب معين</label>
                        <label style="cursor:pointer; font-weight:bold; color:#2e7d32;"><input type="radio" name="waTargetMode" value="class" onchange="toggleWaMode()"> مراسلة الصف كاملاً (إرسال عام)</label>
                    </div>

                    <div id="singleStudentBox" style="margin-top:12px;">
                        <label><b>2. اختر الطالب:</b></label>
                        <select id="waStudentSelect" onchange="fillStudentPhone()">
                            <option value="">-- اختر الطالب أولاً --</option>
                        </select>
                        <label style="margin-top:8px; display:block;"><b>رقم الهاتف للواتساب:</b></label>
                        <input type="text" id="waPhoneInput" placeholder="مثال: 78918411">
                    </div>

                    <div id="classBroadcastBox" style="margin-top:12px; display:none; background:#e8f5e9; padding:10px; border-radius:6px;">
                        <p style="margin:0; font-size:13px; color:#2e7d32; font-weight:bold;">📢 سيتم توجيه الرسالة لكل طلاب هذا الصف.</p>
                    </div>

                    <label style="margin-top:12px; display:block;"><b>3. نص الرسالة المراد إرسالها:</b></label>
                    <textarea id="waMessageInput" placeholder="اكتب نص الرسالة هنا..." style="height:90px;"></textarea>

                    <div style="margin-top:10px; display:flex; gap:10px; flex-wrap:wrap;">
                        <button type="button" onclick="setWaTemplate('absence')" style="background:#e65100; width:auto; font-size:12px;">قالب: إشعار غياب</button>
                        <button type="button" onclick="setWaTemplate('exam')" style="background:#1565c0; width:auto; font-size:12px;">قالب: تذكير امتحان</button>
                        <button type="button" onclick="setWaTemplate('general')" style="background:#37474f; width:auto; font-size:12px;">قالب: تعميم عام للصف</button>
                    </div>

                    <div style="margin-top:15px;">
                        <button type="button" onclick="sendWhatsAppMessage()" class="wa-btn" style="width:100%;">📲 فتح وتوجيه إلى الواتساب فوراً</button>
                    </div>
                </div>
            </div>

            <!-- مركز الواتساب للأساتذة -->
            <div id="whatsAppTeacherSec" class="card">
                <h3 style="color:#25D366; margin-top:0;">📲 مراسلة أستاذ مباشرة وإرسال الحساب</h3>
                <label>اختر الأستاذ:</label>
                <select id="waTeacherSelect" onchange="fillTeacherPhone()">
                    <option value="">-- اختر الأستاذ --</option>
                    ''' + teachers_wa_opts + '''
                </select>
                <label style="margin-top:10px; display:block;">رقم هاتف الأستاذ:</label>
                <input type="text" id="waTeacherPhoneInput" placeholder="رقم الهاتف...">
                <label style="margin-top:10px; display:block;">نص الرسالة:</label>
                <textarea id="waTeacherMsg" placeholder="اكتب الرسالة..." style="height:80px;"></textarea>
                <button type="button" onclick="sendTeacherWhatsApp()" class="wa-btn" style="margin-top:12px; width:100%;">📲 إرسال عبر الواتساب</button>
            </div>

            <!-- دليل المستشفيات والـ GPS (الميزة المدمجة) -->
            <div id="gpsHospitalsSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">🏥 دليل المستشفيات ومواقع GPS والخدمات</h3>
                <p style="font-size:13px; color:#555;">المواقع الحيوية والمستشفيات في الهرمل ومحيط المعهد:</p>
                <table>
                    <tr>
                        <th>اسم المكان / المستشفى</th>
                        <th>التصنيف</th>
                        <th>رقم الهاتف</th>
                        <th>العنوان</th>
                        <th>الموقع (GPS)</th>
                    </tr>
                    ''' + hospitals_rows + '''
                </table>

                <div style="margin-top:20px; background:#e3f2fd; padding:15px; border-radius:8px;">
                    <h4 style="margin-top:0; color:#0d47a1;">➕ إضافة موقع أو مستشفى جديد</h4>
                    <form method="POST">
                        <input type="hidden" name="action" value="add_hospital_gps">
                        <div style="display:flex; gap:10px; flex-wrap:wrap;">
                            <input type="text" name="h_name" placeholder="اسم المستشفى أو الموقع" required style="flex:1; min-width:200px;">
                            <input type="text" name="h_type" placeholder="التصنيف (مستشفى، مركز،...)" required style="flex:1; min-width:150px;">
                        </div>
                        <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:8px;">
                            <input type="text" name="h_phone" placeholder="رقم الهاتف" style="flex:1;">
                            <input type="text" name="h_address" placeholder="العنوان بالتفصيل" style="flex:1;">
                        </div>
                        <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:8px;">
                            <input type="text" name="h_lat" placeholder="خط العرض Lat (مثال: 34.3880)" style="flex:1;">
                            <input type="text" name="h_lng" placeholder="خط الطول Lng (مثال: 36.3810)" style="flex:1;">
                        </div>
                        <button type="submit" style="margin-top:12px; background:#2e7d32;">💾 حفظ وإضافة الموقع للقاعدة</button>
                    </form>
                </div>
            </div>

            <!-- جدول الأساتذة وتوليد الحسابات -->
            <div id="teachersListSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">👨‍🏫 سجل الأساتذة ومعلومات الدخول (اسم المستخدم وكلمة المرور)</h3>
                <form method="POST" style="margin-bottom:15px;">
                    <input type="hidden" name="action" value="create_auto_accounts">
                    <button type="submit" style="background:#2e7d32;">⚡ توليد حسابات الأساتذة من بطاقات الأساتذة</button>
                </form>
                <table>
                    <tr>
                        <th>اسم الأستاذ والمعلومات</th>
                        <th>اسم المستخدم (Username)</th>
                        <th>كلمة المرور (الرقم الآلي)</th>
                        <th>رقم الهاتف</th>
                        <th>إرسال الحساب واتساب</th>
                    </tr>
                    ''' + teachers_rows + '''
                </table>
            </div>

            <div id="academicYearSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">📅 التبديل وتحديد السنة الدراسية النشطة</h3>
                <form action="/admin/set_academic_year" method="POST">
                    <label>اختر السنة الدراسية النشطة للنظام:</label>
                    <select name="academic_year">''' + year_select_opts + '''</select>
                    <button type="submit" style="background:#2e7d32; margin-top:12px;">تأكيد واعتماد السنة الدراسية</button>
                </form>
            </div>

            <div id="studentAttendanceSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">📋 سجل حضور وغياب الطلاب</h3>
                <p>يتم رصد الغياب تلقائياً فور إدخاله من واجهات الأساتذة.</p>
            </div>

            <div id="studentGradesSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">📝 علامات ونتائج الطلاب</h3>
                <p>استعراض علامات الطلاب.</p>
            </div>

            <div id="uploadDirectorateFilesSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">⚙️ رفع ملفات المديرية (Excel)</h3>
                <form method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="action" value="upload_directorate_file">
                    <label>نوع الملف:</label>
                    <select name="file_key" required>
                        <option value="students_registered">📂 1. الطلاب المسجلون</option>
                        <option value="teachers_cards">📇 2. بطاقات الاساتذة</option>
                        <option value="teachers_and_subjects">📋 3. الاستاذ والمواد (التوزيع الرسمي)</option>
                    </select>
                    <input type="file" name="excel_file" accept=".xlsx, .xls" required style="margin-top:10px;">
                    <button type="submit" style="margin-top:12px; background:#2e7d32;">📥 رفع وتحديث البيانات</button>
                </form>
            </div>

            <div id="deviceBindingSec" class="card">
                <h3 style="color:#c62828; margin-top:0;">📱 إدارة أجهزة الأساتذة (فك الربط)</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="reset_teacher_device">
                    <select name="target_user" required><option value="">-- اختر الأستاذ --</option>
                    ''' + teachers_wa_opts + '''
                    </select>
                    <button type="submit" style="margin-top:10px; background:#c62828;">🔓 فك الربط فوراً</button>
                </form>
            </div>

            <div id="backupSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">💾 النسخ الاحتياطي</h3>
                <a href="/admin/download_backup" style="display:inline-block; background:#2e7d32; color:white; padding:10px 18px; border-radius:6px; text-decoration:none; font-weight:bold;">📥 تنزيل نسخة احتياطية</a>
            </div>

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

            let currentClassStudents = [];

            function loadStudentsForWhatsApp() {
                let cls = document.getElementById('waClassSelect').value;
                let stdSelect = document.getElementById('waStudentSelect');
                stdSelect.innerHTML = '<option value="">جاري التحميل...</option>';
                currentClassStudents = [];
                if(!cls) return;
                
                fetch('/api/get_students/' + encodeURIComponent(cls)).then(res => res.json()).then(data => {
                    currentClassStudents = data.details;
                    let opts = '<option value="">-- اختر الطالب --</option>';
                    data.details.forEach(st => {
                        opts += `<option value="${st.phone}" data-name="${st.name}">${st.name} ${st.phone ? '('+st.phone+')' : '(بدون رقم)'}</option>`;
                    });
                    stdSelect.innerHTML = opts;
                });
            }

            function toggleWaMode() {
                let mode = document.querySelector('input[name="waTargetMode"]:checked').value;
                let singleBox = document.getElementById('singleStudentBox');
                let classBox = document.getElementById('classBroadcastBox');
                if(mode === 'student') {
                    singleBox.style.display = 'block';
                    classBox.style.display = 'none';
                } else {
                    singleBox.style.display = 'none';
                    classBox.style.display = 'block';
                }
            }

            function fillStudentPhone() {
                let stdSelect = document.getElementById('waStudentSelect');
                let phone = stdSelect.value;
                if(phone) { document.getElementById('waPhoneInput').value = phone; }
            }

            function fillTeacherPhone() {
                let tSelect = document.getElementById('waTeacherSelect');
                let phone = tSelect.value;
                if(phone) { document.getElementById('waTeacherPhoneInput').value = phone; }
            }

            function setWaTemplate(type) {
                let mode = document.querySelector('input[name="waTargetMode"]:checked').value;
                let msgBox = document.getElementById('waMessageInput');

                if(mode === 'student') {
                    let stdSelect = document.getElementById('waStudentSelect');
                    let selectedOpt = stdSelect.options[stdSelect.selectedIndex];
                    let studentName = selectedOpt ? selectedOpt.getAttribute('data-name') || 'الطالب' : 'الطالب';
                    if(type === 'absence') {
                        msgBox.value = `حضرة ولي أمر الطالب/ة ${studentName} المحترم، نحيطكم علماً بتسجيل غياب عن الحصص الدراسية اليوم في معهد الهرمل الفني.`;
                    } else if(type === 'exam') {
                        msgBox.value = `جانب الطالب/ة ${studentName} المحترم، نذكركم بموعد الامتحان القادم في معهد الهرمل الفني. نتمنى لكم التوفيق والنجاح.`;
                    } else if(type === 'general') {
                        msgBox.value = `جانب الطالب/ة ${studentName}، تحية طيبة من إدارة معهد الهرمل الفني الرسمية.`;
                    }
                } else {
                    let clsName = document.getElementById('waClassSelect').value || 'الصف';
                    if(type === 'absence') {
                        msgBox.value = `تنبيه لطلاب صف ${clsName} في معهد الهرمل الفني: يرجى الانتباه للدوام المدرسي.`;
                    } else if(type === 'exam') {
                        msgBox.value = `تنويه هام لطلاب صف ${clsName}: نذكركم بمواعيد الامتحانات القادمة. نتمنى للجميع النجاح.`;
                    } else if(type === 'general') {
                        msgBox.value = `تعميم إداري هام صادر عن إدارة معهد الهرمل الفني لطلاب صف ${clsName}: ...`;
                    }
                }
            }

            function sendWhatsAppMessage() {
                let mode = document.querySelector('input[name="waTargetMode"]:checked').value;
                let msg = encodeURIComponent(document.getElementById('waMessageInput').value);

                if(mode === 'student') {
                    let phone = document.getElementById('waPhoneInput').value.replace(/\D/g, '');
                    if(!phone) { alert("يرجى إدخال أو اختيار رقم الهاتف أولاً"); return; }
                    if(!phone.startsWith('961') && phone.length <= 8) { phone = '961' + phone; }
                    window.open(`https://wa.me/${phone}?text=${msg}`, '_blank');
                } else {
                    if(currentClassStudents.length === 0) { alert("لا توجد أسماء طلاب في هذا الصف أو لم يتم تحميلهم"); return; }
                    let validStudents = currentClassStudents.filter(st => st.phone && st.phone.trim() !== '');
                    if(validStudents.length === 0) { alert("لا توجد أرقام هواتف مسجلة لطلاب هذا الصف"); return; }
                    
                    if(confirm(`سيتم فتح محادثات واتساب تباعاً لـ (${validStudents.length}) طالب لديهم أرقام هواتف. هل تريد المتابعة؟`)) {
                        validStudents.forEach((st, idx) => {
                            let phone = st.phone.replace(/\D/g, '');
                            if(!phone.startsWith('961') && phone.length <= 8) { phone = '961' + phone; }
                            setTimeout(() => {
                                window.open(`https://wa.me/${phone}?text=${msg}`, '_blank');
                            }, idx * 600);
                        });
                    }
                }
            }

            function sendTeacherWhatsApp() {
                let phone = document.getElementById('waTeacherPhoneInput').value.replace(/\D/g, '');
                let msg = encodeURIComponent(document.getElementById('waTeacherMsg').value);
                if(!phone) { alert("يرجى اختيار الأستاذ أو إدخال رقم الهاتف أولاً"); return; }
                if(!phone.startsWith('961') && phone.length <= 8) { phone = '961' + phone; }
                window.open(`https://wa.me/${phone}?text=${msg}`, '_blank');
            }
        </script>
    </body>
    </html>
    '''
    return render_template_string(admin_template, current_academic_year=current_academic_year, msg=msg)

@app.route('/teacher', methods=['GET', 'POST'])
def teacher_dashboard():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    username = session.get('username')
    user_data = teachers_db.get(username, {})
    t_name = user_data.get('name', '').strip()
    msg = ''
    teacher_assignments = get_teacher_assignments(t_name)

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'submit_class_grades':
            assignment_pair = request.form.get('assignment_pair')
            if assignment_pair and '|' in assignment_pair:
                class_name, subject = assignment_pair.split('|')
                students = classes_students.get(class_name, [])
                for st in students:
                    val = request.form.get(f"grade_{st}")
                    if val is not None and val != "":
                        grades_db[f"{st} - {class_name} ({subject})"] = val
                save_to_disk()
                msg = f"تم حفظ ورصد علامات مادة ({subject}) بنجاح!"

    grade_assignment_opts = "".join([f'<option value="{asg["class"]}|{asg["subject"]}">صف: {asg["class"]} - مادة: {asg["subject"]}</option>' for asg in teacher_assignments])
    att_class_opts = "".join([f'<option value="{c}">{c}</option>' for c in classes_students.keys()])

    teacher_template = """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>واجهة الأستاذ - معهد الهرمل الفني</title>
        <style>
            body { font-family: system-ui, sans-serif; background: #f4f6f9; margin: 0; padding-bottom: 30px; }
            .card { background: white; padding: 18px; border-radius: 8px; margin-top: 15px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); border-top: 4px solid #0d47a1; }
            input, select, textarea, button { width: 100%; padding: 10px; margin-top: 6px; box-sizing: border-box; font-family: inherit; }
            button { background: #0d47a1; color: white; border: none; font-weight: bold; cursor: pointer; border-radius: 5px; }
            .student-row { display: flex; justify-content: space-between; align-items: center; padding: 8px; border-bottom: 1px solid #eee; background: #fafafa; margin-top: 5px; }
        </style>
    </head>
    <body>
        <div style="background:#0d47a1; color:white; padding:12px 20px; display:flex; justify-content:space-between; align-items:center;">
            <div><h3 style="margin:0;">معهد الهرمل الفني</h3><small>الأستاذ: {{ t_name }}</small></div>
            <a href="/logout" style="color:#ffcdd2; background:#c62828; padding:6px 12px; border-radius:4px; text-decoration:none; font-size:12px;">خروج</a>
        </div>
        <div style="padding:15px;">
            {% if msg %}<div style="background:#e8f5e9; color:#2e7d32; padding:10px; border-radius:6px; margin-bottom:10px; font-weight:bold;">{{ msg }}</div>{% endif %}
            <div class="card">
                <h4 style="color:#0d47a1; margin-top:0;">📝 إدخال ورصد علامات الطلاب (0 إلى 20 أو غائب):</h4>
                <form method="POST">
                    <input type="hidden" name="action" value="submit_class_grades">
                    <label>اختر الصف والمادة:</label>
                    <select name="assignment_pair" id="gradePair" onchange="loadStudentsForGrades()" required>
                        <option value="">-- اختر الصف والمادة الموكلة إليك --</option>
                        {{ grade_assignment_opts | safe }}
                    </select>
                    <div id="gradeContainer" style="margin-top:10px;"></div>
                    <button type="submit" id="gradeBtn" style="display:none; margin-top:10px;">حفظ ورصد العلامات</button>
                </form>
            </div>
        </div>
        <script>
            function loadStudentsForGrades() {
                let val = document.getElementById('gradePair').value;
                let cont = document.getElementById('gradeContainer');
                let btn = document.getElementById('gradeBtn');
                cont.innerHTML = '';
                if(!val || !val.includes('|')) { btn.style.display='none'; return; }
                let className = val.split('|')[0];
                fetch('/api/get_students/' + encodeURIComponent(className)).then(res => res.json()).then(data => {
                    let html = '<p style="font-size:13px; color:#555;">حدد العلامة للطالب:</p>';
                    data.students.forEach(st => {
                        let selectOpts = '<option value="">-- حدد العلامة --</option><option value="غائب" style="color:#c62828; font-weight:bold;">❌ غائب</option>';
                        for(let i=0; i<=20; i+=0.5) { selectOpts += `<option value="${i}">${i} / 20</option>`; }
                        html += `<div class="student-row"><span style="flex:1; font-weight:bold;">${st}</span><select name="grade_${st}" style="width:140px;" required>${selectOpts}</select></div>`;
                    });
                    cont.innerHTML = html;
                    btn.style.display = 'block';
                });
            }
        </script>
    </body>
    </html>
    """
    return render_template_string(teacher_template, t_name=t_name, msg=msg, grade_assignment_opts=grade_assignment_opts, att_class_opts=att_class_opts)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)