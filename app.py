import os
import json
import io
import math
import shutil
import re
import pandas as pd
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, session, send_from_directory, jsonify, send_file

app = Flask(__name__)
app.secret_key = 'hermel_tech_school_shams_secret_key_2026'

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'xlsx', 'xls', 'json'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_FILE = os.path.join(os.getcwd(), 'database.json')
BACKUP_FILE = os.path.join(os.getcwd(), 'database_backup.json')

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
grade_edit_permissions = {} 
attendance_db = {}        
classes_students = {}
admin_replies = []
admin_credentials = {'username': 'admin', 'password': '123456'}

academic_years_db = ["2025-2026", "2026-2027", "2027-2028", "2028-2029"]
current_academic_year = "2026-2027"

students_db = []
field_sessions = []
MONTH_COLUMNS = ["10", "11", "12", "01", "02", "03", "04", "05", "06", "07", "08"]

directorate_excel_tables = {
    "executed_hours": {"title": "الساعات المنفذة للأساتذة", "columns": [], "data": [], "monthly_hours": {}},
    "students_registered": {"title": "الطلاب المسجلون", "columns": [], "data": []},
    "personal_info": {"title": "المعلومات الشخصية", "columns": [], "data": []},
    "transport_days": {"title": "أيام الحضور وبدل النقل للأساتذة", "columns": [], "data": [], "monthly_transport": {}},
    "teachers_and_subjects": {"title": "الاستاذ والمواد (التوزيع الرسمي)", "columns": [], "data": [], "parsed_schedule": {}},
    "teachers_cards": {"title": "بطاقات الأساتذة", "columns": [], "data": []}
}

def clean_column_name(col):
    col_str = str(col).strip()
    col_str = col_str.replace("&#x27;", "").replace("'", "").replace('"', '')
    col_str = re.sub(r'^ش\s*', '', col_str)
    if len(col_str) == 1 and col_str.isdigit():
        col_str = '0' + col_str
    return col_str

def normalize_name(name):
    if not name: return ""
    n = str(name).strip()
    n = re.sub(r'[أإآ]', 'ا', n)
    n = re.sub(r'ى', 'ي', n)
    n = re.sub(r'ة', 'ه', n)
    n = re.sub(r'\s+', ' ', n)
    return n.lower()

def save_to_disk():
    try:
        data = {
            'teachers_db': teachers_db,
            'grades_db': grades_db,
            'grade_edit_permissions': grade_edit_permissions,
            'attendance_db': attendance_db,
            'admin_replies': admin_replies,
            'admin_credentials': admin_credentials,
            'classes_students': classes_students,
            'academic_years_db': academic_years_db,
            'current_academic_year': current_academic_year,
            'students_db': students_db,
            'field_sessions': field_sessions,
            'directorate_excel_tables': directorate_excel_tables
        }
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        shutil.copyfile(DB_FILE, BACKUP_FILE)
    except Exception as e:
        print(f"Error saving database: {e}")

def load_from_disk():
    global teachers_db, grades_db, grade_edit_permissions, attendance_db, admin_replies, admin_credentials, classes_students
    global academic_years_db, current_academic_year, students_db, field_sessions, directorate_excel_tables
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                teachers_db = data.get('teachers_db', {})
                grades_db = data.get('grades_db', {})
                grade_edit_permissions = data.get('grade_edit_permissions', {})
                attendance_db = data.get('attendance_db', {})
                admin_replies = data.get('admin_replies', [])
                admin_credentials = data.get('admin_credentials', {'username': 'admin', 'password': '123456'})
                classes_students = data.get('classes_students', {})
                academic_years_db = data.get('academic_years_db', academic_years_db)
                current_academic_year = data.get('current_academic_year', current_academic_year)
                students_db = data.get('students_db', [])
                field_sessions = data.get('field_sessions', [])
                directorate_excel_tables = data.get('directorate_excel_tables', directorate_excel_tables)
                return True
        except Exception as e:
            print(f"Error loading database file: {e}")
    return False

load_from_disk()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_teachers_and_subjects(df):
    parsed_teachers = {}
    for _, row in df.iterrows():
        teacher_name = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
        class_name = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
        subject_name = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
        sub_type = str(row.iloc[3]).strip() if len(row) > 3 and pd.notna(row.iloc[3]) else "نظري"

        if teacher_name and teacher_name != "nan" and subject_name and subject_name != "nan" and class_name and class_name != "nan":
            norm_t = normalize_name(teacher_name)
            if norm_t:
                if norm_t not in parsed_teachers:
                    parsed_teachers[norm_t] = []
                
                item = {"day": "حسب التوزيع", "period": "دوام رسمي", "class": class_name, "subject": subject_name, "type": sub_type}
                if item not in parsed_teachers[norm_t]:
                    parsed_teachers[norm_t].append(item)

    return parsed_teachers

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
        <button class="dropbtn">الطلاب والتقارير ▾</button>
        <div class="dropdown-content">
            <a href="javascript:void(0)" onclick="showSection('studentAttendanceSec')">📋 حضور وغياب الطلاب (حسب اليوم والشهر والصف)</a>
            <a href="javascript:void(0)" onclick="showSection('studentGradesSec')">📝 علامات ونتائج الطلاب الرسمية</a>
            <a href="javascript:void(0)" onclick="showSection('lateTeachersSec')">⚠️ الأساتذة المتأخرون عن رصد العلامات</a>
            <a href="javascript:void(0)" onclick="showSection('viewRegisteredStudents')">📂 جدول الطلاب المسجلون</a>
        </div>
    </div>

    <div class="dropdown">
        <button class="dropbtn">الأساتذة والدوام ▾</button>
        <div class="dropdown-content">
            <a href="javascript:void(0)" onclick="showSection('teachersListSec')">👨‍🏫 سجل الأساتذة وعقود الساعات</a>
            <a href="javascript:void(0)" onclick="showSection('viewTeachersCards')">📇 بطاقات الاساتذة والمعلومات الشخصية</a>
            <a href="javascript:void(0)" onclick="showSection('viewTeachersAndSubjects')">📋 جدول الاستاذ والمواد وتوزيع الحصص</a>
            <a href="javascript:void(0)" onclick="showSection('viewExecutedHours')">⏱️ الساعات المنفذة شهرياً</a>
            <a href="javascript:void(0)" onclick="showSection('viewTransportDays')">🚗 بدل وأيام النقل شهرياً</a>
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
            <a href="javascript:void(0)" onclick="showSection('grantEditPermissionSec')">💡 تحكم بفتح/إغلاق إدخال العلامات (On/Off)</a>
            <a href="javascript:void(0)" onclick="showSection('uploadDirectorateFilesSec')">⚙️ رفع ملفات المديرية والبرنامج (Excel)</a>
            <a href="javascript:void(0)" onclick="showSection('deviceBindingSec')">📱 إدارة أجهزة الأساتذة (فك الربط)</a>
            <a href="javascript:void(0)" onclick="showSection('sendNotifSec')">📢 إرسال تعميم / تنبيه</a>
            <a href="javascript:void(0)" onclick="showSection('teacherRepliesSec')">📩 الرسائل والأعذار الواردة</a>
            <a href="javascript:void(0)" onclick="showSection('backupSec')">💾 النسخ الاحتياطي والاسترداد</a>
            <a href="javascript:void(0)" onclick="showSection('changePassSec')">🔑 تغيير كلمة السر الإدارية</a>
        </div>
    </div>
</div>

