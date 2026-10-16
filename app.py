from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)

# 1. الصفحة الرئيسية (توجيه تلقائي لصفحة تسجيل الدخول)
@app.route('/')
def home():
    return redirect(url_for('login'))

# 2. صفحة تسجيل الدخول واللوحة الرسمية لـ معهد الهرمل الفني
@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # التحقق من بيانات المدير
        if username == 'admin' and password == '123456':
            return '''
            <!DOCTYPE html>
            <html lang="ar" dir="rtl">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>معهد الهرمل الفني - لوحة التحكم</title>
                <style>
                    body { font-family: system-ui, -apple-system, sans-serif; background: #edf2f7; margin: 0; padding: 20px; text-align: center; color: #2d3748; }
                    .header { background: #1a365d; color: white; padding: 25px 15px; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
                    .header h1 { margin: 0 0 8px 0; font-size: 26px; }
                    .header p { margin: 0; opacity: 0.9; font-size: 15px; }
                    .card { background: white; padding: 30px 20px; border-radius: 12px; box-shadow: 0 10px 20px rgba(0,0,0,0.08); max-width: 480px; margin: 0 auto; }
                    h2 { color: #2b6cb0; margin-top: 0; }
                    .status { background: #c6f6d5; color: #22543d; padding: 10px; border-radius: 8px; font-weight: bold; margin: 15px 0; display: inline-block; width: 100%; box-sizing: border-box; }
                    .btn { display: inline-block; width: 100%; padding: 12px; background: #e53e3e; color: white; text-decoration: none; border-radius: 6px; font-weight: bold; margin-top: 20px; box-sizing: border-box; }
                    .btn:hover { background: #c53030; }
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>معهد الهرمل الفني</h1>
                    <p>النظام الإلكتروني الرسمي لإدارة الأساتذة والساعات التعليمية</p>
                </div>
                <div class="card">
                    <h2>مرحباً بك أستاذ محمد 👋</h2>
                    <div class="status">✓ تم تسجيل الدخول بنجاح كـ (مدير النظام)</div>
                    <p style="text-align: right; line-height: 1.6; color: #4a5568;">
                        المنصة الإلكترونية السحابية للمعهد أصبحت تعمل بكفاءة كاملة ورسمية. يمكنك الآن توزيع الرابط على الأساتذة لمتابعة ساعاتهم التعليمية.
                    </p>
                    <a href="/login" class="btn">تسجيل الخروج</a>
                </div>
            </body>
            </html>
            '''
        else:
            msg = 'اسم المستخدم أو كلمة المرور غير صحيحة'

    return f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>معهد الهرمل الفني - تسجيل الدخول</title>
        <style>
            body {{ font-family: system-ui, -apple-system, sans-serif; background: #f7fafc; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
            .card {{ background: white; padding: 35px 25px; border-radius: 14px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); width: 90%; max-width: 360px; text-align: center; }}
            h2 {{ color: #1a365d; margin-top: 0; margin-bottom: 20px; font-size: 24px; }}
            input {{ width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #cbd5e0; border-radius: 6px; box-sizing: border-box; font-size: 15px; text-align: right; }}
            input:focus {{ outline: none; border-color: #3182ce; box-shadow: 0 0 0 3px rgba(66,153,225,0.2); }}
            button {{ width: 100%; padding: 12px; background: #2b6cb0; color: white; border: none; border-radius: 6px; font-weight: bold; font-size: 16px; cursor: pointer; margin-top: 12px; }}
            button:hover {{ background: #1a365d; }}
            .error {{ color: #e53e3e; margin-top: 12px; font-size: 14px; font-weight: 500; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>معهد الهرمل الفني</h2>
            <form method="POST">
                <input type="text" name="username" placeholder="اسم المستخدم" required><br>
                <input type="password" name="password" placeholder="كلمة المرور" required><br>
                <button type="submit">تسجيل الدخول</button>
            </form>
            <div class="error">{msg}</div>
        </div>
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)