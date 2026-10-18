import os
import json
import io
import math
import shutil
import pandas as pd
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, session, send_from_directory, jsonify

app = Flask(__name__)
app.secret_key = 'hermel_tech_school_shams_secret_key_2026'

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'xlsx', 'xls'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_FILE = 'database.json'
BACKUP_FILE = 'database_backup.json'

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

MONTH_COLUMNS = ["10", "11", "12", "01", "02", "03", "04", "05", "06", "07", "08"]

directorate_excel_tables = {
    "students_registered": {"title": "الطلاب المسجلون", "columns": [], "data": []},
    "teachers_cards": {"title": "بطاقات الاساتذة", "columns": [], "data": []},
    "personal_info": {"title": "المعلومات الشخصية", "columns": [], "data": []},
    "weekly_schedule": {"title": "برنامج اسبوعي مع الاساتذة والمواد", "columns": [], "data": [], "parsed_schedule": {}},
    "executed_hours": {"title": "الساعات المنفذة للاساتذة", "columns": [], "data": [], "monthly_hours": {}}
}

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
            'teacher_absences_log': teacher_absences_log,
            'directorate_excel_tables': directorate_excel_tables
        }
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        shutil.copyfile(DB_FILE, BACKUP_FILE)
    except Exception as e:
        print(f"Error saving database: {e}")

def load_from_disk():
    global teachers_db, grades_db, attendance_db, teacher_classes_map, admin_replies, admin_credentials, classes_students
    global academic_years_db, current_academic_year, students_db, field_sessions, teacher_absences_log, directorate_excel_tables
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
                directorate_excel_tables = data.get('directorate_excel_tables', directorate_excel_tables)
                return True
        except Exception as e:
            print(f"Error loading database file: {e}")
    return False

if not load_from_disk():
    classes_students = {
        "سنة ثالثة عناية تمريضية": ["علي أحمد شمص", "حسن محمد زعيتر", "ميرا شمص", "سيلا شمص"],
        "سنة ثانية معلوماتية": ["محمد حسين أمهز", "سارة يوسف دندش"]
    }
    teachers_db = {
        "teacher_1": {"name": "أحمد خضر", "password": "123", "subject": "تمريض", "device_id": "", "notifications": [], "monthly_hours": {}, "contract_hours": 300},
        "teacher_2": {"name": "علي ناصرالدين", "password": "123", "subject": "معلوماتية", "device_id": "", "notifications": [], "monthly_hours": {}, "contract_hours": 300}
    }
    teacher_classes_map = {"teacher_1": ["سنة ثالثة عناية تمريضية"], "teacher_2": ["سنة ثانية معلوماتية"]}
    save_to_disk()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_weekly_schedule(df):
    parsed_teachers = {}
    current_class = "عام"
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
            <a href="javascript:void(0)" onclick="showSection('viewExecutedHours')">⏱️ الساعات المنفذة شهرياً (نظام المديرية)</a>
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
            <a href="javascript:void(0)" onclick="showSection('uploadDirectorateFilesSec')">⚙️ رفع ملفات المديرية والساعات (Excel)</a>
            <a href="javascript:void(0)" onclick="showSection('deviceBindingSec')">📱 إدارة أجهزة الأساتذة (فك الربط)</a>
            <a href="javascript:void(0)" onclick="showSection('sendNotifSec')">📢 إرسال تعميم / تنبيه</a>
            <a href="javascript:void(0)" onclick="showSection('teacherRepliesSec')">📩 الرسائل والأعذار الواردة</a>
            <a href="javascript:void(0)" onclick="showSection('changePassSec')">🔑 تغيير كلمة السر الإدارية</a>
        </div>
    </div>
</div>

