import os
import random
import string
import pandas as pd
from flask import Flask, render_template_string, request, redirect, url_for, session, send_from_directory, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'hermel_tech_school_shams_secret_key_2026'

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'xlsx', 'xls'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# قاعدة بيانات الأساتذة
teachers_db = {}
admin_replies = []  # لاستقبال ردود وإجابات الأساتذة للمدير

def load_initial_teachers():
    global teachers_db
    try:
        if os.path.exists('بطاقات الاساتذة.xlsx'):
            df = pd.read_excel('بطاقات الاساتذة.xlsx', sheet_name=0)
            for index, row in df.iterrows():
                name = str(row.get('الاسم الثلاثي', f'أستاذ_{index}')).strip()
                if not name or name == 'nan':
                    continue
                username = f"teacher_{index+1}"
                password = str(int(row.get('الرقم الآلي', 123456))) if pd.notna(row.get('الرقم الآلي')) else "123456"
                
                teachers_db[username] = {
                    'password': password,
                    'name': name,
                    # كافة البيانات الشخصية والإدارية من ملف الإكسل
                    'dob': str(row.get('تاريخ الميلاد', 'غير محدد')) if pd.notna(row.get('تاريخ الميلاد')) else 'غير محدد',
                    'register_no': str(row.get('رقم السجل', 'غير محدد')) if pd.notna(row.get('رقم السجل')) else 'غير محدد',
                    'district': str(row.get('القضاء', 'غير محدد')) if pd.notna(row.get('القضاء')) else 'غير محدد',
                    'town': str(row.get('بلدة النفوس', 'غير محدد')) if pd.notna(row.get('بلدة النفوس')) else 'غير محدد',
                    'address': str(row.get('العنوان الحالي', 'غير محدد')) if pd.notna(row.get('العنوان الحالي')) else 'غير محدد',
                    'marital_status': str(row.get('الوضع العائلي', 'غير محدد')) if pd.notna(row.get('الوضع العائلي')) else 'غير محدد',
                    'children_count': str(row.get('عدد الأولاد', '0')) if pd.notna(row.get('عدد الأولاد')) else '0',
                    'start_date': str(row.get('تاريخ المباشرة', 'غير محدد')) if pd.notna(row.get('تاريخ المباشرة')) else 'غير محدد',
                    'job_status': str(row.get('الوضع الوظيفي', 'غير محدد')) if pd.notna(row.get('الوضع الوظيفي')) else 'غير محدد',
                    'degree': str(row.get('الشهادة', 'غير محددة')) if pd.notna(row.get('الشهادة')) else 'غير محددة',
                    'subject': str(row.get('المادة التي يدرسها', 'غير محددة')) if pd.notna(row.get('المادة التي يدرسها')) else 'غير محددة',
                    'teaching_degree': str(row.get('الشهادة التي يدرسها', 'غير محددة')) if pd.notna(row.get('الشهادة التي يدرسها')) else 'غير محددة',
                    'contract_hours': int(row.get('مجموع ساعات العقود', 0)) if pd.notna(row.get('مجموع ساعات العقود')) else 0,
                    'phone': str(row.get('رقم الهاتف', 'غير متوفر')) if pd.notna(row.get('رقم الهاتف')) else 'غير متوفر',
                    'bank': str(row.get('اسم البنك', 'غير متوفر')) if pd.notna(row.get('اسم البنك')) else 'غير متوفر',
                    'iban': str(row.get('Iban Number', 'غير متوفر')) if pd.notna(row.get('Iban Number')) else 'غير متوفر',
                    
                    'schedule_pdf': None,
                    'notifications': [],
                    'monthly_data': {}, # { 'كانون الثاني': {'hours': 40, 'transport': '2,500,000 ل.ل'} }
                    'absence_requests': []
                }
    except Exception as e:
        print(f"Error loading excel: {e}")

