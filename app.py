import os
import sys
#import library
from flask import Flask, session, jsonify, request, abort, render_template, json, redirect, url_for
import gspread

#Service client credential from oauth2client
from oauth2client.service_account import ServiceAccountCredentials


app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

scope = [
'https://www.googleapis.com/auth/spreadsheets',
'https://www.googleapis.com/auth/drive'
]

warning={}

#create some credential using that scope and content of startup_funding.json
credential = ServiceAccountCredentials.from_json_keyfile_name('startup_funding.json',scope)

#create gspread authorize using that credential
client = gspread.authorize(credential)

#Now will can access our google sheets we call client.open on StartupName
workers_tab = client.open_by_key('19UBIonRYVjlAPu7nWfRUD69oFeUV32sUuk_LeJK-AyM')
workers_sheet = workers_tab.worksheet('users')
#user_data = workers_sheet.get_all_records()

def get_current_user():
    if 'user' in session:
        user = session['user']
        return user

@app.route('/', methods=['GET','POST'])
def index():
    if request.method == 'POST':

        username = request.form['name'].strip()
        password = request.form['password'].strip()

        if (not username or not password) or (username == 'username' and password == 'password'): # If username or password is empty
            warning['login']='Pole nesmí být prázdné'
            return render_template('login.html', page_title='login', login_text=warning['login']) # Return to login page
        else:
            user = workers_sheet.find(username)
            if not user:
                warning['login'] = 'Jméno je špatné'
                return render_template('login.html', page_title='login',login_text = warning["login"])  # Return to login page
            #print(user, file=sys.stdout)
            user_row = user.row
            row = workers_sheet.row_values(user_row)
            if password == row[1]:
                session['user_name'] = row[0]
                session['role'] = row[2]
                return render_template('result.html', page_title='result',
                                       user=session.get('user_name'),
                                       role = int(session.get('role')))
            else:
                warning['login'] = 'Heslo je špatné'
                return render_template('login.html', page_title='login',login_text = warning["login"])
    else:
        return render_template('login.html', page_title='login')

@app.route('/login')
def login():
    pass

@app.route('/register_new_user')
def register_new_user():
    pass

@app.route('/new_attendence')
def new_attendence():
    pass

@app.route('/attendence_overview')
def attendence_overview():
    pass

@app.route('/logout')
def logout():
    session['name'] = None
    return redirect("/")


if __name__=='__main__':
    app.run(debug=True)