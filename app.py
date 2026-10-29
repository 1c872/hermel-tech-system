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

# مسارات التخزين الدائم محلياً في مجلد المشروع لضمان حفظ البيانات وعدم ضياعها
DB_FILE = os.path.abspath('hermel_database.json')
BACKUP_FILE = os.path.abspath('hermel_database_backup.json')

UPLOAD_FOLDER = os.path.abspath('uploads')
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
                if 'teachers_db' in data:
                    teachers_db.clear()
                    teachers_db.update(data['teachers_db'])
                if 'grades_db' in data:
                    grades_db.clear()
                    grades_db.update(data['grades_db'])
                if 'attendance_db' in data:
                    attendance_db.clear()
                    attendance_db.update(data['attendance_db'])
                if 'classes_students' in data:
                    classes_students.clear()
                    classes_students.update(data['classes_students'])
                if 'directorate_excel_tables' in data:
                    directorate_excel_tables.clear()
                    directorate_excel_tables.update(data['directorate_excel_tables'])
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
    error