load_initial_teachers()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 1. صفحة تسجيل الدخول
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ''
    if request.method == 'POST':
        username = request.form.get('username').strip().lower()
        password = request.form.get('password').strip()
        
        if username == 'admin' and password == '123456':
            session['username'] = 'admin'
            session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))
        elif username in teachers_db and teachers_db[username]['password'] == password:
            session['username'] = username
            session['role'] = 'teacher'
            return redirect(url_for('teacher_dashboard'))
        else:
            error = 'اسم المستخدم أو كلمة المرور غير صحيحة'
            
    return f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>معهد الهرمل الفني - تسجيل الدخول</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background: #1a202c; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; flex-direction: column; }}
            .card {{ background: white; padding: 40px 30px; border-radius: 16px; width: 90%; max-width: 380px; text-align: center; box-shadow: 0 15px 35px rgba(0,0,0,0.3); }}
            h2 {{ color: #1a365d; margin-bottom: 25px; font-size: 24px; font-weight: bold; }}
            input {{ width: 100%; padding: 12px; margin: 10px 0; border: 1.5px solid #cbd5e0; border-radius: 8px; box-sizing: border-box; text-align: right; font-size: 15px; }}
            button {{ width: 100%; padding: 12px; background: #2b6cb0; color: white; border: none; border-radius: 8px; font-weight: bold; font-size: 16px; cursor: pointer; margin-top: 15px; }}
            button:hover {{ background: #1a365d; }}
            .error {{ color: #e53e3e; margin-top: 12px; font-weight: bold; font-size: 14px; }}
            .designer-tag {{ margin-top: 25px; color: #a0aec0; font-size: 13px; font-weight: 500; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>معهد الهرمل الفني</h2>
            <form method="POST">
                <input type="text" name="username" placeholder="اسم المستخدم" required>
                <input type="password" name="password" placeholder="كلمة المرور" required>
                <button type="submit">دخول النظام</button>
            </form>
            <div class="error">{error}</div>
        </div>
        <div class="designer-tag">🛠️ تم تصميم وتطوير البرنامج من قبل الأستاذ محمد حسين شمص</div>
    </body>
    </html>
    '''

# 2. لوحة المدير
@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    msg = ''
    if request.method == 'POST':
        action = request.form.get('action')
        
        # رفع إكسل الساعات وبدلات النقل الشهري
        if action == 'upload_monthly_excel':
            month_name = request.form.get('month_name')
            file = request.files.get('monthly_excel')
            if file and allowed_file(file.filename):
                try:
                    df_m = pd.read_excel(file)
                    updated_count = 0
                    for _, row in df_m.iterrows():
                        t_name = str(row.get('الاسم الثلاثي', '')).strip()
                        hours = row.get('عدد الحصص', row.get('ساعات التدريس', 0))
                        transport = row.get('بدل النقل', 0)
                        
                        # مطابقة الأستاذ بالاسم
                        for u, t_data in teachers_db.items():
                            if t_data['name'] == t_name or t_name in t_data['name']:
                                if 'monthly_data' not in t_data:
                                    t_data['monthly_data'] = {}
                                t_data['monthly_data'][month_name] = {
                                    'hours': hours,
                                    'transport': transport
                                }
                                updated_count += 1
                    msg = f"تم استيراد بيانات شهر ({month_name}) بنجاح لعدد ({updated_count}) أستاذ!"
                except Exception as e:
                    msg = f"حدث خطأ أثناء قراءة ملف الإكسل: {e}"

        elif action == 'send_notification':
            target_user = request.form.get('target_user')
            notif = request.form.get('notification_text')
            if target_user in teachers_db and notif:
                teachers_db[target_user]['notifications'].append(notif)
                msg = f"تم إرسال التنبيه للأستاذ {teachers_db[target_user]['name']} بنجاح!"

        elif action == 'upload_pdf':
            target_user = request.form.get('target_user')
            file = request.files.get('pdf_file')
            if target_user in teachers_db and file and allowed_file(file.filename):
                filename = secure_filename(f"schedule_{target_user}.pdf")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                teachers_db[target_user]['schedule_pdf'] = filename
                msg = "تم رفع جدول التدريس PDF بنجاح."

    # استعراض الردود القادمة من الأساتذة
    replies_html = ""
    for r in reversed(admin_replies):
        report_link = f"<a href='/uploads/{r['report']}' target='_blank'>📎 عرض التقرير المرفق</a>" if r.get('report') else "لا يوجد مرفق"
        replies_html += f"""
        <div style="background:#fffaf0; border-right:4px solid #dd6b20; padding:12px; margin-bottom:10px; border-radius:6px;">
            <span style="color:#2b6cb0; font-weight:bold;">📩 من الأستاذ: {r['teacher_name']}</span> | <small>{r.get('date', '')}</small><br>
            <b>الرسالة/الطلب:</b> {r['message']}<br>
            <small>{report_link}</small>
        </div>
        """
    if not replies_html:
        replies_html = "<p style='color:#718096;'>لا توجد إجابات أو رسائل جديدة من الأساتذة حالياً.</p>"

    # جدول الأساتذة
    rows = ""
    for username, t in teachers_db.items():
        if username == 'admin': continue
        pdf_status = f"<a href='/uploads/{t['schedule_pdf']}' target='_blank'>📄 عرض PDF</a>" if t['schedule_pdf'] else "غير مرفوع"
        
        m_data_list = []
        for m, val in t.get('monthly_data', {}).items():
            m_data_list.append(f"<b>{m}:</b> {val.get('hours', 0)} حصة | بدل نقل: {val.get('transport', 0)}")
        m_str = "<br>".join(m_data_list) if m_data_list else "لم تُرفع بعد"

        rows += f"""
        <tr>
            <td>
                <b>{t['name']}</b><br>
                <small style='color:#4a5568;'>مادة: {t['subject']}</small><br>
                <code>حساب: {username} | سر: {t['password']}</code>
            </td>
            <td><b>{t['contract_hours']} ساعة</b></td>
            <td style="background:#f7fafc; color:#2b6cb0; font-size:12px;">{m_str}</td>
            <td>{pdf_status}</td>
        </tr>
        """

    active_teachers_opts = "".join([f'<option value="{u}">{t["name"]}</option>' for u,t in teachers_db.items() if u != 'admin'])

    return f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>معهد الهرمل الفني - لوحة المدير</title>
        <style>
            body {{ font-family: system-ui, sans-serif; background: #edf2f7; margin: 0; padding: 15px; }}
            .navbar {{ background: #1a365d; color: white; padding: 18px 25px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }}
            .card {{ background: white; padding: 20px; border-radius: 12px; margin-top: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
            th, td {{ border: 1px solid #e2e8f0; padding: 10px; text-align: center; font-size: 13px; }}
            th {{ background: #2b6cb0; color: white; }}
            form {{ display: flex; flex-direction: column; gap: 10px; margin-top: 10px; }}
            input, select, button {{ padding: 10px; border: 1px solid #cbd5e0; border-radius: 6px; text-align: right; font-size: 14px; }}
            button {{ background: #38a169; color: white; border: none; font-weight: bold; cursor: pointer; }}
            .msg {{ background: #c6f6d5; color: #22543d; padding: 12px; border-radius: 8px; margin-top: 15px; font-weight: bold; text-align: center; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; }}
            .designer-tag {{ margin-top: 30px; color: #718096; font-size: 13px; font-weight: 500; text-align: center; border-top: 1px solid #cbd5e0; padding-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="navbar">
            <h2 style="margin:0;">معهد الهرمل الفني - لوحة الإدارة</h2>
            <a href="/logout" style="color:white; font-weight:bold; text-decoration:none; background:#e53e3e; padding:8px 15px; border-radius:6px;">تسجيل الخروج</a>
        </div>

        {f'<div class="msg">{msg}</div>' if msg else ''}

        <!-- صندوق ردود وإجابات الأساتذة البارز -->
        <div class="card" style="border-top: 4px solid #dd6b20;">
            <h3 style="margin-top:0; color:#c05621;">📥 إجابات ورسائل الأساتذة الواردة:</h3>
            {replies_html}
        </div>

        <div class="grid">
            <!-- رفع ملف إكسل شهري -->
            <div class="card" style="border-top: 4px solid #38a169;">
                <h4>📊 رفع إكسل الحصص وبدلات النقل الشهرية:</h4>
                <form method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="action" value="upload_monthly_excel">
                    <input type="text" name="month_name" placeholder="اسم الشهر (مثال: كانون الثاني)" required>
                    <label style="font-size:12px; color:#4a5568;">اختر ملف الإكسل للشهر:</label>
                    <input type="file" name="monthly_excel" accept=".xlsx,.xls" required>
                    <button type="submit" style="background:#38a169;">استيراد بيانات الشهر وتحديث الأساتذة</button>
                </form>
            </div>

            <div class="card">
                <h4>📢 إرسال إشعار / رسالة لأستاذ:</h4>
                <form method="POST">
                    <input type="hidden" name="action" value="send_notification">
                    <select name="target_user" required>{active_teachers_opts}</select>
                    <input type="text" name="notification_text" placeholder="نص الرسالة والتنبيه..." required>
                    <button type="submit" style="background:#2b6cb0;">إرسال التنبيه الفوري</button>
                </form>
            </div>

            <div class="card">
                <h4>📄 رفع جدول التدريس (PDF):</h4>
                <form method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="action" value="upload_pdf">
                    <select name="target_user" required>{active_teachers_opts}</select>
                    <input type="file" name="pdf_file" accept=".pdf" required>
                    <button type="submit" style="background:#4a5568;">رفع ملف PDF</button>
                </form>
            </div>
        </div>

        <div class="card">
            <h3 style="margin-top:0; color:#1a365d;">سجل الأساتذة الكامل</h3>
            <table>
                <tr>
                    <th>بيانات الأستاذ</th>
                    <th>العقود</th>
                    <th>الحصص وبدل النقل الشهري</th>
                    <th>جدول PDF</th>
                </tr>
                {rows}
            </table>
        </div>

        <div class="designer-tag">🛠️ تم تصميم وتطوير البرنامج من قبل الأستاذ محمد حسين شمص</div>
    </body>
    </html>
    '''

# 3. لوحة الأستاذ
@app.route('/teacher', methods=['GET', 'POST'])
def teacher_dashboard():
    if session.get('role') != 'teacher':
        return redirect(url_for('login'))
        
    username = session.get('username')
    user_data = teachers_db.get(username, {})
    msg = ''

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'send_reply':
            reply_msg = request.form.get('reply_message')
            file = request.files.get('medical_report')
            report_filename = None
            if file and allowed_file(file.filename):
                report_filename = secure_filename(f"report_{username}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], report_filename))
            
            admin_replies.append({
                'teacher_name': user_data['name'],
                'message': reply_msg,
                'report': report_filename,
                'date': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')
            })
            msg = "تم إرسال إجابتك/رسالتك إلى لوحة المدير بنجاح!"

    notifs_html = "".join([f"<div class='notif-box'>🔔 <b>إشعار إدارة:</b> {n}</div>" for n in user_data.get('notifications', [])])
    pdf_html = f"<a href='/uploads/{user_data['schedule_pdf']}' class='btn-pdf' target='_blank'>📄 فتح/تحميل جدول الحصص الأسبوعي PDF</a>" if user_data.get('schedule_pdf') else "لم يتم رفع جدول الحصص بعد."
    
    # جدول البدلات والحصص الشهري للأستاذ
    monthly_rows = ""
    for m, val in user_data.get('monthly_data', {}).items():
        monthly_rows += f"<tr><td><b>{m}</b></td><td><span style='color:#2b6cb0; font-weight:bold;'>{val.get('hours', 0)} حصة</span></td><td><span style='color:#38a169; font-weight:bold;'>{val.get('transport', 0)}</span></td></tr>"
    if not monthly_rows:
        monthly_rows = "<tr><td colspan='3'>لم يتم رفع بيانات الحصص والبدلات الشهرية بعد.</td></tr>"

    return f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>معهد الهرمل الفني - بطاقة الأستاذ</title>
        <style>
            body {{ font-family: system-ui, sans-serif; background: #f7fafc; margin: 0; padding: 15px; color: #2d3748; }}
            .navbar {{ background: #1a365d; color: white; padding: 15px; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; }}
            .card {{ background: white; padding: 20px; border-radius: 12px; margin-top: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }}
            .info-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 10px; }}
            .info-item {{ background: #edf2f7; padding: 10px 14px; border-radius: 8px; font-size: 13.5px; line-height: 1.6; }}
            .info-item b {{ color: #1a365d; }}
            .notif-box {{ background: #ebf8ff; border-right: 4px solid #3182ce; color: #2b6cb0; padding: 12px; margin-bottom: 8px; border-radius: 6px; font-weight: 500; }}
            .btn-pdf {{ display: inline-block; background: #2b6cb0; color: white; padding: 10px 15px; border-radius: 6px; text-decoration: none; font-weight: bold; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ border: 1px solid #e2e8f0; padding: 10px; text-align: center; font-size: 14px; }}
            th {{ background: #2b6cb0; color: white; }}
            button {{ background: #38a169; color: white; border: none; padding: 10px 15px; border-radius: 6px; font-weight: bold; cursor: pointer; }}
            .designer-tag {{ margin-top: 30px; color: #718096; font-size: 13px; font-weight: 500; text-align: center; border-top: 1px solid #cbd5e0; padding-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="navbar">
            <h3 style="margin:0;">معهد الهرمل الفني</h3>
            <span style="font-size:14px;">أهلاً بك أستاذ: {user_data.get('name')} | <a href="/logout" style="color:#feb2b2; text-decoration:none; font-weight:bold;">خروج</a></span>
        </div>

        {f'<div style="background:#c6f6d5; color:#22543d; padding:10px; border-radius:6px; margin-top:10px; font-weight:bold;">{msg}</div>' if msg else ''}

        {f'<div class="card"><h4>📩 التنبيهات والإشعارات الواردة:</h4>{notifs_html}</div>' if user_data.get('notifications') else ''}

        <!-- البطاقة الشخصية الكاملة من الإكسل -->
        <div class="card" style="border-top: 4px solid #2b6cb0;">
            <h4 style="margin-top:0; color:#1a365d; border-bottom:2px solid #edf2f7; padding-bottom:8px;">📋 البطاقة الشخصية والمعلومات الإدارية الكاملة:</h4>
            <div class="info-grid">
                <div class="info-item"><b>الاسم الثلاثي:</b> {user_data.get('name')}</div>
                <div class="info-item"><b>تاريخ الميلاد:</b> {user_data.get('dob')}</div>
                <div class="info-item"><b>رقم السجل:</b> {user_data.get('register_no')}</div>
                <div class="info-item"><b>القضاء / بلدة النفوس:</b> {user_data.get('district')} / {user_data.get('town')}</div>
                <div class="info-item"><b>العنوان الحالي:</b> {user_data.get('address')}</div>
                <div class="info-item"><b>الوضع العائلي:</b> {user_data.get('marital_status')} (الأولاد: {user_data.get('children_count')})</div>
                <div class="info-item"><b>الوضع الوظيفي:</b> {user_data.get('job_status')}</div>
                <div class="info-item"><b>تاريخ المباشرة:</b> {user_data.get('start_date')}</div>
                <div class="info-item"><b>الشهادة العلمية:</b> {user_data.get('degree')}</div>
                <div class="info-item"><b>المادة التي يدرّسها:</b> {user_data.get('subject')}</div>
                <div class="info-item"><b>مجموع ساعات العقود:</b> {user_data.get('contract_hours')} ساعة</div>
                <div class="info-item"><b>رقم الهاتف:</b> {user_data.get('phone')}</div>
                <div class="info-item"><b>البنك المعني:</b> {user_data.get('bank')}</div>
                <div class="info-item"><b>رقم الـ IBAN:</b> {user_data.get('iban')}</div>
            </div>
        </div>

        <!-- جدول الحصص وبدلات النقل الشهرية -->
        <div class="card">
            <h4 style="margin-top:0; color:#1a365d;">💰 سجل الحصص وبدلات النقل الشهرية:</h4>
            <table>
                <tr>
                    <th>الشهر</th>
                    <th>عدد الحصص المنفذة</th>
                    <th>بدل النقل المستحق</th>
                </tr>
                {monthly_rows}
            </table>
        </div>

        <div class="card">
            <h4 style="margin-top:0; color:#1a365d;">📅 جدول التدريس الأسبوعي:</h4>
            {pdf_html}
        </div>

        <!-- إرسال إجابة أو طلب للإدارة -->
        <div class="card">
            <h4 style="margin-top:0; color:#1a365d;">💬 إرسال إجابة / طلب تغيب / عذر رسمي للإدارة:</h4>
            <form method="POST" enctype="multipart/form-data">
                <input type="hidden" name="action" value="send_reply">
                <textarea name="reply_message" placeholder="اكتب رسالتك أو سبب التغيب هنا..." required style="width:100%; height:80px; padding:10px; border:1px solid #cbd5e0; border-radius:6px; box-sizing:border-box; margin-bottom:10px;"></textarea>
                <label style="font-size:13px; color:#4a5568;">إرفاق تقرير طبي أو عذر رسمي (اختياري):</label><br>
                <input type="file" name="medical_report" accept=".pdf,.png,.jpg,.jpeg" style="margin:5px 0;"><br>
                <button type="submit" style="background:#2b6cb0; margin-top:10px;">إرسال الرد للإدارة</button>
            </form>
        </div>

        <div class="designer-tag">🛠️ تم تصميم وتطوير البرنامج من قبل الأستاذ محمد حسين شمص</div>

        <script>
            // تفعيل طلب الإشعارات الفورية على هاتف الأستاذ
            if ('Notification' in window) {{
                if (Notification.permission !== 'granted') {{
                    Notification.requestPermission();
                }}
            }}
        </script>
    </body>
    </html>
    '''

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)