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
                teachers_db.clear()
                teachers_db.update(data.get('teachers_db', {}))
                grades_db.clear()
                grades_db.update(data.get('grades_db', {}))
                attendance_db.clear()
                attendance_db.update(data.get('attendance_db', {}))
                classes_students.clear()
                classes_students.update(data.get('classes_students', {}))
                directorate_excel_tables.clear()
                directorate_excel_tables.update(data.get('directorate_excel_tables', directorate_excel_tables))
                return True
        except Exception as e:
            print(f"Error loading database file: {e}")
    return False

load_from_disk()

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
                                categories[clean_t] = sheet_name
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
        <button class="dropbtn">الأساتذة والدوام (بصمة) ▾</button>
        <div class="dropdown-content">
            <a href="javascript:void(0)" onclick="showSection('teachersListSec')">👨‍🏫 سجل الأساتذة وحسابات الدخول والبصمة</a>
            <a href="javascript:void(0)" onclick="showSection('deviceConfigSec')">🖧 إعدادات جهاز البصمة ومراقبة الـ LAN</a>
            <a href="javascript:void(0)" onclick="showSection('dailyAttendanceReportSec')">📊 تقرير الدوام اليومي والغياب (Live LAN)</a>
        </div>
    </div>

    <div class="dropdown">
        <button class="dropbtn">الإدارة والإعدادات ▾</button>
        <div class="dropdown-content">
            <a href="javascript:void(0)" onclick="showSection('uploadDirectorateFilesSec')">⚙️ رفع ملفات المديرية والبصمة (Excel)</a>
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
    client_ip = request.remote_addr # الحصول على عنوان آي بي الجهاز المتصل
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '').strip()
        
        if username == admin_credentials['username'] and password == admin_credentials['password']:
            session['username'] = 'admin'
            session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))
        elif username in teachers_db and teachers_db[username]['password'] == password:
            t_data = teachers_db[username]
            bound_device = t_data.get('bound_device', '')
            
            # قفل الجهاز: إذا كان الأستاذ مرتبطاً بجهاز معين ولم يتم تسجيل جهازه مسبقاً، نربطه أو نتحقق منه
            if not bound_device:
                teachers_db[username]['bound_device'] = client_ip
                save_to_disk()
            elif bound_device != client_ip:
                error = f'عذراً! هذا الحساب مرتبط بجهاز آخر (IP: {bound_device}). لا يمكنك الدخول من هذا الجهاز.'
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
            <small style="color:#0d47a1; display:block; margin-bottom:15px;">نظام الحماية وقفل الجهاز المعتمد</small>
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
                    rows_data = [{str(col): ("" if pd.isna(row[col]) else str(row[col]).strip()) for col in df_renamed.columns} for _, row in df_renamed.iterrows()]
                    directorate_excel_tables[file_key] = {"title": "ملف المديرية", "columns": list(df_renamed.columns), "data": rows_data}
                    
                    if file_key == 'weekly_schedule':
                        file.seek(0)
                        directorate_excel_tables['weekly_schedule']['parsed_schedule'] = parse_schedule_excel(file)
                    if file_key == 'fingerprint_ids':
                        file.seek(0)
                        p_ids, cats = parse_fingerprint_ids(file)
                        directorate_excel_tables['fingerprint_ids']['parsed_ids'] = p_ids
                        directorate_excel_tables['fingerprint_ids']['categories'] = cats

                    save_to_disk()
                    msg = "تم رفع وتحديث الملف وحفظه بنجاح!"
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
                        "bound_device": ""
                    }
                    count += 1
            save_to_disk()
            msg = f"تم توليد ({count}) حساب للأساتذة بنجاح!"

        elif action == 'add_single_teacher':
            t_name = request.form.get('teacher_name', '').strip()
            cat = request.form.get('category', 'متعاقدين')
            f_id = request.form.get('fingerprint_id', '').strip()
            shift = request.form.get('official_shift', '07:50 - 13:30')
            if t_name and f_id:
                user_id = f"teacher_{f_id}"
                teachers_db[user_id] = {
                    "name": t_name,
                    "password": "123",
                    "category": cat,
                    "fingerprint_id": int(f_id),
                    "official_shift": shift,
                    "bound_device": ""
                }
                save_to_disk()
                msg = f"تم إضافة الأستاذ '{t_name}' وتوليد حسابه بنجاح!"

        elif action == 'edit_teacher':
            t_key = request.form.get('teacher_key')
            if t_key in teachers_db:
                teachers_db[t_key]['name'] = request.form.get('teacher_name', '').strip()
                teachers_db[t_key]['category'] = request.form.get('category', '').strip()
                teachers_db[t_key]['fingerprint_id'] = int(request.form.get('fingerprint_id', 0))
                teachers_db[t_key]['official_shift'] = request.form.get('official_shift', '').strip()
                if request.form.get('reset_device') == 'on':
                    teachers_db[t_key]['bound_device'] = '' # إبطال قفل الجهاز ليتمكن من الدخول من جهاز جديد
                save_to_disk()
                msg = f"تم تعديل بيانات الأستاذ بنجاح!"

        elif action == 'delete_teacher':
            t_key = request.form.get('teacher_key')
            if t_key in teachers_db:
                del teachers_db[t_key]
                save_to_disk()
                msg = f"تم حذف الأستاذ بنجاح!"

    teachers_rows = ""
    for u, t in teachers_db.items():
        cat = t.get('category', 'متعاقدين')
        shift = t.get('official_shift', '07:50 إلى 1:30 ظهراً')
        bound_dev = t.get('bound_device', '')
        device_status = f"<code style='color:#0d47a1;'>مرتبط بـ: {bound_dev}</code>" if bound_dev else "<span style='color:#c62828;'>غير مرتبط بجهاز بعد</span>"
        
        teachers_rows += f"""
        <tr>
            <td><b>{t['name']}</b></td>
            <td><span style='background:#e3f2fd; color:#0d47a1; padding:3px 8px; border-radius:4px; font-size:12px;'>{cat}</span></td>
            <td><code style='color:#0d47a1;'>{u}</code></td>
            <td><code style='color:#2e7d32; font-weight:bold;'>{t.get('fingerprint_id')}</code></td>
            <td style='font-size:12px; color:#333; font-weight:bold;'>{shift}</td>
            <td>{device_status}</td>
            <td>
                <button type="button" onclick="openEditModal('{u}', '{t['name']}', '{cat}', '{t.get('fingerprint_id')}', '{shift}')" style="background:#1976d2; padding:5px 10px; font-size:12px; width:auto; margin-bottom:4px;">✏️ تعديل</button>
                <form method="POST" onsubmit="return confirm('هل أنت متأكد من حذف هذا الأستاذ؟');" style="margin:0; display:inline;">
                    <input type="hidden" name="action" value="delete_teacher">
                    <input type="hidden" name="teacher_key" value="{u}">
                    <button type="submit" style="background:#c62828; padding:5px 10px; font-size:12px; width:auto;">🗑️ حذف</button>
                </form>
            </td>
        </tr>
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
            .card { background: white; padding: 20px; border-radius: 8px; margin-top: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); border-top: 4px solid #0d47a1; }
            input, select, button { width: 100%; padding: 10px; margin-top: 6px; box-sizing: border-box; font-family: inherit; }
            button { background: #0d47a1; color: white; border: none; font-weight: bold; cursor: pointer; border-radius: 5px; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { border: 1px solid #e0e0e0; padding: 9px; text-align: center; font-size: 13.5px; }
            th { background: #0d47a1; color: white; }
            .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); justify-content: center; align-items: center; }
            .modal-content { background: white; padding: 25px; border-radius: 8px; width: 400px; max-width: 90%; }
        </style>
    </head>
    <body>
        ''' + HEADER_VTE_HTML + '''

        <div class="container">
            {% if msg %}
            <div style="background:#e8f5e9; color:#2e7d32; padding:12px; border-radius:6px; font-weight:bold; margin-bottom:15px; border-right:4px solid #2e7d32;">
                💾 {{ msg }}
            </div>
            {% endif %}

            <div class="card">
                <h3 style="color:#0d47a1; margin-top:0;">👨‍🏫 سجل الأساتذة والموظفين (مع قفل الجهاز وأوقات الدوام)</h3>
                
                <div style="display:flex; gap:15px; margin-bottom:20px; flex-wrap:wrap;">
                    <form method="POST" style="flex:1; background:#f0f4f8; padding:15px; border-radius:6px; margin:0;">
                        <input type="hidden" name="action" value="create_auto_accounts">
                        <h4 style="margin-top:0; color:#0d47a1;">⚡ توليد جماعي من الشيتات</h4>
                        <button type="submit" style="background:#2e7d32;">توليد كل الحسابات والـ IDs</button>
                    </form>

                    <form method="POST" style="flex:1; background:#f0f4f8; padding:15px; border-radius:6px; margin:0;">
                        <input type="hidden" name="action" value="add_single_teacher">
                        <h4 style="margin-top:0; color:#0d47a1;">➕ إضافة أستاذ جديد يدوياً</h4>
                        <input type="text" name="teacher_name" placeholder="اسم الأستاذ الثلاثي" required style="margin-bottom:6px;">
                        <select name="category" required style="margin-bottom:6px; background:white;">
                            <option value="الملاك">الملاك</option>
                            <option value="شراء الخدمات">شراء الخدمات</option>
                            <option value="متعاقدين">متعاقدين</option>
                        </select>
                        <input type="number" name="fingerprint_id" placeholder="رقم البصمة ID" required style="margin-bottom:6px;">
                        <input type="text" name="official_shift" placeholder="أوقات الدوام الرسمي (مثال: 07:50 - 1:30)" value="07:50 - 1:30" required style="margin-bottom:6px;">
                        <button type="submit" style="background:#0d47a1;">إضافة الأستاذ</button>
                    </form>
                </div>

                <table>
                    <tr><th>اسم الأستاذ</th><th>التصنيف</th><th>اليوزر</th><th>البصمة ID</th><th>أوقات الدوام الرسمي</th><th>حالة الجهاز (Device Lock)</th><th>إجراءات</th></tr>
                    {{ teachers_rows | safe }}
                </table>
            </div>

            <!-- نافذة التعديل المنبثقة (Modal) -->
            <div id="editModal" class="modal">
                <div class="modal-content">
                    <h3 style="color:#0d47a1; margin-top:0;">✏️ تعديل معلومات الأستاذ والدوام</h3>
                    <form method="POST">
                        <input type="hidden" name="action" value="edit_teacher">
                        <input type="hidden" id="edit_teacher_key" name="teacher_key">
                        <label><b>اسم الأستاذ:</b></label>
                        <input type="text" id="edit_name" name="teacher_name" required>
                        <label style="margin-top:8px; display:block;"><b>التصنيف:</b></label>
                        <select id="edit_category" name="category" required style="background:white;">
                            <option value="الملاك">الملاك</option>
                            <option value="شراء الخدمات">شراء الخدمات</option>
                            <option value="متعاقدين">متعاقدين</option>
                        </select>
                        <label style="margin-top:8px; display:block;"><b>رقم البصمة ID:</b></label>
                        <input type="number" id="edit_f_id" name="fingerprint_id" required>
                        <label style="margin-top:8px; display:block;"><b>أوقات الدوام الرسمي:</b></label>
                        <input type="text" id="edit_shift" name="official_shift" required>
                        <div style="margin-top:10px;">
                            <label><input type="checkbox" name="reset_device" value="on"> إلغاء قفل الجهاز (ليتمكن من الدخول من جهاز جديد)</label>
                        </div>
                        <div style="display:flex; gap:10px; margin-top:15px;">
                            <button type="submit" style="background:#2e7d32; flex:1;">حفظ التعديلات</button>
                            <button type="button" onclick="closeEditModal()" style="background:#c62828; flex:1;">إلغاء</button>
                        </div>
                    </form>
                </div>
            </div>

            <div class="card" style="margin-top:20px;">
                <h3 style="color:#0d47a1; margin-top:0;">⚙️ رفع ملفات المديرية والبصمة (Excel)</h3>
                <form method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="action" value="upload_directorate_file">
                    <select name="file_key" required style="font-weight:bold; background:#e3f2fd; margin-bottom:10px;">
                        <option value="fingerprint_ids">🆔 ملف البصمة ID (الشيتات الثلاثة)</option>
                        <option value="weekly_schedule">📅 البرنامج الأسبوعي للمعهد والمواد</option>
                    </select>
                    <input type="file" name="excel_file" accept=".xlsx, .xls" required>
                    <button type="submit" style="margin-top:10px; background:#2e7d32;">📥 رفع وتحليل الملف</button>
                </form>
            </div>
        </div>

        <script>
            function openEditModal(key, name, cat, fId, shift) {
                document.getElementById('edit_teacher_key').value = key;
                document.getElementById('edit_name').value = name;
                document.getElementById('edit_category').value = cat;
                document.getElementById('edit_f_id').value = fId;
                document.getElementById('edit_shift').value = shift;
                document.getElementById('edit_modal').style.display = 'flex'; // تم التصحيح ليتطابق مع الـ ID
                document.getElementById('editModal').style.display = 'flex';
            }
            function closeEditModal() {
                document.getElementById('editModal').style.display = 'none';
            }
        </script>
    </body>
    </html>
    '''
    return render_template_string(admin_template, teachers_rows=teachers_rows, msg=msg)

@app.route('/teacher', methods=['GET'])
def teacher_dashboard():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    username = session.get('username')
    user_data = teachers_db.get(username, {})
    return f"<h1>أهلاً بك يا أستاذ {user_data.get('name')}</h1><p>أوقات دوامك الرسمي: {user_data.get('official_shift')}</p><a href='/logout'>خروج</a>"

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000) 