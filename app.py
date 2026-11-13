import os
import json
import math
import re
import traceback
import pandas as pd
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, session, send_from_directory, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = 'hermel_tech_enterprise_shams_2026_secure_key'

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'xlsx', 'xls'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    if not DATABASE_URL:
        return None
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"Error connecting to Supabase: {e}")
        return None

def init_supabase_db():
    conn = get_db_connection()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value JSONB
            );
        ''')
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error initializing Supabase tables: {e}")

init_supabase_db()

TRAINING_LOCATIONS = {
    "مستشفى الهرمل الحكومي": {"lat": 34.381283, "lng": 36.424456, "radius_meters": 300},
    "مستشفى البتول": {"lat": 34.381283, "lng": 36.424456, "radius_meters": 300},
    "مستشفى دار الكرامة": {"lat": 34.403492, "lng": 36.396789, "radius_meters": 250},
    "مستشفى العاصي": {"lat": 34.398330, "lng": 36.406490, "radius_meters": 250},
    "مدرسة سانرايز": {"lat": 34.403492, "lng": 36.396789, "radius_meters": 200},
    "ثانوية الرشاد": {"lat": 34.403826, "lng": 36.391736, "radius_meters": 200},
    "مدرسة الإمام علي": {"lat": 34.395518, "lng": 36.386411, "radius_meters": 200}
}

MONTH_COLUMNS = ["10", "11", "12", "01", "02", "03", "04", "05", "06", "07", "08"]

def save_to_disk(key, value):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO kv_store (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;",
                (key, json.dumps(value, ensure_ascii=False))
            )
            conn.commit()
            cur.close()
            conn.close()
            return
        except Exception as e:
            print(f"Error saving {key} to Supabase: {e}")

    local_data = {}
    if os.path.exists('local_db.json'):
        try:
            with open('local_db.json', 'r', encoding='utf-8') as f:
                local_data = json.load(f)
        except: pass
    local_data[key] = value
    with open('local_db.json', 'w', encoding='utf-8') as f:
        json.dump(local_data, f, ensure_ascii=False, indent=2)

def load_from_disk(key, default_val=None):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT value FROM kv_store WHERE key = %s;", (key,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row and row.get('value') is not None:
                val = row['value']
                if isinstance(val, str):
                    return json.loads(val)
                return val
        except Exception as e:
            print(f"Error loading {key} from Supabase: {e}")

    if os.path.exists('local_db.json'):
        try:
            with open('local_db.json', 'r', encoding='utf-8') as f:
                local_data = json.load(f)
                if key in local_data:
                    return local_data[key]
        except: pass
    return default_val

teachers_db = load_from_disk('teachers_db', {})
grades_db = load_from_disk('grades_db', {})
attendance_db = load_from_disk('attendance_db', {})
teacher_classes_map = load_from_disk('teacher_classes_map', {})
admin_replies = load_from_disk('admin_replies', [])
admin_credentials = load_from_disk('admin_credentials', {'username': 'admin', 'password': '123456'})
classes_students = load_from_disk('classes_students', {
    "سنة ثالثة عناية تمريضية": ["علي أحمد شمص", "حسن محمد زعيتر", "ميرا شمص", "سيلا شمص"],
    "سنة ثانية معلوماتية": ["محمد حسين أمهز", "سارة يوسف دندش"]
})
current_academic_year = load_from_disk('current_academic_year', "2026-2027")
field_sessions = load_from_disk('field_sessions', [])
directorate_excel_tables = load_from_disk('directorate_excel_tables', {
    "students_registered": {"title": "الطلاب المسجلون", "columns": [], "data": []},
    "teachers_cards": {"title": "بطاقات الاساتذة", "columns": [], "data": []},
    "personal_info": {"title": "المعلومات الشخصية", "columns": [], "data": []},
    "weekly_schedule": {"title": "برنامج اسبوعي مع الاساتذة والمواد", "columns": [], "data": [], "parsed_schedule": {}},
    "executed_hours": {"title": "الساعات المنفذة للاساتذة", "columns": [], "data": [], "monthly_hours": {}},
    "fingerprint_ids": {"title": "أرقام بصمات الأساتذة والموظفين (IDs)", "columns": [], "data": []}
})

def save_all_data():
    try:
        save_to_disk('teachers_db', teachers_db)
        save_to_disk('grades_db', grades_db)
        save_to_disk('attendance_db', attendance_db)
        save_to_disk('teacher_classes_map', teacher_classes_map)
        save_to_disk('admin_replies', admin_replies)
        save_to_disk('admin_credentials', admin_credentials)
        save_to_disk('classes_students', classes_students)
        save_to_disk('current_academic_year', current_academic_year)
        save_to_disk('field_sessions', field_sessions)
        save_to_disk('directorate_excel_tables', directorate_excel_tables)
    except Exception as e:
        print(f"Error in save_all_data: {e}")

def clean_column_name(col):
    try:
        col_str = str(col).strip()
        col_str = col_str.replace("&#x27;", "").replace("'", "").replace('"', '')
        col_str = re.sub(r'^ش\s*', '', col_str)
        if len(col_str) == 1 and col_str.isdigit():
            col_str = '0' + col_str
        return col_str
    except:
        return "البيان"

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_weekly_schedule(df):
    parsed_teachers = {}
    current_class = "عام"
    try:
        for _, row in df.iterrows():
            first_col = str(row.iloc[0]).strip()
            if "المستوى" in first_col or "الصف" in first_col:
                current_class = first_col
                continue
            day_name = first_col
            if day_name in ["الاثنين", "الثلاثاء", "الاربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]:
                for col_idx in range(1, len(row)):
                    cell_val = row.iloc[col_idx]
                    if pd.notna(cell_val):
                        cell_str = str(cell_val).strip()
                        if "/***/" in cell_str:
                            parts = cell_str.split("/***/")
                            teacher_name = parts[0].strip()
                            subject_name = parts[1].strip() if len(parts) > 1 else "مادة عامة"
                            period_num = f"حصة {col_idx}"
                            if teacher_name not in parsed_teachers:
                                parsed_teachers[teacher_name] = []
                            parsed_teachers[teacher_name].append({
                                "day": day_name, "period": period_num, "class": current_class, "subject": subject_name
                            })
    except Exception as e:
        print(f"Error parsing schedule: {e}")
    return parsed_teachers

@app.errorhandler(Exception)
def handle_exception(e):
    err_msg = traceback.format_exc()
    return f"""
    <div dir="rtl" style="font-family:sans-serif; padding:30px; background:#ffebee; color:#c62828; border:2px solid #c62828; border-radius:8px; margin:20px;">
        <h2>⚠️ حدث خطأ تقني في النظام:</h2>
        <pre style="background:#fff; padding:15px; border:1px solid #ffcdd2; overflow-x:auto; direction:ltr; text-align:left;">{err_msg}</pre>
    </div>
    """, 500

SHARED_HEAD = '''
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.rtl.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body { font-family: system-ui, -apple-system, sans-serif; background-color: #f8fafc; color: #1e293b; }
        .navbar-custom { background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
        .card-custom { border: none; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03); background: #ffffff; transition: transform 0.2s; margin-bottom: 20px; display: none; }
        .card-custom.active { display: block; animation: fadeIn 0.3s ease-in-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        .btn-primary-custom { background-color: #1e3a8a; border-color: #1e3a8a; color: white; font-weight: 600; }
        .btn-primary-custom:hover { background-color: #1e40af; border-color: #1e40af; color: white; }
        .table-custom th { background-color: #f1f5f9; color: #334155; font-weight: 600; text-align: center; }
        .table-custom td { text-align: center; vertical-align: middle; }
        .dropdown-menu { border-radius: 10px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); border: none; }
        .dropdown-item { font-weight: 500; padding: 8px 16px; }
        .dropdown-item:hover { background-color: #eff6ff; color: #1e3a8a; }
    </style>
'''

HEADER_VTE_HTML = '''
<nav class="navbar navbar-expand-lg navbar-dark navbar-custom px-4 py-3">
    <div class="container-fluid">
        <a class="navbar-brand d-flex align-items-center gap-3" href="/admin">
            <div class="bg-white p-2 rounded-circle text-primary shadow-sm">
                <i class="fa-solid fa-graduation-cap fa-lg"></i>
            </div>
            <div>
                <div class="fw-bold fs-5">الجمهورية اللبنانية 🌲 - معهد الهرمل الفني</div>
                <div class="small text-info">نظام الإدارة الرقمية والذكية - إشراف وإدارة المدير</div>
            </div>
        </a>
        <div class="d-flex align-items-center gap-3">
            <a href="/logout" class="btn btn-danger btn-sm px-3 fw-bold shadow-sm"><i class="fa-solid fa-right-from-bracket ms-1"></i> خروج</a>
        </div>
    </div>
</nav>

<div class="bg-primary bg-gradient px-4 py-2 shadow-sm">
    <div class="container-fluid d-flex flex-wrap gap-2 align-items-center justify-content-start">
        <a href="/admin" class="btn btn-light btn-sm fw-bold text-primary"><i class="fa-solid fa-house ms-1"></i> الرئيسية</a>
        
        <div class="dropdown">
            <button class="btn btn-outline-light btn-sm dropdown-toggle fw-bold" data-bs-toggle="dropdown"><i class="fa-solid fa-user-graduate ms-1"></i> الطلاب</button>
            <ul class="dropdown-menu">
                <li><a class="dropdown-item" href="javascript:void(0)" onclick="showSection('studentAttendanceSec')"><i class="fa-solid fa-clipboard-user text-primary ms-2"></i> حضور وغياب الطلاب</a></li>
                <li><a class="dropdown-item" href="javascript:void(0)" onclick="showSection('studentGradesSec')"><i class="fa-solid fa-star text-warning ms-2"></i> علامات ونتائج الطلاب</a></li>
                <li><a class="dropdown-item" href="javascript:void(0)" onclick="showSection('viewRegisteredStudents')"><i class="fa-solid fa-folder-open text-success ms-2"></i> جدول الطلاب المسجلون</a></li>
            </ul>
        </div>

        <div class="dropdown">
            <button class="btn btn-outline-light btn-sm dropdown-toggle fw-bold" data-bs-toggle="dropdown"><i class="fa-solid fa-chalkboard-user ms-1"></i> الأساتذة والدوام</button>
            <ul class="dropdown-menu">
                <li><a class="dropdown-item" href="javascript:void(0)" onclick="showSection('attendanceReportSec')"><i class="fa-solid fa-clock-rotate-left text-primary ms-2"></i> كشف الحضور والغياب (20 حصة)</a></li>
                <li><a class="dropdown-item" href="javascript:void(0)" onclick="showSection('teachersListSec')"><i class="fa-solid fa-users text-success ms-2"></i> سجل الأساتذة وعقود الساعات</a></li>
                <li><a class="dropdown-item" href="javascript:void(0)" onclick="showSection('viewFingerprintIds')"><i class="fa-solid fa-fingerprint text-danger ms-2"></i> أرقام البصمة ID</a></li>
                <li><a class="dropdown-item" href="javascript:void(0)" onclick="showSection('viewWeeklySchedule')"><i class="fa-solid fa-calendar-days text-info ms-2"></i> البرنامج الأسبوعي والمواد</a></li>
                <li><a class="dropdown-item" href="javascript:void(0)" onclick="showSection('viewExecutedHours')"><i class="fa-solid fa-chart-line text-warning ms-2"></i> الساعات المنفذة شهرياً</a></li>
            </ul>
        </div>

        <div class="dropdown">
            <button class="btn btn-outline-light btn-sm dropdown-toggle fw-bold" data-bs-toggle="dropdown"><i class="fa-solid fa-map-location-dot ms-1"></i> التدريب الميداني GPS</button>
            <ul class="dropdown-menu">
                <li><a class="dropdown-item" href="javascript:void(0)" onclick="showSection('fieldSessionSec')"><i class="fa-solid fa-hospital text-danger ms-2"></i> إدارة الجلسات الميدانية</a></li>
            </ul>
        </div>

        <div class="dropdown">
            <button class="btn btn-outline-light btn-sm dropdown-toggle fw-bold" data-bs-toggle="dropdown"><i class="fa-solid fa-gears ms-1"></i> الإعدادات والملفات</button>
            <ul class="dropdown-menu">
                <li><a class="dropdown-item" href="javascript:void(0)" onclick="showSection('uploadDirectorateFilesSec')"><i class="fa-solid fa-file-excel text-success ms-2"></i> رفع ملفات المديرية (Excel)</a></li>
                <li><a class="dropdown-item" href="javascript:void(0)" onclick="showSection('deviceBindingSec')"><i class="fa-solid fa-mobile-screen text-primary ms-2"></i> إدارة أجهزة الأساتذة (فك الربط)</a></li>
                <li><a class="dropdown-item" href="javascript:void(0)" onclick="showSection('sendNotifSec')"><i class="fa-solid fa-bullhorn text-warning ms-2"></i> إرسال تعميم إداري</a></li>
                <li><a class="dropdown-item" href="javascript:void(0)" onclick="showSection('teacherRepliesSec')"><i class="fa-solid fa-envelope-open-text text-info ms-2"></i> الأعذار والرسائل الواردة</a></li>
                <li><a class="dropdown-item" href="javascript:void(0)" onclick="showSection('changePassSec')"><i class="fa-solid fa-key text-danger ms-2"></i> تغيير كلمة السر الإدارية</a></li>
            </ul>
        </div>
    </div>
</div>
'''

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ''
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '').strip()
        current_device_fingerprint = request.headers.get('User-Agent', 'unknown_device')
        
        if username == admin_credentials.get('username', 'admin') and password == admin_credentials.get('password', '123456'):
            session['username'] = 'admin'
            session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))
        elif username in teachers_db and teachers_db[username].get('password') == password:
            t_data = teachers_db[username]
            if not t_data.get('device_id'):
                t_data['device_id'] = current_device_fingerprint
                save_all_data()
            elif t_data.get('device_id') != current_device_fingerprint:
                error = 'عذراً! هذا الحساب مرتبط بهاتف أستاذ آخر. يرجى التواصل مع مدير المعهد لإعادة تعيين الجهاز.'
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
        {{ shared_head | safe }}
        <title>تسجيل الدخول - معهد الهرمل الفني</title>
        <style>
            body { background: linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%); height: 100vh; display: flex; align-items: center; justify-content: center; }
            .login-card { background: white; border-radius: 16px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.2); width: 100%; max-width: 420px; padding: 40px; border-top: 6px solid #1e3a8a; }
        </style>
    </head>
    <body>
        <div class="login-card text-center">
            <div class="bg-primary bg-opacity-10 p-3 rounded-circle d-inline-block text-primary mb-3 shadow-sm">
                <i class="fa-solid fa-graduation-cap fa-2x"></i>
            </div>
            <div class="small fw-bold text-muted mb-1">الجمهورية اللبنانية 🌲</div>
            <h3 class="fw-bold text-dark mb-2">معهد الهرمل الفني</h3>
            <p class="text-muted small mb-4">نظام الحضور والإنصراف الذكي</p>
            <form method="POST">
                <div class="mb-3 text-start">
                    <label class="form-label small fw-bold text-secondary">اسم المستخدم</label>
                    <div class="input-group">
                        <span class="input-group-text bg-light"><i class="fa-solid fa-user text-muted"></i></span>
                        <input type="text" name="username" class="form-control" placeholder="أدخل اسم المستخدم" required>
                    </div>
                </div>
                <div class="mb-4 text-start">
                    <label class="form-label small fw-bold text-secondary">كلمة المرور</label>
                    <div class="input-group">
                        <span class="input-group-text bg-light"><i class="fa-solid fa-lock text-muted"></i></span>
                        <input type="password" name="password" class="form-control" placeholder="أدخل كلمة المرور" required>
                    </div>
                </div>
                <button type="submit" class="btn btn-primary-custom w-100 py-2 shadow-sm"><i class="fa-solid fa-right-to-bracket ms-2"></i> تسجيل الدخول</button>
            </form>
            {% if error %}
            <div class="alert alert-danger mt-3 py-2 small fw-bold shadow-sm" role="alert">
                <i class="fa-solid fa-triangle-exclamation ms-1"></i> {{ error }}
            </div>
            {% endif %}
            <div class="mt-4 text-muted small border-top pt-3">تصميم وإشراف: مدير المعهد (محمد حسين شمص)</div>
        </div>
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
    save_all_data()
    session['msg'] = "تم تكليف جلسة التدريب الميداني بنجاح!"
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_reply/<int:reply_id>', methods=['POST'])
def delete_reply(reply_id):
    if session.get('role') == 'admin' and 0 <= reply_id < len(admin_replies):
        admin_replies.pop(reply_id)
        save_all_data()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    msg = session.pop('msg', '')
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'upload_directorate_file':
            file_key = request.form.get('file_key')
            file = request.files.get('excel_file')
            
            if file and allowed_file(file.filename) and file_key in directorate_excel_tables:
                try:
                    xls_file = pd.ExcelFile(file)
                    all_rows_data = []
                    all_clean_cols = []
                    
                    for sheet_name in xls_file.sheet_names:
                        df_sheet = pd.read_excel(xls_file, sheet_name=sheet_name)
                        for _, row in df_sheet.iterrows():
                            row_dict = {}
                            has_val = False
                            for col in df_sheet.columns:
                                val = row[col]
                                c_clean = clean_column_name(col)
                                if c_clean not in all_clean_cols and c_clean:
                                    all_clean_cols.append(c_clean)
                                s_val = "" if pd.isna(val) else str(val).strip()
                                if s_val and s_val != 'nan':
                                    has_val = True
                                row_dict[c_clean] = s_val
                            if has_val:
                                all_rows_data.append(row_dict)

                    title_map = {
                        "students_registered": "الطلاب المسجلون",
                        "teachers_cards": "بطاقات الاساتذة",
                        "personal_info": "المعلومات الشخصية",
                        "weekly_schedule": "برنامج اسبوعي مع الاساتذة والمواد",
                        "executed_hours": "الساعات المنفذة للاساتذة",
                        "fingerprint_ids": "أرقام بصمات الأساتذة والموظفين (البصمة ID)"
                    }
                    
                    table_title = title_map.get(file_key, "ملف المديرية")
                    
                    if file_key == 'executed_hours':
                        monthly_map = {}
                        contract_map = {}
                        for r in all_rows_data:
                            t_name = r.get('الاسم الثلاثي', r.get('اسم الاستاذ', '')).strip()
                            if t_name:
                                if t_name not in monthly_map:
                                    monthly_map[t_name] = {}
                                try:
                                    c_hrs = float(r.get('Maxhoures', 300) or 300)
                                    contract_map[t_name] = int(c_hrs)
                                except:
                                    contract_map[t_name] = 300
                                
                                for m_col in MONTH_COLUMNS:
                                    found_val = None
                                    for key, val in r.items():
                                        if clean_column_name(key) == m_col:
                                            found_val = val
                                            break
                                    if found_val is not None:
                                        try:
                                            monthly_map[t_name][m_col] = float(found_val or 0)
                                        except:
                                            monthly_map[t_name][m_col] = 0.0
                                    else:
                                        monthly_map[t_name][m_col] = 0.0
                        
                        directorate_excel_tables['executed_hours']['monthly_hours'] = monthly_map
                        for u, t_info in teachers_db.items():
                            t_real_name = t_info['name'].strip()
                            if t_real_name in monthly_map:
                                t_info['monthly_hours'] = monthly_map[t_real_name]
                            if t_real_name in contract_map:
                                t_info['contract_hours'] = contract_map[t_real_name]

                    directorate_excel_tables[file_key] = {
                        "title": table_title,
                        "columns": all_clean_cols if all_clean_cols else ["البيان"],
                        "data": all_rows_data,
                        "monthly_hours": directorate_excel_tables.get('executed_hours', {}).get('monthly_hours', {})
                    }
                    
                    if file_key == 'weekly_schedule':
                        df_first = pd.read_excel(file)
                        parsed = parse_weekly_schedule(df_first)
                        directorate_excel_tables['weekly_schedule']['parsed_schedule'] = parsed

                    if file_key == 'students_registered':
                        new_classes = {}
                        for r in all_rows_data:
                            c_name = r.get('الصف', r.get('Class', r.get('التخصص', 'غير مصنف')))
                            s_name = r.get('اسم الطالب الكامل', r.get('اسم الطالب', r.get('الاسم الثلاثي', r.get('الاسم', ''))))
                            if c_name and s_name and str(c_name) != 'nan' and str(s_name) != 'nan':
                                if c_name not in new_classes:
                                    new_classes[c_name] = []
                                if s_name not in new_classes[c_name]:
                                    new_classes[c_name].append(s_name)
                        if new_classes:
                            classes_students.update(new_classes)

                    save_all_data()
                    msg = f"تم رفع وتحديث ملف ({table_title}) بنجاح!"
                except Exception as e:
                    msg = f"خطأ في قراءة ملف الإكسل: {e}"
            else:
                msg = "الرجاء اختيار ملف صالح وتحديد نوع الجدول بدقة."

        elif action == 'create_auto_accounts':
            count = 0
            sources_to_scan = []
            sources_to_scan.extend(directorate_excel_tables.get('teachers_cards', {}).get('data', []))
            sources_to_scan.extend(directorate_excel_tables.get('fingerprint_ids', {}).get('data', []))
            
            for card in sources_to_scan:
                name = ""
                for k, v in card.items():
                    if any(w in str(k) for w in ['اسم', 'الاسم', 'ملاك', 'متعاقد', 'الأساتذة', 'الاستاذ']) and len(str(v).strip()) > 2:
                        if not str(v).isdigit() and 'ID' not in str(v) and 'بصمة' not in str(v):
                            name = str(v).strip()
                            break
                if not name:
                    vals = [str(v).strip() for v in card.values() if v and not str(v).isdigit() and len(str(v).strip()) > 2]
                    if vals:
                        name = vals[0]

                if name and name not in ['أساتذة الملاك', 'شراء الخدمات (خدمات اخرى)', 'شراءالخدمات (حراسة)', 'ID البصمة', 'بصمة ID']:
                    exists = any(t.get('name') == name for t in teachers_db.values())
                    if not exists:
                        user_id = f"teacher_{len(teachers_db) + 1}"
                        teachers_db[user_id] = {
                            "name": name,
                            "password": "123",
                            "subject": "عام",
                            "device_id": "",
                            "notifications": [],
                            "monthly_hours": {},
                            "contract_hours": 300
                        }
                        count += 1
            save_all_data()
            msg = f"تم توليد ({count}) حساب جديد للأساتذة بنجاح بكلمة سر افتراضية (123)!"

        elif action == 'reset_teacher_device':
            target_user = request.form.get('target_user')
            if target_user in teachers_db:
                teachers_db[target_user]['device_id'] = ''
                save_all_data()
                msg = f"تم مسح بصمة الجهاز وإعادة تعيين الهوية للأستاذ ({teachers_db[target_user].get('name')}) بنجاح!"

        elif action == 'send_notification':
            target_user = request.form.get('target_user')
            notif = request.form.get('notification_text')
            if target_user == 'all':
                for u, t in teachers_db.items():
                    t.setdefault('notifications', []).append(f"📢 تعميم: {notif}")
                msg = "تم إرسال التعميم لجميع الأساتذة!"
            elif target_user in teachers_db:
                teachers_db[target_user].setdefault('notifications', []).append(notif)
                msg = f"تم إرسال الإشعار للأستاذ بنجاح!"
            save_all_data()

        elif action == 'change_admin_password':
            new_pass = request.form.get('new_password', '').strip()
            if new_pass:
                admin_credentials['password'] = new_pass
                save_all_data()
                msg = "تم تغيير كلمة مرور الإدارة بنجاح!"

    attendance_rows = "".join([f"<tr><td><b>{k}</b></td><td class='text-danger fw-bold'>متغيبون: {v.get('absent', [])}</td></tr>" for k, v in attendance_db.items()])
    grades_rows = "".join([f"<tr><td><b>{k}</b></td><td><span class='badge bg-primary fs-6'>{v} / 20</span></td></tr>" for k, v in grades_db.items()]) if isinstance(grades_db, dict) and grades_db else ""
    
    executed_hours_table_html = ""
    monthly_data_map = directorate_excel_tables.get('executed_hours', {}).get('monthly_hours', {})
    
    if monthly_data_map:
        m_headers = "".join([f"<th>ش {m}</th>" for m in MONTH_COLUMNS])
        m_rows = ""
        for t_name, m_dict in monthly_data_map.items():
            m_tds = "".join([f"<td>{m_dict.get(m, 0):.0f}</td>" for m in MONTH_COLUMNS])
            total_exec = sum(m_dict.values())
            m_rows += f"<tr><td class='text-start fw-bold'>{t_name}</td>{m_tds}<td class='table-active'><span class='badge bg-primary'>{total_exec:.0f}</span></td></tr>"
        
        executed_hours_table_html = f"""
        <div class="table-responsive">
            <table class="table table-bordered table-hover table-custom">
                <thead><tr><th style="min-width:180px;">الاسم الثلاثي</th>{m_headers}<th>المجموع المنفذ</th></tr></thead>
                <tbody>{m_rows}</tbody>
            </table>
        </div>
        """
    else:
        executed_hours_table_html = "<div class='alert alert-light border text-muted text-center py-3'>لم يتم رفع ملف الساعات المنفذة بعد.</div>"

    teachers_rows = ""
    if teachers_db:
        for u, t in teachers_db.items():
            dev_stat = "<span class='badge bg-success'><i class='fa-solid fa-mobile-screen ms-1'></i> مرتبط</span>" if t.get('device_id') else "<span class='badge bg-warning text-dark'><i class='fa-solid fa-clock ms-1'></i> في انتظار التسجيل</span>"
            monthly_h = t.get('monthly_hours', {})
            executed_hrs = sum([float(v) for v in monthly_h.values()]) if monthly_h else 0
            contract_hrs = float(t.get('contract_hours', 300))
            remaining_hrs = contract_hrs - executed_hrs
            rem_badge = f"<span class='badge bg-success'>{remaining_hrs:.0f} ساعة</span>" if remaining_hrs >= 0 else f"<span class='badge bg-danger'>{remaining_hrs:.0f} ساعة</span>"
            
            teachers_rows += f"""
            <tr>
                <td class='fw-bold text-start'>{t.get('name')}</td>
                <td><code>{u}</code></td>
                <td><code>{t.get('password')}</code></td>
                <td>{dev_stat}</td>
                <td><b>{int(contract_hrs)} ساعة</b></td>
                <td><span class='text-primary fw-bold'>{executed_hrs:.0f} ساعة</span></td>
                <td>{rem_badge}</td>
            </tr>
            """
    else:
        teachers_rows = "<tr><td colspan='7' class='text-muted py-3'>لا توجد حسابات أساتذة مسجلة. ارفع ملفات الإكسل ثم اضغط على زر توليد الحسابات أعلاه.</td></tr>"
    
    field_rows = ""
    for fs in reversed(field_sessions):
        stat = "<span class='badge bg-success'><i class='fa-solid fa-check ms-1'></i> مكتملة بالـ GPS</span>" if fs.get('status')=='مكتملة' else "<span class='badge bg-warning text-dark'><i class='fa-solid fa-hourglass-half ms-1'></i> قيد الانتظار</span>"
        field_rows += f"<tr><td class='text-start'><b>{fs.get('location')}</b><br><small class='text-muted'>{fs.get('class_name')}</small></td><td class='fw-bold'>{fs.get('primary_teacher')}</td><td>{stat}</td></tr>"

    replies_html = ""
    for idx, r in enumerate(reversed(admin_replies)):
        real_idx = len(admin_replies) - 1 - idx
        replies_html += f"""
        <div class="alert alert-warning border-start border-warning border-4 shadow-sm d-flex justify-content-between align-items-center mb-3">
            <div>
                <h6 class="fw-bold mb-1 text-dark"><i class="fa-solid fa-user-pen ms-1"></i> من: {r.get('teacher_name')} <small class="text-muted fw-normal ms-2">({r.get('date')})</small></h6>
                <p class="mb-0 text-secondary">{r.get('message')}</p>
            </div>
            <form method="POST" action="/admin/delete_reply/{real_idx}" class="m-0"><button type="submit" class="btn btn-outline-danger btn-sm"><i class="fa-solid fa-trash"></i></button></form>
        </div>
        """

    directorate_htmls = {}
    for k, tinfo in directorate_excel_tables.items():
        cols = tinfo.get('columns', [])
        rows = tinfo.get('data', [])
        headers_th = "".join([f"<th>{c}</th>" for c in cols]) if cols else "<th>لا توجد أعمدة</th>"
        body_tr = ""
        if rows:
            for r in rows[:100]:
                tds = "".join([f"<td>{r.get(c, '')}</td>" for c in cols])
                body_tr += f"<tr>{tds}</tr>"
        else:
            body_tr = f"<tr><td colspan='{len(cols) or 1}' class='text-muted py-3'>لم يتم رفع بيانات لهذا الملف بعد</td></tr>"

        directorate_htmls[k] = f"""
        <div class="card card-custom p-4 active shadow-sm">
            <h4 class="text-primary mb-3 fw-bold border-bottom pb-2"><i class="fa-solid fa-folder-tree ms-2"></i> {tinfo.get('title')}</h4>
            <div class="table-responsive">
                <table class="table table-bordered table-striped table-hover table-custom">
                    <thead><tr>{headers_th}</tr></thead>
                    <tbody>{body_tr}</tbody>
                </table>
            </div>
            <div class="small text-muted mt-3">إجمالي السجلات: <b class="text-dark">{len(rows)}</b> سجل</div>
        </div>
        """

    teacher_opts = "".join([f"<option value='{u}'>{t.get('name')} ({u})</option>" for u, t in teachers_db.items()]) if teachers_db else "<option value=''>-- لا توجد حسابات أساتذة --</option>"
    locations_opts = "".join([f"<option value='{loc}'>{loc}</option>" for loc in TRAINING_LOCATIONS.keys()])

    admin_template = '''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        {{ shared_head | safe }}
        <title>لوحة الإدارة الذكية - معهد الهرمل الفني</title>
        <style>
            @media print { .no-print { display: none !important; } body { background: white !important; } .card-custom { box-shadow: none !important; border: none !important; display: block !important; } }
        </style>
    </head>
    <body>
        {{ header_html | safe }}

        <div class="container-fluid py-4 px-4">
            {% if msg %}
            <div class="alert alert-success alert-dismissible fade show shadow-sm fw-bold" role="alert">
                <i class="fa-solid fa-circle-check ms-2"></i> {{ msg }}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
            {% endif %}

            <div id="attendanceReportSec" class="card card-custom p-4 active">
                <div class="text-center border-bottom pb-3 mb-4">
                    <h4 class="fw-bold text-dark mb-1">الجمهورية اللبنانية 🌲</h4>
                    <h5 class="text-secondary mb-1">وزارة التربية والتعليم العالي - المديرية العامة للتعليم المهني والتقني</h5>
                    <h5 class="text-primary fw-bold mb-2">معهد الهرمل الفني</h5>
                    <p class="badge bg-primary bg-opacity-10 text-primary px-3 py-2 rounded-pill fw-bold">كشف الدوام والتغيب التفصيلي للأساتذة (النصاب الأسبوعي: 20 حصة)</p>
                </div>
                <div class="text-end mb-3 no-print">
                    <button class="btn btn-success btn-sm fw-bold shadow-sm" onclick="window.print()"><i class="fa-solid fa-print ms-1"></i> طباعة التقرير الرسمي</button>
                </div>
                <div class="table-responsive">
                    <table class="table table-bordered table-hover table-custom">
                        <thead>
                            <tr>
                                <th>اسم الأستاذ</th>
                                <th>رقم البصمة (ID)</th>
                                <th>النصاب الأسبوعي</th>
                                <th>تاريخ التغيب المسجل</th>
                                <th>الحالة</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td class="fw-bold text-start">إيمان جانبيه</td>
                                <td><code>32</code></td>
                                <td><b>20 حصة</b></td>
                                <td class="text-danger fw-bold">2026/10/26 (الحصة 3)</td>
                                <td><span class="badge bg-danger">غائب</span></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div id="studentAttendanceSec" class="card card-custom p-4">
                <h4 class="text-primary fw-bold mb-3"><i class="fa-solid fa-clipboard-user ms-2"></i> سجل حضور وغياب الطلاب</h4>
                <div class="table-responsive">
                    <table class="table table-bordered table-hover table-custom">
                        <thead><tr><th>الصف والتاريخ</th><th>الطلاب المتغيبون</th></tr></thead>
                        <tbody>{{ attendance_rows | safe if attendance_rows else '<tr><td colspan="2" class="text-muted py-3">لا توجد بيانات غياب مسجلة</td></tr>' }}</tbody>
                    </table>
                </div>
            </div>

            <div id="studentGradesSec" class="card card-custom p-4">
                <h4 class="text-primary fw-bold mb-3"><i class="fa-solid fa-star ms-2"></i> علامات ونتائج الطلاب (من 20)</h4>
                <div class="table-responsive">
                    <table class="table table-bordered table-hover table-custom">
                        <thead><tr><th>اسم الطالب والمادة</th><th>العلامة</th></tr></thead>
                        <tbody>{{ grades_rows | safe if grades_rows else '<tr><td colspan="2" class="text-muted py-3">لم تُدخل علامات بعد</td></tr>' }}</tbody>
                    </table>
                </div>
            </div>

            <div id="viewRegisteredStudents" class="card card-custom p-4">
                {{ directorate_htmls.get('students_registered', '') | safe }}
            </div>

            <div id="viewTeachersCards" class="card card-custom p-4">
                {{ directorate_htmls.get('teachers_cards', '') | safe }}
                <div class="my-4"></div>
                {{ directorate_htmls.get('personal_info', '') | safe }}
            </div>

            <div id="viewFingerprintIds" class="card card-custom p-4">
                <h4 class="text-primary fw-bold mb-3"><i class="fa-solid fa-fingerprint ms-2"></i> أرقام بصمات الأساتذة والموظفين</h4>
                {{ directorate_htmls.get('fingerprint_ids', '') | safe }}
            </div>

            <div id="viewWeeklySchedule" class="card card-custom p-4">
                {{ directorate_htmls.get('weekly_schedule', '') | safe }}
            </div>

            <div id="viewExecutedHours" class="card card-custom p-4">
                <h4 class="text-primary fw-bold mb-3"><i class="fa-solid fa-chart-line ms-2"></i> الساعات المنفذة شهرياً</h4>
                {{ executed_hours_table_html | safe }}
            </div>

            <div id="teachersListSec" class="card card-custom p-4">
                <div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
                    <h4 class="text-primary fw-bold m-0"><i class="fa-solid fa-chalkboard-user ms-2"></i> سجل الأساتذة وحسابات الدخول وساعات العقود</h4>
                    <form method="POST" class="m-0">
                        <input type="hidden" name="action" value="create_auto_accounts">
                        <button type="submit" class="btn btn-success btn-sm fw-bold shadow-sm"><i class="fa-solid fa-wand-magic-sparkles ms-1"></i> توليد حسابات الأساتذة تلقائياً</button>
                    </form>
                </div>
                <div class="table-responsive">
                    <table class="table table-bordered table-hover table-custom">
                        <thead>
                            <tr>
                                <th>اسم الأستاذ</th>
                                <th>اسم المستخدم</th>
                                <th>كلمة المرور</th>
                                <th>حالة الهاتف</th>
                                <th>العقد الإجمالي</th>
                                <th>المنفذ حتى الآن</th>
                                <th>المتبقي من العقد</th>
                            </tr>
                        </thead>
                        <tbody>{{ teachers_rows | safe }}</tbody>
                    </table>
                </div>
            </div>

            <div id="fieldSessionSec" class="card card-custom p-4">
                <h4 class="text-primary fw-bold mb-3"><i class="fa-solid fa-hospital ms-2"></i> تكليف وإدارة التدريب الميداني (GPS)</h4>
                <form action="/admin/create_field_session" method="POST" class="bg-light p-4 rounded-3 border mb-4">
                    <div class="row g-3">
                        <div class="col-md-3">
                            <label class="form-label small fw-bold">المكان التدريبي:</label>
                            <select name="location" class="form-select" required>{{ locations_opts | safe }}</select>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small fw-bold">الصف:</label>
                            <input type="text" name="class_name" class="form-control" placeholder="مثال: سنة ثالثة عناية" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small fw-bold">الاختصاص:</label>
                            <input type="text" name="major" class="form-control" placeholder="مثال: تمريض" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small fw-bold">الأستاذ المشرف:</label>
                            <select name="primary_teacher" class="form-select" required>{{ teacher_opts | safe }}</select>
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary-custom mt-3 px-4 shadow-sm"><i class="fa-solid fa-circle-plus ms-1"></i> حفظ وتكليف الجلسة</button>
                </form>
                <h5 class="text-dark fw-bold mb-3">سجل الجلسات الميدانية النشطة:</h5>
                <div class="table-responsive">
                    <table class="table table-bordered table-hover table-custom">
                        <thead><tr><th>المكان والصف</th><th>المشرف</th><th>الحالة</th></tr></thead>
                        <tbody>{{ field_rows | safe if field_rows else '<tr><td colspan="3" class="text-muted py-3">لا توجد جلسات ميدانية</td></tr>' }}</tbody>
                    </table>
                </div>
            </div>

            <div id="uploadDirectorateFilesSec" class="card card-custom p-4">
                <h4 class="text-primary fw-bold mb-3"><i class="fa-solid fa-file-excel ms-2"></i> رفع ملفات المديرية والبصمة والساعات (Excel)</h4>
                <form method="POST" enctype="multipart/form-data" class="bg-light p-4 rounded-3 border">
                    <input type="hidden" name="action" value="upload_directorate_file">
                    <div class="mb-3 text-start">
                        <label class="form-label fw-bold small text-secondary">حدد نوع الملف المراد رفعه:</label>
                        <select name="file_key" class="form-select fw-bold" required>
                            <option value="fingerprint_ids">🆔 ملف البصمة ID (الملاك، المتعاقدين، شراء الخدمات)</option>
                            <option value="students_registered">📂 الطلاب المسجلون</option>
                            <option value="teachers_cards">📇 بطاقات الاساتذة</option>
                            <option value="personal_info">👤 المعلومات الشخصية</option>
                            <option value="weekly_schedule">📅 البرنامج الأسبوعي مع الاساتذة والمواد</option>
                            <option value="executed_hours">⏱️ الساعات المنفذة للاساتذة</option>
                        </select>
                    </div>
                    <div class="mb-3 text-start">
                        <label class="form-label fw-bold small text-secondary">اختر ملف الإكسل (.xlsx أو .xls):</label>
                        <input type="file" name="excel_file" class="form-control" accept=".xlsx, .xls" required>
                    </div>
                    <button type="submit" class="btn btn-success px-4 fw-bold shadow-sm"><i class="fa-solid fa-cloud-arrow-up ms-1"></i> رفع وتحديث الملف فوراً</button>
                </form>
            </div>

            <div id="deviceBindingSec" class="card card-custom p-4">
                <h4 class="text-danger fw-bold mb-3"><i class="fa-solid fa-mobile-screen-button ms-2"></i> إدارة أجهزة الأساتذة (فك ربط الجهاز)</h4>
                <form method="POST" class="bg-light p-4 rounded-3 border" style="max-width: 600px;">
                    <input type="hidden" name="action" value="reset_teacher_device">
                    <div class="mb-3 text-start">
                        <label class="form-label fw-bold small text-secondary">اختر الأستاذ:</label>
                        <select name="target_user" class="form-select" required><option value="">-- اختر الأستاذ --</option>{{ teacher_opts | safe }}</select>
                    </div>
                    <button type="submit" class="btn btn-danger px-4 fw-bold shadow-sm"><i class="fa-solid fa-unlock ms-1"></i> مسح بصمة الجهاز والسماح بتسجيل هاتف جديد</button>
                </form>
            </div>

            <div id="sendNotifSec" class="card card-custom p-4">
                <h4 class="text-primary fw-bold mb-3"><i class="fa-solid fa-bullhorn ms-2"></i> إرسال تعميم إداري للأساتذة</h4>
                <form method="POST" class="bg-light p-4 rounded-3 border" style="max-width: 700px;">
                    <input type="hidden" name="action" value="send_notification">
                    <div class="mb-3 text-start">
                        <label class="form-label fw-bold small text-secondary">المستهدف:</label>
                        <select name="target_user" class="form-select" required><option value="all">📢 إرسال لجميع الأساتذة</option>{{ teacher_opts | safe }}</select>
                    </div>
                    <div class="mb-3 text-start">
                        <label class="form-label fw-bold small text-secondary">نص التعميم:</label>
                        <textarea name="notification_text" class="form-control" rows="3" placeholder="اكتب نص التعميم هنا..." required></textarea>
                    </div>
                    <button type="submit" class="btn btn-primary-custom px-4 shadow-sm"><i class="fa-solid fa-paper-plane ms-1"></i> إرسال التعميم</button>
                </form>
            </div>

            <div id="teacherRepliesSec" class="card card-custom p-4">
                <h4 class="text-primary fw-bold mb-3"><i class="fa-solid fa-envelope-open-text ms-2"></i> الأعذار والرسائل الواردة من الأساتذة</h4>
                {{ replies_html | safe if replies_html else '<div class="alert alert-light border text-muted py-3 text-center">لا توجد رسائل أو أعذار واردة حالياً.</div>' }}
            </div>

            <div id="changePassSec" class="card card-custom p-4">
                <h4 class="text-danger fw-bold mb-3"><i class="fa-solid fa-key ms-2"></i> تغيير كلمة السر الإدارية</h4>
                <form method="POST" class="bg-light p-4 rounded-3 border" style="max-width: 450px;">
                    <input type="hidden" name="action" value="change_admin_password">
                    <div class="mb-3 text-start">
                        <label class="form-label fw-bold small text-secondary">كلمة المرور الجديدة:</label>
                        <input type="password" name="new_password" class="form-control" placeholder="أدخل كلمة المرور الجديدة" required>
                    </div>
                    <button type="submit" class="btn btn-danger px-4 fw-bold shadow-sm"><i class="fa-solid fa-floppy-disk ms-1"></i> تحديث كلمة المرور</button>
                </form>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            function showSection(secId) {
                document.querySelectorAll('.card-custom').forEach(el => el.classList.remove('active'));
                let target = document.getElementById(secId);
                if(target) target.classList.add('active');
            }
        </script>
    </body>
    </html>
    '''
    return render_template_string(admin_template, header_html=HEADER_VTE_HTML, shared_head=SHARED_HEAD, attendance_rows=attendance_rows, grades_rows=grades_rows, teachers_rows=teachers_rows, field_rows=field_rows, replies_html=replies_html, teacher_opts=teacher_opts, locations_opts=locations_opts, directorate_htmls=directorate_htmls, executed_hours_table_html=executed_hours_table_html, msg=msg)

@app.route('/teacher', methods=['GET', 'POST'])
def teacher_dashboard():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    
    username = session.get('username')
    user_data = teachers_db.get(username, {})
    t_name = user_data.get('name', '').strip()
    msg = ''

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'change_my_password':
            new_p = request.form.get('new_password', '').strip()
            if new_p:
                user_data['password'] = new_p
                save_all_data()
                msg = "تم تغيير كلمة المرور الخاصة بك بنجاح!"

        elif action == 'submit_class_grades':
            class_name = request.form.get('class_name')
            subject = user_data.get('subject', 'عام')
            students = classes_students.get(class_name, [])
            for st in students:
                val = request.form.get(f"grade_{st}")
                if val:
                    grades_db[f"{st} - {class_name} ({subject})"] = val
            save_all_data()
            msg = "تم حفظ ورصد علامات الطلاب بنجاح!"

        elif action == 'submit_class_attendance':
            class_name = request.form.get('class_name')
            students = classes_students.get(class_name, [])
            present_sts = request.form.getlist('attendance_check')
            absent_sts = [s for s in students if s not in present_sts]
            date_key = datetime.now().strftime('%Y-%m-%d')
            attendance_db[f"{class_name} ({date_key})"] = {'present': present_sts, 'absent': absent_sts}
            save_all_data()
            msg = "تم تسجيل حضور وغياب الطلاب بنجاح!"

        elif action == 'send_reply':
            reply_msg = request.form.get('reply_message')
            admin_replies.append({'teacher_name': t_name, 'message': reply_msg, 'report': None, 'date': datetime.now().strftime('%Y-%m-%d %H:%M')})
            save_all_data()
            msg = "تم إرسال رسالتك للإدارة بنجاح!"

    my_classes = list(classes_students.keys())
    class_opts = "".join([f'<option value="{c}">{c}</option>' for c in my_classes])
    
    raw_notifs = user_data.get('notifications', [])
    notifs = "".join([f"<div class='alert alert-info py-2 mb-2 small fw-bold shadow-sm'><i class='fa-solid fa-bell ms-1'></i> {n}</div>" for n in raw_notifs])

    monthly_hrs = user_data.get('monthly_hours', {})
    contract_hrs = float(user_data.get('contract_hours', 300))
    executed_hrs = sum([float(v) for v in monthly_hrs.values()]) if monthly_hrs else 0
    remaining_hrs = contract_hrs - executed_hrs
    
    hrs_html = ""
    if monthly_hrs:
        m_headers = "".join([f"<th>ش {m}</th>" for m in MONTH_COLUMNS])
        m_tds = "".join([f"<td>{monthly_hrs.get(m, 0):.0f}</td>" for m in MONTH_COLUMNS])
        hrs_html = f"""
        <div class="card card-custom p-4 active shadow-sm mb-4 border-top border-primary border-4">
            <h5 class="text-primary fw-bold mb-3"><i class="fa-solid fa-chart-pie ms-2"></i> ملخص عقد الساعات والمنفذ شهرياً:</h5>
            <div class="row g-3 mb-4">
                <div class="col-md-4">
                    <div class="p-3 bg-light rounded-3 text-center border">
                        <small class="text-muted fw-bold">ساعات العقد الإجمالية</small>
                        <div class="fs-4 fw-bold text-primary mt-1">{int(contract_hrs)} ساعة</div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="p-3 bg-success bg-opacity-10 rounded-3 text-center border border-success">
                        <small class="text-success fw-bold">المنفذ حتى الآن</small>
                        <div class="fs-4 fw-bold text-success mt-1">{executed_hrs:.0f} ساعة</div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="p-3 bg-warning bg-opacity-10 rounded-3 text-center border border-warning">
                        <small class="text-warning-emphasis fw-bold">المتبقي من العقد</small>
                        <div class="fs-4 fw-bold text-warning-emphasis mt-1">{remaining_hrs:.0f} ساعة</div>
                    </div>
                </div>
            </div>
            <div class="table-responsive"><table class="table table-bordered table-custom"><thead><tr>{m_headers}</tr></thead><tbody><tr>{m_tds}</tr></tbody></table></div>
        </div>
        """
    else:
        hrs_html = f"""
        <div class="card card-custom p-4 active shadow-sm mb-4 border-top border-primary border-4">
            <h5 class="text-primary fw-bold mb-2"><i class="fa-solid fa-file-contract ms-2"></i> ملخص العقد والساعات:</h5>
            <p class="text-muted mb-0">ساعات العقد الإجمالية: <b class="text-dark">{int(contract_hrs)} ساعة</b>.</p>
        </div>
        """

    parsed_schedule = directorate_excel_tables.get('weekly_schedule', {}).get('parsed_schedule', {})
    teacher_schedule_items = parsed_schedule.get(t_name, [])
    schedule_html = ""
    if teacher_schedule_items:
        schedule_rows = "".join([f"<tr><td><b>{item.get('day')}</b></td><td>{item.get('period')}</td><td>{item.get('class')}</td><td><b class='text-primary'>{item.get('subject')}</b></td></tr>" for item in teacher_schedule_items])
        schedule_html = f"""
        <div class="card card-custom p-4 active shadow-sm mb-4 border-top border-success border-4">
            <h5 class="text-success fw-bold mb-3"><i class="fa-solid fa-calendar-days ms-2"></i> برنامجي الأسبوعي:</h5>
            <div class="table-responsive">
                <table class="table table-bordered table-hover table-custom">
                    <thead><tr><th>اليوم</th><th>الحصة</th><th>الصف والمستوى</th><th>المادة</th></tr></thead>
                    <tbody>{schedule_rows}</tbody>
                </table>
            </div>
        </div>
        """

    my_sessions = [s for s in field_sessions if s.get('primary_teacher') == t_name or s.get('secondary_teacher') == t_name]
    field_html = ""
    for s in my_sessions:
        if s.get('status') == 'قيد التدريب':
            field_html += f'''
            <div class="alert alert-warning border-warning border-4 shadow-sm mb-4 d-flex justify-content-between align-items-center flex-wrap gap-3">
                <div>
                    <h6 class="fw-bold text-dark mb-1"><i class="fa-solid fa-location-dot text-danger ms-1"></i> مكان التدريب الميداني: {s.get('location')}</h6>
                    <p class="mb-0 small text-muted">الصف: {s.get('class_name')}</p>
                </div>
                <button type="button" onclick="submitGps({s.get('id')}, '{t_name}', '{s.get('location')}')" class="btn btn-success btn-sm fw-bold shadow-sm"><i class="fa-solid fa-location-crosshairs ms-1"></i> توثيق الحضور الجغرافي (GPS)</button>
            </div>
            '''
        else:
            field_html += f'''<div class="alert alert-success shadow-sm mb-4 fw-bold"><i class="fa-solid fa-circle-check ms-2"></i> تم توثيق الحضور الجغرافي لـ ({s.get('location')}) بنجاح!</div>'''

    teacher_template = """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        {{ shared_head | safe }}
        <title>واجهة الأستاذ - معهد الهرمل الفني</title>
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-dark navbar-custom px-4 py-3">
            <div class="container-fluid">
                <div class="d-flex align-items-center gap-3">
                    <div class="bg-white p-2 rounded-circle text-primary shadow-sm">
                        <i class="fa-solid fa-user-chalkboard fa-lg"></i>
                    </div>
                    <div>
                        <div class="fw-bold fs-5 text-white">الجمهورية اللبنانية 🌲 - معهد الهرمل الفني</div>
                        <div class="small text-info">الأستاذ: {{ t_name }}</div>
                    </div>
                </div>
                <a href="/logout" class="btn btn-danger btn-sm px-3 fw-bold shadow-sm"><i class="fa-solid fa-right-from-bracket ms-1"></i> خروج</a>
            </div>
        </nav>

        <div class="container py-4" style="max-width: 900px;">
            {% if msg %}
            <div class="alert alert-success alert-dismissible fade show shadow-sm fw-bold" role="alert">
                <i class="fa-solid fa-circle-check ms-2"></i> {{ msg }}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
            {% endif %}

            {{ hrs_html | safe }}
            {{ schedule_html | safe }}
            {{ field_html | safe }}

            <div class="card card-custom p-4 active shadow-sm mb-4">
                <h5 class="text-primary fw-bold mb-3"><i class="fa-solid fa-bullhorn ms-2"></i> التعاميم والتنبيهات الواردة:</h5>
                {{ notifs | safe if notifs else '<div class="text-muted small">لا توجد تعاميم جديدة.</div>' }}
            </div>

            <div class="card card-custom p-4 active shadow-sm mb-4">
                <h5 class="text-primary fw-bold mb-3"><i class="fa-solid fa-clipboard-user ms-2"></i> توثيق حضور وغياب الطلاب اليومي:</h5>
                <form method="POST">
                    <input type="hidden" name="action" value="submit_class_attendance">
                    <div class="mb-3 text-start">
                        <label class="form-label small fw-bold">اختر الصف:</label>
                        <select name="class_name" id="attClass" class="form-select" onchange="loadStudentsForAtt()" required>
                            <option value="">-- اختر الصف --</option>
                            {{ class_opts | safe }}
                        </select>
                    </div>
                    <div id="attContainer" class="mb-3"></div>
                    <button type="submit" id="attBtn" class="btn btn-success px-4 fw-bold shadow-sm" style="display:none;"><i class="fa-solid fa-floppy-disk ms-1"></i> حفظ الحضور والغياب</button>
                </form>
            </div>

            <div class="card card-custom p-4 active shadow-sm mb-4">
                <h5 class="text-primary fw-bold mb-3"><i class="fa-solid fa-star ms-2"></i> إدخال ورصد علامات الطلاب (من 20):</h5>
                <form method="POST">
                    <input type="hidden" name="action" value="submit_class_grades">
                    <div class="mb-3 text-start">
                        <label class="form-label small fw-bold">اختر الصف:</label>
                        <select name="class_name" id="gradeClass" class="form-select" onchange="loadStudentsForGrades()" required>
                            <option value="">-- اختر الصف --</option>
                            {{ class_opts | safe }}
                        </select>
                    </div>
                    <div id="gradeContainer" class="mb-3"></div>
                    <button type="submit" id="gradeBtn" class="btn btn-primary-custom px-4 fw-bold shadow-sm" style="display:none;"><i class="fa-solid fa-floppy-disk ms-1"></i> حفظ ورصد العلامات</button>
                </form>
            </div>

            <div class="card card-custom p-4 active shadow-sm">
                <h5 class="text-primary fw-bold mb-3"><i class="fa-solid fa-paper-plane ms-2"></i> إرسال رسالة أو عذر للإدارة:</h5>
                <form method="POST">
                    <input type="hidden" name="action" value="send_reply">
                    <div class="mb-3 text-start">
                        <textarea name="reply_message" class="form-control" rows="3" placeholder="اكتب رسالتك أو عذرك للإدارة هنا..." required></textarea>
                    </div>
                    <button type="submit" class="btn btn-primary-custom px-4 shadow-sm"><i class="fa-solid fa-envelope ms-1"></i> إرسال للإدارة</button>
                </form>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            function loadStudentsForAtt() {
                let cls = document.getElementById('attClass').value;
                let cont = document.getElementById('attContainer');
                let btn = document.getElementById('attBtn');
                cont.innerHTML = '';
                if(!cls) { btn.style.display='none'; return; }
                fetch('/api/get_students/' + encodeURIComponent(cls)).then(res => res.json()).then(data => {
                    let html = '<div class="alert alert-light border small fw-bold text-primary mb-3">الكل حاضر افتراضياً ✅ (أزل علامة الصح عن الطالب المتغيب):</div>';
                    data.students.forEach(st => {
                        html += `<div class="d-flex justify-content-between align-items-center p-2 mb-2 bg-light rounded border">
                            <span class="fw-bold">${st}</span>
                            <div class="form-check form-switch">
                                <input class="form-check-input" type="checkbox" name="attendance_check" value="${st}" checked style="transform: scale(1.3);">
                                <label class="form-check-label fw-bold text-success me-2">حاضر</label>
                            </div>
                        </div>`;
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
                        html += `<div class="d-flex justify-content-between align-items-center p-2 mb-2 bg-light rounded border">
                            <span class="fw-bold" style="flex:1;">${st}</span>
                            <input type="number" step="0.5" min="0" max="20" name="grade_${st}" class="form-control text-center fw-bold" placeholder="/20" style="width: 120px;" required>
                        </div>`;
                    });
                    cont.innerHTML = html;
                    btn.style.display = 'block';
                });
            }

            function submitGps(sessionId, teacherName, locationName) {
                if(!navigator.geolocation) { alert("خدمة تحديد الموقع (GPS) غير مدعومة في متصفحك"); return; }
                navigator.geolocation.getCurrentPosition(function(pos) {
                    fetch('/teacher/submit_field_attendance', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({session_id: sessionId, sender_name: teacherName, location: locationName, lat: pos.coords.latitude, lng: pos.coords.longitude})
                    }).then(res => res.json()).then(data => {
                        alert(data.message);
                        if(data.success) location.reload();
                    });
                }, function(err) { alert("يرجى تفعيل الـ GPS في هاتفك لتأكيد الحضور الجغرافي."); }, {enableHighAccuracy: true});
            }
        </script>
    </body>
    </html>
    """
    return render_template_string(teacher_template, shared_head=SHARED_HEAD, t_name=t_name, msg=msg, class_opts=class_opts, notifs=notifs, hrs_html=hrs_html, schedule_html=schedule_html, field_html=field_html)

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
            return jsonify({"success": False, "message": f"عذراً! أنت خارج نطاق موقع ({loc_name}). المسافة الحالية هي {int(dist)} متر."}), 400

    s_item = next((s for s in field_sessions if s.get('id') == s_id), None)
    if s_item:
        s_item['status'] = "مكتملة"
        save_all_data()
        return jsonify({"success": True, "message": "تم التحقق الجغرافي بالـ GPS بنجاح!"})
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