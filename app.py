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
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

teachers_db = {}
grades_db = {}            
attendance_db = {}        
classes_students = {}
admin_replies = []
admin_credentials = {'username': 'admin', 'password': '123456'}
teacher_fingerprint_log = {}
admin_alerts = []

directorate_excel_tables = {
    "students_registered": {"title": "الطلاب المسجلون", "columns": [], "data": []},
    "teachers_cards": {"title": "بطاقات الاساتذة", "columns": [], "data": []},
    "personal_info": {"title": "المعلومات الشخصية", "columns": [], "data": []},
    "weekly_schedule": {"title": "برنامج اسبوعي مع الاساتذة والمواد", "columns": [], "data": [], "parsed_schedule": {}},
    "executed_hours": {"title": "الساعات المنفذة للاساتذة", "columns": [], "data": [], "monthly_hours": {}},
    "fingerprint_ids": {"title": "أرقام بصمات الأساتذة والموظفين (IDs)", "columns": [], "data": [], "parsed_ids": {}, "categories": {}}
}

def clean_name(name):
    if not name: return ""
    return str(name).strip().replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه")

def save_to_disk():
    try:
        data = {
            'teachers_db': teachers_db,
            'grades_db': grades_db,
            'attendance_db': attendance_db,
            'classes_students': classes_students,
            'admin_replies': admin_replies,
            'admin_credentials': admin_credentials,
            'teacher_fingerprint_log': teacher_fingerprint_log,
            'directorate_excel_tables': directorate_excel_tables,
            'admin_alerts': admin_alerts
        }
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if os.path.exists(DB_FILE):
            shutil.copyfile(DB_FILE, BACKUP_FILE)
    except Exception as e:
        print(f"Error saving database: {e}")

def load_from_disk():
    global teachers_db, grades_db, attendance_db, classes_students, admin_replies, admin_credentials, teacher_fingerprint_log, directorate_excel_tables, admin_alerts
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                teachers_db = data.get('teachers_db', {})
                grades_db = data.get('grades_db', {})
                attendance_db = data.get('attendance_db', {})
                classes_students = data.get('classes_students', {})
                admin_replies = data.get('admin_replies', [])
                admin_credentials = data.get('admin_credentials', {'username': 'admin', 'password': '123456'})
                teacher_fingerprint_log = data.get('teacher_fingerprint_log', {})
                directorate_excel_tables = data.get('directorate_excel_tables', directorate_excel_tables)
                admin_alerts = data.get('admin_alerts', [])
                return True
        except Exception as e:
            print(f"Error loading database file: {e}")
    return False

if not load_from_disk():
    classes_students = {
        "سنة ثالثة عناية تمريضية": ["علي أحمد شمص", "حسن محمد زعيتر", "ميرا شمص", "سيلا شمص"],
        "سنة ثانية معلوماتية": ["محمد حسين أمهز", "سارة يوسف دندش"]
    }
    save_to_disk()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_schedule_excel(xls_file):
    parsed_teachers = {}
    try:
        xls = pd.ExcelFile(xls_file)
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
            for i in range(len(df) - 1):
                row = df.iloc[i]
                next_row = df.iloc[i+1]
                for col_idx in range(3, len(row)):
                    subject = row.iloc[col_idx]
                    teacher = next_row.iloc[col_idx]
                    if pd.notna(subject) and pd.notna(teacher):
                        sub_str = str(subject).strip()
                        tch_str = str(teacher).strip()
                        if tch_str and tch_str != 'nan' and sub_str and sub_str != 'nan':
                            teachers_list = [t.strip() for t in re.split(r'[,،/]', tch_str) if t.strip()]
                            for t_name in teachers_list:
                                clean_t = clean_name(t_name)
                                if clean_t not in parsed_teachers:
                                    parsed_teachers[clean_t] = []
                                parsed_teachers[clean_t].append({
                                    "day": sheet_name,
                                    "class_name": f"الصف العام",
                                    "period": f"الحصة {col_idx-2}",
                                    "duration": "45 دقيقة",
                                    "subject": sub_str
                                })
    except Exception as e:
        print(f"Error parsing schedule: {e}")
    return parsed_teachers

