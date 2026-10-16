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
                    .header h1 { margin: 
