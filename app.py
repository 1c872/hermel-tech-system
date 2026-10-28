import os
import json
import io
import math
import shutil
import re
import pandas as pd
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, session, send_from_directory, jsonify

app = Flask(__name__)
app.secret_key = 'hermel_tech_school_shams_secret_key_2026'

DB_FILE = os.path.join('/tmp', 'database.json')
BACKUP_FILE = os.path.join('/tmp', 'database_backup.json')

UPLOAD_FOLDER = os.path.join('/tmp', 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'xlsx', 'xls'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

teachers_db = {}
grades_db = {}            
attendance_db = {}        
teacher_classes_map = {}  
classes_students = {}
admin_replies = []
admin_credentials = {'username': 'admin', 'password': '123456'}

directorate_excel_tables = {
    "students_registered": {"title": "الطلاب المسجلون", "columns": [], "data": []},
    "teachers_cards": {"title": "بطاقات الاساتذة", "columns": [], "data": []},
    "personal_info": {"title": "المعلومات الشخصية", "columns": [], "data": []},
    "weekly_schedule": {"title": "برنامج اسبوعي مع الاساتذة والمواد", "columns": [], "data": [], "parsed_schedule": {}},
    "executed_hours": {"title": "الساعات المنفذة للاساتذة", "columns": [], "data": [], "monthly_hours": {}},
    "fingerprint_ids": {"title": "أرقام بصمات الأساتذة والموظفين (IDs)", "columns": [], "data": []}
}

MONTH_COLUMNS = ["10", "11", "12", "01", "02", "03", "04", "05", "06", "07", "08"]

def clean_column_name(col):
    col_str = str(col).strip()
    col_str = col_str.replace("&#x27;", "").replace("'", "").replace('"', '')
    col_str = re.sub(r'^ش\s*', '', col_str)
    if len(col_str) == 1 and col_str.isdigit():
        col_str = '0' + col_str
    return col_str

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
            'directorate_excel_tables': directorate_excel_tables
        }
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if os.path.exists(DB_FILE):
            shutil.copyfile(DB_FILE, BACKUP_FILE)
    except Exception as e:
        print(f"Error saving database: {e}")

def load_from_disk():
    global teachers_db, grades_db, attendance_db, teacher_classes_map, admin_replies, admin_credentials, classes_students, directorate_excel_tables
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
        "teacher_1": {"name": "ايمان جانبيه", "password": "123", "subject": "تمريض", "device_id": "", "notifications": [], "monthly_hours": {}, "contract_hours": 300},
        "teacher_2": {"name": "ايلي العرجا", "password": "123", "subject": "معلوماتية", "device_id": "", "notifications": [], "monthly_hours": {}, "contract_hours": 300}
    }
    save_to_disk()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_schedule_excel(xls_file):
    """دالة ذكية لقراءة البرنامج الأسبوعي مع ربط الصفوف بالأساتذة والمواد بدقة"""
    parsed_teachers = {}
    xls = pd.ExcelFile(xls_file)
    for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet_name)
        # البحث في صفوف الجدول عن المواد والأساتذة أسفلها
        current_class = "عام"
        for i in range(len(df)):
            row = df.iloc[i]
            # التحقق إذا كانت السطر يحتوي على جدول حصص
            # عادة سطر المواد يليه سطر الأساتذة في الجدول الفعلي للمعهد
            if i + 1 < len(df):
                next_row = df.iloc[i+1]
                # فحص الأعمدة من 3 فصاعداً (أعمدة الحصص)
                for col_idx in range(3, len(row)):
                    subject = row.iloc[col_idx]
                    teacher = next_row.iloc[col_idx]
                    if pd.notna(subject) and pd.notna(teacher):
                        sub_str = str(subject).strip()
                        tch_str = str(teacher).strip()
                        if tch_str and tch_str != 'nan' and sub_str and sub_str != 'nan':
                            # يمكن أن يكون هناك أكثر من أستاذ مفصولين بفاصل أو في نفس الخلية
                            teachers_list = [t.strip() for t in re.split(r'[,،/]', tch_str) if t.strip()]
                            for t_name in teachers_list:
                                if t_name not in parsed_teachers:
                                    parsed_teachers[t_name] = []
                                parsed_teachers[t_name].append({
                                    "day": sheet_name,
                                    "period": f"حصة {col_idx-2}",
                                    "subject": sub_str
                                })
    return parsed_teachers