<style>
    .dropdown { position: relative; display: inline-block; }
    .dropbtn { background-color: #1565c0; color: white; padding: 12px 16px; font-size: 14px; border: none; cursor: pointer; font-weight: bold; font-family: inherit; }
    .dropdown:hover .dropbtn { background-color: #0d47a1; }
    .dropdown-content { display: none; position: absolute; background-color: #ffffff; min-width: 280px; box-shadow: 0px 8px 16px rgba(0,0,0,0.2); z-index: 100; border-radius: 0 0 6px 6px; }
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
        user_agent = request.headers.get('User-Agent', '')
        
        is_pc = ("Windows" in user_agent or "Macintosh" in user_agent or "Linux" in user_agent) and not "Android" in user_agent
        device_category = "pc" if is_pc else "mobile"
        device_fingerprint = f"{'💻 لابتوب' if is_pc else '📱 هاتف'} ({user_agent[:40]})"
        
        if username == admin_credentials['username'] and password == admin_credentials['password']:
            session['username'] = 'admin'
            session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))
        elif username in teachers_db and teachers_db[username]['password'] == password:
            t_data = teachers_db[username]
            
            if device_category == "mobile":
                registered_dev = t_data.get('mobile_device', '')
                if not registered_dev:
                    t_data['mobile_device'] = device_fingerprint
                    save_to_disk()
                elif registered_dev != device_fingerprint:
                    error = 'عذراً! حسابك مرتبط بهاتف آخر. التواصل مع الإدارة لفك الربط لتغيير الهاتف.'
                    return render_template_string(login_template, error=error)
            else:
                registered_dev = t_data.get('pc_device', '')
                if not registered_dev:
                    t_data['pc_device'] = device_fingerprint
                    save_to_disk()
                elif registered_dev != device_fingerprint:
                    error = 'عذراً! حسابك مرتبط بلابتوب آخر. التواصل مع الإدارة لفك الربط لتغيير اللابتوب.'
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
        <div style="margin-top: 25px; color: #5c6bc0; font-size: 12px;">🛠️ تم تصميم وتطوير البرنامج من قبل الأستاذ محمد حسين شمص</div>
    </body>
    </html>
'''

@app.route('/api/get_students/<path:class_name>')
def get_students(class_name):
    students = classes_students.get(class_name, [])
    return jsonify({'students': students})

@app.route('/api/check_notifications')
def check_notifications():
    if session.get('role') != 'teacher':
        return jsonify({'notifications': []})
    username = session.get('username')
    user_data = teachers_db.get(username, {})
    return jsonify({'notifications': user_data.get('notifications', [])})

@app.route('/report/official_sheet')
def official_report_sheet():
    class_name = request.args.get('class_name', '')
    subject_name = request.args.get('subject_name', '')
    teacher_username = request.args.get('teacher_username', session.get('username', ''))
    
    t_info = teachers_db.get(teacher_username, {})
    teacher_display_name = t_info.get('name', teacher_username)
    students = classes_students.get(class_name, [])
    
    report_rows = ""
    for idx, st in enumerate(students, 1):
        g_key = f"{st} || {class_name} || {subject_name}"
        g_data = grades_db.get(g_key, {})
        grade_val = g_data.get('grade', 'غير مرصود')
        mod_val = g_data.get('modified_grade', '')
        note_val = g_data.get('note', '')
        
        report_rows += f"""
        <tr>
            <td>{idx}</td>
            <td style="text-align:right; font-weight:bold; padding-right:15px;">{st}</td>
            <td style="font-weight:bold; color:#0d47a1; font-size:15px;">{grade_val}</td>
            <td></td><td></td>
            <td style="color:#2e7d32; font-weight:bold;">{mod_val}</td>
            <td style="text-align:right; font-size:12px;">{note_val}</td>
        </tr>
        """

    report_template = f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>لائحة تقييم الطلاب للامتحان - معهد الهرمل الفني</title>
        <style>
            body {{ font-family: 'Times New Roman', serif, system-ui; background: white; color: black; margin: 0; padding: 20px; }}
            .header-table {{ width: 100%; border: none; margin-bottom: 10px; }}
            .header-table td {{ border: none; padding: 4px; text-align: center; vertical-align: middle; }}
            .box-title {{ border: 2px solid black; padding: 8px 15px; font-weight: bold; font-size: 17px; display: inline-block; background: #fafafa; }}
            .info-bar {{ width: 100%; margin-top: 15px; margin-bottom: 15px; font-weight: bold; font-size: 15px; }}
            .info-bar td {{ border: none; padding: 5px 10px; text-align: right; }}
            table.sheet {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            table.sheet th, table.sheet td {{ border: 1.5px solid black; padding: 8px; text-align: center; font-size: 14px; }}
            table.sheet th {{ background-color: #e3f2fd; font-weight: bold; color: black; }}
            @media print {{
                .no-print {{ display: none; }}
                body {{ padding: 0; }}
            }}
        </style>
    </head>
    <body>
        <div class="no-print" style="margin-bottom:20px; text-align:left;">
            <button onclick="window.print()" style="background:#0d47a1; color:white; padding:10px 20px; border:none; font-weight:bold; cursor:pointer; border-radius:5px;">🖨️ طباعة التقرير / حفظ كـ PDF</button>
        </div>
        <table class="header-table">
            <tr>
                <td style="width:35%; text-align:right;">
                    <b>وزارة التربية والتعليم العالي</b><br>
                    <b>المديرية العامة للتعليم المهني والتقني</b><br>
                    <b style="font-size:16px;">معهد الهرمل الفني</b>
                </td>
                <td style="width:65%; text-align:center;">
                    <div class="box-title">لائحة تقييم الطلاب للامتحان ....................</div>
                </td>
            </tr>
        </table>
        <table class="info-bar">
            <tr>
                <td><b>الشهادة والسنة:</b> {class_name}</td>
                <td><b>الصف:</b> {class_name} ({current_academic_year})</td>
            </tr>
            <tr>
                <td><b>الاختصاص:</b> {class_name}</td>
                <td><b>اسم المادة:</b> <span style="color:#0d47a1;">{subject_name}</span></td>
                <td><b>اسم الأستاذ:</b> {teacher_display_name}</td>
            </tr>
        </table>
        <table class="sheet">
            <thead>
                <tr>
                    <th style="width:5%;">#</th>
                    <th style="width:35%;">اسم الطالب الثلاثي</th>
                    <th style="width:10%;">التقييم 1</th>
                    <th style="width:10%;">التقييم 2</th>
                    <th style="width:10%;">التقييم 3</th>
                    <th style="width:12%;">التعديل</th>
                    <th style="width:18%;">ملاحظات</th>
                </tr>
            </thead>
            <tbody>
                {report_rows}
            </tbody>
        </table>
        <div style="margin-top:30px; display:flex; justify-content:space-between; padding:0 40px; font-weight:bold;">
            <div>توقيع الأستاذ: ..................</div>
            <div>توقيع وتصديق المدير: ..................</div>
        </div>
    </body>
    </html>
    '''
    return render_template_string(report_template)

@app.route('/admin/toggle_grade_permission', methods=['POST'])
def toggle_grade_permission():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    t_user = request.form.get('target_user')
    c_name = request.form.get('class_name')
    s_name = request.form.get('subject_name')
    action_type = request.form.get('action_type')
    
    perm_key = f"{t_user} || {c_name} || {s_name}"
    if action_type == 'open':
        grade_edit_permissions[perm_key] = True
        session['msg'] = f"🟢 تم فتح وتخويل إدخال العلامات لمادة ({s_name}) صف ({c_name}) بنجاح!"
    else:
        grade_edit_permissions[perm_key] = False
        session['msg'] = f"🔴 تم قفل وإغلاق إدخال العلامات لمادة ({s_name}) صف ({c_name})."
    
    save_to_disk()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/download_backup')
def download_backup():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    save_to_disk()
    if os.path.exists(DB_FILE):
        return send_file(DB_FILE, as_attachment=True, download_name=f"hermel_database_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
    return "ملف البيانات غير موجود", 404

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
    session['msg'] = "تم تكليف جلسة التدريب الميداني مع الأستاذ الأساسي والمساعد بنجاح!"
    return redirect(url_for('admin_dashboard'))

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    msg = session.pop('msg', '')
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'restore_backup_file':
            file = request.files.get('backup_file')
            if file and file.filename.endswith('.json'):
                try:
                    file.save(DB_FILE)
                    load_from_disk()
                    msg = "تم استرداد قاعدة البيانات بالكامل وتحديث كافة السجلات بنجاح! ✅"
                except Exception as e:
                    msg = f"خطأ في استرداد ملف البيانات: {e}"

        elif action == 'upload_directorate_file':
            file_key = request.form.get('file_key')
            file = request.files.get('excel_file')
            
            if file and allowed_file(file.filename) and file_key in directorate_excel_tables:
                try:
                    df = pd.read_excel(file, sheet_name=0)
                    col_mapping = {col: clean_column_name(col) for col in df.columns}
                    df_renamed = df.rename(columns=col_mapping)
                    clean_columns = list(df_renamed.columns)
                    
                    rows_data = []
                    for _, row in df_renamed.iterrows():
                        row_dict = {col: "" if pd.isna(row[col]) else str(row[col]).strip() for col in df_renamed.columns}
                        rows_data.append(row_dict)
                    
                    table_title = directorate_excel_tables[file_key]['title']
                    
                    if file_key in ['teachers_cards', 'personal_info']:
                        for r in rows_data:
                            t_raw_name = r.get('الاسم الثلاثي', r.get('اسم الاستاذ', r.get('الاسم', ''))).strip()
                            t_norm_key = normalize_name(t_raw_name)
                            allowed_hrs = r.get('عدد الساعات المسموح بها', r.get('الساعات المسموح بها', r.get('Maxhoures', '')))
                            if t_norm_key and allowed_hrs:
                                try:
                                    c_val = float(allowed_hrs)
                                    for u, t_info in teachers_db.items():
                                        if normalize_name(t_info['name']) == t_norm_key:
                                            t_info['contract_hours'] = int(c_val)
                                except:
                                    pass

                    if file_key == 'teachers_and_subjects':
                        parsed = parse_teachers_and_subjects(df)
                        directorate_excel_tables['teachers_and_subjects']['parsed_schedule'] = parsed
                        
                        # إنشاء/توليد حسابات للأساتذة من ملف الاستاذ والمواد تلقائياً
                        count_gen = 0
                        for norm_name, items in parsed.items():
                            orig_name = items[0]['class'] # name anchor
                            raw_t_name = str(df[df.iloc[:, 0].astype(str).apply(normalize_name) == norm_name].iloc[0, 0]).strip() if not df[df.iloc[:, 0].astype(str).apply(normalize_name) == norm_name].empty else norm_name
                            
                            # التأكد إذا كان الأستاذ موجود في قاعدة الحسابات
                            exists = any(normalize_name(t['name']) == norm_name or norm_name in normalize_name(t['name']) or normalize_name(t['name']) in norm_name for t in teachers_db.values())
                            if not exists:
                                u_id = f"teacher_{len(teachers_db) + 1}"
                                teachers_db[u_id] = {
                                    "name": raw_t_name,
                                    "auto_id": f"100{len(teachers_db)+1}",
                                    "password": f"100{len(teachers_db)+1}",
                                    "subject": items[0]['subject'],
                                    "mobile_device": "",
                                    "pc_device": "",
                                    "notifications": [],
                                    "monthly_hours": {},
                                    "contract_hours": 300
                                }
                                count_gen += 1

                    if file_key == 'executed_hours':
                        monthly_map = {}
                        contract_map = {}
                        for r in rows_data:
                            t_raw_name = r.get('الاسم الثلاثي', r.get('اسم الاستاذ', '')).strip()
                            t_norm_key = normalize_name(t_raw_name)
                            if t_raw_name:
                                if t_norm_key not in monthly_map: monthly_map[t_norm_key] = {}
                                allowed_hrs = r.get('عدد الساعات المسموح بها', r.get('Maxhoures', None))
                                if allowed_hrs is not None and str(allowed_hrs).strip() != '':
                                    try: contract_map[t_norm_key] = int(float(allowed_hrs))
                                    except: pass
                                for m_col in MONTH_COLUMNS:
                                    found_val = None
                                    for key, val in r.items():
                                        if clean_column_name(key) == m_col:
                                            found_val = val
                                            break
                                    if found_val is not None:
                                        try: monthly_map[t_norm_key][m_col] = float(found_val or 0)
                                        except: monthly_map[t_norm_key][m_col] = 0.0
                                    else:
                                        monthly_map[t_norm_key][m_col] = 0.0
                        directorate_excel_tables['executed_hours']['monthly_hours'] = monthly_map
                        for u, t_info in teachers_db.items():
                            t_norm = normalize_name(t_info['name'])
                            if t_norm in monthly_map: t_info['monthly_hours'] = monthly_map[t_norm]
                            if t_norm in contract_map: t_info['contract_hours'] = contract_map[t_norm]

                    if file_key == 'transport_days':
                        transport_map = {}
                        for r in rows_data:
                            t_raw_name = r.get('الاسم الثلاثي', r.get('اسم الاستاذ', '')).strip()
                            t_norm_key = normalize_name(t_raw_name)
                            if t_raw_name:
                                if t_norm_key not in transport_map: transport_map[t_norm_key] = {}
                                for m_col in MONTH_COLUMNS:
                                    found_val = None
                                    for key, val in r.items():
                                        if clean_column_name(key) == m_col:
                                            found_val = val
                                            break
                                    if found_val is not None:
                                        try: transport_map[t_norm_key][m_col] = float(found_val or 0)
                                        except: transport_map[t_norm_key][m_col] = 0.0
                                    else:
                                        transport_map[t_norm_key][m_col] = 0.0
                        directorate_excel_tables['transport_days']['monthly_transport'] = transport_map

                    if file_key == 'students_registered':
                        new_classes = {}
                        for r in rows_data:
                            c_name = r.get('الصف', r.get('Class', r.get('التخصص', 'غير مصنف')))
                            s_name = r.get('اسم الطالب الكامل', r.get('اسم الطالب', r.get('الاسم الثلاثي', r.get('الاسم', ''))))
                            if c_name and s_name and str(c_name) != 'nan' and str(s_name) != 'nan':
                                if c_name not in new_classes: new_classes[c_name] = []
                                if s_name not in new_classes[c_name]: new_classes[c_name].append(s_name)
                        if new_classes: classes_students.update(new_classes)

                    directorate_excel_tables[file_key] = {
                        "title": table_title,
                        "columns": clean_columns,
                        "data": rows_data,
                        "monthly_hours": directorate_excel_tables.get('executed_hours', {}).get('monthly_hours', {}),
                        "monthly_transport": directorate_excel_tables.get('transport_days', {}).get('monthly_transport', {})
                    }

                    save_to_disk()
                    msg = f"تم رفع وتحديث ملف ({table_title}) وتربيط المواد والحسابات بنجاح!"
                except Exception as e:
                    msg = f"خطأ في قراءة ملف الإكسل: {e}"

        elif action == 'create_auto_accounts':
            t_cards = directorate_excel_tables.get('teachers_cards', {}).get('data', [])
            count = 0
            for card in t_cards:
                name = card.get('الاسم الثلاثي', card.get('الاسم', '')).strip()
                auto_id = card.get('الرقم الالي', card.get('الرقم الآلي', card.get('رقم الاستاذ', '123456'))).strip()
                allowed_hrs = card.get('عدد الساعات المسموح بها', card.get('الساعات المسموح بها', card.get('Maxhoures', 300)))
                try: c_hrs_val = int(float(allowed_hrs))
                except: c_hrs_val = 300

                if name:
                    user_id = f"teacher_{len(teachers_db) + 1}"
                    if not any(normalize_name(t['name']) == normalize_name(name) for t in teachers_db.values()):
                        teachers_db[user_id] = {
                            "name": name,
                            "auto_id": auto_id,
                            "password": auto_id if auto_id else "123456",
                            "subject": card.get('المادة', 'عام'),
                            "mobile_device": "",
                            "pc_device": "",
                            "notifications": [],
                            "monthly_hours": {},
                            "contract_hours": c_hrs_val
                        }
                        count += 1
            save_to_disk()
            msg = f"تم توليد ({count}) حساب جديد للأساتذة بنجاح!"

        elif action == 'reset_teacher_device':
            target_user = request.form.get('target_user')
            if target_user in teachers_db:
                teachers_db[target_user]['mobile_device'] = ''
                teachers_db[target_user]['pc_device'] = ''
                save_to_disk()
                msg = "تم فك ربط جهاز الأستاذ بنجاح!"

        elif action == 'send_notification':
            target_user = request.form.get('target_user')
            notif = request.form.get('notification_text')
            formatted_notif = f"📢 {notif} (تاريخ الإرسال: {datetime.now().strftime('%Y-%m-%d %H:%M')})"
            if target_user == 'all':
                for u, t in teachers_db.items(): t['notifications'].append(formatted_notif)
            elif target_user in teachers_db:
                teachers_db[target_user]['notifications'].append(formatted_notif)
            save_to_disk()
            msg = "تم إرسال التنبيه والتعميم بنجاح!"

    monthly_data_map = directorate_excel_tables.get('executed_hours', {}).get('monthly_hours', {})
    executed_hours_table_html = ""
    if monthly_data_map:
        m_headers = "".join([f"<th>ش {m}</th>" for m in MONTH_COLUMNS])
        m_rows = ""
        for norm_k, m_dict in monthly_data_map.items():
            disp_name = norm_k
            for t_info in teachers_db.values():
                if normalize_name(t_info['name']) == norm_k:
                    disp_name = t_info['name']
                    break
            m_tds = "".join([f"<td>{m_dict.get(m, 0):.0f}</td>" for m in MONTH_COLUMNS])
            total_exec = sum(m_dict.values())
            m_rows += f"<tr><td style='text-align:right; font-weight:bold;'>{disp_name}</td>{m_tds}<td style='background:#e3f2fd;'><b style='color:#0d47a1;'>{total_exec:.0f}</b></td></tr>"
        executed_hours_table_html = f"<div style='overflow-x:auto;'><table><tr><th style='min-width:180px;'>الاسم الثلاثي</th>{m_headers}<th>المجموع</th></tr>{m_rows}</table></div>"
    else:
        executed_hours_table_html = "<p style='color:#666;'>لم يتم رفع ملف الساعات المنفذة بعد.</p>"

    monthly_trans_map = directorate_excel_tables.get('transport_days', {}).get('monthly_transport', {})
    transport_table_html = ""
    if monthly_trans_map:
        t_headers = "".join([f"<th>ش {m}</th>" for m in MONTH_COLUMNS])
        t_rows = ""
        for norm_k, m_dict in monthly_trans_map.items():
            disp_name = norm_k
            for t_info in teachers_db.values():
                if normalize_name(t_info['name']) == norm_k:
                    disp_name = t_info['name']
                    break
            t_tds = "".join([f"<td>{m_dict.get(m, 0):.0f} يوم</td>" for m in MONTH_COLUMNS])
            total_days = sum(m_dict.values())
            t_rows += f"<tr><td style='text-align:right; font-weight:bold;'>{disp_name}</td>{t_tds}<td style='background:#e8f5e9;'><b style='color:#2e7d32;'>{total_days:.0f} يوم</b></td></tr>"
        transport_table_html = f"<div style='overflow-x:auto;'><table><tr><th style='min-width:180px;'>الاسم الثلاثي</th>{t_headers}<th>إجمالي الأيام</th></tr>{t_rows}</table></div>"
    else:
        transport_table_html = "<p style='color:#666;'>لم يتم رفع ملف أيام وبدل النقل بعد.</p>"

    parsed_sched = directorate_excel_tables.get('teachers_and_subjects', {}).get('parsed_schedule', {})
    
    late_teachers_rows = ""
    if not parsed_sched:
        late_teachers_rows = "<tr><td colspan='4' style='color:#c62828; font-weight:bold;'>⚠️ لم يتم رفع جدول (الاستاذ والمواد) بعد.</td></tr>"
    else:
        for u, t_info in teachers_db.items():
            norm_t = normalize_name(t_info['name'])
            items = []
            for sched_name, sched_items in parsed_sched.items():
                if norm_t in sched_name or sched_name in norm_t or any(part in sched_name for part in norm_t.split() if len(part) > 2):
                    items.extend(sched_items)
            
            pending_subjects = []
            for item in items:
                c_name = item['class']
                s_name = item['subject']
                st_list = classes_students.get(c_name, [])
                if not st_list:
                    pending_subjects.append(f"{c_name} ({s_name} - بانتظار طلاب الصف)")
                    continue
                
                submitted_count = 0
                for st in st_list:
                    if f"{st} || {c_name} || {s_name}" in grades_db:
                        submitted_count += 1
                
                if submitted_count < len(st_list):
                    pending_subjects.append(f"{c_name} ({s_name})")
            
            if pending_subjects:
                late_teachers_rows += f"<tr><td><b>{t_info['name']}</b></td><td><code>{u}</code></td><td><span style='color:#c62828; font-weight:bold;'>⚠️ لم يُسلم علامات مواد: {', '.join(set(pending_subjects))}</span></td><td><a href='/report/official_sheet?teacher_username={u}' target='_blank'>📄 معاينة</a></td></tr>"

    if not late_teachers_rows:
        late_teachers_rows = "<tr><td colspan='4' style='color:#2e7d32; font-weight:bold;'>جميع الأساتذة قاموا بتسليم العلامات لكافة موادهم بنجاح! 🎉</td></tr>"

    official_reports_list_html = ""
    if parsed_sched:
        for u, t_info in teachers_db.items():
            norm_t = normalize_name(t_info['name'])
            items = []
            for sched_name, sched_items in parsed_sched.items():
                if norm_t in sched_name or sched_name in norm_t or any(part in sched_name for part in norm_t.split() if len(part) > 2):
                    items.extend(sched_items)
            
            seen_combos = set()
            for item in items:
                c_name = item['class']
                s_name = item['subject']
                combo_key = f"{c_name} || {s_name}"
                if combo_key not in seen_combos:
                    seen_combos.add(combo_key)
                    official_reports_list_html += f"<tr><td><b>{t_info['name']}</b></td><td><b>{c_name}</b></td><td><b style='color:#0d47a1;'>{s_name}</b></td><td><a href='/report/official_sheet?class_name={c_name}&subject_name={s_name}&teacher_username={u}' target='_blank' style='background:#0d47a1; color:white; padding:5px 12px; border-radius:4px; text-decoration:none;'>📄 فتح التقرير الرسمي</a></td></tr>"
    if not official_reports_list_html:
        official_reports_list_html = "<tr><td colspan='4'>لم يتم رفع ملف الاستاذ والمواد بعد</td></tr>"

    attendance_detailed_rows = ""
    if attendance_db:
        for key, record in attendance_db.items():
            present_list = record.get('present', [])
            absent_list = record.get('absent', [])
            attendance_detailed_rows += f"""
            <tr>
                <td style='font-weight:bold; color:#0d47a1;'>{key}</td>
                <td style='color:#2e7d32; font-weight:bold;'>الحاضرون ({len(present_list)}): {', '.join(present_list[:10])}{' ...' if len(present_list)>10 else ''}</td>
                <td style='color:#c62828; font-weight:bold;'>المتغيبون ({len(absent_list)}): {', '.join(absent_list) if absent_list else 'لا يوجد غياب ✅'}</td>
            </tr>
            """
    else:
        attendance_detailed_rows = "<tr><td colspan='3' style='color:#666;'>لم يتم تسجيل أي حضور أو غياب للطلاب حتى الآن.</td></tr>"

    teachers_rows = "".join([f"<tr><td><b>{t['name']}</b><br><small>رقم آلي: {t.get('auto_id','')}</small></td><td><code>{u}</code></td><td><b style='color:#d32f2f;'>{t['password']}</b></td><td>{'📱 مرتبط' if t.get('mobile_device') else 'غير مسجل'}</td></tr>" for u, t in teachers_db.items()])
    
    field_rows = "".join([f"<tr><td><b>{fs['location']}</b><br><small>{fs['class_name']}</small></td><td>👤 أساسي: <b style='color:#0d47a1;'>{fs['primary_teacher']}</b><br>{'👥 مساعد: <b style=\'color:#2e7d32;\'>' + fs['secondary_teacher'] + '</b>' if fs.get('secondary_teacher') else ''}</td><td>{fs['status']}</td></tr>" for fs in reversed(field_sessions)])
    
    replies_html = "".join([f"<div style='background:#fff3e0; padding:10px; margin-bottom:8px; border-radius:6px;'><b>من: {r['teacher_name']}</b><br>{r['message']}</div>" for r in reversed(admin_replies)])
    
    directorate_htmls = {}
    for k, v in directorate_excel_tables.items():
        cols = v.get('columns', [])
        rows_d = v.get('data', [])
        headers_th = "".join([f"<th>{c}</th>" for c in cols]) if cols else "<th>البيانات</th>"
        body_tr = ""
        if rows_d:
            for r in rows_d[:50]:
                tds = "".join([f"<td>{r.get(c, '')}</td>" for c in cols]) if cols else f"<td>{str(r)}</td>"
                body_tr += f"<tr>{tds}</tr>"
        else:
            body_tr = "<tr><td colspan='1'>لا توجد بيانات مرفوعة بعد</td></tr>"
        directorate_htmls[k] = f"<h4>📂 {v['title']}</h4><div style='overflow-x:auto;'><table><tr>{headers_th}</tr>{body_tr}</table></div><small>إجمالي السجلات: {len(rows_d)}</small>"

    teacher_opts = "".join([f"<option value='{u}'>{t['name']} ({u})</option>" for u, t in teachers_db.items()])
    locations_opts = "".join([f"<option value='{loc}'>{loc}</option>" for loc in TRAINING_LOCATIONS.keys()])

    schedule_mapping = {}
    if parsed_sched:
        for norm_t, items in parsed_sched.items():
            t_user_key = None
            t_disp_name = norm_t
            for u, t_info in teachers_db.items():
                if normalize_name(t_info['name']) == norm_t:
                    t_user_key = u
                    t_disp_name = t_info['name']
                    break
            
            for item in items:
                c_full = item['class']
                c_name = c_full
                major_name = "الاختصاص"
                if " - " in c_full:
                    parts = c_full.split(" - ")
                    c_name = parts[0].strip()
                    major_name = parts[1].strip()

                if c_name not in schedule_mapping:
                    schedule_mapping[c_name] = {}
                if major_name not in schedule_mapping[c_name]:
                    schedule_mapping[c_name][major_name] = []
                
                t_obj = {"username": t_user_key or norm_t, "name": t_disp_name}
                if t_obj not in schedule_mapping[c_name][major_name]:
                    schedule_mapping[c_name][major_name].append(t_obj)
    
    if not schedule_mapping and teachers_db:
        schedule_mapping["الصف الأول"] = {"الاختصاص العام": [{"username": u, "name": t['name']} for u, t in teachers_db.items()]}

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
        </style>
    </head>
    <body>
        ''' + HEADER_VTE_HTML + '''

        <div class="container">
            {% if msg %}<div style="background:#e8f5e9; color:#2e7d32; padding:12px; border-radius:6px; font-weight:bold; margin-bottom:15px;">{{ msg }}</div>{% endif %}

            <div id="studentAttendanceSec" class="card active">
                <h3 style="color:#0d47a1; margin-top:0;">📋 تقرير حضور وغياب الطلاب المفصل (حسب الصف، اليوم، والشهر)</h3>
                <table>
                    <tr><th>الصف وتاريخ السجل (اليوم والشهر)</th><th>الطلاب الحاضرون</th><th>الطلاب المتغيبون</th></tr>
                    {{ attendance_detailed_rows | safe }}
                </table>
            </div>

            <div id="studentGradesSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">📝 التقارير الرسمية لعلامات الطلاب (لائحة تقييم الطلاب للامتحان)</h3>
                <table>
                    <tr><th>اسم الأستاذ</th><th>الصف والسنة</th><th>المادة التعليمية</th><th>عرض وطباعة التقرير الرسمي</th></tr>
                    {{ official_reports_list_html | safe }}
                </table>
            </div>

            <div id="lateTeachersSec" class="card">
                <h3 style="color:#c62828; margin-top:0;">⚠️ الأساتذة المتأخرون عن تسليم العلامات في المواد الخاصة بهم</h3>
                <table>
                    <tr><th>اسم الأستاذ</th><th>اسم المستخدم</th><th>المواد والصفوف المتبقية ولم تُدخل لها علامة</th><th>معاينة التقرير</th></tr>
                    {{ late_teachers_rows | safe }}
                </table>
            </div>

            <div id="grantEditPermissionSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">💡 التحكم بفتح وإغلاق إدخال العلامات للأستاذ (On / Off)</h3>
                <form action="/admin/toggle_grade_permission" method="POST">
                    <label>اختر الأستاذ:</label>
                    <select name="target_user" required>{{ teacher_opts | safe }}</select>
                    <label>اسم الصف والمستوى:</label>
                    <input type="text" name="class_name" placeholder="مثال: BT1 الكهرباء" required>
                    <label>اسم المادة:</label>
                    <input type="text" name="subject_name" placeholder="مثال: الرياضيات العامة" required>
                    <label>حالة الضوء (الإذن):</label>
                    <select name="action_type" required style="font-weight:bold; background:#e3f2fd;">
                        <option value="open">🟢 فتح المجال (إضاءة الضوء ON للسماح بالإدخال)</option>
                        <option value="close">🔴 إغلاق المجال (إطفاء الضوء OFF وقفل التعديل)</option>
                    </select>
                    <button type="submit" style="background:#2e7d32; margin-top:12px; font-size:15px;">💾 تنفيذ حالة الإذن فوراً</button>
                </form>
            </div>

            <div id="viewRegisteredStudents" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">📂 الطلاب المسجلون</h3>
                {{ directorate_htmls['students_registered'] | safe }}
            </div>

            <div id="viewTeachersCards" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">📇 بطاقات الأساتذة والمعلومات الشخصية</h3>
                {{ directorate_htmls['teachers_cards'] | safe }}
                <hr style="margin:20px 0;">
                {{ directorate_htmls['personal_info'] | safe }}
            </div>

            <div id="viewTeachersAndSubjects" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">📋 جدول الاستاذ والمواد (نظري / تطبيقي)</h3>
                {{ directorate_htmls['teachers_and_subjects'] | safe }}
            </div>

            <div id="viewExecutedHours" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">⏱️ الساعات المنفذة للأساتذة شهرياً</h3>
                {{ executed_hours_table_html | safe }}
            </div>

            <div id="viewTransportDays" class="card">
                <h3 style="color:#2e7d32; margin-top:0;">🚗 أيام الحضور وبدل النقل للأساتذة شهرياً</h3>
                {{ transport_table_html | safe }}
            </div>

            <div id="teachersListSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">👨‍🏫 سجل الأساتذة وعقود الساعات</h3>
                <form method="POST" style="margin-bottom:15px;">
                    <input type="hidden" name="action" value="create_auto_accounts">
                    <button type="submit" style="background:#2e7d32;">⚡ توليد حسابات الأساتذة تلقائياً من إكسل البطاقات</button>
                </form>
                <table><tr><th>الاسم</th><th>اسم المستخدم</th><th>كلمة المرور</th><th>الجهاز</th></tr>{{ teachers_rows | safe }}</table>
            </div>

            <div id="fieldSessionSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">🏥 إضافة وإدارة الجلسات الميدانية والـ GPS</h3>
                <form action="/admin/create_field_session" method="POST">
                    <label><b>1. اختر المركز التدريبي:</b></label>
                    <select name="location" required>{{ locations_opts | safe }}</select>

                    <label style="margin-top:10px; display:block;"><b>2. اختر الصف:</b></label>
                    <select name="class_name" id="fieldClassSelect" onchange="onFieldClassChange()" required>
                        <option value="">-- اختر الصف --</option>
                    </select>

                    <label style="margin-top:10px; display:block;"><b>3. اختر الاختصاص:</b></label>
                    <select name="major" id="fieldMajorSelect" onchange="onFieldMajorChange()" required>
                        <option value="">-- اختر الصف أولاً --</option>
                    </select>

                    <label style="margin-top:10px; display:block;"><b>4. اختر الأستاذ الأساسي للتدريب:</b></label>
                    <select name="primary_teacher" id="fieldPrimaryTeacher" required>
                        <option value="">-- اختر الاختصاص أولاً --</option>
                    </select>

                    <label style="margin-top:10px; display:block;"><b>5. اختر الأستاذ المساعد (اختياري):</b></label>
                    <select name="secondary_teacher" id="fieldSecondaryTeacher">
                        <option value="none">-- بدون أستاذ مساعد --</option>
                    </select>

                    <button type="submit" style="margin-top:15px; background:#2e7d32; font-size:15px;">✅ تأكيد وتكليف جلسة التدريب</button>
                </form>

                <hr style="margin:20px 0;">
                <h4 style="color:#0d47a1;">📋 سجل جلسات التدريب الميداني</h4>
                <table><tr><th>المركز والصف</th><th>الأساتذة المكلفون (أساسي ومساعد)</th><th>الحالة</th></tr>{{ field_rows | safe }}</table>
            </div>

            <div id="uploadDirectorateFilesSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">⚙️ رفع ملفات المديرية والبرنامج (Excel)</h3>
                <form method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="action" value="upload_directorate_file">
                    <label><b>حدد نوع جدول الإكسل المراد رفعه:</b></label>
                    <select name="file_key" required style="font-weight:bold; background:#e3f2fd;">
                        <option value="teachers_and_subjects">📋 0. جدول الاستاذ والمواد (المطلوب)</option>
                        <option value="executed_hours">⏱️ 1. الساعات المنفذة للأساتذة</option>
                        <option value="students_registered">📂 2. الطلاب المسجلون</option>
                        <option value="personal_info">👤 3. المعلومات الشخصية</option>
                        <option value="transport_days">🚗 4. أيام الحضور وبدل النقل للأساتذة</option>
                        <option value="teachers_cards">📇 5. بطاقات الأساتذة</option>
                    </select>
                    <label style="margin-top:12px; display:block;"><b>اختر ملف الإكسل (.xlsx أو .xls):</b></label>
                    <input type="file" name="excel_file" accept=".xlsx, .xls" required style="margin-top:5px;">
                    <button type="submit" style="background:#2e7d32; margin-top:15px; font-size:15px;">📥 رفع وتحديث الملف فوراً</button>
                </form>
            </div>

            <div id="deviceBindingSec" class="card">
                <h3 style="color:#c62828; margin-top:0;">📱 إدارة أجهزة الأساتذة (فك الربط)</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="reset_teacher_device">
                    <select name="target_user" required>{{ teacher_opts | safe }}</select>
                    <button type="submit" style="background:#c62828; margin-top:10px;">🔓 فك الربط</button>
                </form>
            </div>

            <div id="sendNotifSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">📢 إرسال تعميم أو تنبيه</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="send_notification">
                    <select name="target_user" required><option value="all">الجميع</option>{{ teacher_opts | safe }}</select>
                    <textarea name="notification_text" required style="height:70px;"></textarea>
                    <button type="submit" style="margin-top:10px;">إرسال التعميم</button>
                </form>
            </div>

            <div id="backupSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">💾 النسخ الاحتياطي والاسترداد</h3>
                <div style="display:flex; gap:15px; flex-wrap:wrap; align-items:center; margin-top:12px;">
                    <a href="/admin/download_backup" style="display:inline-block; background:#2e7d32; color:white; padding:10px 18px; border-radius:6px; text-decoration:none; font-weight:bold;">📥 تنزيل نسخة احتياطية (JSON)</a>
                    
                    <form method="POST" enctype="multipart/form-data" style="display:flex; gap:10px; align-items:center; flex:1; margin:0;">
                        <input type="hidden" name="action" value="restore_backup_file">
                        <input type="file" name="backup_file" accept=".json" required style="padding:6px; margin:0;">
                        <button type="submit" style="background:#c62828; width:auto; padding:10px 18px; margin:0;">📤 استرداد نسخة سابقة</button>
                    </form>
                </div>
            </div>

            <div id="teacherRepliesSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">📩 الرسائل الواردة</h3>
                {{ replies_html | safe }}
            </div>
        </div>

        <script>
            let schedMap = {{ schedule_mapping | tojson }};

            function initFieldDropdowns() {
                let classSel = document.getElementById('fieldClassSelect');
                if(!classSel) return;
                classSel.innerHTML = '<option value="">-- اختر الصف --</option>';
                Object.keys(schedMap).forEach(c => {
                    classSel.innerHTML += `<option value="${c}">${c}</option>`;
                });
            }

            function onFieldClassChange() {
                let c = document.getElementById('fieldClassSelect').value;
                let majorSel = document.getElementById('fieldMajorSelect');
                let pTeachSel = document.getElementById('fieldPrimaryTeacher');
                let sTeachSel = document.getElementById('fieldSecondaryTeacher');

                majorSel.innerHTML = '<option value="">-- اختر الاختصاص --</option>';
                pTeachSel.innerHTML = '<option value="">-- اختر الاختصاص أولاً --</option>';
                sTeachSel.innerHTML = '<option value="none">-- بدون أستاذ مساعد --</option>';

                if(c && schedMap[c]) {
                    Object.keys(schedMap[c]).forEach(m => {
                        majorSel.innerHTML += `<option value="${m}">${m}</option>`;
                    });
                }
            }

            function onFieldMajorChange() {
                let c = document.getElementById('fieldClassSelect').value;
                let m = document.getElementById('fieldMajorSelect').value;
                let pTeachSel = document.getElementById('fieldPrimaryTeacher');
                let sTeachSel = document.getElementById('fieldSecondaryTeacher');

                pTeachSel.innerHTML = '<option value="">-- اختر الأستاذ الأساسي --</option>';
                sTeachSel.innerHTML = '<option value="none">-- بدون أستاذ مساعد --</option>';

                if(c && m && schedMap[c] && schedMap[c][m]) {
                    schedMap[c][m].forEach(t => {
                        pTeachSel.innerHTML += `<option value="${t.name}">${t.name}</option>`;
                        sTeachSel.innerHTML += `<option value="${t.name}">${t.name}</option>`;
                    });
                }
            }

            document.addEventListener('DOMContentLoaded', function() {
                initFieldDropdowns();
            });

            function showSection(secId) {
                document.querySelectorAll('.card').forEach(el => el.classList.remove('active'));
                let target = document.getElementById(secId);
                if(target) target.classList.add('active');
            }
        </script>
    </body>
    </html>
    '''
    return render_template_string(admin_template, attendance_detailed_rows=attendance_detailed_rows, teachers_rows=teachers_rows, late_teachers_rows=late_teachers_rows, official_reports_list_html=official_reports_list_html, field_rows=field_rows, replies_html=replies_html, teacher_opts=teacher_opts, locations_opts=locations_opts, directorate_htmls=directorate_htmls, executed_hours_table_html=executed_hours_table_html, transport_table_html=transport_table_html, schedule_mapping=schedule_mapping, msg=msg)

@app.route('/teacher', methods=['GET', 'POST'])
def teacher_dashboard():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    
    username = session.get('username')
    user_data = teachers_db.get(username, {})
    t_name = user_data.get('name', '').strip()
    norm_t_name = normalize_name(t_name)
    msg = ''

    parsed_schedule = directorate_excel_tables.get('teachers_and_subjects', {}).get('parsed_schedule', {})
    my_schedule_items = []
    
    # مطابقة ذكية شامِلة وقوية جداً للمطابقة بين الأسماء
    for sched_name, items in parsed_schedule.items():
        if (norm_t_name in sched_name or 
            sched_name in norm_t_name or 
            any(part in sched_name for part in norm_t_name.split() if len(part) > 2) or
            any(part in norm_t_name for part in sched_name.split() if len(part) > 2)):
            my_schedule_items.extend(items)

    my_classes_map = {}
    for item in my_schedule_items:
        c_name = item['class']
        s_name = f"{item['subject']} ({item.get('type', 'نظري')})"
        if c_name not in my_classes_map:
            my_classes_map[c_name] = []
        if s_name not in my_classes_map[c_name]:
            my_classes_map[c_name].append(s_name)

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'submit_class_grades':
            class_name = request.form.get('class_name')
            raw_subject_name = request.form.get('subject_name')
            subject_name = raw_subject_name.split(' (')[0] if ' (' in raw_subject_name else raw_subject_name
            
            perm_key = f"{username} || {class_name} || {subject_name}"
            is_open = grade_edit_permissions.get(perm_key, False)
            already_submitted = any(f"{st} || {class_name} || {subject_name}" in grades_db for st in classes_students.get(class_name, []))
            
            if already_submitted and not is_open:
                msg = "🔴 عذراً! مجال إدخال وتعديل العلامات مغلق من قبل الإدارة (الضوء مطفأ). يرجى مراجعة المدير لفتح المجال."
            else:
                students = classes_students.get(class_name, [])
                for st in students:
                    g_val = request.form.get(f"grade_{st}")
                    note_val = request.form.get(f"note_{st}", '')
                    g_key = f"{st} || {class_name} || {subject_name}"
                    
                    existing = grades_db.get(g_key, {})
                    first_g = existing.get('grade', g_val)
                    mod_g = g_val if already_submitted else ''
                    
                    grades_db[g_key] = {
                        "student": st,
                        "class": class_name,
                        "subject": subject_name,
                        "grade": first_g,
                        "modified_grade": mod_g,
                        "note": note_val,
                        "teacher": username,
                        "submitted_at": datetime.now().strftime('%Y-%m-%d %H:%M')
                    }
                save_to_disk()
                msg = "🟢 تم حفظ ورصد علامات الطلاب بنجاح وإرسالها للإدارة!"

        elif action == 'submit_class_attendance':
            class_name = request.form.get('class_name')
            students = classes_students.get(class_name, [])
            present_sts = request.form.getlist('attendance_check')
            absent_sts = [s for s in students if s not in present_sts]
            date_key = datetime.now().strftime('%Y-%m-%d (%A)')
            attendance_db[f"الصف: {class_name} | التاريخ: {date_key}"] = {'present': present_sts, 'absent': absent_sts}
            save_to_disk()
            msg = "تم تسجيل حضور وغياب الطلاب بنجاح!"

    my_class_opts = "".join([f'<option value="{c}">{c}</option>' for c in my_classes_map.keys()])
    
    pending_alerts = []
    for c_name, sub_list in my_classes_map.items():
        st_list = classes_students.get(c_name, [])
        for s_full in sub_list:
            s_name = s_full.split(' (')[0] if ' (' in s_full else s_full
            submitted = any(f"{st} || {c_name} || {s_name}" in grades_db for st in st_list)
            if not submitted:
                pending_alerts.append(f"⚠️ صف ({c_name}) - مادة ({s_full})")

    pending_alerts_html = ""
    if pending_alerts:
        pending_alerts_html = "<div style='background:#fff3e0; border-right:4px solid #e65100; padding:10px; margin-bottom:12px; font-weight:bold; color:#e65100;'>تنبيه: لديك مواد لم تقم برصد علاماتها بعد:<br>" + "<br>".join(pending_alerts) + "</div>"

    schedule_html = ""
    if my_schedule_items:
        s_rows = "".join([f"<tr><td>{item['day']}</td><td>{item['period']}</td><td><b>{item['class']}</b></td><td><b style='color:#0d47a1;'>{item['subject']}</b></td><td><span style='background:#e3f2fd; padding:3px 8px; border-radius:4px; font-size:12px;'>{item.get('type','نظري')}</span></td></tr>" for item in my_schedule_items])
        schedule_html = f"<div class='card' style='border-top:4px solid #2e7d32;'><h4 style='color:#2e7d32; margin-top:0;'>📋 المواد والصفوف الخاصة بي (حسب جدول الاستاذ والمواد):</h4><table><tr><th>اليوم</th><th>الدوام</th><th>الصف والمستوى</th><th>المادة</th><th>النوع</th></tr>{s_rows}</table></div>"
    else:
        schedule_html = "<div class='card'><p style='color:#c62828; font-weight:bold;'>⚠️ لم يتم العثور على مواد مرتبطة باسمك في جدول (الاستاذ والمواد). تأكد من رفع الملف من لوحة الإدارة.</p></div>"

    my_monthly_hours = user_data.get('monthly_hours', {})
    total_exec_hrs = sum(my_monthly_hours.values()) if my_monthly_hours else 0
    contract_limit = user_data.get('contract_hours', 300)

    transport_map_all = directorate_excel_tables.get('transport_days', {}).get('monthly_transport', {})
    my_transport_dict = {}
    for norm_k, trans_d in transport_map_all.items():
        if norm_k in norm_t_name or norm_t_name in norm_k:
            my_transport_dict = trans_d
            break
    total_trans_days = sum(my_transport_dict.values()) if my_transport_dict else 0

    teacher_finance_html = f"""
    <div class='card' style='border-top:4px solid #0d47a1;'>
        <h4 style='color:#0d47a1; margin-top:0;'>📊 رصيدي المالي والساعات المنفذة وبدلات النقل:</h4>
        <div style='display:flex; gap:15px; flex-wrap:wrap; margin-top:10px;'>
            <div style='flex:1; background:#e3f2fd; padding:12px; border-radius:6px; text-align:center;'>
                <div style='font-size:13px; color:#555;'>إجمالي الساعات المنفذة</div>
                <div style='font-size:20px; font-weight:bold; color:#0d47a1; margin-top:4px;'>{total_exec_hrs:.0f} ساعة</div>
                <small style='color:#666;'>من أصل {contract_limit} ساعة</small>
            </div>
            <div style='flex:1; background:#e8f5e9; padding:12px; border-radius:6px; text-align:center;'>
                <div style='font-size:13px; color:#555;'>إجمالي أيام وحضور النقل</div>
                <div style='font-size:20px; font-weight:bold; color:#2e7d32; margin-top:4px;'>{total_trans_days:.0f} يوم</div>
            </div>
        </div>
    </div>
    """

    raw_notifs = user_data.get('notifications', [])
    notifs = "".join([f"<div style='background:#e3f2fd; padding:10px; margin-bottom:6px; border-radius:6px; font-weight:bold; color:#0d47a1;'>🔔 {str(n)}</div>" for n in reversed(raw_notifs)]) if raw_notifs else "<p style='color:#666;'>لا توجد تعاميم جديدة.</p>"

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
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { border: 1px solid #e0e0e0; padding: 8px; text-align: center; font-size: 13px; }
            th { background: #0d47a1; color: white; }
            .student-row { display: flex; gap: 10px; align-items: center; padding: 8px; border-bottom: 1px solid #eee; background: #fafafa; margin-top: 5px; border-radius: 4px; }
        </style>
    </head>
    <body>
        <div style="background:#0d47a1; color:white; padding:12px 20px; display:flex; justify-content:space-between; align-items:center;">
            <div><h3 style="margin:0;">معهد الهرمل الفني</h3><small>الأستاذ: {{ t_name }}</small></div>
            <a href="/logout" style="color:#ffcdd2; background:#c62828; padding:6px 12px; border-radius:4px; text-decoration:none; font-size:12px;">خروج</a>
        </div>

        <audio id="notifSound" src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" preload="auto"></audio>

        <div style="padding:15px;">
            {% if msg %}<div style="background:#e8f5e9; color:#2e7d32; padding:10px; border-radius:6px; margin-bottom:10px; font-weight:bold;">{{ msg }}</div>{% endif %}

            {{ pending_alerts_html | safe }}

            {{ teacher_finance_html | safe }}

            {{ schedule_html | safe }}

            <div class="card">
                <h4 style="color:#0d47a1; margin-top:0;">📝 إدخال ورصد علامات الطلاب (من 0 إلى 20 أو غائب):</h4>
                <form method="POST">
                    <input type="hidden" name="action" value="submit_class_grades">
                    <label>اختر الصف الخاص بك:</label>
                    <select name="class_name" id="gradeClass" onchange="updateSubjectOpts()" required>
                        <option value="">-- اختر الصف --</option>
                        {{ my_class_opts | safe }}
                    </select>

                    <label style="margin-top:10px; display:block;">اختر المادة التعليمية الخاصة بك:</label>
                    <select name="subject_name" id="gradeSubject" onchange="loadStudentsForGrades()" required>
                        <option value="">-- اختر المادة --</option>
                    </select>

                    <div id="gradeContainer" style="margin-top:10px;"></div>
                    <button type="submit" id="gradeBtn" style="display:none; margin-top:10px;">💾 تسليم ورصد العلامات رسمياً</button>
                </form>
            </div>

            <div class="card">
                <h4 style="color:#0d47a1; margin-top:0;">📋 توثيق حضور وغياب الطلاب اليومي:</h4>
                <form method="POST">
                    <input type="hidden" name="action" value="submit_class_attendance">
                    <label>اختر الصف:</label>
                    <select name="class_name" id="attClass" onchange="loadStudentsForAtt()" required><option value="">-- اختر الصف --</option>{{ my_class_opts | safe }}</select>
                    <div id="attContainer" style="margin-top:10px;"></div>
                    <button type="submit" id="attBtn" style="display:none; background:#2e7d32; margin-top:10px;">حفظ الحضور والغياب</button>
                </form>
            </div>

            <div class="card">
                <h4 style="color:#0d47a1; margin-top:0;">📢 الإشعارات الواردة:</h4>
                {{ notifs | safe }}
            </div>
        </div>

        <script>
            let myClassesData = {{ my_classes_map | tojson }};

            function updateSubjectOpts() {
                let cls = document.getElementById('gradeClass').value;
                let subSelect = document.getElementById('gradeSubject');
                subSelect.innerHTML = '<option value="">-- اختر المادة --</option>';
                document.getElementById('gradeContainer').innerHTML = '';
                document.getElementById('gradeBtn').style.display = 'none';

                if(cls && myClassesData[cls]) {
                    myClassesData[cls].forEach(s => {
                        subSelect.innerHTML += `<option value="${s}">${s}</option>`;
                    });
                }
            }

            function loadStudentsForGrades() {
                let cls = document.getElementById('gradeClass').value;
                let sub = document.getElementById('gradeSubject').value;
                let cont = document.getElementById('gradeContainer');
                let btn = document.getElementById('gradeBtn');
                cont.innerHTML = '';
                if(!cls || !sub) { btn.style.display='none'; return; }

                fetch('/api/get_students/' + encodeURIComponent(cls)).then(res => res.json()).then(data => {
                    let html = '';
                    data.students.forEach(st => {
                        html += `
                        <div class="student-row">
                            <span style="flex:1; font-weight:bold;">${st}</span>
                            <select name="grade_${st}" style="width:120px; margin:0;" required>
                                <option value="">-- العلامة --</option>
                                <option value="غائب">غائب (Absent)</option>
                                <option value="0">0 / 20</option>
                                <option value="0.5">0.5 / 20</option>
                                <option value="1">1 / 20</option>
                                <option value="1.5">1.5 / 20</option>
                                <option value="2">2 / 20</option>
                                <option value="2.5">2.5 / 20</option>
                                <option value="3">3 / 20</option>
                                <option value="3.5">3.5 / 20</option>
                                <option value="4">4 / 20</option>
                                <option value="4.5">4.5 / 20</option>
                                <option value="5">5 / 20</option>
                                <option value="5.5">5.5 / 20</option>
                                <option value="6">6 / 20</option>
                                <option value="6.5">6.5 / 20</option>
                                <option value="7">7 / 20</option>
                                <option value="7.5">7.5 / 20</option>
                                <option value="8">8 / 20</option>
                                <option value="8.5">8.5 / 20</option>
                                <option value="9">9 / 20</option>
                                <option value="9.5">9.5 / 20</option>
                                <option value="10">10 / 20</option>
                                <option value="10.5">10.5 / 20</option>
                                <option value="11">11 / 20</option>
                                <option value="11.5">11.5 / 20</option>
                                <option value="12">12 / 20</option>
                                <option value="12.5">12.5 / 20</option>
                                <option value="13">13 / 20</option>
                                <option value="13.5">13.5 / 20</option>
                                <option value="14">14 / 20</option>
                                <option value="14.5">14.5 / 20</option>
                                <option value="15">15 / 20</option>
                                <option value="15.5">15.5 / 20</option>
                                <option value="16">16 / 20</option>
                                <option value="16.5">16.5 / 20</option>
                                <option value="17">17 / 20</option>
                                <option value="17.5">17.5 / 20</option>
                                <option value="18">18 / 20</option>
                                <option value="18.5">18.5 / 20</option>
                                <option value="19">19 / 20</option>
                                <option value="19.5">19.5 / 20</option>
                                <option value="20">20 / 20</option>
                            </select>
                            <input type="text" name="note_${st}" placeholder="ملاحظة (اختياري)" style="width:160px; margin:0;">
                        </div>`;
                    });
                    cont.innerHTML = html;
                    btn.style.display = 'block';
                });
            }

            function loadStudentsForAtt() {
                let cls = document.getElementById('attClass').value;
                let cont = document.getElementById('attContainer');
                let btn = document.getElementById('attBtn');
                cont.innerHTML = '';
                if(!cls) { btn.style.display='none'; return; }
                fetch('/api/get_students/' + encodeURIComponent(cls)).then(res => res.json()).then(data => {
                    let html = '<p style="font-size:13.5px; color:#0d47a1; font-weight:bold;">الكل حاضر افتراضياً ✅ (أزل الصح عن المتغيب):</p>';
                    data.students.forEach(st => {
                        html += `<div class="student-row"><span style="flex:1;">${st}</span><label style="color:#2e7d32; font-weight:bold; cursor:pointer;"><input type="checkbox" name="attendance_check" value="${st}" checked style="width:auto; transform:scale(1.2);"> حاضر</label></div>`;
                    });
                    cont.innerHTML = html;
                    btn.style.display = 'block';
                });
            }
        </script>
    </body>
    </html>
    """
    return render_template_string(teacher_template, t_name=t_name, msg=msg, my_class_opts=my_class_opts, my_classes_map=my_classes_map, pending_alerts_html=pending_alerts_html, schedule_html=schedule_html, teacher_finance_html=teacher_finance_html, notifs=notifs)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('logout'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)