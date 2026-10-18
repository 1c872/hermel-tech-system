import os
import json
import io
import math
import shutil
import pandas as pd
from datetime import datetime, time
from flask import Flask, render_template_string, request, redirect, url_for, session, send_from_directory, send_file, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'hermel_tech_school_shams_secret_key_2026'

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'xlsx', 'xls'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_FILE = 'database.json'
BACKUP_FILE = 'database_backup.json'

# جدول الحصص الرسمي المعتمد في المعهد
PERIODS_SCHEDULE = {
    1: {"start": "07:50", "end": "08:30", "label": "الحصة الأولى (07:50 - 08:30)"},
    2: {"start": "08:30", "end": "09:10", "label": "الحصة الثانية (08:30 - 09:10)"},
    3: {"start": "09:10", "end": "09:50", "label": "الحصة الثالثة (09:10 - 09:50)"},
    4: {"start": "09:50", "end": "10:30", "label": "الحصة الرابعة (09:50 - 10:30)"},
    5: {"start": "10:50", "end": "11:30", "label": "الحصة الخامسة (10:50 - 11:30)"},
    6: {"start": "11:30", "end": "12:10", "label": "الحصة السادسة (11:30 - 12:10)"},
    7: {"start": "12:10", "end": "12:50", "label": "الحصة السابعة (12:10 - 12:50)"},
    8: {"start": "12:50", "end": "01:30", "label": "الحصة الثامنة (12:50 - 01:30)"},
    9: {"start": "01:30", "end": "02:10", "label": "الحصة التاسعة (01:30 - 02:10)"}
}

teachers_db = {}
supervisors_db = {
    "sup_1": {
        "name": "أحمد الأحمد",
        "password": "123",
        "floor": "الطابق الأول",
        "classes": ["BP1 الكترونيك", "BP2 معلوماتية"]
    }
}
general_supervisors = {'general_admin': {'name': 'الناظر العام', 'password': '123'}}
grades_db = {}
attendance_db = {}
teacher_classes_map = {}
classes_students = {
    "BP1 الكترونيك": ["علي أحمد شمص", "حسين محمد زعيتر", "حسن علي ناصرالدين"],
    "BP2 معلوماتية": ["محمد حسين أمهز", "سارة يوسف دندش", "فاطمة أحمد طه"],
    "BT1 كهرباء": ["مهدي حسن مرتضى", "علي الرضا علوه", "زينب محمد شمص"],
    "BT2 الكترونيك": ["هادي أحمد ناصرالدين", "زين العابدين خزعل", "فاطمة علي أمهز"]
}

admin_replies = []
admin_credentials = {'username': 'admin', 'password': '123456'}
current_academic_year = "2026-2027"
field_sessions = []
teacher_absences_log = []   
student_exit_permissions = [] 

def save_to_disk():
    try:
        data = {
            'teachers_db': teachers_db,
            'supervisors_db': supervisors_db,
            'general_supervisors': general_supervisors,
            'grades_db': grades_db,
            'attendance_db': attendance_db,
            'teacher_classes_map': teacher_classes_map,
            'admin_replies': admin_replies,
            'admin_credentials': admin_credentials,
            'classes_students': classes_students,
            'field_sessions': field_sessions,
            'teacher_absences_log': teacher_absences_log,
            'student_exit_permissions': student_exit_permissions
        }
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        shutil.copyfile(DB_FILE, BACKUP_FILE)
    except Exception as e:
        print(f"Error saving database: {e}")

def load_from_disk():
    global teachers_db, supervisors_db, general_supervisors, grades_db, attendance_db, teacher_classes_map
    global admin_replies, admin_credentials, classes_students, field_sessions, teacher_absences_log, student_exit_permissions
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                teachers_db = data.get('teachers_db', {})
                supervisors_db = data.get('supervisors_db', supervisors_db)
                general_supervisors = data.get('general_supervisors', general_supervisors)
                grades_db = data.get('grades_db', {})
                attendance_db = data.get('attendance_db', {})
                teacher_classes_map = data.get('teacher_classes_map', {})
                admin_replies = data.get('admin_replies', [])
                admin_credentials = data.get('admin_credentials', {'username': 'admin', 'password': '123456'})
                classes_students = data.get('classes_students', classes_students)
                field_sessions = data.get('field_sessions', [])
                teacher_absences_log = data.get('teacher_absences_log', [])
                student_exit_permissions = data.get('student_exit_permissions', [])
                return True
        except Exception as e:
            print(f"Error loading database: {e}")
    return False

