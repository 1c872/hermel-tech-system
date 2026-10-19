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

teachers_db = {}
grades_db = {}             
grade_edit_permissions = {} 
attendance_db = {}        
classes_students = {}
admin_credentials = {'username': 'admin', 'password': '123456'}
current_academic_year = "2026-2027"

directorate_excel_tables = {
    "teachers_and_subjects": {"title": "الاستاذ والمواد (التوزيع الرسمي)", "columns": [], "data": [], "parsed_schedule": {}},
    "students_registered": {"title": "الطلاب المسجلون", "columns": [], "data": []},
    "teachers_cards": {"title": "بطاقات الأساتذة", "columns": [], "data": []}
}

def clean_column_name(col):
    return str(col).strip().replace("&#x27;", "").replace("'", "").replace('"', '')

def clean_auto_id(val):
    if pd.isna(val) or val is None:
        return ""
    val_str = str(val).strip()
    if val_str.endswith('.0'):
        val_str = val_str[:-2]
    return val_str

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
            'admin_credentials': admin_credentials,
            'classes_students': classes_students,
            'current_academic_year': current_academic_year,
            'directorate_excel_tables': directorate_excel_tables
        }
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        shutil.copyfile(DB_FILE, BACKUP_FILE)
    except Exception as e:
        print(f"Error saving database: {e}")

def load_from_disk():
    global teachers_db, grades_db, grade_edit_permissions, attendance_db, admin_credentials, classes_students, current_academic_year, directorate_excel_tables
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                teachers_db = data.get('teachers_db', {})
                grades_db = data.get('grades_db', {})
                grade_edit_permissions = data.get('grade_edit_permissions', {})
                attendance_db = data.get('attendance_db', {})
                admin_credentials = data.get('admin_credentials', admin_credentials)
                classes_students = data.get('classes_students', {})
                current_academic_year = data.get('current_academic_year', current_academic_year)
                directorate_excel_tables = data.get('directorate_excel_tables', directorate_excel_tables)
                return True
        except Exception as e:
            print(f"Error loading database file: {e}")
    return False

load_from_disk()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_teachers_and_subjects_smart(df):
    parsed_teachers = {}
    
    for _, row in df.iterrows():
        row_vals = [str(val).strip() for val in row.values if pd.notna(val) and str(val).strip() != 'nan']
        if len(row_vals) < 2:
            continue
            
        t_name = ""
        c_name = ""
        s_name = ""
        s_type = "نظري"
        
        for val in row_vals:
            if any(k in val for k in ["BP", "BT", "TS", "LT", "سنة", "رعاية", "كهرباء", "ميكانيك", "محاسبة", "إصلاح", "بيع"]):
                if not c_name: c_name = val
            elif val in ["نظري", "تطبيقي", "عملي"]:
                s_type = val
            elif len(val.split()) >= 2 and not t_name and not any(dig in val for dig in "0123456789"):
                t_name = val
            elif not s_name and val != t_name and val != c_name:
                s_name = val

        if not t_name and len(row) > 0 and pd.notna(row.iloc[0]): t_name = str(row.iloc[0]).strip()
        if not c_name and len(row) > 1 and pd.notna(row.iloc[1]): c_name = str(row.iloc[1]).strip()
        if not s_name and len(row) > 2 and pd.notna(row.iloc[2]): s_name = str(row.iloc[2]).strip()
        if len(row) > 3 and pd.notna(row.iloc[3]): 
            t_val = str(row.iloc[3]).strip()
            if t_val in ["نظري", "تطبيقي", "عملي"]: s_type = t_val

        if t_name and t_name != "nan" and s_name and s_name != "nan" and c_name and c_name != "nan":
            norm_t = normalize_name(t_name)
            if norm_t:
                if norm_t not in parsed_teachers:
                    parsed_teachers[norm_t] = {"name": t_name, "items": []}
                
                item = {"class": c_name, "subject": s_name, "type": s_type}
                if item not in parsed_teachers[norm_t]["items"]:
                    parsed_teachers[norm_t]["items"].append(item)

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
    <button onclick="showSection('viewTeachersAndSubjects')" class="nav-btn">📋 جدول الأساتذة والمواد والصفوف</button>
    <button onclick="showSection('studentGradesSec')" class="nav-btn">📝 كشوفات العلامات الرسمية</button>
    <button onclick="showSection('teachersListSec')" class="nav-btn">👨‍🏫 سجل الأساتذة وكلمات المرور</button>
    <button onclick="showSection('uploadDirectorateFilesSec')" class="nav-btn">⚙️ رفع ملفات الإكسل</button>
