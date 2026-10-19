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
admin_replies = []
admin_credentials = {'username': 'admin', 'password': '123456'}
current_academic_year = "2026-2027"

directorate_excel_tables = {
    "teachers_and_subjects": {"title": "الاستاذ والمواد (التوزيع الرسمي)", "columns": [], "data": [], "parsed_schedule": {}},
    "students_registered": {"title": "الطلاب المسجلون", "columns": [], "data": []},
    "teachers_cards": {"title": "بطاقات الأساتذة", "columns": [], "data": []}
}

def clean_column_name(col):
    col_str = str(col).strip()
    col_str = col_str.replace("&#x27;", "").replace("'", "").replace('"', '')
    return col_str

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
            'admin_replies': admin_replies,
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
    global teachers_db, grades_db, grade_edit_permissions, attendance_db, admin_replies, admin_credentials, classes_students, current_academic_year, directorate_excel_tables
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                teachers_db = data.get('teachers_db', {})
                grades_db = data.get('grades_db', {})
                grade_edit_permissions = data.get('grade_edit_permissions', {})
                attendance_db = data.get('attendance_db', {})
                admin_replies = data.get('admin_replies', [])
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
                    parsed_teachers[norm_t] = {"name": teacher_name, "items": []}
                
                item = {"class": class_name, "subject": subject_name, "type": sub_type}
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
    <a href="/admin" style="color:white; text-decoration:none; padding:12px 16px; font-weight:bold; font-size:14px; background:#0d47a1;">🏠 الرئيسية والإدارة</a>
    <a href="/admin" onclick="showSection('viewTeachersAndSubjects')" style="color:white; text-decoration:none; padding:12px 16px; font-weight:bold; font-size:14px;">📋 جدول الأساتذة والمواد والصفوق</a>
    <a href="/admin" onclick="showSection('studentGradesSec')" style="color:white; text-decoration:none; padding:12px 16px; font-weight:bold; font-size:14px;">📝 كشوفات العلامات الرسمية</a>