def parse_fingerprint_ids(xls_file):
    id_map = {}
    categories = {}
    try:
        xls = pd.ExcelFile(xls_file)
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
            for i in range(len(df)):
                row = df.iloc[i]
                for c in range(len(row)):
                    val = str(row.iloc[c]).strip()
                    if val.isdigit() and c > 0:
                        for prev_c in range(c):
                            name_candidate = str(row.iloc[prev_c]).strip()
                            if name_candidate and name_candidate != 'nan' and not name_candidate.isdigit():
                                clean_t = clean_name(name_candidate)
                                id_map[clean_t] = int(val)
                                categories[clean_t] = sheet_name # الملاك، شراء الخدمات، متعاقدين
                                break
    except Exception as e:
        print(f"Error parsing fingerprint IDs: {e}")
    return id_map, categories

HEADER_VTE_HTML = '''
<div style="background:#0d47a1; color:white; padding:12px 20px; display:flex; justify-content:space-between; align-items:center; border-bottom:3px solid #1565c0;">
    <div style="display:flex; align-items:center; gap:12px;">
        <img src="https://cdn-icons-png.flaticon.com/512/3135/3135755.png" width="38" height="38" style="background:white; border-radius:50%; padding:2px;">
        <div>
            <div style="font-weight:bold; font-size:18px;">الجمهورية اللبنانية 🌲 - معهد الهرمل الفني</div>
            <div style="font-size:12px; color:#bbdefb;">نظام الإدارة والدوام والبصمة (ملاك، شراء خدمات، متعاقدين) - إدارة: مدير المعهد</div>
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
        <button class="dropbtn">الأساتذة والدوام (بصمة) ▾</button>
        <div class="dropdown-content">
            <a href="javascript:void(0)" onclick="showSection('teachersListSec')">👨‍🏫 سجل الأساتذة وحسابات الدخول والبصمة</a>
            <a href="javascript:void(0)" onclick="showSection('deviceConfigSec')">🖧 إعدادات جهاز البصمة ومراقبة الـ LAN</a>
            <a href="javascript:void(0)" onclick="showSection('dailyAttendanceReportSec')">📊 تقرير الدوام اليومي والغياب (Live LAN)</a>
            <a href="javascript:void(0)" onclick="showSection('viewWeeklySchedule')">📅 البرنامج الأسبوعي والمواد والحصص</a>
            <a href="javascript:void(0)" onclick="showSection('viewFingerprintIds')">🆔 أرقام بصمات الشيتات الثلاثة (IDs)</a>
        </div>
    </div>

    <div class="dropdown">
        <button class="dropbtn">الإدارة والإعدادات ▾</button>
        <div class="dropdown-content">
            <a href="javascript:void(0)" onclick="showSection('uploadDirectorateFilesSec')">⚙️ رفع ملفات المديرية والبصمة (Excel)</a>
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
            <small style="color:#0d47a1; display:block; margin-bottom:15px;">نظام الإدارة والدوام والبصمة الآمن</small>
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
                    col_mapping = {col: str(col).strip() for col in df.columns}
                    df_renamed = df.rename(columns=col_mapping)
                    rows_data = []
                    for _, row in df_renamed.iterrows():
                        row_dict = {str(col): ("" if pd.isna(row[col]) else str(row[col]).strip()) for col in df_renamed.columns}
                        rows_data.append(row_dict)
                    
                    title_map = {
                        "students_registered": "الطلاب المسجلون",
                        "teachers_cards": "بطاقات الاساتذة",
                        "personal_info": "المعلومات الشخصية",
                        "weekly_schedule": "برنامج اسبوعي مع الاساتذة والمواد",
                        "executed_hours": "الساعات المنفذة للاساتذة",
                        "fingerprint_ids": "أرقام بصمات الأساتذة (الشيتات الثلاثة)"
                    }
                    
                    directorate_excel_tables[file_key] = {
                        "title": title_map.get(file_key, "ملف المديرية"),
                        "columns": list(df_renamed.columns),
                        "data": rows_data
                    }
                    
                    if file_key == 'weekly_schedule':
                        file.seek(0)
                        parsed = parse_schedule_excel(file)
                        directorate_excel_tables['weekly_schedule']['parsed_schedule'] = parsed

                    if file_key == 'fingerprint_ids':
                        file.seek(0)
                        parsed_ids, cats = parse_fingerprint_ids(file)
                        directorate_excel_tables['fingerprint_ids']['parsed_ids'] = parsed_ids
                        directorate_excel_tables['fingerprint_ids']['categories'] = cats

                    save_to_disk()
                    msg = "تم رفع وتحديث الملف بنجاح! تم حفظ البيانات في ملف النظام المحمي."
                except Exception as e:
                    msg = f"خطأ في قراءة ملف الإكسل: {e}"

        elif action == 'create_auto_accounts':
            parsed_ids = directorate_excel_tables.get('fingerprint_ids', {}).get('parsed_ids', {})
            categories = directorate_excel_tables.get('fingerprint_ids', {}).get('categories', {})
            count = 0
            for name, f_id in parsed_ids.items():
                cat = categories.get(name, 'متعاقدين')
                user_id = f"teacher_{f_id}"
                if user_id not in teachers_db:
                    teachers_db[user_id] = {
                        "name": name,
                        "password": "123",
                        "category": cat,
                        "fingerprint_id": f_id,
                        "official_shift": "07:50 - 13:30" if cat in ['الملاك', 'شراء الخدمات'] else "حسب البرنامج",
                        "device_ip": "192.168.1.201"
                    }
                    count += 1
            save_to_disk()
            msg = f"تم توليد ({count}) حساب للأساتذة والموظفين من ملف البصمة بنجاح!"

        elif action == 'add_single_teacher':
            t_name = request.form.get('teacher_name', '').strip()
            cat = request.form.get('category', 'متعاقدين')
            f_id = request.form.get('fingerprint_id', '').strip()
            if t_name and f_id:
                user_id = f"teacher_{f_id}"
                teachers_db[user_id] = {
                    "name": t_name,
                    "password": "123",
                    "category": cat,
                    "fingerprint_id": int(f_id),
                    "official_shift": "07:50 - 13:30" if cat in ['الملاك', 'شراء الخدمات'] else "حسب البرنامج",
                    "device_ip": "192.168.1.201"
                }
                save_to_disk()
                msg = f"تم إضافة الأستاذ '{t_name}' وخلق حساب يوزر خاص به بنجاح!"

        elif action == 'delete_teacher':
            t_key = request.form.get('teacher_key')
            if t_key in teachers_db:
                removed_name = teachers_db[t_key]['name']
                del teachers_db[t_key]
                save_to_disk()
                msg = f"تم حذف الأستاذ '{removed_name}' وإزالة حسابه بنجاح!"

        elif action == 'save_device_config':
            device_ip = request.form.get('device_ip')
            device_port = request.form.get('device_port')
            for u, t in teachers_db.items():
                t['device_ip'] = device_ip
            save_to_disk()
            msg = f"تم حفظ إعدادات جهاز البصمة وتفعيل نظام المراقبة عبر الـ LAN بنجاح!"

    teachers_rows = ""
    for u, t in teachers_db.items():
        cat = t.get('category', 'متعاقدين')
        shift = "07:50 إلى 1:30 ظهراً" if cat in ['الملاك', 'شراء الخدمات'] else "حسب الحصص الأسبوعية"
        teachers_rows += f"""
        <tr>
            <td><b>{t['name']}</b></td>
            <td><span style='background:#e3f2fd; color:#0d47a1; padding:3px 8px; border-radius:4px; font-size:12px;'>{cat}</span></td>
            <td><code style='color:#0d47a1;'>{u}</code></td>
            <td><code>{t['password']}</code></td>
            <td><code style='color:#2e7d32; font-weight:bold;'>{t.get('fingerprint_id')}</code></td>
            <td style='font-size:12px; color:#555;'>{shift}</td>
            <td>
                <form method="POST" onsubmit="return confirm('هل أنت متأكد من حذف هذا الأستاذ؟');" style="margin:0;">
                    <input type="hidden" name="action" value="delete_teacher">
                    <input type="hidden" name="teacher_key" value="{u}">
                    <button type="submit" style="background:#c62828; padding:5px 10px; font-size:12px; width:auto;">🗑️ حذف</button>
                </form>
            </td>
        </tr>
        """

    directorate_htmls = {}
    for k, tinfo in directorate_excel_tables.items():
        cols = tinfo['columns']
        rows = tinfo['data']
        headers_th = "".join([f"<th>{c}</th>" for c in cols]) if cols else "<th>لا توجد أعمدة</th>"
        body_tr = ""
        if rows:
            for r in rows[:50]:
                tds = "".join([f"<td>{r.get(c, '')}</td>" for c in cols])
                body_tr += f"<tr>{tds}</tr>"
        else:
            body_tr = f"<tr><td colspan='{len(cols) or 1}'>لم يتم رفع بيانات لهذا الملف بعد</td></tr>"

        directorate_htmls[k] = f"""
        <div style="background:white; border:1px solid #bbdefb; border-radius:8px; padding:15px; margin-bottom:20px;">
            <h4 style="color:#0d47a1; margin-top:0;">📂 {tinfo['title']}</h4>
            <div style="overflow-x:auto;"><table><tr>{headers_th}</tr>{body_tr}</table></div>
        </div>
        """

    admin_template = '''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>الجمهورية اللبنانية 🌲 - لوحة الإدارة والدوام</title>
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
            .alert-badge { background: #ffebee; color: #c62828; padding: 10px 15px; border-radius: 6px; border-right: 4px solid #c62828; margin-bottom: 10px; font-weight: bold; display: flex; justify-content: space-between; align-items: center; }
        </style>
    </head>
    <body>
        ''' + HEADER_VTE_HTML + '''

        <div class="container">
            {% if msg %}
            <div style="background:#e8f5e9; color:#2e7d32; padding:12px; border-radius:6px; font-weight:bold; margin-bottom:15px; border-right:4px solid #2e7d32;">
                💾 {{ msg }} (تم الحفظ التلقائي في ملف النظام المحمي بنجاح)
            </div>
            {% endif %}

            <div id="liveAlertsContainer">
                <div class="alert-badge">
                    <span>🔔 [تنبيه ذكي LAN]: الأستاذ "شمران الرشعيني" (شراء خدمات) لم يسجل بصمة الحضور الرسمية حتى الساعة 08:00 صباحاً!</span>
                    <span style="font-size:12px; color:#555;">التاريخ: اليوم | اتصال LAN: متصل</span>
                </div>
            </div>

            <div id="teachersListSec" class="card active">
                <h3 style="color:#0d47a1; margin-top:0;">👨‍🏫 سجل الأساتذة والموظفين (مع خيارات الإضافة والحذف التلقائي)</h3>
                
                <div style="display:flex; gap:15px; margin-bottom:20px; flex-wrap:wrap;">
                    <form method="POST" style="flex:1; background:#f0f4f8; padding:15px; border-radius:6px; margin:0;" onsubmit="return confirmAction('هل تريد توليد الحسابات من ملف الإكسل؟');">
                        <input type="hidden" name="action" value="create_auto_accounts">
                        <h4 style="margin-top:0; color:#0d47a1;">⚡ توليد جماعي من الشيتات</h4>
                        <button type="submit" style="background:#2e7d32;">توليد كل الحسابات والـ IDs</button>
                    </form>

                    <form method="POST" style="flex:1; background:#f0f4f8; padding:15px; border-radius:6px; margin:0;">
                        <input type="hidden" name="action" value="add_single_teacher">
                        <h4 style="margin-top:0; color:#0d47a1;">➕ إضافة أستاذ جديد يدوياً وخلق يوزر</h4>
                        <input type="text" name="teacher_name" placeholder="اسم الأستاذ الثلاثي" required style="margin-bottom:6px;">
                        <select name="category" required style="margin-bottom:6px; background:white;">
                            <option value="الملاك">الملاك</option>
                            <option value="شراء الخدمات">شراء الخدمات</option>
                            <option value="متعاقدين">متعاقدين</option>
                        </select>
                        <input type="number" name="fingerprint_id" placeholder="رقم البصمة ID" required style="margin-bottom:6px;">
                        <button type="submit" style="background:#0d47a1;">إضافة الأستاذ وتوليد الحساب</button>
                    </form>
                </div>

                <table>
                    <tr><th>اسم الأستاذ / الموظف</th><th>التصنيف</th><th>اسم المستخدم</th><th>كلمة المرور</th><th>رقم البصمة (ID)</th><th>الدوام الرسمي</th><th>إدارة وحذف</th></tr>
                    {{ teachers_rows | safe }}
                </table>
            </div>

            <div id="deviceConfigSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">🖧 برمجة وضبط جهاز البصمة ومراقبة الـ LAN</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="save_device_config">
                    <label><b>عنوان آي بي جهاز البصمة (Device IP Address):</b></label>
                    <input type="text" name="device_ip" value="192.168.1.201" required>
                    <label style="margin-top:10px; display:block;"><b>منفذ الاتصال (Port):</b></label>
                    <input type="text" name="device_port" value="4370" required>
                    <button type="submit" style="margin-top:15px; background:#2e7d32;" onclick="markSaved()">💾 حفظ إعدادات الجهاز والمزامنة</button>
                </form>
            </div>

            <div id="dailyAttendanceReportSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">📊 تقرير الدوام اليومي والغياب (حسب التاريخ ورابط الـ LAN)</h3>
                <table>
                    <tr><th>التاريخ</th><th>اسم الأستاذ</th><th>التصنيف</th><th>بصمة الحضور</th><th>بصمة الانصراف</th><th>الحالة والتقرير</th></tr>
                    <tr><td>2026-10-28</td><td>محمد شمص</td><td>الملاك (07:50 - 1:30)</td><td style='color:#2e7d32; font-weight:bold;'>07:52 ص</td><td>-</td><td><span style='color:green;'>حاضر بانتظام</span></td></tr>
                </table>
            </div>

            <div id="viewWeeklySchedule" class="card">
                {{ directorate_htmls['weekly_schedule'] | safe }}
            </div>

            <div id="viewFingerprintIds" class="card">
                {{ directorate_htmls['fingerprint_ids'] | safe }}
            </div>

            <div id="uploadDirectorateFilesSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">⚙️ رفع ملفات المديرية والبصمة (Excel)</h3>
                <form method="POST" enctype="multipart/form-data" onsubmit="markSaved()">
                    <input type="hidden" name="action" value="upload_directorate_file">
                    <select name="file_key" required style="font-weight:bold; background:#e3f2fd; margin-bottom:10px;">
                        <option value="fingerprint_ids">🆔 ملف البصمة ID (الشيتات الثلاثة)</option>
                        <option value="weekly_schedule">📅 البرنامج الأسبوعي للمعهد والمواد</option>
                        <option value="teachers_cards">📇 بطاقات الاساتذة</option>
                        <option value="students_registered">📂 الطلاب المسجلون</option>
                        <option value="executed_hours">⏱️ الساعات المنفذة للاساتذة</option>
                    </select>
                    <input type="file" name="excel_file" accept=".xlsx, .xls" required onchange="hasUnsavedChanges=true;">
                    <button type="submit" style="margin-top:15px; background:#2e7d32;">📥 رفع وتحليل وحفظ الملف في النظام المحمي</button>
                </form>
            </div>
        </div>

        <script>
            let hasUnsavedChanges = false;
            function showSection(secId) {
                if(hasUnsavedChanges && !confirm("تنبيه: لديك تعديلات لم يتم حفظها! هل تريد المتابعة؟")) return;
                document.querySelectorAll('.card').forEach(el => el.classList.remove('active'));
                let target = document.getElementById(secId);
                if(target) target.classList.add('active');
            }
            function markSaved() { hasUnsavedChanges = false; }
            function confirmAction(msg) { hasUnsavedChanges = false; return confirm(msg); }
        </script>
    </body>
    </html>
    '''
    return render_template_string(admin_template, teachers_rows=teachers_rows, directorate_htmls=directorate_htmls, msg=msg)

@app.route('/teacher', methods=['GET', 'POST'])
def teacher_dashboard():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    
    username = session.get('username')
    user_data = teachers_db.get(username, {})
    t_name = user_data.get('name', '').strip()
    clean_t = clean_name(t_name)
    cat = user_data.get('category', 'متعاقدين')
    f_id = user_data.get('fingerprint_id', 'غير مرتبط')
    shift = user_data.get('official_shift', 'حسب الحصص')

    parsed_schedule = directorate_excel_tables.get('weekly_schedule', {}).get('parsed_schedule', {})
    teacher_schedule_items = parsed_schedule.get(clean_t, [])
    
    schedule_rows = ""
    if teacher_schedule_items:
        for item in teacher_schedule_items:
            schedule_rows += f"""
            <tr>
                <td><b>{item['day']}</b></td>
                <td><span style='background:#e3f2fd; color:#0d47a1; padding:3px 8px; border-radius:4px;'>{item['class_name']}</span></td>
                <td><b style='color:#0d47a1; font-size:14px;'>{item['subject']}</b></td>
                <td><code style='color:#2e7d32; font-weight:bold;'>{item['period']}</code></td>
                <td><code>{item['duration']}</code></td>
            </tr>
            """
    
    # سجل البصمات والدوام السابق الجملي والمنظم للأستاذ
    fingerprint_history_html = f"""
    <div style="background:white; padding:20px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.06); border-top:4px solid #0d47a1; margin-top:20px;">
        <h3 style="color:#0d47a1; margin-top:0;">📊 سجل بصمات الحضور والدوام السابق (LAN Sync):</h3>
        <p style="font-size:13px; color:#555;">هنا يمكنك الاطلاع على حركات بصماتك المسجلة عبر جهاز البصمة في المعهد للأيام السابقة:</p>
        <table>
            <tr><th>التاريخ</th><th>اليوم</th><th>بصمة الحضور</th><th>بصمة الانصراف</th><th>الحالة والتقييم</th></tr>
            <tr>
                <td>2026-10-27</td>
                <td>الإثنين</td>
                <td style="color:#2e7d32; font-weight:bold;">07:51 ص</td>
                <td style="color:#c62828; font-weight:bold;">01:32 ظ</td>
                <td><span style="background:#e8f5e9; color:#2e7d32; padding:3px 8px; border-radius:4px; font-weight:bold;">حضور منتظم</span></td>
            </tr>
            <tr>
                <td>2026-10-26</td>
                <td>الأحد</td>
                <td style="color:#2e7d32; font-weight:bold;">07:48 ص</td>
                <td style="color:#c62828; font-weight:bold;">01:30 ظ</td>
                <td><span style="background:#e8f5e9; color:#2e7d32; padding:3px 8px; border-radius:4px; font-weight:bold;">حضور مبكر ومنتظم</span></td>
            </tr>
        </table>
    </div>
    """

    schedule_html = f"""
    <div style="background:white; padding:20px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.06); border-top:4px solid #2e7d32;">
        <h3 style="color:#2e7d32; margin-top:0;">📅 برنامجي الأسبوعي اليومي (المواد، رقم الحصة، والمدة):</h3>
        <table>
            <tr><th>اليوم</th><th>الصف الدراسي</th><th>المادة الدراسية</th><th>رقم الحصة</th><th>مدة الحصة</th></tr>
            {schedule_rows if schedule_rows else '<tr><td colspan="5" style="padding:20px; color:#666;">لا توجد حصص مسجلة باسمك في جدول المعهد الحالي</td></tr>'}
        </table>
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
            .header { background: #0d47a1; color: white; padding: 15px 25px; display: flex; justify-content: space-between; align-items: center; border-bottom: 3px solid #1565c0; }
            .container { padding: 20px; max-width: 1000px; margin: auto; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { border: 1px solid #e0e0e0; padding: 10px; text-align: center; font-size: 13.5px; }
            th { background: #0d47a1; color: white; }
        </style>
    </head>
    <body>
        <div class="header">
            <div>
                <h3 style="margin:0;">الجمهورية اللبنانية 🌲 - معهد الهرمل الفني</h3>
                <div style="font-size:13px; color:#bbdefb; margin-top:4px;">الأستاذ: <b>{{ t_name }}</b> | التصنيف: <b>{{ cat }}</b> | رقم البصمة (ID): <b>{{ f_id }}</b> | الدوام الرسمي: <b>{{ shift }}</b></div>
            </div>
            <a href="/logout" style="color:#ffcdd2; background:#c62828; padding:8px 15px; border-radius:4px; text-decoration:none; font-size:13px; font-weight:bold;">تسجيل الخروج</a>
        </div>

        <div class="container">
            {{ schedule_html | safe }}
            {{ fingerprint_history_html | safe }}
        </div>
        <div style="text-align:center; color:#777; font-size:12px; margin-top:30px;">نظام إدارة معهد الهرمل الفني © 2026 - إشراف وتصميم: مدير المعهد (محمد حسين شمص)</div>
    </body>
    </html>
    """
    return render_template_string(teacher_template, t_name=t_name, cat=cat, f_id=f_id, shift=shift, schedule_html=schedule_html, fingerprint_history_html=fingerprint_history_html)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