</div>

<style>
    .nav-btn { background: #1565c0; color: white; border: none; padding: 12px 16px; font-weight: bold; font-size: 13.5px; cursor: pointer; border-radius: 4px; margin: 2px; }
    .nav-btn:hover { background: #0d47a1; }
</style>
'''

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ''
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = clean_auto_id(request.form.get('password', ''))
        
        if username == admin_credentials['username'] and password == admin_credentials['password']:
            session['username'] = 'admin'
            session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))
        elif username in teachers_db and clean_auto_id(teachers_db[username]['password']) == password:
            session['username'] = username
            session['role'] = 'teacher'
            return redirect(url_for('teacher_dashboard'))
        else:
            error = 'اسم المستخدم أو كلمة المرور (الرقم الآلي) غير صحيحة'
            
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
                <input type="password" name="password" placeholder="كلمة المرور (الرقم الآلي بدون .0)" required>
                <button type="submit">دخول النظام</button>
            </form>
            <div style="color:#d32f2f; margin-top:12px; font-weight:bold; font-size:13px;">{{ error }}</div>
        </div>
        <div style="margin-top: 25px; color: #5c6bc0; font-size: 12px;">🛠️ إشراف وإدارة: الأستاذ محمد حسين شمص</div>
    </body>
    </html>
'''

@app.route('/api/get_students/<path:class_name>')
def get_students(class_name):
    students = classes_students.get(class_name, [])
    return jsonify({'students': students})

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
                    <div class="box-title">لائحة تقييم الطلاب للامتحان الرسمي</div>
                </td>
            </tr>
        </table>
        <table class="info-bar">
            <tr>
                <td><b>الصف والمستوى:</b> {class_name}</td>
                <td><b>العام الدراسي:</b> {current_academic_year}</td>
            </tr>
            <tr>
                <td><b>اسم المادة:</b> <span style="color:#0d47a1;">{subject_name}</span></td>
                <td><b>اسم الأستاذ:</b> {teacher_display_name}</td>
            </tr>
        </table>
        <table class="sheet">
            <thead>
                <tr>
                    <th style="width:5%;">#</th>
                    <th style="width:35%;">اسم الطالب الثلاثي</th>
                    <th style="width:10%;">العلامة</th>
                    <th style="width:10%;">إعادة 1</th>
                    <th style="width:10%;">إعادة 2</th>
                    <th style="width:12%;">المعدل</th>
                    <th style="width:18%;">ملاحظات</th>
                </tr>
            </thead>
            <tbody>
                {report_rows}
            </tbody>
        </table>
        <div style="margin-top:40px; display:flex; justify-content:space-between; padding:0 30px; font-weight:bold;">
            <div>توقيع الأستاذ: ............................</div>
            <div>توقيع وتصديق المدير: ............................</div>
        </div>
    </body>
    </html>
    '''
    return render_template_string(report_template)

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
            
            if file and allowed_file(file.filename):
                try:
                    df = pd.read_excel(file, sheet_name=0)
                    
                    if file_key == 'teachers_and_subjects':
                        parsed = parse_teachers_and_subjects_smart(df)
                        directorate_excel_tables['teachers_and_subjects']['parsed_schedule'] = parsed
                        
                        count = 0
                        for norm_key, data_obj in parsed.items():
                            t_name = data_obj['name']
                            exists = any(normalize_name(t['name']) == norm_key for t in teachers_db.values())
                            if not exists:
                                u_id = f"teacher_{len(teachers_db)+1}"
                                a_pwd = f"100{len(teachers_db)+1}"
                                teachers_db[u_id] = {
                                    "name": t_name,
                                    "auto_id": a_pwd,
                                    "password": a_pwd,
                                    "subject": data_obj['items'][0]['subject'] if data_obj['items'] else "عام",
                                    "mobile_device": "",
                                    "pc_device": "",
                                    "notifications": []
                                }
                                count += 1

                    elif file_key == 'students_registered':
                        new_classes = {}
                        for _, row in df.iterrows():
                            c_name = ""
                            s_name = ""
                            for val in row.values:
                                if pd.notna(val):
                                    v_str = str(val).strip()
                                    if any(k in v_str for k in ["BP", "BT", "TS", "LT", "سنة", "رعاية", "كهرباء", "ميكانيك", "محاسبة"]):
                                        if len(v_str) < 50: c_name = v_str
                                    elif len(v_str.split()) >= 3 and not s_name:
                                        s_name = v_str
                            if c_name and s_name and c_name != 'nan' and s_name != 'nan':
                                if c_name not in new_classes: new_classes[c_name] = []
                                if s_name not in new_classes[c_name]: new_classes[c_name].append(s_name)
                        if new_classes: classes_students.update(new_classes)

                    save_to_disk()
                    msg = f"تم رفع وتحديث الملف بنجاح واستخراج الأساتذة والمواد بنجاح تام!"
                except Exception as e:
                    msg = f"خطأ في قراءة ملف الإكسل: {e}"

    parsed_sched = directorate_excel_tables.get('teachers_and_subjects', {}).get('parsed_schedule', {})
    sorted_parsed_keys = sorted(parsed_sched.keys(), key=lambda k: parsed_sched[k]['name'])

    teachers_subjects_rows = ""
    if sorted_parsed_keys:
        for norm_k in sorted_parsed_keys:
            data_obj = parsed_sched[norm_k]
            t_name = data_obj['name']
            items_str = "<br>".join([f"المادة: <b>{item['subject']}</b> ➔ الصف: <b style='color:#0d47a1;'>{item['class']}</b> (النوع: <span style='color:#2e7d32; font-weight:bold;'>{item['type']}</span>)" for item in data_obj['items']])
            teachers_subjects_rows += f"<tr><td style='font-weight:bold; font-size:15px;'>{t_name}</td><td style='text-align:right;'>{items_str}</td></tr>"
    else:
        teachers_subjects_rows = "<tr><td colspan='2' style='color:#c62828; font-weight:bold;'>⚠️ لم يتم رفع ملف (الاستاذ والمواد.xlsx) بعد. قم برفعه من قسم رفع الملفات بالأسفل.</td></tr>"

    sorted_teachers_list = sorted(teachers_db.items(), key=lambda x: x[1]['name'])
    teachers_credentials_rows = "".join([f"<tr><td><b>{t['name']}</b></td><td><code>{u}</code></td><td><b style='color:#d32f2f;'>{t['password']}</b></td></tr>" for u, t in sorted_teachers_list])
    
    official_reports_list_html = ""
    if sorted_teachers_list and parsed_sched:
        for u, t_info in sorted_teachers_list:
            norm_t = normalize_name(t_info['name'])
            data_obj = parsed_sched.get(norm_t)
            if not data_obj:
                for pk, pval in parsed_sched.items():
                    if pk in norm_t or norm_t in pk or any(part in pk for part in norm_t.split() if len(part)>2):
                        data_obj = pval
                        break
            if data_obj:
                seen_combos = set()
                for item in data_obj['items']:
                    combo_key = f"{item['class']} || {item['subject']}"
                    if combo_key not in seen_combos:
                        seen_combos.add(combo_key)
                        official_reports_list_html += f"<tr><td><b>{t_info['name']}</b></td><td><b>{item['class']}</b></td><td><b style='color:#0d47a1;'>{item['subject']}</b> ({item['type']})</td><td><a href='/report/official_sheet?class_name={item['class']}&subject_name={item['subject']}&teacher_username={u}' target='_blank' style='background:#0d47a1; color:white; padding:6px 14px; border-radius:4px; text-decoration:none; font-weight:bold;'>📄 فتح التقرير الرسمي</a></td></tr>"
    if not official_reports_list_html:
        official_reports_list_html = "<tr><td colspan='4'>لم يتم رفع ملف الاستاذ والمواد بعد</td></tr>"

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
            .card.active { display: block !important; }
            input, select, textarea, button { width: 100%; padding: 10px; margin-top: 6px; box-sizing: border-box; font-family: inherit; }
            button { background: #0d47a1; color: white; border: none; font-weight: bold; cursor: pointer; border-radius: 5px; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { border: 1px solid #e0e0e0; padding: 10px; text-align: center; font-size: 13.5px; }
            th { background: #0d47a1; color: white; }
        </style>
    </head>
    <body>
        ''' + HEADER_VTE_HTML + '''

        <div class="container">
            {% if msg %}<div style="background:#e8f5e9; color:#2e7d32; padding:12px; border-radius:6px; font-weight:bold; margin-bottom:15px;">{{ msg }}</div>{% endif %}

            <div id="viewTeachersAndSubjects" class="card active">
                <h3 style="color:#0d47a1; margin-top:0;">📋 جدول الأساتذة والمواد والصفوف (مرتبة أبجديأ أ - ي)</h3>
                <table>
                    <tr><th style="width:30%;">اسم الأستاذ</th><th>المواد والصفوف المسندة</th></tr>
                    {{ teachers_subjects_rows | safe }}
                </table>
            </div>

            <div id="studentGradesSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">📝 كشوفات العلامات الرسمية (لائحة تقييم الطلاب للامتحان)</h3>
                <table>
                    <tr><th>اسم الأستاذ</th><th>الصف والمستوى</th><th>المادة والنوع</th><th>عرض واستعراض التقرير</th></tr>
                    {{ official_reports_list_html | safe }}
                </table>
            </div>

            <div id="teachersListSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">👨‍🏫 سجل الأساتذة وكلمات المرور (الرقم الآلي الصافي)</h3>
                <table><tr><th>اسم الأستاذ</th><th>اسم المستخدم</th><th>كلمة المرور</th></tr>{{ teachers_credentials_rows | safe }}</table>
            </div>

            <div id="uploadDirectorateFilesSec" class="card" style="display:block; margin-top:20px;">
                <h3 style="color:#0d47a1; margin-top:0;">⚙️ رفع ملفات الإكسل الذكية (Excel)</h3>
                <form method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="action" value="upload_directorate_file">
                    <label><b>حدد ملف الإكسل المطلوب رفعه:</b></label>
                    <select name="file_key" required style="font-weight:bold; background:#e3f2fd; font-size:14px;">
                        <option value="teachers_and_subjects">📋 0. جدول الاستاذ والمواد (الذكي)</option>
                        <option value="students_registered">📂 1. ملف الطلاب المسجلون</option>
                    </select>
                    <label style="margin-top:12px; display:block;"><b>اختر الملف (.xlsx):</b></label>
                    <input type="file" name="excel_file" accept=".xlsx, .xls" required style="margin-top:5px;">
                    <button type="submit" style="background:#2e7d32; margin-top:15px; font-size:15px;">📥 رفع واستخراج الأساتذة والمواد فوراً</button>
                </form>
            </div>
        </div>

        <script>
            function showSection(secId) {
                document.querySelectorAll('.card').forEach(el => {
                    el.classList.remove('active');
                    el.style.display = 'none';
                });
                let target = document.getElementById(secId);
                if(target) {
                    target.classList.add('active');
                    target.style.display = 'block';
                }
            }
        </script>
    </body>
    </html>
    '''
    return render_template_string(admin_template, teachers_subjects_rows=teachers_subjects_rows, teachers_credentials_rows=teachers_credentials_rows, official_reports_list_html=official_reports_list_html, msg=msg)

@app.route('/teacher', methods=['GET', 'POST'])
def teacher_dashboard():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    
    username = session.get('username')
    user_data = teachers_db.get(username, {})
    t_name = user_data.get('name', '').strip()
    norm_t_name = normalize_name(t_name)
    msg = ''

    parsed_sched = directorate_excel_tables.get('teachers_and_subjects', {}).get('parsed_schedule', {})
    data_obj = parsed_sched.get(norm_t_name)
    if not data_obj:
        for pk, pval in parsed_sched.items():
            if pk in norm_t_name or norm_t_name in pk or any(part in pk for part in norm_t_name.split() if len(part)>2):
                data_obj = pval
                break

    my_items = data_obj['items'] if data_obj else []

    my_classes_map = {}
    for item in my_items:
        c_name = item['class']
        s_display = f"{item['subject']} ({item['type']})"
        if c_name not in my_classes_map:
            my_classes_map[c_name] = []
        if s_display not in my_classes_map[c_name]:
            my_classes_map[c_name].append(s_display)

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'submit_class_grades':
            class_name = request.form.get('class_name')
            raw_sub = request.form.get('subject_name')
            subject_name = raw_sub.split(' (')[0] if ' (' in raw_sub else raw_sub
            
            students = classes_students.get(class_name, [])
            for st in students:
                g_val = request.form.get(f"grade_{st}")
                note_val = request.form.get(f"note_{st}", '')
                g_key = f"{st} || {class_name} || {subject_name}"
                
                grades_db[g_key] = {
                    "student": st,
                    "class": class_name,
                    "subject": subject_name,
                    "grade": g_val,
                    "note": note_val,
                    "teacher": username,
                    "submitted_at": datetime.now().strftime('%Y-%m-%d %H:%M')
                }
            save_to_disk()
            msg = "🟢 تم حفظ ورصد علامات الطلاب بنجاح!"

    my_class_opts = "".join([f'<option value="{c}">{c}</option>' for c in my_classes_map.keys()])
    schedule_rows = "".join([f"<tr><td><b>{item['class']}</b></td><td><b style='color:#0d47a1;'>{item['subject']}</b></td><td><span>{item['type']}</span></td></tr>" for item in my_items])
    schedule_html = f"<div class='card' style='border-top:4px solid #2e7d32;'><h4 style='color:#2e7d32; margin-top:0;'>📚 موادي وصفوفي الخاصة بي:</h4><table><tr><th>الصف</th><th>المادة</th><th>النوع</th></tr>{schedule_rows}</table></div>" if my_items else "<div class='card'><p style='color:#c62828;'>⚠️ لم يتم العثور على مواد مرتبطة باسمك.</p></div>"

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

        <div style="padding:15px;">
            {% if msg %}<div style="background:#e8f5e9; color:#2e7d32; padding:10px; border-radius:6px; margin-bottom:10px; font-weight:bold;">{{ msg }}</div>{% endif %}

            {{ schedule_html | safe }}

            <div class="card">
                <h4 style="color:#0d47a1; margin-top:0;">📝 إدخال ورصد علامات الطلاب:</h4>
                <form method="POST">
                    <input type="hidden" name="action" value="submit_class_grades">
                    <label>اختر الصف:</label>
                    <select name="class_name" id="gradeClass" onchange="updateSubjectOpts()" required>
                        <option value="">-- اختر الصف --</option>
                        {{ my_class_opts | safe }}
                    </select>

                    <label style="margin-top:10px; display:block;">اختر المادة والنوع:</label>
                    <select name="subject_name" id="gradeSubject" onchange="loadStudentsForGrades()" required>
                        <option value="">-- اختر المادة --</option>
                    </select>

                    <div id="gradeContainer" style="margin-top:10px;"></div>
                    <button type="submit" id="gradeBtn" style="display:none; margin-top:10px;">💾 تسليم ورصد العلامات رسمياً</button>
                </form>
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
                                <option value="10">10 / 20</option>
                                <option value="12">12 / 20</option>
                                <option value="14">14 / 20</option>
                                <option value="16">16 / 20</option>
                                <option value="18">18 / 20</option>
                                <option value="20">20 / 20</option>
                            </select>
                            <input type="text" name="note_${st}" placeholder="ملاحظة" style="width:140px; margin:0;">
                        </div>`;
                    });
                    cont.innerHTML = html;
                    btn.style.display = 'block';
                });
            }
        </script>
    </body>
    </html>
    """
    return render_template_string(teacher_template, t_name=t_name, msg=msg, my_class_opts=my_class_opts, my_classes_map=my_classes_map, schedule_html=schedule_html)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)