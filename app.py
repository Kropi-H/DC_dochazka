import os
import sys
#import library
from flask import Flask, jsonify, request, abort, render_template, json, redirect, url_for
import gspread

#Service client credential from oauth2client
from oauth2client.service_account import ServiceAccountCredentials


app = Flask(__name__)

scope = [
'https://www.googleapis.com/auth/spreadsheets',
'https://www.googleapis.com/auth/drive'
]

#create some credential using that scope and content of startup_funding.json
credential = ServiceAccountCredentials.from_json_keyfile_name('startup_funding.json',scope)

#create gspread authorize using that credential
client = gspread.authorize(credential)

#Now will can access our google sheets we call client.open on StartupName
workers_tab = client.open_by_key('19UBIonRYVjlAPu7nWfRUD69oFeUV32sUuk_LeJK-AyM')
workers_sheet = workers_tab.worksheet('users')



@app.route('/', methods=['GET','POST'])
def index():
    user_data = workers_sheet.get_all_records()

    if request.method == 'POST':

        username = request.form['name'].strip()
        password = request.form['password'].strip()

        if (not username or not password) or (username == 'username' and password == 'password'): # If username or password is empty
            return render_template('login.html', page_title='login') # Return to login page
        else:
            user = workers_sheet.find(username)
            if not user:
                return render_template('login.html', page_title='login')  # Return to login page
            print(user, file=sys.stdout)
            user_row = user.row

            row = workers_sheet.row_values(user_row)
            if password == row[1]:
                return "yes"
            else:
                return render_template('login.html', page_title='login')
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
    pass

if __name__=='__main__':
    app.run(debug=True)