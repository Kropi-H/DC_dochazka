import os
import sys
#import library
from flask import Flask, session, jsonify, request, abort, render_template, json, redirect, url_for
from datetime import datetime, date, timedelta, time
import gspread
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms.fields import SubmitField
from wtforms import fields, DateField, TimeField, TextAreaField, SelectField,IntegerField
from wtforms.validators import DataRequired,InputRequired
from wtforms_components import DateRange
import calendar


#Service client credential from oauth2client
from oauth2client.service_account import ServiceAccountCredentials


app = Flask(__name__)
Bootstrap(app)
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
    if 'user_name' in session:
        user = session['user_name']
        return user

class InfoForm(FlaskForm):
    startdate = DateField(label='Datum',
                          format='%Y-%m-%d',
                          default=date.today(),
                          validators=[DateRange(min=(date.today() - timedelta(days=7)), max=date.today(), message='Maximálně 7 dní nazpět!')]   )
    starttime = TimeField('Začátek',validators=[DataRequired()])
    endtime = TimeField('Konec',validators=[DataRequired()])
    selectfield = SelectField(u'Vyber činnost', choices=[("","Vyber činnost .."),('pila', 'PILA'), ('olepka', 'OLEPKA'),('jine','JINÉ')],validators=[DataRequired()])
    numberfield = IntegerField(label='Počty',render_kw={'placeholder': 'Počet desek / metrů ...'}) #, validators=[InputRequired(message=None)]
    textfield = TextAreaField(render_kw={'placeholder': 'Zde napište počet řezání PD, čištění stroje, ...'})
    submit = SubmitField(label='Uložit')



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
                return redirect(url_for('attendence_individual'))
            else:
                warning['login'] = 'Heslo je špatné'
                return render_template('login.html', page_title='login',login_text = warning["login"])
    else:
        return render_template('login.html', page_title='login')

@app.route('/login')
def login():
    pass

@app.route('/register_new_user', methods=['GET','POST'])
def register_new_user():
    user = get_current_user()
    if not user:
        return redirect('/')
    if user and request.method == 'GET':
        return render_template('new_registration.html', page_title='Nová registrace',user=session.get('user_name'),role = int(session.get('role')))
    if request.method == 'POST':

        first_name = request.form['first_name'].strip()
        last_name = request.form['second_name'].strip()
        password = request.form['password'].strip()
        working_role = int(request.form['role'].strip())
        email = request.form['email'].strip()
        phone = int(request.form['phone'].strip())

        length_of_list = len(workers_sheet.get_all_values()) # count of all rows in sheet
        new_user_row = first_name, password, working_role, first_name, last_name, email, phone, length_of_list
        workers_sheet.insert_row(new_user_row,length_of_list+1) # put data to the table on the bottom line
        return render_template('new_user_confirmation.html', page_title='Nový Uživatel',
                               new_user_data=new_user_row,
                               user=session.get('user_name'),
                               role = int(session.get('role')))

@app.route('/attendence_individual', methods=['GET', 'POST'])
def attendence_individual():

    user=session.get('user_name')
    role = int(session.get('role'))

    form = InfoForm()
    # Attencence form data request
    if request.method == 'POST' and form.validate_on_submit():
        startdate = form.startdate.data.strftime('%d.%m.%Y')
        #month_range = form.startdate.data.monthrange()
        starttime = form.starttime.data.strftime('%H:%M')
        endtime = form.endtime.data.strftime('%H:%M')
        selectfield = form.selectfield.data
        numberfield = int(form.numberfield.data)
        textfield = form.textfield.data

        hodiny_start, minuty_start = map(int, starttime.split(':'))
        hodiny_end, minuty_end = map(int,endtime.split(':'))
        come_time = time(hodiny_start, minuty_start)
        end_time = time(hodiny_end, minuty_end)
        break_time=timedelta(days=0,hours=0,minutes=30)
        work_hour_limit = timedelta(days=0, hours=4, minutes=0)
        timedelta1 = timedelta(hours = come_time.hour, minutes = come_time.minute)
        timedelta2 = timedelta(hours=end_time.hour, minutes=end_time.minute)
        delta_time = timedelta2-timedelta1

        if delta_time > work_hour_limit:
            time_result = delta_time-break_time
        else:
            time_result = delta_time

        # Získání hodin a minut z rozdílu
        hodiny_rozdil = time_result.seconds // 3600
        minuty_rozdil = (time_result.seconds // 60) % 60
        odd_time= time(hodiny_rozdil,minuty_rozdil)

        attendence_tab = client.open_by_key('1FiDYtNRIa4mMB6mZdDhxzNxcPTklPQhj8Of3PcqDbyc') # Access to google sheets
        attendece_sheet = attendence_tab.worksheet(user) # Chose current user sheet
        current_date = attendece_sheet.find(startdate) # Find current day cell
        date_row = current_date.row # Current day row

        cell_range = f'B{date_row}:G{date_row}' # Cell range as string
        attendece_sheet.update(cell_range, [[str(starttime),str(endtime),str(time_result),selectfield,numberfield,textfield]], value_input_option='USER_ENTERED' )


        return redirect('attendence_overview')

    return render_template('attendence_individual.html', page_title='Zadání docházky', user = user, role=role, form=form)

@app.route('/attendence_overview', methods=['GET', 'POST'])
def attendence_overview():
    user=session.get('user_name')
    role = 1

    if request.method == 'GET':
        months = {'červenec':'01.07.2023'}
        attendence_tab = client.open_by_key('1FiDYtNRIa4mMB6mZdDhxzNxcPTklPQhj8Of3PcqDbyc') # Access to google sheets
        attendece_sheet = attendence_tab.worksheet(user) # Chose current user sheet
        current_date = attendece_sheet.find(months['červenec']) # Find current day cell
        date_row = current_date.row # Current day row
        #print(date_row, file=sys.stdout)
        row_value = attendece_sheet.row_values(current_date.row)

        months_values = attendece_sheet.batch_get(('A183:G213',))
        #return '{}'.format(months_values)


        return render_template('attendece_overview.html', page_title = 'Přehled', user = user, role = role, user_value = row_value, user_month_values = months_values)

@app.route('/logout')
def logout():
    session['name'] = None
    return redirect("/")


if __name__=='__main__':
    app.run(debug=True)