</div>
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
                <input type="text" name="username" placeholder="اسم المستخدم (أو الرقم الآلي)" required>
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
                    <b style="font-size:16px;">معهد الهرمل الفني (رقم: 84)</b>
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
        <div style="margin-top:40px; display:flex; justify-content:space-between; padding:0 30px; font-weight:bold; font-size:15px;">
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
                        parsed = parse_teachers_and_subjects(df)
                        directorate_excel_tables['teachers_and_subjects']['parsed_schedule'] = parsed
                        
                        # توليد حسابات لكل الأساتذة بدقة من ملف الاستاذ والمواد تلقائياً
                        count = 0
                        for norm_key, t_data in parsed.items():
                            t_name = t_data['name']
                            # تحقق هل الأستاذ مسجل مسبقاً
                            existing_u = None
                            for u, info in teachers_db.items():
                                if normalize_name(info['name']) == norm_key:
                                    existing_u = u
                                    break
                            
                            if not existing_u:
                                u_id = f"teacher_{len(teachers_db) + 1}"
                                auto_pwd = f"100{len(teachers_db)+1}"
                                teachers_db[u_id] = {
                                    "name": t_name,
                                    "auto_id": auto_pwd,
                                    "password": auto_pwd,
                                    "subject": t_data['items'][0]['subject'] if t_data['items'] else "عام",
                                    "mobile_device": "",
                                    "pc_device": "",
                                    "notifications": []
                                }
                                count += 1

                    elif file_key == 'students_registered':
                        new_classes = {}
                        for _, row in df.iterrows():
                            # البحث بذكاء عن أعمدة الصف واسم الطالب
                            c_name = ""
                            s_name = ""
                            for val in row.values:
                                if pd.notna(val):
                                    v_str = str(val).strip()
                                    if any(k in v_str for k in ["BP", "BT", "TS", "LT", "رعاية", "كهرباء", "ميكانيك", "محاسبة"]):
                                        if len(v_str) < 50: c_name = v_str
                                    elif len(v_str.split()) >= 3 and not s_name:
                                        s_name = v_str
                            
                            # التقاط حسب الأعمدة المباشرة إن وجدت
                            for col in df.columns:
                                col_s = str(col).strip()
                                cell_val = str(row[col]).strip() if pd.notna(row[col]) else ""
                                if "الصف" in col_s or "التخصص" in col_s: c_name = cell_val
                                if "اسم" in col_s or "الطالب" in col_s: s_name = cell_val

                            if c_name and s_name and c_name != 'nan' and s_name != 'nan':
                                if c_name not in new_classes: new_classes[c_name] = []
                                if s_name not in new_classes[c_name]: new_classes[c_name].append(s_name)
                        if new_classes:
                            classes_students.update(new_classes)

                    save_to_disk()
                    msg = f"تم رفع وتحديث الملف بنجاح واستخراج كافة الأساتذة والصفوف والبيانات بدقة!"
                except Exception as e:
                    msg = f"خطأ في قراءة ملف الإكسل: {e}"

    # جدول عرض الأساتذة وموادهم للإدارة
    parsed_sched = directorate_excel_tables.get('teachers_and_subjects', {}).get('parsed_schedule', {})
    teachers_subjects_rows = ""
    if parsed_sched:
        for norm_k, data in parsed_sched.items():
            t_name = data['name']
            items_str = "<br>".join([f"📖 <b>{item['subject']}</b> ➔ الصف: <b style='color:#0d47a1;'>{item['class']}</b> (<span style='color:#2e7d32;'>{item['type']}</span>)" for item in data['items']])
            teachers_subjects_rows += f"<tr><td style='font-weight:bold; font-size:15px;'>{t_name}</td><td>{items_str}</td></tr>"
    else:
        teachers_subjects_rows = "<tr><td colspan='2' style='color:#c62828; font-weight:bold;'>⚠️ لم يتم رفع ملف (الاستاذ والمواد.xlsx) بعد. قم برفعه من الأسفل.</td></tr>"

    teachers_credentials_rows = "".join([f"<tr><td><b>{t['name']}</b></td><td><code>{u}</code></td><td><b style='color:#d32f2f;'>{t['password']}</b></td></tr>" for u, t in teachers_db.items()])
    
    # كشوفات العلامات للإدارة
    official_reports_rows = ""
    if parsed_sched:
        for u, t_info in teachers_db.items():
            norm_t = normalize_name(t_info['name'])
            t_data = parsed_sched.get(norm_t)
            if not t_data:
                # محاولة مطابقة جزئية
                for pk, pval in parsed_sched.items():
                    if pk in norm_t or norm_t in pk or any(part in pk for part in norm_t.split() if len(part)>2):
                        t_data = pval
                        break
            if t_data:
                for item in t_data['items']:
                    official_reports_rows += f"<tr><td><b>{t_info['name']}</b></td><td><b>{item['class']}</b></td><td><b style='color:#0d47a1;'>{item['subject']}</b> ({item['type']})</td><td><a href='/report/official_sheet?class_name={item['class']}&subject_name={item['subject']}&teacher_username={u}' target='_blank' style='background:#0d47a1; color:white; padding:6px 14px; border-radius:4px; text-decoration:none;'>📄 فتح وطباعة اللائحة الرسمية</a></td></tr>"
    if not official_reports_rows:
        official_reports_rows = "<tr><td colspan='4'>لا توجد كشوفات متاحة حالياً</td></tr>"

    teacher_opts = "".join([f"<option value='{u}'>{t['name']} ({u})</option>" for u, t in teachers_db.items()])

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
            th, td { border: 1px solid #e0e0e0; padding: 10px; text-align: center; font-size: 13.5px; }
            th { background: #0d47a1; color: white; }
        </style>
    </head>
    <body>
        ''' + HEADER_VTE_HTML + '''

        <div class="container">
            {% if msg %}<div style="background:#e8f5e9; color:#2e7d32; padding:12px; border-radius:6px; font-weight:bold; margin-bottom:15px;">{{ msg }}</div>{% endif %}

            <div id="viewTeachersAndSubjects" class="card active">
                <h3 style="color:#0d47a1; margin-top:0;">📋 جدول الأساتذة والمواد والصفوق وأنواعها (من ملف الاستاذ والمواد)</h3>
                <table>
                    <tr><th style="width:25%;">اسم الأستاذ</th><th>المواد والصفوف وتوزيع الحصص</th></tr>
                    {{ teachers_subjects_rows | safe }}
                </table>
            </div>

            <div id="studentGradesSec" class="card">
                <h3 style="color:#0d47a1; margin-top:0;">📝 كشوفات ولائح تقييم العلامات الرسمية للطلاب</h3>
                <table>
                    <tr><th>اسم الأستاذ</th><th>الصف والمستوى</th><th>المادة التعليمية والنوع</th><th>إجراء المعاينة والطباعة</th></tr>
                    {{ official_reports_rows | safe }}
                </table>
            </div>

            <div id="uploadDirectorateFilesSec" class="card" style="display:block; margin-top:20px;">
                <h3 style="color:#0d47a1; margin-top:0;">⚙️ رفع ملفات الإكسل الأساسية (الاستاذ والمواد + الطلاب المسجلون)</h3>
                <form method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="action" value="upload_directorate_file">
                    <label><b>حدد ملف الإكسل المطلوب رفعه:</b></label>
                    <select name="file_key" required style="font-weight:bold; background:#e3f2fd; font-size:14px;">
                        <option value="teachers_and_subjects">📋 1. ملف "الاستاذ والمواد.xlsx" (الأساسي لتوزيع الأساتذة والمواد والصفوف)</option>
                        <option value="students_registered">📂 2. ملف "الطلاب المسجلون.xlsx" (لجلب أسماء الطلاب لكل صف)</option>
                    </select>
                    <label style="margin-top:12px; display:block;"><b>اختر الملف (.xlsx):</b></label>
                    <input type="file" name="excel_file" accept=".xlsx, .xls" required style="margin-top:5px;">
                    <button type="submit" style="background:#2e7d32; margin-top:15px; font-size:15px;">📥 رفع واستخراج البيانات فوراً</button>
                </form>
            </div>

            <div class="card" style="display:block; margin-top:20px;">
                <h3 style="color:#0d47a1; margin-top:0;">🔑 حسابات الأساتذة وكلمات المرور (الرقم الآلي الصافي)</h3>
                <table>
                    <tr><th>اسم الأستاذ</th><th>اسم المستخدم</th><th>كلمة المرور (الرقم الآلي بدون .0)</th></tr>
                    {{ teachers_credentials_rows | safe }}
                </table>
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
    return render_template_string(admin_template, teachers_subjects_rows=teachers_subjects_rows, teachers_credentials_rows=teachers_credentials_rows, official_reports_rows=official_reports_rows, teacher_opts=teacher_opts, msg=msg)

@app.route('/teacher', methods=['GET', 'POST'])
def teacher_dashboard():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    
    username = session.get('username')
    user_data = teachers_db.get(username, {})
    t_name = user_data.get('name', '').strip()
    norm_t_name = normalize_name(t_name)
    msg = ''

    parsed_sched = directorate_excel_tables.get('teachers_and_subjects', {}).get('parsed_schedule', {})
    my_t_data = parsed_sched.get(norm_t_name)
    if not my_t_data:
        for pk, pval in parsed_sched.items():
            if pk in norm_t_name or norm_t_name in pk or any(part in pk for part in norm_t_name.split() if len(part)>2):
                my_t_data = pval
                break

    my_items = my_t_data['items'] if my_t_data else []

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
            msg = "🟢 تم حفظ ورصد علامات الطلاب بنجاح تام وإرسالها للإدارة!"

    my_class_opts = "".join([f'<option value="{c}">{c}</option>' for c in my_classes_map.keys()])
    
    schedule_rows = "".join([f"<tr><td><b>{item['class']}</b></td><td><b style='color:#0d47a1;'>{item['subject']}</b></td><td><span style='background:#e3f2fd; padding:3px 10px; border-radius:4px;'>{item['type']}</span></td></tr>" for item in my_items])
    schedule_html = f"<div class='card' style='border-top:4px solid #2e7d32;'><h4 style='color:#2e7d32; margin-top:0;'>📚 موادي وصفوفي الخاصة بي (من جدول الاستاذ والمواد):</h4><table><tr><th>الصف والمستوى</th><th>المادة التعليمية</th><th>النوع</th></tr>{schedule_rows}</table></div>" if my_items else "<div class='card'><p style='color:#c62828; font-weight:bold;'>⚠️ لم يتم العثور على مواد مرتبطة باسمك. تأكد من رفع ملف (الاستاذ والمواد.xlsx) من لوحة الإدارة.</p></div>"

    teacher_template = """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>واجهة الأستاذ - معهد الهرمل الفني</title>
        <style>
            body { font-family: system-ui, sans-serif; background: #f4f6f9; margin: 0; padding-bottom: 30px; }
            .card { background: white; padding: 20px; border-radius: 8px; margin-top: 15px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); border-top: 4px solid #0d47a1; }
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
            {% if msg %}<div style="background:#e8f5e9; color:#2e7d32; padding:12px; border-radius:6px; margin-bottom:10px; font-weight:bold;">{{ msg }}</div>{% endif %}

            {{ schedule_html | safe }}

            <div class="card">
                <h4 style="color:#0d47a1; margin-top:0;">📝 إدخال ورصد علامات الطلاب (من 0 إلى 20 أو غائب):</h4>
                <form method="POST">
                    <input type="hidden" name="action" value="submit_class_grades">
                    <label><b>اختر الصف الخاص بك:</b></label>
                    <select name="class_name" id="gradeClass" onchange="updateSubjectOpts()" required>
                        <option value="">-- اختر الصف --</option>
                        {{ my_class_opts | safe }}
                    </select>

                    <label style="margin-top:10px; display:block;"><b>اختر المادة والنوع:</b></label>
                    <select name="subject_name" id="gradeSubject" onchange="loadStudentsForGrades()" required>
                        <option value="">-- اختر المادة أولاً --</option>
                    </select>

                    <div id="gradeContainer" style="margin-top:15px;"></div>
                    <button type="submit" id="gradeBtn" style="display:none; margin-top:15px; background:#2e7d32; font-size:15px;">💾 تسليم ورصد العلامات رسمياً</button>
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
                    if(!data.students || data.students.length === 0) {
                        cont.innerHTML = '<p style="color:#c62828; font-weight:bold;">⚠️ لم يتم العثور على طلاب مسجلين لهذا الصف. تأكد من رفع ملف (الطلاب المسجلون.xlsx) من لوحة الإدارة.</p>';
                        btn.style.display = 'none';
                        return;
                    }
                    let html = '<p style="font-weight:bold; color:#0d47a1;">أسماء الطلاب في الصف:</p>';
                    data.students.forEach(st => {
                        html += `
                        <div class="student-row">
                            <span style="flex:1; font-weight:bold;">${st}</span>
                            <select name="grade_${st}" style="width:130px; margin:0;" required>
                                <option value="">-- العلامة --</option>
                                <option value="غائب">غائب (Absent)</option>
                                <option value="0">0 / 20</option>
                                <option value="2">2 / 20</option>
                                <option value="4">4 / 20</option>
                                <option value="6">6 / 20</option>
                                <option value="8">8 / 20</option>
                                <option value="10">10 / 20</option>
                                <option value="11">11 / 20</option>
                                <option value="12">12 / 20</option>
                                <option value="13">13 / 20</option>
                                <option value="14">14 / 20</option>
                                <option value="15">15 / 20</option>
                                <option value="16">16 / 20</option>
                                <option value="17">17 / 20</option>
                                <option value="18">18 / 20</option>
                                <option value="19">19 / 20</option>
                                <option value="20">20 / 20</option>
                            </select>
                            <input type="text" name="note_${st}" placeholder="ملاحظة (اختياري)" style="width:150px; margin:0;">
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
    app.run(host='0.0.0.0', port=5000)