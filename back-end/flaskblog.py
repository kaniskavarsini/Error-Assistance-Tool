from flask import Flask, request, render_template, url_for, redirect,session
from flask.scaffold import F
from sql_connection import get_sql_connection
from core import *
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired,BadSignature
import re, os

app = Flask(__name__)
app.secret_key = 'drgh45dfh45yhr5y4y345sdfh'
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
app.config.from_pyfile('config.cfg')
mail = Mail(app)
connection = get_sql_connection()
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLD = 'static\program_files' 
UPLOAD_FOLDER = os.path.join(APP_ROOT, UPLOAD_FOLD)
ALLOWED_EXTENSIONS = {'py'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route("/")
def welcome():
    return render_template('welcome.html', title='Welcome')


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
	
@app.route('/uploader', methods = ['POST'])
def uploader():
   if session:
       msg=''
       if request.method == 'POST':
           f = request.files['file']
           if f.filename == '':
               return 'No selected file'
           if f and allowed_file(f.filename):
               f.save(os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(f.filename)))
               urls,error_msg=executefile(f)
               if error_msg=='no error':
                   msg='No errors found!'
                   return render_template('home.html',msg=msg)
               cursor=connection.cursor()
               for i in urls:
                   cursor.execute('insert into search_table (error_msg,search_link,username) values(%s,%s,%s)',(error_msg,i,session['username'],))
                   connection.commit()
               msg=' File uploaded successfully'
               return redirect(url_for('feedback'))
           else:
               msg='File type not allowed. Check FAQ for more details'
               return render_template('home.html', msg = msg)
       else:
            return redirect(url_for('home'))
   else:
       return render_template('login.html')

@app.route("/home")
def home():
    msg=''
    if session:
        msg='Hey there '+session['username']
        return render_template('home.html', msg=msg)
    else:
        return redirect(url_for('login'))

@app.route("/history")
def history():
    if session:
        cursor=connection.cursor()
        cursor.execute('SELECT error_msg,search_link from search_table where username= %s',(session['username'],))
        data=cursor.fetchall()
        headings=['error_msg','link']
        return render_template('history.html',headings=headings,output_data=data)
    else:
        return redirect(url_for('login'))

@app.route('/logout',methods=['GET', 'POST'])
def logout():
   session.pop('loggedin', None)
   session.pop('username', None)
   return redirect(url_for('welcome'))

@app.route("/login", methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']
        cursor = connection.cursor()
        query=('select * from user where username = %s and password = %s')
        query_data=(username,password)
        cursor.execute(query,query_data)
        account = cursor.fetchone()
        if account:
            msg = 'Logged in successfully !'
            session['loggedin'] = True
            session['username'] = request.form['username']
            return redirect(url_for('home'))
        else:
            msg = 'Incorrect username and password !'
    return render_template('login.html', msg = msg)

@app.route("/register", methods=['GET', 'POST'])
def register():
    msg = ''
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form and 'email' in request.form:
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        cursor = connection.cursor()
        cursor.execute('SELECT * FROM user WHERE username = %s', (username,))
        account = cursor.fetchone()
        if account:
            msg = 'Account already exists!'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            msg = 'Invalid email address!'
        elif not re.match(r'[A-Za-z0-9]+', username):
            msg = 'Username must contain only characters and numbers'
        elif not username or not password or not email:
            msg = 'Please fill out the form'
        else:
            cursor.execute('INSERT INTO user VALUES (%s, %s, %s)', (username, password, email,))
            connection.commit()
            msg = 'You have successfully registered!'
            return render_template('login.html', msg=msg)

    elif request.method == 'POST':
        msg = 'Please fill out the form'
    return render_template('register.html', msg=msg)

@app.route("/forgot_password", methods=['GET', 'POST'])
def forgot_password():
     m=''
     if request.method == 'POST' and 'email' in request.form:
      global email_id
      email_id = request.form['email']
      cursor = connection.cursor()
      cursor.execute('SELECT * FROM user WHERE email = %s', (email_id,))
      account=cursor.fetchone()
      if account:
            m = 'A mail has been sent to the given email address!'
            token = s.dumps(email_id)
            msg = Message('Confirm Email', sender='Error Assisstance Tool', recipients=[email_id])
            link = url_for('confirm_email', token=token, _external=True)
            msg.body = 'Your link for resetting your password is {}'.format(link)
            mail.send(msg)
            return render_template('login.html',msg=m)
      else:
            m = 'No account exists with given email address!'
     return render_template('forgot_password.html',msg=m)

@app.route("/confirm_email/<token>",methods=['GET','POST'])
def confirm_email(token):
    msg=''
    try:
        email = s.loads(token, max_age=120) 
        return redirect(url_for('reset_password'))   
    except SignatureExpired:
        msg='Time limit exceeded!'
        return render_template('forgot_password.html',msg=msg)
    except BadSignature:
        msg='Token does not match'
        return render_template('forgot_password.html',msg=msg)
    

@app.route("/reset_password",methods=['GET','POST'])
def reset_password():
    msg=''
    if request.method == 'POST' and 'password' in request.form and 'confirm_password' in request.form:
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        cursor = connection.cursor()
        if password==confirm_password:
            cursor.execute('UPDATE user SET password=%s where email=%s',(password,email_id,))
            connection.commit()
            msg = 'Password Reset Successful!'
            return render_template('login.html', msg=msg)
        else:
            msg='Password mismatch!'
    return render_template('reset_password.html',msg=msg)


@app.route("/feedback",methods=['GET','POST'])
def feedback():
    if session:
        msg=''
        if request.method == 'POST' and 'rate' in request.form and 'feedback' in request.form:
            feedback = request.form['feedback']
            rate = request.form['rate']
            cursor = connection.cursor()
            cursor.execute('insert into feedback_table (feedback,username,rate) values(%s,%s,%s)',(feedback,session['username'],rate,))
            connection.commit()
            if not rate or not feedback:
                msg = 'Please fill out the form'
            else:
                msg='Thank you for your valuable feedback!'
                return render_template('home.html',msg=msg)
        return render_template('feedback.html', msg=msg)
    else:
        return render_template('login.html')


if __name__ == '__main__':
    app.run(debug=True)