HEADER_VTE_HTML = '''
<div style="background:#0d47a1; color:white; padding:12px 20px; display:flex; justify-content:space-between; align-items:center; border-bottom:3px solid #1565c0;">
    <div style="display:flex; align-items:center; gap:12px;">
        <img src="https://cdn-icons-png.flaticon.com/512/3135/3135755.png" width="38" height="38" style="background:white; border-radius:50%; padding:2px;">
        <div>
            <div style="font-weight:bold; font-size:18px;">الجمهورية اللبنانية 🌲 - معهد الهرمل الفني</div>
            <div style="font-size:12px; color:#bbdefb;">نظام الإدارة المدرسية - إشراف وإدارة: مدير المعهد</div>
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
        <button class="dropbtn">الأساتذة والساعات ▾</button>
        <div class="dropdown-content">
            <a href="javascript:void(0)" onclick="showSection('teachersListSec')">👨‍🏫 سجل الأساتذة وعقود الساعات</a>
            <a href="javascript:void(0)" onclick="showSection('viewFingerprintIds')">🆔 أقسام البصمة (ملاك، متعاقدين، خدمات)</a>
            <a href="javascript:void(0)" onclick="showSection('viewWeeklySchedule')">📅 البرنامج الأسبوعي والأساتذة والمواد</a>
            <a href="javascript:void(0)" onclick="showSection('viewExecutedHours')">⏱️ الساعات المنفذة شهرياً (نظام المديرية)</a>
        </div>
    </div>

    <div class="dropdown">
        <button class="dropbtn">الإدارة والإعدادات ▾</button>
        <div class="dropdown-content">
            <a href="javascript:void(0)" onclick="showSection('uploadDirectorateFilesSec')">⚙️ رفع ملفات المديرية والبصمة والساعات (Excel)</a>
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
        <title>الجمهورية اللبنانية 🌲 - معهد الهرمل الفني</title>
        <style>
            body { font-family: system-ui, sans-serif; background: #e3f2fd; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; flex-direction: column; }
            .card { background: white; padding: 35px 25px; border-radius: 12px; width: 90%; max-width: 380px; text-align: center; box-shadow: 0 8px 20px rgba(13,71,161,0.15); border-top: 5px solid #0d47a1; }
            h2 { color: #0d47a1; margin-bottom: 5px; font-size: 20px; }
            input { width: 100%; padding: 12px; margin: 8px 0; border: 1.5px solid #bbdefb; border-radius: 6px; box-sizing: border-box; text-align: right; font-size: 14px; }
            button { width: 100%; padding: 12px; background: #0d47a1; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; margin-top: 10px; font-size: 15px; }
        </style>
    </head>
    <body>
        <div class="card">
            <img src="https://cdn-icons-png.flaticon.com/512/3135/3135755.png" width="60" style="margin-bottom:5px;">
            <div style="font-size:13px; color:#555; font-weight:bold;">الجمهورية اللبنانية 🌲</div>
            <h2>معهد الهرمل الفني</h2>
            <small style="color:#0d47a1; display:block; margin-bottom:15px;">نظام الإدارة المدرسية</small>
            <form method="POST">
                <input type="text" name="username" placeholder="اسم المستخدم" required>
                <input type="password" name="password" placeholder="كلمة المرور" required>
                <button type="submit">دخول النظام</button>
            </form>
            <div style="color:#d32f2f; margin-top:12px; font-weight:bold; font-size:13px;">{{ error }}</div>
        </div>
        <div style="margin-top: 20px; color: #5c6bc0; font-size: 12px; text-align:center;">إشراف وتصميم: مدير المعهد (محمد حسين شمص)</div>
    </body>
    </html>
'''