<style>
    .dropdown { position: relative; display: inline-block; }
    .dropbtn { background-color: #1565c0; color: white; padding: 12px 16px; font-size: 14px; border: none; cursor: pointer; font-weight: bold; font-family: inherit; }
    .dropdown:hover .dropbtn { background-color: #0d47a1; }
    .dropdown-content { display: none; position: absolute; background-color: #ffffff; min-width: 250px; box-shadow: 0px 8px 16px rgba(0,0,0,0.2); z-index: 100; border-radius: 0 0 6px 6px; }
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
            if not t_data.get('device_id'):
                t_data['device_id'] = current_device_fingerprint
                save_to_disk()
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
        
        if action == 'upload_directorate_file':
            file_key = request.form.get('file_key')
            file = request.files.get('excel_file')
            
            if file and allowed_file(file.filename) and file_key in directorate_excel_tables:
                try:
                    df = pd.read_excel(file)
                    clean_cols = [str(col).strip().replace("'", "").replace('"', '') for col in df.columns]
                    df.columns = clean_cols
                    columns = clean_cols
                    
                    rows_data = []
                    for _, row in df.iterrows():
                        row_dict = {}
                        for col in columns:
                            val = row[col]
                            row_dict[col] = "" if pd.isna(val) else str(val).strip()
                        rows_data.append(row_dict)
                    
                    title_map = {
                        "students_registered": "الطلاب المسجلون",
                        "teachers_cards": "بطاقات الاساتذة",
                        "personal_info": "المعلومات الشخصية",
                        "weekly_schedule": "برنامج اسبوعي مع الاساتذة والمواد",
                        "executed_hours": "الساعات المنفذة للاساتذة"
                    }
                    
                    table_title = title_map.get(file_key, "ملف المديرية")
                    
                    if file_key == 'executed_hours':
                        monthly_map = {}
                        contract_map = {}
                        
                        for r in rows_data:
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
                                    if m_col in r:
                                        try:
                                            val_num = float(r.get(m_col, 0) or 0)
                                            monthly_map[t_name][m_col] = val_num
                                        except:
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
                        "columns": columns,
                        "data": rows_data,
                        "monthly_hours": directorate_excel_tables.get('executed_hours', {}).get('monthly_hours', {})
                    }
                    
                    if file_key == 'weekly_schedule':
                        parsed = parse_weekly_schedule(df)
                        directorate_excel_tables['weekly_schedule']['parsed_schedule'] = parsed

                    if file_key == 'students_registered':
                        new_classes = {}
                        for r in rows_data:
                            c_name = r.get('الصف', r.get('Class', r.get('التخصص', 'غير مصنف')))
                            s_name = r.get('اسم الطالب الكامل', r.get('اسم الطالب', r.get('الاسم الثلاثي', r.get('الاسم', ''))))
                            if c_name and s_name and str(c_name) != 'nan' and str(s_name) != 'nan':
                                if c_name not in new_classes:
                                    new_classes[c_name] = []
                                if s_name not in new_classes[c_name]:
                                    new_classes[c_name].append(s_name)
                        if new_classes:
                            classes_students.update(new_classes)

                    save_to_disk()
                    msg = f"تم رفع وتحديث ملف ({table_title}) بقراءة مجدولة على طريقة المديرية بنجاح!"
                except Exception as e:
                    msg = f"خطأ في قراءة ملف الإكسل: {e}"
            else:
                msg = "الرجاء اختيار ملف صالح وتحديد نوع جدول المديرية بدقة."

        elif action == 'create_auto_accounts':
            t_cards = directorate_excel_tables.get('teachers_cards', {}).get('data', [])
            count = 0
            for card in t_cards:
                name = card.get('الاسم الثلاثي', card.get('الاسم', '')).strip()
                if name:
                    user_id = f"teacher_{len(teachers_db) + 1}"
                    if not any(t['name'] == name for t in teachers_db.values()):
                        teachers_db[user_id] = {
                            "name": name,
                            "password": "123",
                            "subject": card.get('المادة', 'عام'),
                            "device_id": "",
                            "notifications": [],
                            "monthly_hours": {},
                            "contract_hours": 300
                        }
                        count += 1
            save_to_disk()
            msg = f"تم توليد ({count}) حساب جديد للأساتذة بكلمة سر افتراضية (123)!"

        elif action == 'reset_teacher_device':
            target_user = request.form.get('target_user')
            if target_user in teachers_db:
                teachers_db[target_user]['device_id'] = ''
                save_to_disk()
                msg = f"تم مسح بصمة الجهاز وإعادة تعيين الهوية للأستاذ ({teachers_db[target_user]['name']}) بنجاح!"

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
    
    executed_hours_table_html = ""
    monthly_data_map = directorate_excel_tables.get('executed_hours', {}).get('monthly_hours', {})
    
    if monthly_data_map:
        m_headers = "".join([f"<th>ش {m}</th>" for m in MONTH_COLUMNS])
        m_rows = ""
        for t_name, m_dict in monthly_data_map.items():
            m_tds = "".join([f"<td>{m_dict.get(m, 0):.0f}</td>" for m in MONTH_COLUMNS])
            total_exec = sum(m_dict.values())
            m_rows += f"<tr><td style='text-align:right; font-weight:bold;'>{t_name}</td>{m_tds}<td style='background:#e3f2fd;'><b style='color:#0d47a1;'>{total_exec:.0f}</b></td></tr>"
        
        executed_hours_table_html = f"""
        <div style="overflow-x:auto;">
            <table>
                <tr>
                    <th style="min-width:180px;">الاسم الثلاثي</th>
                    {m_headers}
                    <th>المجموع المنفذ</th>
                </tr>
                {m_rows}
            </table>
        </div>
        """
    else:
        executed_hours_table_html = "<p style='color:#666;'>لم يتم رفع ملف الساعات المنفذة بعد.</p>"

    teachers_rows = ""
    for u, t in teachers_db.items():
        dev_stat = "<span style='color:#2e7d32; font-weight:bold;'>مرتبط برقم هاتف</span>" if t.get('device_id') else "<span style='color:#e65100;'>في انتظار تسجيل الهاتف</span>"
        
        monthly_h = t.get('monthly_hours', {})
        executed_hrs = sum([float(v) for v in monthly_h.values()]) if monthly_h else 0
        contract_hrs = float(t.get('contract_hours', 300))
        remaining_hrs = contract_hrs - executed_hrs
        
        rem_color = "#2e7d32" if remaining_hrs >= 0 else "#c62828"
        
        teachers_rows += f"""
        <tr>
            <td><b>{t['name']}</b></td>
            <td><code style='color:#0d47a1;'>{u}</code></td>
            <td><code>{t['password']}</code></td>
            <td>{dev_stat}</td>
            <td><b>{int(contract_hrs)} ساعة</b></td>
            <td><b style='color:#0d47a1;'>{executed_hrs:.0f} ساعة</b></td>
            <td><b style='color:{rem_color};'>{remaining_hrs:.0f} ساعة</b></td>
        </tr>
        """
    
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

    directorate_htmls = {}
    for k, tinfo in directorate_excel_tables.items():
        cols = tinfo['columns']
        rows = tinfo['data']
        headers_th = "".join([f"<th>{c}</th>" for c in cols]) if cols else "<th>لا توجد أعمدة</th>"
        body_tr = ""
        if rows:
            for r in rows[:100]:
                tds = "".join([f"<td>{r.get(c, '')}</td>" for c in cols])
                body_tr += f"<tr>{tds}</tr>"
        else:
            body_tr = f"<tr><td colspan='{len(cols) or 1}'>لم يتم رفع بيانات لهذا الملف بعد</td></tr>"

        directorate_htmls[k] = f"""
        <div style="background:white; border:1px solid #bbdefb; border-radius:8px; padding:15px; margin-bottom:20px; box-shadow:0 2px 5px rgba(0,0,0,0.05);">
            <h4 style="color:#0d47a1; margin-top:0; border-bottom:2px solid #e3f2fd; padding-bottom:8px;">📂 جدول مديرية التعليم المهني: {tinfo['title']}</h4>
            <div style="overflow-x:auto;">
                <table>
                    <tr>{headers_th}</tr>
                    {body_tr}
                </table>
            </div>
            <small style="color:#555; display:block; margin-top:8px;">إجمالي السجلات: <b>{len(rows)}</b> سجل | الأعمدة المستخرجة: <b>{len(cols)}</b> عمود</small>
        </div>
        """

    teacher_opts = "".join([f"<option value='{u}'>{t['name']} ({u})</option>" for u, t in teachers_db.items()])
    locations_opts = "".join([f"<option value='{loc}'>{loc}</option>" for loc in TRAINING_LOCATIONS.keys()])

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
                <h3 style="color:#0d47a1; margin-top:0;">📋 سجل حضور وغياب الطلاب</h3>
                <table>
                    <tr><th>الصف والتاريخ</th><th>الطلاب المتغيبون</th></tr>
                    {{ attendance_rows | safe if attendance_rows else '<tr><td colspan="2">لا توجد بيانات غياب مسجلة</td></tr>' }}
                </table>
            </div>

            <div id="studentGradesSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">📝 علامات ونتائج الطلاب (من 20)</h3>
                <table>
                    <tr><th>اسم الطالب والمادة</th><th>العلامة</th></tr>
                    {{ grades_rows | safe if grades_rows else '<tr><td colspan="2">لم تُدخل علامات بعد</td></tr>' }}
                </table>
            </div>

            <div id="viewRegisteredStudents" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">📂 الطلاب المسجلون (بيانات المديرية)</h3>
                {{ directorate_htmls['students_registered'] | safe }}
            </div>

            <div id="viewTeachersCards" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">📇 بطاقات الاساتذة والمعلومات الشخصية</h3>
                {{ directorate_htmls['teachers_cards'] | safe }}
                <div style="margin-top:15px;"></div>
                {{ directorate_htmls['personal_info'] | safe }}
            </div>

            <div id="viewWeeklySchedule" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">📅 البرنامج الأسبوعي مع الأساتذة والمواد</h3>
                {{ directorate_htmls['weekly_schedule'] | safe }}
            </div>

            <div id="viewExecutedHours" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">⏱️ الساعات المنفذة شهرياً (عرض جدول المديرية التفصيلي)</h3>
                {{ executed_hours_table_html | safe }}
            </div>

            <div id="teachersListSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">👨‍🏫 سجل الأساتذة وحسابات الدخول وساعات العقود</h3>
                <form method="POST" style="margin-bottom:15px;">
                    <input type="hidden" name="action" value="create_auto_accounts">
                    <button type="submit" style="background:#2e7d32;">⚡ توليد يوزر وباسورد افتراضي لجميع الأساتذة تلقائياً</button>
                </form>
                <table>
                    <tr>
                        <th>اسم الأستاذ</th>
                        <th>اسم المستخدم</th>
                        <th>كلمة المرور</th>
                        <th>حالة الهاتف</th>
                        <th>العقد الإجمالي</th>
                        <th>المنفذ حتى الآن</th>
                        <th>المتبقي من العقد</th>
                    </tr>
                    {{ teachers_rows | safe }}
                </table>
            </div>

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

            <div id="uploadDirectorateFilesSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">⚙️ رفع ملفات المديرية والساعات المنفذة (Excel)</h3>
                <form method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="action" value="upload_directorate_file">
                    
                    <label><b>حدد نوع الملف المراد رفعه:</b></label>
                    <select name="file_key" required style="font-weight:bold; background:#e3f2fd;">
                        <option value="students_registered">📂 1. الطلاب المسجلون</option>
                        <option value="teachers_cards">📇 2. بطاقات الاساتذة</option>
                        <option value="personal_info">👤 3. المعلومات الشخصية</option>
                        <option value="weekly_schedule">📅 4. البرنامج الأسبوعي مع الاساتذة والمواد</option>
                        <option value="executed_hours">⏱️ 5. الساعات المنفذة للاساتذة</option>
                    </select>

                    <label style="margin-top:12px; display:block;"><b>اختر ملف الإكسل (.xlsx أو .xls):</b></label>
                    <input type="file" name="excel_file" accept=".xlsx, .xls" required>
                    
                    <button type="submit" style="margin-top:15px; background:#2e7d32; font-size:15px;">📥 رفع وتحديث الساعات والعقود فوراً</button>
                </form>
            </div>

            <div id="deviceBindingSec" class="card">
                <h3 style="color:#c62828; margin-top:0;">📱 إدارة أجهزة الأساتذة (إعادة تعيين الجهاز بنقرة زر)</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="reset_teacher_device">
                    <label>اختر الأستاذ لإعادة تعيين هاتفه الحسابي:</label>
                    <select name="target_user" required><option value="">-- اختر الأستاذ --</option>{{ teacher_opts | safe }}</select>
                    <button type="submit" style="margin-top:10px; background:#c62828;">🔓 مسح البصمة والسماح بتسجيل هاتف جديد للأستاذ</button>
                </form>
            </div>

            <div id="sendNotifSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">📢 إرسال تعميم إداري</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="send_notification">
                    <select name="target_user" required><option value="all">📢 إرسال للجميع</option>{{ teacher_opts | safe }}</select>
                    <textarea name="notification_text" placeholder="اكتب التعميم..." required style="height:70px;"></textarea>
                    <button type="submit" style="margin-top:10px;">إرسال</button>
                </form>
            </div>

            <div id="teacherRepliesSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">📩 الأعذار والرسائل الواردة</h3>
                {{ replies_html | safe if replies_html else '<p>لا توجد رسائل.</p>' }}
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
        </script>
    </body>
    </html>
    '''
    return render_template_string(admin_template, attendance_rows=attendance_rows, grades_rows=grades_rows, teachers_rows=teachers_rows, field_rows=field_rows, replies_html=replies_html, teacher_opts=teacher_opts, locations_opts=locations_opts, directorate_htmls=directorate_htmls, executed_hours_table_html=executed_hours_table_html, msg=msg)

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
                save_to_disk()
                msg = "تم تغيير كلمة المرور الخاصة بك بنجاح!"

        elif action == 'submit_class_grades':
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

    monthly_hrs = user_data.get('monthly_hours', {})
    contract_hrs = float(user_data.get('contract_hours', 300))
    executed_hrs = sum([float(v) for v in monthly_hrs.values()]) if monthly_hrs else 0
    remaining_hrs = contract_hrs - executed_hrs
    
    hrs_html = ""
    if monthly_hrs:
        m_headers = "".join([f"<th>ش {m}</th>" for m in MONTH_COLUMNS])
        m_tds = "".join([f"<td>{monthly_hrs.get(m, 0):.0f}</td>" for m in MONTH_COLUMNS])
        
        hrs_html = f"""
        <div class="card" style="border-top:4px solid #1565c0; background:#ffffff;">
            <h4 style="color:#0d47a1; margin-top:0; border-bottom:2px solid #e3f2fd; padding-bottom:8px;">📊 ملخص عقد الساعات والمنفذ شهرياً:</h4>
            
            <div style="display:flex; gap:12px; margin-bottom:15px; flex-wrap:wrap;">
                <div style="flex:1; min-width:140px; background:#e3f2fd; padding:12px; border-radius:8px; text-align:center;">
                    <small style="color:#0d47a1; font-weight:bold;">ساعات العقد الإجمالية</small>
                    <div style="font-size:20px; font-weight:bold; color:#0d47a1; margin-top:4px;">{int(contract_hrs)} ساعة</div>
                </div>
                <div style="flex:1; min-width:140px; background:#e8f5e9; padding:12px; border-radius:8px; text-align:center;">
                    <small style="color:#2e7d32; font-weight:bold;">المنفذ حتى الآن</small>
                    <div style="font-size:20px; font-weight:bold; color:#2e7d32; margin-top:4px;">{executed_hrs:.0f} ساعة</div>
                </div>
                <div style="flex:1; min-width:140px; background:#fff3e0; padding:12px; border-radius:8px; text-align:center;">
                    <small style="color:#e65100; font-weight:bold;">المتبقي من العقد</small>
                    <div style="font-size:20px; font-weight:bold; color:#e65100; margin-top:4px;">{remaining_hrs:.0f} ساعة</div>
                </div>
            </div>

            <div style="overflow-x:auto;">
                <table style="width:100%; border-collapse:collapse;">
                    <tr>{m_headers}</tr>
                    <tr>{m_tds}</tr>
                </table>
            </div>
        </div>
        """
    else:
        hrs_html = f"""
        <div class="card" style="border-top:4px solid #1565c0;">
            <h4 style="color:#0d47a1; margin-top:0;">📊 ملخص العقد والساعات:</h4>
            <p style="margin:0; color:#555;">ساعات العقد الإجمالية المسجلة: <b>{int(contract_hrs)} ساعة</b> (في انتظار رفع ملف الساعات المنفذة للمديرية).</p>
        </div>
        """

    parsed_schedule = directorate_excel_tables.get('weekly_schedule', {}).get('parsed_schedule', {})
    teacher_schedule_items = parsed_schedule.get(t_name, [])
    schedule_html = ""
    if teacher_schedule_items:
        schedule_rows = "".join([f"<tr><td><b>{item['day']}</b></td><td>{item['period']}</td><td>{item['class']}</td><td><b style='color:#0d47a1;'>{item['subject']}</b></td></tr>" for item in teacher_schedule_items])
        schedule_html = f"""
        <div class="card" style="border-top:4px solid #2e7d32;">
            <h4 style="color:#2e7d32; margin-top:0;">📅 برنامجي الأسبوعي (المستخرج من جدول المديرية):</h4>
            <table>
                <tr><th>اليوم</th><th>الحصة</th><th>الصف والمستوى</th><th>المادة</th></tr>
                {schedule_rows}
            </table>
        </div>
        """

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
            .student-row { display: flex; justify-content: space-between; align-items: center; padding: 8px; border-bottom: 1px solid #eee; background: #fafafa; margin-top: 5px; border-radius: 4px; }
        </style>
    </head>
    <body>
        <div style="background:#0d47a1; color:white; padding:12px 20px; display:flex; justify-content:space-between; align-items:center;">
            <div><h3 style="margin:0;">معهد الهرمل الفني</h3><small>الأستاذ: {{ t_name }}</small></div>
            <a href="/logout" style="color:#ffcdd2; background:#c62828; padding:6px 12px; border-radius:4px; text-decoration:none; font-size:12px;">خروج</a>
        </div>

        <div style="padding:15px;">
            {% if msg %}<div style="background:#e8f5e9; color:#2e7d32; padding:10px; border-radius:6px; margin-bottom:10px; font-weight:bold;">{{ msg }}</div>{% endif %}

            {{ hrs_html | safe }}

            {{ schedule_html | safe }}

            {{ field_html | safe }}

            <div class="card">
                <h4 style="color:#0d47a1; margin-top:0;">🔑 تغيير كلمة المرور الخاصة بي:</h4>
                <form method="POST">
                    <input type="hidden" name="action" value="change_my_password">
                    <input type="password" name="new_password" placeholder="أدخل كلمة المرور الجديدة..." required>
                    <button type="submit" style="background:#1565c0; margin-top:8px;">تحديث كلمة المرور</button>
                </form>
            </div>

            <div class="card">
                <h4 style="color:#0d47a1; margin-top:0;">📢 التعاميم الواردة:</h4>
                {{ notifs | safe if notifs else '<p style="color:#666;">لا توجد تعاميم جديدة.</p>' }}
            </div>

            <div class="card">
                <h4 style="color:#0d47a1; margin-top:0;">📋 توثيق حضور وغياب الطلاب اليومي:</h4>
                <form method="POST">
                    <input type="hidden" name="action" value="submit_class_attendance">
                    <label>اختر الصف:</label>
                    <select name="class_name" id="attClass" onchange="loadStudentsForAtt()" required><option value="">-- اختر الصف --</option>{{ class_opts | safe }}</select>
                    <div id="attContainer" style="margin-top:10px;"></div>
                    <button type="submit" id="attBtn" style="display:none; background:#2e7d32; margin-top:10px;">حفظ الحضور والغياب</button>
                </form>
            </div>

            <div class="card">
                <h4 style="color:#0d47a1; margin-top:0;">📝 إدخال ورصد علامات الطلاب (من 20):</h4>
                <form method="POST">
                    <input type="hidden" name="action" value="submit_class_grades">
                    <label>اختر الصف:</label>
                    <select name="class_name" id="gradeClass" onchange="loadStudentsForGrades()" required><option value="">-- اختر الصف --</option>{{ class_opts | safe }}</select>
                    <div id="gradeContainer" style="margin-top:10px;"></div>
                    <button type="submit" id="gradeBtn" style="display:none; margin-top:10px;">حفظ ورصد العلامات</button>
                </form>
            </div>

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
                    let html = '<p style="font-size:13.5px; color:#0d47a1; font-weight:bold;">الكل حاضر افتراضياً ✅ (أزل الصح عن المتغيب):</p>';
                    data.students.forEach(st => {
                        html += `<div class="student-row"><span>${st}</span><label style="color:#2e7d32; font-weight:bold; cursor:pointer;"><input type="checkbox" name="attendance_check" value="${st}" checked style="width:auto; transform:scale(1.2);"> حاضر</label></div>`;
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
                        html += `<div class="student-row"><span style="flex:1; font-weight:bold;">${st}</span><input type="number" step="0.5" min="0" max="20" name="grade_${st}" placeholder="العلامة /20" style="width:110px; margin-top:0;" required></div>`;
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
    """
    return render_template_string(teacher_template, t_name=t_name, msg=msg, class_opts=class_opts, notifs=notifs, hrs_html=hrs_html, schedule_html=schedule_html, field_html=field_html)

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

@app.uploads('/uploads/<filename>')
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)