load_from_disk()

ICON_URL = "https://cdn-icons-png.flaticon.com/512/3135/3135755.png"

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
            return redirect(url_for('supervisor_dashboard'))
        elif username in supervisors_db and supervisors_db[username]['password'] == password:
            session['username'] = username
            session['role'] = 'supervisor'
            return redirect(url_for('supervisor_dashboard'))
        else:
            error = 'اسم المستخدم أو كلمة المرور غير صحيحة'
            
    return render_template_string('''
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
            <img src="{{ icon_url }}" width="65" style="margin-bottom:5px;">
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
    ''', icon_url=ICON_URL, error=error)

@app.route('/api/get_students/<class_name>')
def get_students(class_name):
    students = classes_students.get(class_name, ["طالب 1", "طالب 2", "طالب 3"])
    return jsonify({'students': students})

@app.route('/supervisor', methods=['GET', 'POST'])
def supervisor_dashboard():
    if session.get('role') not in ['supervisor', 'admin']: 
        return redirect(url_for('login'))
    
    username = session.get('username')
    if username == 'admin':
        sup_data = {"name": "مدير النظام", "floor": "الإدارة العامة", "classes": list(classes_students.keys())}
    else:
        sup_data = supervisors_db.get(username, {"name": "ناظر", "floor": "الطابق الأول", "classes": []})
        
    assigned_classes = sup_data.get('classes', [])
    floor_name = sup_data.get('floor', 'الطابق الأول')
    msg = ''

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'submit_supervisor_attendance':
            c_name = request.form.get('class_name')
            period_num = request.form.get('period_num')
            present_sts = request.form.getlist('attendance_check')
            teacher_status = request.form.get('teacher_status')
            
            all_sts = classes_students.get(c_name, [])
            absent_sts = [s for s in all_sts if s not in present_sts]
            date_str = datetime.now().strftime('%Y-%m-%d %H:%M')
            
            attendance_db[f"ناظر ({floor_name}) - {c_name} - الحصة {period_num} ({date_str})"] = {
                'present': present_sts,
                'absent': absent_sts,
                'teacher_status': teacher_status,
                'logged_by': sup_data.get('name')
            }
            
            if teacher_status in ['absent', 'escaped']:
                status_txt = "متغيب تماماً عن الحصة" if teacher_status == 'absent' else "توقيع شكلي ثم تهرب ومغادرة الصف!"
                admin_replies.append({
                    'teacher_name': f"تقرير الناظر: {sup_data.get('name')} ({floor_name})",
                    'message': f"🚨 بلاغ عاجل للمدير: أستاذ صف ({c_name}) للحصة ({period_num}) - حالة الأستاذ: {status_txt}",
                    'report': None,
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M')
                })
            save_to_disk()
            msg = f"تم تسجيل تقرير الحصة {period_num} لصف {c_name} بنجاح!"

        elif action == 'log_student_exit':
            st_name = request.form.get('student_name')
            c_name = request.form.get('class_name')
            p_num = request.form.get('period_num')
            exit_time = request.form.get('exit_time')
            
            student_exit_permissions.append({
                'date': datetime.now().strftime('%Y-%m-%d'),
                'student_name': st_name,
                'class_name': c_name,
                'period': p_num,
                'time': exit_time,
                'floor': floor_name,
                'supervisor': sup_data.get('name')
            })
            save_to_disk()
            msg = f"تم توثيق إذن خروج الطالب ({st_name}) للحصة ({p_num}) عند الساعة ({exit_time})!"

    class_opts = "".join([f'<option value="{c}">{c}</option>' for c in assigned_classes])
    period_opts = "".join([f'<option value="{k}">{v["label"]}</option>' for k, v in PERIODS_SCHEDULE.items()])

    return render_template_string('''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>لوحة الناظر - معهد الهرمل الفني</title>
        <style>
            body { font-family: system-ui, sans-serif; background: #f4f6f9; margin: 0; padding: 20px; }
            .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); border-top: 4px solid #0d47a1; margin-top: 15px; }
            select, input, button { width: 100%; padding: 10px; margin-top: 8px; box-sizing: border-box; font-family: inherit; }
            button { background: #0d47a1; color: white; font-weight: bold; border: none; cursor: pointer; border-radius: 5px; }
            .student-row { display: flex; justify-content: space-between; padding: 8px; border-bottom: 1px solid #eee; }
        </style>
    </head>
    <body>
        <div style="background:#0d47a1; color:white; padding:12px 20px; display:flex; justify-content:space-between; align-items:center; border-radius:8px;">
            <div>
                <h3 style="margin:0;">صفحة الناظر: {{ sup_name }}</h3>
                <small style="color:#bbdefb;">المسؤول عن: {{ floor_name }} | الصفوف المتاحة</small>
            </div>
            <a href="/logout" style="color:white; background:#c62828; padding:6px 12px; border-radius:4px; text-decoration:none;">خروج</a>
        </div>

        {% if msg %}
        <div style="background:#e8f5e9; color:#2e7d32; padding:10px; border-radius:6px; margin-top:15px; font-weight:bold;">{{ msg }}</div>
        {% endif %}

        <div class="card">
            <h3 style="color:#0d47a1; margin-top:0;">📋 رصد الحصص وتغيب/تهرب الأساتذة ({{ floor_name }})</h3>
            <form method="POST">
                <input type="hidden" name="action" value="submit_supervisor_attendance">
                
                <label><b>1. اختر الحصة الدراسية:</b></label>
                <select name="period_num" required>{{ period_opts | safe }}</select>

                <label style="margin-top:10px; display:block;"><b>2. اختر الصف:</b></label>
                <select name="class_name" id="supClassSelect" onchange="loadSupStudents()" required>
                    <option value="">-- اختر الصف --</option>
                    {{ class_opts | safe }}
                </select>

                <div id="supStudentsContainer" style="margin-top:15px;"></div>

                <div style="margin-top:15px; background:#fff3e0; padding:15px; border-radius:6px; border-right:4px solid #e65100;">
                    <label style="font-weight:bold; color:#e65100;">🕵️‍♂️ التزام أستاذ هذه الحصة:</label><br>
                    <div style="margin-top:8px;">
                        <input type="radio" name="teacher_status" value="present" checked style="width:auto;"> ✅ الأستاذ حاضر ويدرس بالحصة<br>
                        <input type="radio" name="teacher_status" value="absent" style="width:auto;"> ❌ الأستاذ متغيب عن الحصة<br>
                        <input type="radio" name="teacher_status" value="escaped" style="width:auto;"> 🚨 توقيع شكلي ثم تهرب ومغادرة الصف!
                    </div>
                </div>

                <button type="submit" id="supSubmitBtn" style="display:none; margin-top:15px; background:#2e7d32;">تأكيد وتوثيق تقرير الحصة</button>
            </form>
        </div>

        <div class="card">
            <h3 style="color:#0d47a1; margin-top:0;">🚪 تسجيل إذن خروج طالب أثناء الحصة</h3>
            <form method="POST">
                <input type="hidden" name="action" value="log_student_exit">
                <input type="text" name="student_name" placeholder="اسم الطالب الثلاثي" required>
                <select name="class_name" required>
                    <option value="">-- اختر صف الطالب --</option>
                    {{ class_opts | safe }}
                </select>
                <select name="period_num" required>{{ period_opts | safe }}</select>
                <input type="time" name="exit_time" required>
                <button type="submit" style="background:#1565c0;">تسجيل إذن خروج الطالب</button>
            </form>
        </div>

        <script>
            function loadSupStudents() {
                let cName = document.getElementById('supClassSelect').value;
                let container = document.getElementById('supStudentsContainer');
                let submitBtn = document.getElementById('supSubmitBtn');
                container.innerHTML = '';

                if (!cName) { submitBtn.style.display = 'none'; return; }

                fetch('/api/get_students/' + encodeURIComponent(cName))
                    .then(res => res.json())
                    .then(data => {
                        let html = '<p style="font-size:13px; color:#0d47a1; font-weight:bold;">حدد الطلاب الحاضرين لهذه الحصة:</p>';
                        data.students.forEach(st => {
                            html += `
                            <div class="student-row">
                                <span>${st}</span>
                                <input type="checkbox" name="attendance_check" value="${st}" checked style="width:auto;">
                            </div>`;
                        });
                        container.innerHTML = html;
                        submitBtn.style.display = 'block';
                    });
            }
        </script>
    </body>
    </html>
    ''', sup_name=sup_data.get('name'), floor_name=floor_name, class_opts=class_opts, period_opts=period_opts, msg=msg)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)