@app.route('/api/get_students/<path:class_name>')
def get_students(class_name):
    students = classes_students.get(class_name, [])
    return jsonify({'students': students})

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
                    col_mapping = {}
                    clean_columns = []
                    for original_col in df.columns:
                        c_cleaned = clean_column_name(original_col)
                        col_mapping[original_col] = c_cleaned
                        clean_columns.append(c_cleaned)
                    
                    df_renamed = df.rename(columns=col_mapping)
                    rows_data = []
                    for _, row in df_renamed.iterrows():
                        row_dict = {}
                        for col in df_renamed.columns:
                            val = row[col]
                            row_dict[col] = "" if pd.isna(val) else str(val).strip()
                        rows_data.append(row_dict)
                    
                    title_map = {
                        "students_registered": "الطلاب المسجلون",
                        "teachers_cards": "بطاقات الاساتذة",
                        "personal_info": "المعلومات الشخصية",
                        "weekly_schedule": "برنامج اسبوعي مع الاساتذة والمواد",
                        "executed_hours": "الساعات المنفذة للاساتذة",
                        "fingerprint_ids": "أرقام بصمات الأساتذة والموظفين (البصمة ID)"
                    }
                    
                    table_title = title_map.get(file_key, "ملف المديرية")
                    
                    directorate_excel_tables[file_key] = {
                        "title": table_title,
                        "columns": clean_columns,
                        "data": rows_data
                    }
                    
                    if file_key == 'weekly_schedule':
                        file.seek(0)
                        parsed = parse_schedule_excel(file)
                        directorate_excel_tables['weekly_schedule']['parsed_schedule'] = parsed

                    save_to_disk()
                    msg = f"تم رفع وتحديث ملف ({table_title}) بنجاح!"
                except Exception as e:
                    msg = f"خطأ في قراءة ملف الإكسل: {e}"
            else:
                msg = "الرجاء اختيار ملف صالح وتحديد نوع الجدول بدقة."

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

    attendance_rows = "".join([f"<tr><td><b>{k}</b></td><td style='color:#c62828;'>متغيبون: {v.get('absent', [])}</td></tr>" for k, v in attendance_db.items()])
    grades_rows = "".join([f"<tr><td><b>{k}</b></td><td><b style='color:#0d47a1;'>{v} / 20</b></td></tr>" for k, v in grades_db.items()])
    
    teachers_rows = ""
    for u, t in teachers_db.items():
        dev_stat = "<span style='color:#2e7d32; font-weight:bold;'>مرتبط برقم هاتف</span>" if t.get('device_id') else "<span style='color:#e65100;'>في انتظار تسجيل الهاتف</span>"
        teachers_rows += f"""
        <tr>
            <td><b>{t['name']}</b></td>
            <td><code style='color:#0d47a1;'>{u}</code></td>
            <td><code>{t['password']}</code></td>
            <td>{dev_stat}</td>
        </tr>
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
            <h4 style="color:#0d47a1; margin-top:0; border-bottom:2px solid #e3f2fd; padding-bottom:8px;">📂 {tinfo['title']}</h4>
            <div style="overflow-x:auto;">
                <table>
                    <tr>{headers_th}</tr>
                    {body_tr}
                </table>
            </div>
            <small style="color:#555; display:block; margin-top:8px;">إجمالي السجلات: <b>{len(rows)}</b> سجل</small>
        </div>
        """

    teacher_opts = "".join([f"<option value='{u}'>{t['name']} ({u})</option>" for u, t in teachers_db.items()])

    admin_template = '''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>الجمهورية اللبنانية 🌲 - لوحة الإدارة</title>
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
                {{ directorate_htmls['students_registered'] | safe }}
            </div>

            <div id="viewTeachersCards" class="card">
                {{ directorate_htmls['teachers_cards'] | safe }}
            </div>

            <div id="viewFingerprintIds" class="card">
                {{ directorate_htmls['fingerprint_ids'] | safe }}
            </div>

            <div id="viewWeeklySchedule" class="card">
                {{ directorate_htmls['weekly_schedule'] | safe }}
            </div>

            <div id="viewExecutedHours" class="card">
                {{ directorate_htmls['executed_hours'] | safe }}
            </div>

            <div id="teachersListSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">👨‍🏫 سجل الأساتذة وحسابات الدخول</h3>
                <form method="POST" style="margin-bottom:15px;">
                    <input type="hidden" name="action" value="create_auto_accounts">
                    <button type="submit" style="background:#2e7d32;">⚡ توليد يوزر وباسورد افتراضي لجميع الأساتذة تلقائياً</button>
                </form>
                <table>
                    <tr><th>اسم الأستاذ</th><th>اسم المستخدم</th><th>كلمة المرور</th><th>حالة الهاتف</th></tr>
                    {{ teachers_rows | safe }}
                </table>
            </div>

            <div id="uploadDirectorateFilesSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">⚙️ رفع ملفات المديرية (Excel)</h3>
                <form method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="action" value="upload_directorate_file">
                    <label><b>اختر نوع الملف:</b></label>
                    <select name="file_key" required style="font-weight:bold; background:#e3f2fd;">
                        <option value="weekly_schedule">📅 البرنامج الأسبوعي للمعهد والمواد</option>
                        <option value="fingerprint_ids">🆔 ملف البصمة ID</option>
                        <option value="students_registered">📂 الطلاب المسجلون</option>
                        <option value="teachers_cards">📇 بطاقات الاساتذة</option>
                        <option value="executed_hours">⏱️ الساعات المنفذة للاساتذة</option>
                    </select>
                    <label style="margin-top:12px; display:block;"><b>اختر ملف الإكسل:</b></label>
                    <input type="file" name="excel_file" accept=".xlsx, .xls" required>
                    <button type="submit" style="margin-top:15px; background:#2e7d32;">📥 رفع وتحديث الملف</button>
                </form>
            </div>

            <div id="deviceBindingSec" class="card">
                <h3 style="color:#c62828; margin-top:0;">📱 إدارة أجهزة الأساتذة (فك الربط)</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="reset_teacher_device">
                    <label>اختر الأستاذ:</label>
                    <select name="target_user" required><option value="">-- اختر الأستاذ --</option>{{ teacher_opts | safe }}</select>
                    <button type="submit" style="margin-top:10px; background:#c62828;">🔓 مسح البصمة والسماح بتسجيل هاتف جديد</button>
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
    return render_template_string(admin_template, attendance_rows=attendance_rows, grades_rows=grades_rows, teachers_rows=teachers_rows, teacher_opts=teacher_opts, directorate_htmls=directorate_htmls, msg=msg)

@app.route('/teacher', methods=['GET', 'POST'])
def teacher_dashboard():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    
    username = session.get('username')
    user_data = teachers_db.get(username, {})
    t_name = user_data.get('name', '').strip()
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

    my_classes = list(classes_students.keys())
    class_opts = "".join([f'<option value="{c}">{c}</option>' for c in my_classes])
    notifs = "".join([f"<div style='background:#e3f2fd; padding:8px; margin-bottom:5px; border-radius:4px; font-weight:bold;'>🔔 {n}</div>" for n in user_data.get('notifications', [])])

    # استخراج برنامج الأستاذ بأسلوب راقي ومنظم
    parsed_schedule = directorate_excel_tables.get('weekly_schedule', {}).get('parsed_schedule', {})
    teacher_schedule_items = parsed_schedule.get(t_name, [])
    
    schedule_html = ""
    if teacher_schedule_items:
        sched_rows = "".join([f"<tr><td><b>{item['day']}</b></td><td>{item['period']}</td><td><b style='color:#0d47a1;'>{item['subject']}</b></td></tr>" for item in teacher_schedule_items])
        schedule_html = f"""
        <div class="card" style="border-top:4px solid #2e7d32; background:white; padding:18px; border-radius:8px; margin-top:15px; box-shadow:0 2px 6px rgba(0,0,0,0.05);">
            <h4 style="color:#2e7d32; margin-top:0;">📅 برنامجي الأسبوعي المعتمد:</h4>
            <table>
                <tr><th>اليوم</th><th>الحصة</th><th>المادة الدراسية</th></tr>
                {sched_rows}
            </table>
        </div>
        """
    else:
        schedule_html = """
        <div class="card" style="border-top:4px solid #e65100; background:white; padding:18px; border-radius:8px; margin-top:15px;">
            <h4 style="color:#e65100; margin-top:0;">📅 البرنامج الأسبوعي:</h4>
            <p style="color:#666; margin:0;">لم يتم رفع البرنامج الأسبوعي أو لم يتم العثور على حصص مسجلة باسمك بعد. يرجى من الإدارة رفع ملف البرنامج.</p>
        </div>
        """

    teacher_template = """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>الجمهورية اللبنانية 🌲 - واجهة الأستاذ</title>
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
            <div><h3 style="margin:0;">الجمهورية اللبنانية 🌲 - معهد الهرمل الفني</h3><small>الأستاذ: {{ t_name }}</small></div>
            <a href="/logout" style="color:#ffcdd2; background:#c62828; padding:6px 12px; border-radius:4px; text-decoration:none; font-size:12px;">خروج</a>
        </div>

        <div style="padding:15px;">
            {% if msg %}<div style="background:#e8f5e9; color:#2e7d32; padding:10px; border-radius:6px; margin-bottom:10px; font-weight:bold;">{{ msg }}</div>{% endif %}

            {{ schedule_html | safe }}

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
        </script>
    </body>
    </html>
    """
    return render_template_string(teacher_template, t_name=t_name, msg=msg, class_opts=class_opts, notifs=notifs, schedule_html=schedule_html)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

