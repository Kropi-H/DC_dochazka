import json
import os
import tables
from flask import Flask, session, request, render_template, redirect, url_for, send_from_directory
from datetime import datetime, date, timedelta, time
import gspread
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms.fields import SubmitField
from wtforms import DecimalField, TimeField, TextAreaField, SelectField, widgets, IntegerField, PasswordField, DateField, validators, StringField, BooleanField, TelField, EmailField
from wtforms.validators import DataRequired, ValidationError, Regexp, EqualTo
from wtforms_components import DateRange
import hashlib
import calendar
import csv
import math
import re
import threading
import zip_and_send
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit


# Service client credential from oauth2client
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)
Bootstrap(app)
app.config['SECRET_KEY'] = os.urandom(24)

scope = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
# Create some credential using that scope and content of startup_funding.json
credential = ServiceAccountCredentials.from_json_keyfile_name('startup_funding.json', scope)

# Create gspread authorize using that credential
client = gspread.authorize(credential)


# Now will can access our google sheets we call client.open on StartupName
workers_tab = client.open_by_key(tables.cridentials_table['users'])
workers_sheet = workers_tab.worksheet('users')

delay_days_user_input = 5

# Get current year
currentYear = datetime.now().year

# Target searching strings
target_strings = ['pila', 'olepka', 'zavoz', 'sklad', 'obchod', 'kancl', 'jine', '']

first_january = datetime(currentYear, 1, 1)
last_december = datetime(currentYear, 12, 31)

# months
months = {1: '01.01.2024', 2: '01.02.2024', 3: '01.03.2024', 4: '01.04.2024', 5: '01.05.2024', 6: '01.06.2024',
                  7: '01.07.2024', 8: '01.08.2024', 9: '01.09.2024', 10: '01.10.2024', 11: '01.11.2024', 12: '01.12.2024'}
months_name=['Leden', 'Únor', 'Březen', 'Duben', 'Květen', 'Červen', 'Červenec', 'Srpen', 'Září', 'Říjen', 'Listopad', 'Prosinec']

def open_statistics_json_file():
    # funkce pro načtení dat ze souboru statistics.json
    try:
        with open("static/statistics.json", "r", encoding='utf-8') as infile:
            existing_data = json.load(infile)
    except FileNotFoundError:
        existing_data = {}
    return(existing_data)


def get_user_login_list():
    try:
        lines_list = []
        f = open('static/login.csv', 'r', encoding='utf-8')
        for line in f.readlines():
            hodnoty = line.strip().split(';')
            lines_list.append(hodnoty)
        f.close()
        return lines_list
    except:
        pass
    finally:
        f.close()

def get_current_user():
    user_session = {}
    if 'user_name' in session:
        user_session['user'] = session['user_name']
        user_session['role'] = session['role']
        user_session['access'] = session['access']
        return user_session

def user_records(user):
    user_records_list = []
    user_list = read_csv('static/login.csv')
    # Vytvořte slovník pro uchování počtu výskytů jmen a seznamu dat
    count_dict = {}

    # Projděte vnořený list a aktualizujte slovníky
    for item in user_list:
        name, the_date, entrance_count, info_count = item[0], item[1], item[2], item[3]
        count_dict[name] = name
        count_dict[the_date] = the_date
        count_dict[entrance_count] = entrance_count
        count_dict[info_count]=info_count

    # Případ 1: Seznam všech jmen s předposledními daty a počtem výskytů
    if user['role'] == 3:
        for value in user_list:
            name = value[0]
            the_date = value[1]
            entrance_count = value[2]
            info_count = value[3]
            user_records_list.append(dict({'name':name, 'the_date':the_date, 'entrance_count':entrance_count, 'info_count':int(info_count)}))


    # Případ 2: Získání předposledního data a počtu výskytů pro konkrétní jméno
    elif user['role'] != 3:
        target_name = user['user']  # Změňte na požadované jméno
        for value in user_list:
            if target_name == value[0]:
                name = value[0]
                the_date = value[1]
                entrance_count = value[2]
                info_count = value[3]
                user_records_list.append(dict({'name':name, 'the_date':the_date, 'entrance_count':entrance_count, 'info_count':int(info_count)}))

    return user_records_list

@app.context_processor
def inject_globals():
    return dict({
        'current_month': f'{datetime.today().month:02d}'
    })

def read_csv(file_path):
    data = []
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile, delimiter=';')
        for row in reader:
            data.append(row)
    return data

def write_csv(file_path, data):
    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, delimiter=';')
        writer.writerows(data)

def find_and_update_or_append(data, name):
    current_datetime = datetime.now().strftime("%d.%m.%Y/%H:%M")
    found = False

    for i, row in enumerate(data):
        if len(row) >= 4 and row[0] == name:
            info_count = int(row[3])-1 if int(row[3]) > 0 else 0
            data[i] = [name, current_datetime, str(int(row[2]) + 1), str(info_count)]
            found = True
            break

    if not found:
        data.append([name, current_datetime, '1', '3'])


@app.route('/', methods=['GET','POST'])
def index():
    if request.method == 'POST':

        warning={}

        username = request.form['name'].strip()
        password = request.form['password'].strip()

        if (not username or not password) or (username == 'username' and password == 'password'): # If username or password is empty
            warning['login'] = 'Pole nesmí být prázdné'
            return render_template('login.html', page_title='login', login_text=warning['login']) # Return to login page
        else:
            user = workers_sheet.find(username)
            if not user:
                warning['login'] = 'Jméno je špatné'
                return render_template('login.html', page_title='login',login_text = warning["login"])  # Return to login page

            user_row = user.row
            row_data = workers_sheet.row_values(user_row)

            if hashlib.md5(password.encode()).hexdigest() == row_data[1]:
                for user_login_row in get_user_login_list():
                    if user_login_row[0] == row_data[4]:
                        session['access'] = user_login_row[3]
                session['user_name'] = row_data[4]
                session['role'] = int(row_data[2])

                # CSV path
                file_path = 'static/login.csv'
                # Read CSV file
                csv_data = read_csv(file_path)
                # Najděte a aktualizujte nebo přidejte záznam
                find_and_update_or_append(csv_data, row_data[4])
                # Write into CSV file
                write_csv(file_path, csv_data)
                try:
                    find_current_date_in_google_worker_sheet(session['user_name'], 'workers')
                    return redirect(url_for('attendance_individual'))
                except gspread.exceptions.WorksheetNotFound:
                    return redirect(url_for('attendance_all'))

                #if session['role'] == 5:
                #    return redirect(url_for('contracts'))
                #elif session['role'] == 4:
                #    return redirect(url_for('attendance_all'))
                #else:
                #    return redirect(url_for('attendance_individual'))

            else:
                warning['login'] = 'Heslo je špatné'
                return render_template('login.html', page_title='login', login_text=warning["login"])
    else:
        return render_template('login.html', page_title='login')

class form_check_pass(FlaskForm):
    def check_equal(form, field):
        if form.oldPassword.data and not form.newPassword.data and not form.checkPassword.data:
            raise ValidationError('Musí být vyplněno vše!')

    def check_current_password(form, field):
        input_pass = form.oldPassword.data
        user = get_current_user()['user']
        user_row = workers_sheet.find(user).row
        user_pass = workers_sheet.acell(f'B{user_row}').value
        if input_pass and (user_pass != hashlib.md5(input_pass.encode()).hexdigest()):
            raise ValidationError('Chybné heslo!')

    def first_name_check(form, field):
        name_used = int()
        input_name = form.first_name.data.strip()
        user = get_current_user()['user']
        workers_sheet_values = workers_sheet.get_all_values()
        for value in workers_sheet_values:
            if input_name == value[0] and user != value[4]:
                name_used += 1
        if name_used:
            raise ValidationError('Uživatelské jméno už je použito!')

    first_name = StringField("Uživatelské jméno (pro přihlášení)", validators=[first_name_check], render_kw={"placeholder": "JohnD"})
    last_name = StringField("Příjmení",render_kw={"placeholder": "Doe"})
    email = EmailField("Email",render_kw={"placeholder": "johndoe@frk.com"})
    phone_number = TelField('Tel. číslo',render_kw={"placeholder": "123456789"})
    oldPassword = PasswordField('Staré heslo', validators=[check_equal, check_current_password])
    newPassword = PasswordField('Nové heslo')
    checkPassword = PasswordField('Nové heslo znovu ', validators=[EqualTo('newPassword', message='Hesla se musí shodovat!')])
    submit = SubmitField(label='Uložit')


@app.route('/change_password', methods=['GET','POST'])
def change_password():
    user = get_current_user()
    #worker_name = request.args.get('pass_name')
    if not user:
       return redirect('/')

    worker_values = workers_sheet.get_all_values()

    form = form_check_pass()
    if request.method == 'POST' and form.validate_on_submit():
        inputName = request.form['first_name'].strip()
        email = request.form['email'].strip()
        phoneNumber = request.form['phone_number'].strip()
        newPassword = request.form['newPassword'].strip()

        for value in worker_values:
            if (user['user'] == value[4]):
                #value[1] == hashlib.md5(oldPassword.encode()).hexdigest()) and (newPassword == checkPassword)
                inputName = value[0] if not inputName else inputName
                email = value[5] if not email else email
                phoneNumber = value[6] if not phoneNumber else phoneNumber
                newPassword = value[1] if not newPassword else hashlib.md5(newPassword.encode()).hexdigest()
                cell_row = workers_sheet.find(user['user']).row

                workers_sheet.update(f'A{cell_row}', [[inputName,
                                                      f'{newPassword}',
                                                      value[2],
                                                      value[3],
                                                      value[4],
                                                      email,
                                                      phoneNumber]], value_input_option='USER_ENTERED')

                #workers_sheet.update_cell(cell.row, 2, hashlib.md5(newPassword.encode()).hexdigest())
                return render_template('result.html',
                                    title='Změna akceptována',
                                    worker_list=user_records(user),
                                    user=user['user'],
                                    role=int(user['role']),
                                    access = int(user['access']),
                                    workers_list=worker_values,
                                    head_text=f'Údaje pro {user["user"]} uloženy!',
                                    form=form,
                                    target_page = f'change_password')

            #return 'Something went wrong!'

    for value in worker_values:
        if value[4] == user['user']:
            form.first_name.render_kw = {"placeholder": value[0]}
            form.last_name.render_kw = {"placeholder": value[4]}
            form.email.render_kw = {"placeholder": value[5]}
            form.phone_number.render_kw = {"placeholder": f'{value[6]}'}

    return render_template('change_password.html',
                           title='Změna hesla',
                           worker_list=user_records(user),
                           user=user['user'],
                           role=int(user['role']),
                           access = int(user['access']),
                           workers_list=worker_values,
                           head_text=f'Změna uživatele {user["user"]}',
                           form = form)

@app.route('/register_new_user', methods=['GET','POST'])
def register_new_user():
    user = get_current_user()

    if not user or user['role'] != 3:
        return redirect('/')

    if user and request.method == 'GET':
        return render_template('new_registration.html',
                               page_title='Nová registrace',
                               worker_list=user_records(user),
                               user=user['user'],
                               role=int(user['role']),
                               access = int(user['access']))

    if request.method == 'POST':

        first_name = request.form['first_name'].strip()
        last_name = request.form['second_name'].strip()
        password = hashlib.md5(request.form['password'].strip().encode()).hexdigest()
        working_role = int(request.form['role'].strip())
        email = request.form['email'].strip()
        phone = int(request.form['phone'].strip())

        length_of_list = len(workers_sheet.get_all_values()) # count of all rows in sheet
        new_user_row = first_name, password, working_role, first_name, last_name, email, phone, length_of_list
        workers_sheet.insert_row(new_user_row,length_of_list+1) # put data to the table on the bottom line

        # Vytvoření nového listu (kopírováním listu 'mustr') v tabulce google pod jménem uživatele
        attendence_tab = client.open_by_key(tables.workers_table['workers'])
        len_attendece_tab = len(attendence_tab.worksheets())
        muster_sheet = attendence_tab.worksheet('mustr')
        attendence_tab.duplicate_sheet(source_sheet_id=muster_sheet.id,
                                       insert_sheet_index= len_attendece_tab-1,
                                       new_sheet_name=last_name)

        return render_template('new_user_confirmation.html', page_title='Nový Uživatel',
                               new_user_data=new_user_row,
                               worker_list=user_records(user),
                               user=user['user'],
                               role=int(user['role']),
                               access = int(user['access']))

#!-------------------- Attendance_individual --------------------!
class AttendanceIndividualForm(FlaskForm):
      def validate_end_date(self, field):

          if datetime.strptime(self.startdate.raw_data[0], '%Y-%m-%d') > datetime.today() or datetime.strptime(self.startdate.raw_data[0], '%Y-%m-%d') < datetime.today() - timedelta(days=delay_days_user_input):
              raise ValidationError(f"Max {delay_days_user_input} dny zpět")

      def start_time():
          specific_time = datetime.now().replace(hour=15, minute=0, second=0)
          morning_start_time = datetime.now().replace(hour=6, minute=0, second=0)
          afternoon_start_time = datetime.now().replace(hour=13, minute=30, second=0)
          friday_afternoon_start_time = datetime.now().replace(hour=9, minute=30, second=0)
          if datetime.now() < specific_time:
              return morning_start_time
          elif datetime.now().weekday() == 4:
              return friday_afternoon_start_time
          else:
              return afternoon_start_time
      def end_time():
          specific_time = datetime.now().replace(hour=16, minute=00, second=0)
          morning_end_time = datetime.now().replace(hour=14, minute=30, second=0)
          afternoon_end_time = datetime.now().replace(hour=22, minute=0, second=0)
          friday_morning_end_time = datetime.now().replace(hour=18, minute=0, second=0)
          if datetime.now() < specific_time:
              return morning_end_time
          elif datetime.now().weekday() == 4:
              return friday_morning_end_time
          else:
              return afternoon_end_time
      def check_number_value(form, field):
          if form.selectfield.data in ['olepka','pila'] and form.numberfield.data == None:
              raise ValidationError("Je nutné zadat číslo nebo vyber jinou činnost!")

      startdate = DateField(label='Datum',
                            default=date.today,
                            validators=[
                                DataRequired(),
                                validate_end_date
                            ])
      starttime = TimeField('Začátek',
                            default=start_time,
                            validators=[DataRequired()])
      endtime = TimeField('Konec',
                          default=end_time,
                          validators=[DataRequired()])
      selectfield = SelectField(u'Vyber činnost', choices=[("", "Vyber činnost .."), ('pila', 'PILA'), ('olepka', 'OLEPKA'), ('sklad', 'SKLAD'), ('obchod', 'OBCHOD'), ('zavoz', 'ZÁVOZ'), ('jine', 'JINÉ')],
                                validators=[DataRequired(),check_number_value])
      numberfield = DecimalField(label='Počty', render_kw={'placeholder': 'Počet desek / metrů ...'},
                                 validators=[validators.Optional(strip_whitespace=True)])
      textfield = TextAreaField(render_kw={'placeholder': 'Zde napište počet řezání PD, čištění stroje, ...'})
      submit = SubmitField(label='Uložit')


def split_time(time): # Function to split time to useable format
    if not time:
        return int(),int()
    else:
        return map(int, time.split(':'))
def work_time_count(starttime,endtime): # Function for calculate working time
    hodiny_start, minuty_start = split_time(starttime)
    hodiny_end, minuty_end = split_time(endtime)
    # Count user work time
    come_time = time(hodiny_start, minuty_start)
    end_time = time(hodiny_end, minuty_end)

    break_time = timedelta(days=0,hours=0,minutes=30)
    work_time = timedelta(days=0, hours=8, minutes=0)
    work_hour_limit = timedelta(days=0, hours=4, minutes=30)

    timedelta1 = timedelta(hours = come_time.hour, minutes = come_time.minute)
    timedelta2 = timedelta(hours=end_time.hour, minutes=end_time.minute)
    delta_time = timedelta2-timedelta1


    if delta_time >= work_hour_limit:
        time_result = delta_time-break_time
    else:
        time_result = delta_time

    if time_result > work_time:
        over_work_time = time_result-work_time
    else:
        over_work_time = ""

    return ':'.join(str(time_result).split(':')[:2]), ':'.join(str(over_work_time).split(':')[:2])

# Find current day in google sheet
def find_current_date_in_google_worker_sheet(user, works_sheet_table):
    attendence_tab = client.open_by_key(tables.workers_table[works_sheet_table]) # Access to google sheets
    return attendence_tab.worksheet(user) # Chose current user sheet

# Function for saving data to google sheet
def save_user_data_to_google_sheet(user,
                                   startdate,
                                   starttime=None,
                                   endtime=None,
                                   time_result=None,
                                   over_work_time=None,
                                   selectfield=None,
                                   numberfield=None,
                                   textfield=None,
                                   vybrane_prescasy=None,
                                   proplacene_prescasy=None,
                                   vybrana_dovolena=None,
                                   nemoc_lekar=None,
                                   neplacene_volno=None,
                                   placene_volno_krev=None,
                                   svatek=None,
                                   prekazka=None,
                                   doprovod_k_lekari=None,
                                   pohreb=None):

    # Save user data to Google Sheet
    attendece_sheet = find_current_date_in_google_worker_sheet(user, 'workers')
    current_date = attendece_sheet.find(startdate) # Find current day cell
    date_row = current_date.row # Current day row

    cell_range = f'B{date_row}:V{date_row}' # Cell range as string

    if starttime != "": attendece_sheet.update(f'B{date_row}',starttime,value_input_option='USER_ENTERED')
    if endtime != "": attendece_sheet.update(f'C{date_row}',endtime,value_input_option='USER_ENTERED')
    if time_result != "": attendece_sheet.update(f'D{date_row}',time_result,value_input_option='USER_ENTERED')
    if time_result != "": attendece_sheet.update(f'E{date_row}',over_work_time,value_input_option='USER_ENTERED')
    if selectfield != "": attendece_sheet.update(f'F{date_row}',selectfield,value_input_option='USER_ENTERED')
    if numberfield != "": attendece_sheet.update(f'G{date_row}',numberfield,value_input_option='USER_ENTERED')
    if textfield != "": attendece_sheet.update(f'H{date_row}',textfield,value_input_option='USER_ENTERED')
    if vybrane_prescasy != "": attendece_sheet.update(f'M{date_row}',vybrane_prescasy,value_input_option='USER_ENTERED')
    if proplacene_prescasy != "": attendece_sheet.update(f'N{date_row}',proplacene_prescasy,value_input_option='USER_ENTERED')
    if vybrana_dovolena != "": attendece_sheet.update(f'O{date_row}',vybrana_dovolena,value_input_option='USER_ENTERED')
    if nemoc_lekar != "": attendece_sheet.update(f'P{date_row}',nemoc_lekar,value_input_option='USER_ENTERED')
    if neplacene_volno != "": attendece_sheet.update(f'Q{date_row}',neplacene_volno,value_input_option='USER_ENTERED')
    if placene_volno_krev != "": attendece_sheet.update(f'R{date_row}',placene_volno_krev,value_input_option='USER_ENTERED')
    if svatek != "": attendece_sheet.update(f'S{date_row}',svatek,value_input_option='USER_ENTERED')
    if prekazka != "": attendece_sheet.update(f'T{date_row}',prekazka,value_input_option='USER_ENTERED')
    if doprovod_k_lekari != "": attendece_sheet.update(f'U{date_row}',doprovod_k_lekari,value_input_option='USER_ENTERED')
    if pohreb != "": attendece_sheet.update(f'V{date_row}',pohreb,value_input_option='USER_ENTERED')


@app.route('/attendance_individual', methods=['GET', 'POST'])
def attendance_individual():

    user = get_current_user()

    if not user:
       return redirect('/')

    form = AttendanceIndividualForm()
    # Attencence form data request
    if form.validate_on_submit():
        startdate = form.startdate.data.strftime('%d.%m.%Y')
        starttime = form.starttime.data.strftime('%H:%M')
        endtime = form.endtime.data.strftime('%H:%M')
        selectfield = form.selectfield.data
        numberfield = form.numberfield.data if form.numberfield.data != None else 0
        textfield = form.textfield.data
        
        # Clean up user input
        if selectfield == 'olepka' or selectfield == 'pila':
            if numberfield <= 0:
                textfield += f' ! Zadáno {selectfield} a {str(numberfield)} !'
                selectfield = 'jine'
                numberfield = ""
            else:
                numberfield = str(numberfield).replace('.',',')
        else:
            numberfield = None


        time_result, over_work_time = work_time_count(starttime,endtime)

        save_user_data_to_google_sheet(user['user'],startdate,starttime,endtime,time_result,over_work_time,selectfield,numberfield,textfield)

        return redirect(url_for('attendance_overview',pass_date=datetime.now().month))

    return render_template('attendance_individual.html',
                           select_month=datetime.now().month,
                           page_title='Zadání docházky',
                           worker_list=user_records(user),
                           user=user['user'],
                           role=int(user['role']),
                           form=form,
                           delay_days_user_input=delay_days_user_input)

def sum_of_repetition(name, where_to_find):
            for i in where_to_find:
                count = []
                for t in i:
                    if len(t) > 1:
                        if name in t:
                            t[6] = re.sub(r'(?<=[0-9./])\s+(?=[0-9./])','',t[6])
                            count.append(float(t[6].strip(' ').replace(',','.')))
            if not count:
                return(0)
            else:
                return(math.ceil(sum(count)/len(count)))

def find_strings_in_nested_list(nested_list, target_strings):
    result = set()  # Použijeme množinu pro unikátní výsledky

    def recursive_search(nested_list):
        for item in nested_list:
            if isinstance(item, list):
                recursive_search(item)
            else:
                for target_string in target_strings:
                    if target_string in item:
                        result.add(item)  # Přidáme do množiny místo seznamu

    recursive_search(nested_list)
    return result  # Množina automaticky odstraní duplicity


def create_dict(data):
    months_dict = {}
    for row in data[1:-5]:
        row_filtered = [value if value != '' else None for value in row]
        date = row_filtered[0]
        day_data = dict(zip(data[0], row_filtered[0:]))

        # Rozdělení datumu na den, měsíc a rok
        day, month, year = map(int, date.split('.'))
        month_key = f"{year}-{month:02d}-{day:02d}"

        # Přidání klíče "Den" s číslem dne
        day_data['Den'] = f'{day:02d}'

        # Přidání do slovníku pod klíčem měsíce
        if month_key not in months_dict:
            months_dict[month_key] = {}
        months_dict[month_key][f'{day:02d}'] = day_data
    return months_dict

def parse_time(time_str):
    try:
        if time_str:
            time_components = [int(component) for component in time_str.split(':')]
            return timedelta(hours=time_components[0], minutes=time_components[1])
        else:
            return timedelta()
    except (ValueError, IndexError):
        # Pokud dojde k chybě při parsování, vrátíme timedelta() (nula)
        return timedelta()

def sum_hours_in_date_range(data, start_date, end_date, looking_string, second_looking_string=None,third_looking_string=None, specific_employee=None):
    result = {}

    def sum_hours(employee_data):
        total_hours = timedelta()
        for date_data in employee_data.values():
            for entry in date_data.values():
                total_hours += parse_time(entry.get(looking_string, ''))

                if second_looking_string:
                    total_hours -= parse_time(entry.get(second_looking_string, ''))

                if third_looking_string:
                    total_hours -= parse_time(entry.get(third_looking_string, ''))

        return total_hours

    for employee, employee_data in data.items():
        if specific_employee and specific_employee != employee:
            continue

        employee_total_hours = timedelta()

        for date, date_data in employee_data.items():
            if start_date <= date <= end_date:
                employee_total_hours += sum_hours({date: date_data})

        total_seconds = employee_total_hours.total_seconds()
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        total_hours_formatted = f'{hours:02}:{minutes:02}'
        result = total_hours_formatted

        if specific_employee:
            break

    return result

def find_user_note(user):
    notes = ""
    path = 'static/notes.csv'
    mode = 'r' if os.path.exists(path) else 'a+'
    try:
        with open(path, mode, newline='\r\n', encoding='utf-8') as csvfile:
            csvdata = csv.reader(csvfile)
            for row in csvdata:
                row = row[0].split(';')
                if row[0] == user:
                    notes = row[1]
    except FileNotFoundError:
        return('Soubor neexistuje')
    if not notes:
        notes = ""
    return(notes)
def save_user_note(user,user_note):
    with open('static/notes.csv', 'r',newline='\n', encoding='utf-8') as infile:
        reader = csv.reader(infile)
        rows = list(reader)
        newrow=list()
        nemefound=False
        for row in rows:
            if row[0].split(';')[0] == user:
                row = [f'{user};{user_note}']
                nemefound = True
            newrow.append(row)
        if not nemefound:
            newrow.append([f'{user};{user_note}'])

    with open('static/notes.csv', 'w',newline='\n', encoding='utf-8') as outfile:
        writer = csv.writer(outfile)
        writer.writerows(newrow)

@app.route('/attendance_overview/<int:pass_date>', methods=['GET', 'POST'])
def attendance_overview(pass_date):
    user = get_current_user()

    if not user:
       return redirect('/')

    if request.method == 'GET':

        currentMonth = pass_date

        currentMonthRange = calendar.monthrange(currentYear,currentMonth)[1]
        attendece_sheet = find_current_date_in_google_worker_sheet(user['user'], 'workers')

        current_date = attendece_sheet.find(months[currentMonth]) # Find current day cell
        date_row = current_date.row # Current day row

        row_value = attendece_sheet.row_values(current_date.row)
        current_table_range = f'A{date_row}:V{(date_row+currentMonthRange)-1}'
        months_values = attendece_sheet.batch_get((current_table_range,))

        employee_sheet = attendece_sheet.get_all_values()

        found_strings = find_strings_in_nested_list(months_values, target_strings)

        # Načtení existujících dat ze souboru, pokud soubor existuje
        existing_data = open_statistics_json_file()

        # Vytvoření slovníků
        months_dict = {user['user']: create_dict(employee_sheet)}

        # Aktualizace existujících dat
        existing_data.update(months_dict)

        with open(f"static/statistics.json", "w", encoding='utf-8') as outfile:
            json.dump(existing_data, outfile, skipkeys=False, ensure_ascii=True, check_circular=True, allow_nan=True, cls=None, indent=2, separators=None, default=True, sort_keys=False )


        this_month_first, this_month_last = calendar.monthrange(currentYear, currentMonth)

        return render_template('attendance_overview.html',
                               page_title = 'Přehled',
                               worker_list=user_records(user),
                               user=user['user'],
                               role=int(user['role']),
                               access = int(user['access']),
                               user_value=row_value,
                               user_month_values=months_values,
                               target_page='attendance_overview',
                               month_name=months_name[int(pass_date)-1],
                               found_strings=found_strings,
                               rep_glue_count=sum_of_repetition('olepka', months_values),
                               rep_cut_count=sum_of_repetition('pila', months_values),
                               prescasy=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Přesčasy','','',user['user']),
                               prescasy_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Přesčasy','','',user['user']),
                               prescasy_total_odecet=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Přesčasy','Proplacené přesčasy','Vybrané přesčasy',user['user']),
                               hodiny=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Hodiny/Den','','',user['user']),
                               hodiny_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Hodiny/Den','','',user['user']),
                               vybrane_prescasy=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Vybrané přesčasy','','',user['user']),
                               vybrane_prescasy_total=sum_hours_in_date_range(existing_data,  f'{first_january}', f'{last_december}', 'Vybrané přesčasy','','',user['user']),
                               proplacene_prescasy=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Proplacené přesčasy','','',user['user']),
                               proplacene_prescasy_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Proplacené přesčasy','','',user['user']),
                               vybrana_dovolena=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Vybraná dovolená','','',user['user']),
                               vybrana_dovolena_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Vybraná dovolená','','',user['user']),
                               nemoc_lekar=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Nemoc/Lékař','','',user['user']),
                               nemoc_lekar_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Nemoc/Lékař','','',user['user']),
                               neplacene_volno=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Neplacené volno','','',user['user']),
                               neplacene_volno_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Neplacené volno','','',user['user']),
                               placene_volno=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Placené volno/Krev','','',user['user']),
                               placene_volno_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Placené volno/Krev','','',user['user']),
                               svatek=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Svátek','','',user['user']),
                               svatek_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Svátek','','',user['user']),
                               prekazka=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Překážka na straně zaměstnavatele','','',user['user']),
                               prekazka_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Překážka na straně zaměstnavatele','','',user['user']),
                               doprovod=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Doprovod k lékaři','','',user['user']),
                               doprovod_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Doprovod k lékaři','','',user['user']),
                               pohreb=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Pohřeb','','',user['user']),
                               pohreb_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Pohřeb','','',user['user']),
                               user_note = find_user_note(user["user"])
                               )

@app.route('/generate_pdf', methods=['GET'])
def generate_pdf():
    pass

class AttendanceAllForm(FlaskForm):
    def validate_default_date():
        return datetime.today() - timedelta(days=1)

    startdate = DateField(label='Od',
                          format='%Y-%m-%d',
                          default=validate_default_date,
                          validators=[DateRange(),DataRequired()])
    enddate = DateField(label='Do',
                        format='%Y-%m-%d',
                        default=validate_default_date,
                        validators=[DateRange(),DataRequired()])

    submit = SubmitField(label='Zobrazit')

    def validate(self, **kwargs):
        # Standard validators
        rv = FlaskForm.validate(self)
        # Ensure all standard validators are met
        if rv:
            # Ensure end date >= start date
            if self.startdate.data > self.enddate.data:
                self.enddate.errors.append('Zkus to znovu!')
                return False
            return True
        return False

@app.route('/attendance_all', methods=['GET', 'POST'])
def attendance_all():

    user = get_current_user()

    if not user or user['role'] < 2:
       return redirect('/')

    existing_data = open_statistics_json_file()

        # Rekurzivní funkce pro odstranění klíčů s hodnotou None

    def remove_none_values(d):
        for key, value in list(d.items()):
            if value is None:
                d[key] = ""
            elif isinstance(value, dict):
                remove_none_values(value)

    remove_none_values(existing_data)

    form = AttendanceAllForm()

    def date_range_text(startdate, enddate):
        return f'{startdate.strftime("%d.%m.%Y")} - {enddate.strftime("%d.%m.%Y")}'

    #yesterday_date = datetime.now().strftime("%Y-%m-%d") - timedelta(days=1)
    yesterday_date = str((datetime.now().date() - timedelta(days=1)))

    this_month = datetime.today().month


    this_month_first, this_month_last = calendar.monthrange(currentYear, this_month)

    worker_list = []
    for worker, value in existing_data.items():
        worker_list.append(worker)

    def konvertovat_na_cisla(slovnik):
        for klic, hodnota in slovnik.items():
            if isinstance(hodnota, dict):
                # Pokud je hodnota slovníku, zavoláme funkci rekurzivně pro tuto hodnotu.
                konvertovat_na_cisla(hodnota)
            elif isinstance(hodnota, list):
                # Pokud je hodnota seznam, zavoláme funkci rekurzivně pro každý prvek seznamu.
                for i, prvek in enumerate(hodnota):
                    if isinstance(prvek, dict):
                        konvertovat_na_cisla(prvek)
            elif isinstance(hodnota, str):
                try:
                    # Pokusíme se převést řetězec na číslo.
                    cislo = int(hodnota)
                    slovnik[klic] = cislo
                except ValueError:
                    # Pokud selže převod, ponecháme hodnotu nezměněnou.
                    pass

    def sum_of_activitiy_count(my_dict, start_date, end_date, activity_count, activity):
        total_count = 0  # Celkový součet počtu činností pro všechny uživatele

        for user, user_data in my_dict.items():
            user_count = 0  # Součet počtu činností pro konkrétního uživatele

            for month, month_data in user_data.items():
                for day, day_data in month_data.items():
                    date_str = f'{month}'

                    if start_date <= date_str <= end_date:
                        if day_data['Činnost'] == activity:
                            if day_data[activity_count] == '':
                                pass
                            elif activity_count in day_data:
                                day_data[activity_count] = re.sub(r'(?<=[0-9./])\s+(?=[0-9./])','',day_data[activity_count])
                                user_count += math.ceil(float(day_data[activity_count].replace(',','.')))

            total_count += user_count
        return total_count


    def get_values_in_date_range(data_dict,name_arr, start_day, end_day):
        new_data = {}
        # Iterace přes slovník
        for jmeno, name_data in data_dict.items():
            # Kontrola, zda je jméno mezi hledanými
            if jmeno in name_arr:
                # Inicializace slovníku pro dané jméno
                new_data[jmeno] = {}
                # Iterace přes data pro dané jméno
                for month, month_value in name_data.items():
                    # Kontrola rozsahu datumů
                    if start_day <= month <= end_day:
                        new_data[jmeno][month] = month_value
        return new_data

    def worker_sum_total_awg_data(existing_data,start_date,end_date):
        worker_data = {}
        for worker, worker_item in existing_data.items():
            worker_data[worker] = {}
            worker_olepka_count = 0
            worker_olepka_sum = 0
            worker_pila_count = 0
            worker_pila_sum = 0
            for month, month_item in worker_item.items():
                for day, day_item in month_item.items():
                    date_str = f'{month}'
                    if start_date <= date_str <= end_date:
                        if day_item['Činnost'] == 'olepka':
                            worker_olepka_count += 1
                            if day_item['Počet činnosti'] != "":
                                day_item['Počet činnosti'] = re.sub(r'(?<=[0-9./])\s+(?=[0-9./])','',day_item['Počet činnosti'])
                                worker_olepka_sum += math.ceil(float(day_item['Počet činnosti'].replace(',','.')))

                        if day_item['Činnost'] == 'pila':
                            worker_pila_count += 1
                            if day_item['Počet činnosti'] != "":
                                day_item['Počet činnosti'] = re.sub(r'(?<=[0-9./])\s+(?=[0-9./])','',day_item['Počet činnosti'])
                                worker_pila_sum += math.ceil(float(day_item['Počet činnosti'].replace(',','.')))

                if worker_olepka_count != 0:
                    worker_data[worker]['olepka']= round(worker_olepka_count)
                    worker_data[worker]['total olepeno']= worker_olepka_sum
                    if worker_olepka_sum != 0:
                        worker_data[worker]['awg olepka']=round(worker_olepka_sum/worker_olepka_count)

                if worker_pila_count != 0:
                    worker_data[worker]['pila']= worker_pila_count
                    worker_data[worker]['total narezano']= worker_pila_sum
                    if worker_pila_sum != 0:
                        worker_data[worker]['awg pila']=round(worker_pila_sum/worker_pila_count)
        return worker_data

    if request.method == 'POST' and form.validate_on_submit():
        result_name = request.form.getlist('worker')
        start_day = str(form.startdate.data)
        end_day = str(form.enddate.data)

        return render_template('attendance_all.html',
                                glue_activity_sum= sum_of_activitiy_count(get_values_in_date_range(existing_data,result_name,start_day, end_day), start_day, end_day,'Počet činnosti', 'olepka'),
                                cut_activity_sum = sum_of_activitiy_count(get_values_in_date_range(existing_data,result_name,start_day, end_day), start_day, end_day,'Počet činnosti', 'pila'),
                                worker_list=user_records(user),
                                list_of_workers= worker_list,
                                user=user['user'],
                                role=int(user['role']),
                                access = int(user['access']),
                                page_title='Přehled všech',
                                form=form,
                                workers_result= get_values_in_date_range(existing_data, result_name, start_day, end_day),
                                start_day= start_day,
                                end_day= end_day,
                                worker_statistics = worker_sum_total_awg_data(existing_data, start_day, end_day),
                                head_text=f'Přehled {start_day} {end_day}')

    return render_template('attendance_all.html',
                            glue_activity_sum = sum_of_activitiy_count(existing_data, yesterday_date, yesterday_date, 'Počet činnosti', 'olepka'),
                            cut_activity_sum= sum_of_activitiy_count(existing_data, yesterday_date, yesterday_date, 'Počet činnosti', 'pila'),
                            worker_list=user_records(user),# uživatelské přihlášení
                            list_of_workers=worker_list, # uživatelé
                            user=user['user'],
                            role=int(user['role']),
                            access = int(user['access']),
                            page_title='Přehled všech',
                            workers_result= get_values_in_date_range(existing_data, worker_list, yesterday_date, yesterday_date),
                            start_day= yesterday_date,
                            end_day= yesterday_date,
                            worker_statistics = worker_sum_total_awg_data(existing_data,
                                                                          f'{datetime(currentYear, this_month, 1).date()}',
                                                                          f'{datetime(currentYear, this_month, this_month_last).date()}'
                                                                          ),
                            form=form,
                            head_text=f'Přehled všichni včera')

@app.route('/logout')
def logout():
    session['user_name'] = None
    session['role'] = None
    return redirect("/")


class ContractForm(FlaskForm):
    def validate_default_date():
        return datetime.today() + timedelta(days=14)

    customer_name = StringField(label='Nový uživatel',
                                 validators=[DataRequired()],
                                 render_kw={"placeholder": "Jméno"}
                                )
    customer_note = TextAreaField(label='Poznámka',
                                  render_kw={"placeholder": "Poznámka"})

    customer_cut = BooleanField(label='Řezání')
    customer_glue = BooleanField(label='Olepování')
    #customer_cut = IntegerField(label='Řezání',
    #                            render_kw={"placeholder": "Řezání"})
    #customer_glue = IntegerField(label='Olepování',
    #                             render_kw={"placeholder": "Olepování"})
    customer_date_finish = DateField(label='Termín zakázky',
                          format='%Y-%m-%d',
                          default=validate_default_date,
                          validators=[DateRange(),DataRequired()])


    submit = SubmitField(label='Nová zakázka')

def load_id():
    try:
        with open('static/contract_id.csv', 'r', newline='', encoding='utf-8') as csfile:
            result_id = csfile.readlines()
    except FileNotFoundError:
        result_id = None
    return(result_id)

def load_contracts(filename):
    contracts = []
    try:
        with open(f'static/{filename}', 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if row:
                    contracts.append({'id': row[0],
                                      'contract': row[1],
                                      'note': row[2],
                                      'cut_logic': row[3],
                                      'cut_value':row[4],
                                      'glue_logic': row[5],
                                      'glue_value': row[6],
                                      'date_create': row[7],
                                      'date': row[8],
                                      'finished': int(row[9])
                                      })
    except FileNotFoundError:
        pass
    return contracts

def set_id(value):
    new_value = value
    with open('static/contract_id.csv', 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([new_value])

def readGlue():
    try:
        with open('static/glue_type.csv', 'r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            glue_type = next(reader)
    except FileNotFoundError:
        pass
    return glue_type[0]

def set_glue(value):
    with open('static/glue_type.csv', 'w', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([value])

def save_contracts(contracts, filename):
    with open(f'static/{filename}', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        for contract in contracts:
            writer.writerow([contract['id'],
                             contract['contract'],
                             contract['note'],
                             contract['cut_logic'],
                             contract['cut_value'],
                             contract['glue_logic'],
                             contract['glue_value'],
                             contract['date_create'],
                             contract['date'],
                             contract['finished']])

def count_glue_cut_values(contracts):
    cut_count = 0
    glue_count = 0
    for contract in contracts:
            if contract['finished'] == 0:
                if contract['cut_value'].isnumeric() and contract['cut_logic'] == 'True':
                    cut_count += int(contract['cut_value'])
                if contract['glue_value'].isnumeric() and contract['glue_logic'] == 'True':
                    glue_count += int(contract['glue_value'])
    return cut_count, glue_count

def count_contract_day_diff(contracts):
    for contract in contracts:
        date_today = datetime.today()
        datum_start = datetime.strptime(contract['date_create'], '%d.%m.%Y')
        datum_end = datetime.strptime(contract['date'], '%d.%m.%Y')
        rozdil_celkem = (datum_end - datum_start).days
        rozdil_aktualni = (date_today - datum_start).days
        rozdil = rozdil_celkem - rozdil_aktualni
        #try:
        #    procenta_uplynulo = (rozdil_aktualni / rozdil_celkem) * 100
        #except ZeroDivisionError:
        #    procenta_uplynulo = 100
        contract['diff'] = rozdil  # Přidejte rozdíl v dnech (můžete použít jinou jednotku podle potřeby)
        #contract['percent'] = f'{procenta_uplynulo:.2f}'
        contract['date_create']=contract['date_create']
        contract['date']=contract['date']
    return contracts

@app.route('/contracts', methods=['POST','GET'])
def contracts():
    user = get_current_user()

    if not user or user['role'] < 2:
        return redirect('/')
    form = ContractForm()

    if request.method == 'GET':
        contracts = load_contracts('contracts.csv')
        completed_contracts = load_contracts('archived_contracts.csv')

        return render_template('contracts.html',
                               contracts=count_contract_day_diff(contracts),
                               completed_contracts=completed_contracts,
                               cut_count=count_glue_cut_values(contracts)[0],
                               glue_count=count_glue_cut_values(contracts)[1],
                               page_title='Zakázky',
                               form=form,
                               worker_list=user_records(user),
                               user=user['user'],
                               role=int(user['role']),
                               access = int(user['access']),
                               contract_id=load_id(),
                               glue=readGlue(),
                               last_id = int(load_id()[-1])+1,
                               search_contract_str=str(datetime.today().year)[-2:],
                               count_contracts = len(contracts))

@app.route('/set_contract_id/<contract_id>')
def set_contract_id(contract_id):
    set_id(contract_id.strip())
    return redirect('/contracts')

@app.route('/add_contract', methods=['POST'])
def add_contract():

    form = ContractForm()
    if form.validate_on_submit():
        customer_name = request.form['customer_name']
        customer_note = request.form['customer_note']
        contract_cut = form.customer_cut.data
        contract_glue = form.customer_glue.data
        contract_date = form.customer_date_finish.data.strftime('%d.%m.%Y')

        if customer_name:
            contracts = load_contracts('contracts.csv')
            new_id = int(load_id()[-1])+1
            set_id(new_id)
            new_contracts = count_contract_day_diff(contracts)
            new_contract = dict({'id': new_id,
                                       'contract': customer_name,
                                       'note': customer_note,
                                       'cut_logic': contract_cut,
                                       'cut_value': 0,
                                       'glue_logic': contract_glue,
                                       'glue_value': 0,
                                       'date_create': datetime.today().strftime('%d.%m.%Y'),
                                       'date': contract_date,
                                       'finished': 0})
            if new_contracts[0]['diff'] < new_contracts[-1]['diff']:
                new_contracts.append(new_contract)
            elif new_contracts[0]['diff'] > new_contracts[-1]['diff']:
                new_contracts.insert(0, new_contract)

            save_contracts(new_contracts, 'contracts.csv')
            return redirect('/contracts')

@app.route('/set_value/<int:contract_index>/<int:value>/<type>')
def set_value(contract_index, value, type):
    contracts = load_contracts('contracts.csv')
    if 0 <= contract_index < len(contracts):
        if value == 0 and type == 'glue_value':
            contracts[contract_index]['glue_logic'] = False
        elif value == 0 and type == 'cut_value':
            contracts[contract_index]['cut_logic'] = False
        else:
            contracts[contract_index][type] = value
        save_contracts(contracts, 'contracts.csv')
    return redirect('/contracts')

@app.route('/clear_value/<int:contract_index>/<type>')
def clear_value(contract_index, type):
    contracts = load_contracts('contracts.csv')
    if 0 <= contract_index < len(contracts):
        contracts[contract_index][type] = False
        save_contracts(contracts, 'contracts.csv')
    return redirect('/contracts')

@app.route('/complete_contract/<int:contract_index>')
def complete_contract(contract_index):
    contracts = load_contracts('contracts.csv')
    if 0 <= contract_index < len(contracts):
        contracts[contract_index]['finished'] = 1
        save_contracts(contracts, 'contracts.csv')
    return redirect('/archive_contracts')


@app.route('/archive_contracts')
def archive_contracts():
    contracts = load_contracts('contracts.csv')
    completed_contracts = [contract for contract in contracts if contract['finished'] == 1]

    try:
        with open('static/archived_contracts.csv', 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            for contract in completed_contracts:
                contract['date']=datetime.today().strftime('%d.%m.%Y')
                writer.writerow([contract['id'],
                             contract['contract'],
                             contract['note'],
                             contract['cut_logic'],
                             contract['cut_value'],
                             contract['glue_logic'],
                             contract['glue_value'],
                             contract['date_create'],
                             contract['date'],
                             contract['finished']])

        contracts = [contract for contract in contracts if contract['finished'] == 0]
        save_contracts(contracts, 'contracts.csv')
    except FileNotFoundError:
        pass

    return redirect('/contracts')

@app.route('/update_contract_order', methods=['POST'])
def update_contract_order():
    new_order = request.form.getlist('contract_order[]')
    contracts = load_contracts('contracts.csv')

    # Seřadíme úkoly podle nového pořadí
    new_contracts = []
    for index in new_order:
        new_contracts.append(contracts[int(index)])

    # Uložíme nové pořadí do souboru
    save_contracts(new_contracts, 'contracts.csv')

    return redirect('/contracts')

@app.route('/get_number', methods=['POST'])
def get_number():
    number = request.form['number']

@app.route('/print_pdf/<int:contract_index>', methods=['POST', 'GET'])
def print_pdf(contract_index):
    user = get_current_user()
    contracts = load_contracts('contracts.csv')

    id = contracts[contract_index]['id']
    name = contracts[contract_index]['contract']
    note = contracts[contract_index]['note']

    return render_template('contract_pdf.html', user=user['user'], id=f'DC{id}', name=name, note= note)

@app.route('/update_row/<int:contract_index>/<name>/<note>/<int:cut>/<int:glue>/<new_date>', methods=['GET'])
def update_row(contract_index, name, note, cut, glue, new_date):
    current_date = datetime.strptime(new_date, '%Y-%m-%d').strftime('%d.%m.%Y')
    contracts = load_contracts('contracts.csv')
    if 0 <= contract_index < len(contracts):
        contracts[contract_index]['contract'] = name
        contracts[contract_index]['note'] = note

        if int(contracts[contract_index]['cut_value']) != cut:
            contracts[contract_index]['cut_logic'] = True
            contracts[contract_index]['cut_value'] = cut

        if int(contracts[contract_index]['glue_value']) != glue:
            contracts[contract_index]['glue_logic'] = True
            contracts[contract_index]['glue_value'] = glue


        contracts[contract_index]['date'] = current_date
        save_contracts(contracts, 'contracts.csv')
    return redirect('/contracts')

@app.route('/set_glue/<glue>', methods=['GET'])
def setGlue(glue):
    set_glue(glue)
    return redirect('/contracts')

@app.route('/statistics/<selected_month>', methods=['GET','POST'])
def statistics(selected_month):
    user = get_current_user()

    if not user or user['role'] < 3:
       return redirect('/')

    currentMonth = selected_month
    currentMonthRange = calendar.monthrange(currentYear,int(currentMonth))[1]

    # Načtení existujících dat ze souboru, pokud soubor existuje
    existing_data = open_statistics_json_file()

    # Rekurzivní funkce pro odstranění klíčů s hodnotou None
    def remove_none_values(d):
        for key, value in list(d.items()):
            if value is None:
                del d[key]
            elif isinstance(value, dict):
                remove_none_values(value)

    return render_template('statistics.html',
                           page_title = 'Statistics',
                           statistic_data= existing_data,
                           worker_list=user_records(user),
                           user=user['user'],
                           role=int(user['role']),
                           access = int(user['access']),
                           date=selected_month,
                           datum=currentYear,
                           choose_month = f'{currentYear}-{selected_month}',
                           currentMonth=currentMonthRange,
                           month_name=months_name[int(selected_month)-1])

class AttendanceAdditionForm(FlaskForm):

    def valid_field(form, field):
        if form.cinnost.data in ['olepka','pila']:
            raise ValidationError("Je nutné zadat číslo nebo vyber jinou činnost!")

    def empty_string_field(form, field):
        if not re.search(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$',field.data):
            raise ValidationError('Zadej platný formát (např. 8:15)')

        # Regexp(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', message='Zadejte platný formát hodin (např. 8:15)')
    datum = DateField(label='Datum',
                          default=date.today,
                          validators=[
                              DataRequired()
                          ])
    prace_od = StringField('Začátek',
                          render_kw={'placeholder': 'Od 6:00'},
                          validators=[])
    prace_do = StringField('Konec',
                          render_kw={'placeholder': 'Do 14:30'},
                          validators=[])
    cinnost = SelectField(u'Vyber činnost', choices=[("", "Vyber činnost .."), ('pila', 'PILA'), ('olepka', 'OLEPKA'), ('sklad', 'SKLAD'), ('obchod', 'OBCHOD'), ('zavoz', 'ZÁVOZ'), ('jine', 'JINÉ')],
                              validators=[])
    pocet_cinnosti = DecimalField(label='Počty', render_kw={'placeholder': 'Počet desek / metrů ...'},
                               validators=[validators.Optional(strip_whitespace=True)])
    textfield = TextAreaField(render_kw={'placeholder': 'Zde napište počet řezání PD, čištění stroje, ...'})
    notefield = TextAreaField(label='Poznámka pod docházkou',render_kw={'placeholder': 'Poznámka, ...'})

    vybrana_dovolena = SelectField('Vybraná dovolená',
                                 choices=[("", "Dovolená hodiny"), ('4:00','4 Hodiny'),('8:00','8 Hodin')],
                                 validators=[])
    vybrane_prescasy= StringField('Vybrané přesčasy',
                                  render_kw={'placeholder':'Vybrané přesčasy'},
                                  validators=[])
    nemoc_lekar=StringField('Nemoc/Lékař',
                            render_kw={'placeholder':'Nemoc/Lékař'},
                            validators=[])
    neplacene_volno=StringField('Neplacené volno',
                                render_kw={'placeholder':'Neplacené volno'},
                                validators=[])
    placene_volno_krev=StringField('Placené volno / Krev',
                                   render_kw={'placeholder':'Placené volno / Krev'},
                                   validators=[])
    svatek=SelectField(u'Vyber',choices=[("","Svátek"),("8:00", "1 Den")])
    prekazka=StringField('Překážka na straně zaměstnavatele',
                         render_kw={'placeholder':'Překážka na straně zaměstnavatele'},
                         validators=[])
    doprovod_k_lekari=StringField('Doprovod k lékaři',
                                  render_kw={'placeholder':'Doprovod k lékaři'},
                                  validators=[])
    pohreb=SelectField('Pohřeb', choices=[("", "Pohřeb"), ('4:00','4 Hodiny'),('8:00','8 Hodin')],
                                 validators=[])
    proplacene_prescasy=StringField('Proplacené přesčasy',render_kw={'placeholder':'Proplacené přesčasy'})
    submit = SubmitField(label='Uložit')

@app.route('/set_attendance/<pass_name>/<pass_date>', methods = ['GET','POST'])
def set_attendance(pass_name,pass_date):

    user = get_current_user()

    if not user or user['role'] < 3:
        return redirect('/')

    existing_data = open_statistics_json_file() # Load statistic data


    # Rekurzivní funkce pro odstranění klíčů s hodnotou None
    def remove_none_values(d):
        for key, value in list(d.items()):
            if value is None:
                d[key] = ""
            elif isinstance(value, dict):
                remove_none_values(value)

    remove_none_values(existing_data)

    def valid_logic_checkbox(chekbox_field):
        if chekbox_field == None:
            return str("")
        else:
            return 'True'

    worker_list = []
    for worker, value in existing_data.items():
        worker_list.append(worker)

    attendance_form = AttendanceAdditionForm()

    def return_non_empty_field(field_bool,field_data):
        if field_bool == "True" or field_bool is not str(""):
            return field_data
        else:
            return str("")

    currentMonth = int(pass_date)

    currentMonthRange = calendar.monthrange(currentYear,currentMonth)[1]

    try:
        attendece_sheet = find_current_date_in_google_worker_sheet(pass_name, 'workers')
    except gspread.exceptions.WorksheetNotFound:
        return redirect(url_for('statistics',selected_month=pass_date))


    current_date = attendece_sheet.find(months[currentMonth]) # Find current day cell
    date_row = current_date.row # Current day row

    row_value = attendece_sheet.row_values(current_date.row)
    current_table_range = f'A{date_row}:V{(date_row+currentMonthRange)-1}'
    months_values = attendece_sheet.batch_get((current_table_range,))

    employee_sheet = attendece_sheet.get_all_values()

    found_strings = find_strings_in_nested_list(months_values, target_strings)

    # Načtení existujících dat ze souboru, pokud soubor existuje
    existing_data = open_statistics_json_file()

    # Vytvoření slovníků
    months_dict = {pass_name: create_dict(employee_sheet)}

    # Aktualizace existujících dat
    existing_data.update(months_dict)

    with open(f"static/statistics.json", "w", encoding='utf-8') as outfile:
        json.dump(existing_data, outfile, skipkeys=False, ensure_ascii=True, check_circular=True, allow_nan=True, cls=None, indent=2, separators=None, default=True, sort_keys=False )


    this_mont_day_first, this_month_last = calendar.monthrange(currentYear, currentMonth)
    this_month_first = 1

    if request.method == 'GET':
        return render_template('attendance.html',
                                user = user['user'],
                                role = int(user['role']),
                                access = int(user['access']),
                                name=pass_name,
                                date = pass_date,
                                datum=currentYear,
                                target_page='set_attendance',
                                rep_glue_count=sum_of_repetition('olepka', months_values),
                                rep_cut_count=sum_of_repetition('pila', months_values),
                                user_month_values=months_values,
                                user_value=row_value,
                                month_name=months_name[int(currentMonth)-1],
                                found_strings=found_strings,
                                prescasy=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Přesčasy','','',pass_name),
                                prescasy_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Přesčasy','','',pass_name),
                                prescasy_total_odecet=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Přesčasy','Proplacené přesčasy','Vybrané přesčasy',pass_name),
                                hodiny=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Hodiny/Den','','',pass_name),
                                hodiny_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Hodiny/Den','','',pass_name),
                                vybrane_prescasy=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Vybrané přesčasy','','',pass_name),
                                vybrane_prescasy_total=sum_hours_in_date_range(existing_data,  f'{first_january}', f'{last_december}', 'Vybrané přesčasy','','',pass_name),
                                proplacene_prescasy=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Proplacené přesčasy','','',pass_name),
                                proplacene_prescasy_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Proplacené přesčasy','','',pass_name),
                                vybrana_dovolena=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Vybraná dovolená','','',pass_name),
                                vybrana_dovolena_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Vybraná dovolená','','',pass_name),
                                nemoc_lekar=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Nemoc/Lékař','','',pass_name),
                                nemoc_lekar_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Nemoc/Lékař','','',pass_name),
                                neplacene_volno=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Neplacené volno','','',pass_name),
                                neplacene_volno_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Neplacené volno','','',pass_name),
                                placene_volno=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Placené volno/Krev','','',pass_name),
                                placene_volno_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Placené volno/Krev','','',pass_name),
                                svatek=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Svátek','','',pass_name),
                                svatek_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Svátek','','',pass_name),
                                prekazka=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Překážka na straně zaměstnavatele','','',pass_name),
                                prekazka_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Překážka na straně zaměstnavatele','','',pass_name),
                                doprovod=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Doprovod k lékaři','','',pass_name),
                                doprovod_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Doprovod k lékaři','','',pass_name),
                                pohreb=sum_hours_in_date_range(existing_data, f'{datetime(currentYear, currentMonth, 1).date()}', f'{datetime(currentYear, currentMonth, this_month_last).date()}','Pohřeb','','',pass_name),
                                pohreb_total=sum_hours_in_date_range(existing_data, f'{first_january}', f'{last_december}','Pohřeb','','',pass_name),
                                attendance_form = attendance_form,
                                user_note = f'{find_user_note(pass_name)}',
                                worker_list=user_records(user)
                               )
    #if request.method == 'POST':

    if attendance_form.validate_on_submit():
        workers_result = pass_name

        datum = attendance_form.datum.data.strftime('%d.%m.%Y')
        prace_bool = valid_logic_checkbox(request.form.get('prace_bool'))
        prace_od = attendance_form.prace_od.data
        prace_do = attendance_form.prace_do.data
        cinnost = attendance_form.cinnost.data
        pocet_cinnosti = str(attendance_form.pocet_cinnosti.data).replace('.',',') if attendance_form.pocet_cinnosti.data != None else int()
        textfield = attendance_form.textfield.data
        notefield = attendance_form.notefield.data

        vybrana_dovolena_bool = valid_logic_checkbox(request.form.get('vybrana_dovolena_bool'))
        vybrana_dovolena = attendance_form.vybrana_dovolena.data

        vybrane_prescasy_bool = valid_logic_checkbox(request.form.get('vybrane_prescasy_bool'))
        vybrane_prescasy = attendance_form.vybrane_prescasy.data

        nemoc_lekar_bool = valid_logic_checkbox(request.form.get('nemoc_lekar_bool'))
        nemoc_lekar = attendance_form.nemoc_lekar.data

        neplacene_volno_bool = valid_logic_checkbox(request.form.get('neplacene_volno_bool'))
        neplacene_volno = attendance_form.neplacene_volno.data

        placene_volno_krev_bool = valid_logic_checkbox(request.form.get('placene_volno_krev_bool'))
        placene_volno_krev = attendance_form.placene_volno_krev.data

        svatek_bool = valid_logic_checkbox(request.form.get('svatek_bool'))
        svatek = attendance_form.svatek.data

        prekazka_bool = valid_logic_checkbox(request.form.get('prekazka_bool'))
        prekazka = attendance_form.prekazka.data

        doprovod_k_lekari_bool = valid_logic_checkbox(request.form.get('doprovod_k_lekari_bool'))
        doprovod_k_lekari = attendance_form.doprovod_k_lekari.data

        pohreb_bool = valid_logic_checkbox(request.form.get('pohreb_bool'))
        pohreb = attendance_form.pohreb.data

        proplacene_prescasy_bool = valid_logic_checkbox(request.form.get('proplacene_prescasy_bool'))
        proplacene_prescasy = attendance_form.proplacene_prescasy.data

        time_result, over_work_time = work_time_count(return_non_empty_field(prace_bool,prace_od),return_non_empty_field(prace_bool,prace_do))

        if workers_result:
            if not notefield:
                save_user_note(pass_name,str(''))
            else:
                save_user_note(pass_name,notefield)

            save_user_data_to_google_sheet(workers_result,
                                           datum,
                                           return_non_empty_field(prace_bool,prace_od),
                                           return_non_empty_field(prace_bool,prace_do),
                                           time_result if time_result != "0:00" else str(""),
                                           over_work_time,
                                           cinnost,
                                           return_non_empty_field(cinnost,pocet_cinnosti),
                                           return_non_empty_field(textfield,textfield),
                                           return_non_empty_field(vybrane_prescasy_bool,vybrane_prescasy),
                                           return_non_empty_field(proplacene_prescasy_bool,proplacene_prescasy),
                                           return_non_empty_field(vybrana_dovolena_bool,vybrana_dovolena),
                                           return_non_empty_field(nemoc_lekar_bool,nemoc_lekar),
                                           return_non_empty_field(neplacene_volno_bool,neplacene_volno),
                                           return_non_empty_field(placene_volno_krev_bool,placene_volno_krev),
                                           return_non_empty_field(svatek_bool,svatek),
                                           return_non_empty_field(prekazka_bool,prekazka),
                                           return_non_empty_field(doprovod_k_lekari_bool,doprovod_k_lekari),
                                           return_non_empty_field(pohreb_bool,pohreb)
                                           )
            def print_time_function():
                pass # Function, that will run after render_template

            thread = threading.Thread(target=print_time_function())
            thread.start()

            return render_template('result.html',
                                    target_page=f'set_attendance/{pass_name}/{pass_date}',
                                    name=pass_name,
                                    date=pass_date,
                                   user_note = notefield,
                        datum = datum,
                        od = f" Od: {return_non_empty_field(prace_bool,prace_od)}" if return_non_empty_field(prace_bool,prace_od) else "",
                        do = f" Do: {return_non_empty_field(prace_bool,prace_do)}" if return_non_empty_field(prace_bool,prace_do) else "",
                        celkem = f" Celkem: {time_result}" if time_result != "0:00" else "",
                        prescas = f" Přesčas: {over_work_time}" if over_work_time else "",
                        metry = f' {f" Metry/Olepeno: {return_non_empty_field(cinnost,pocet_cinnosti)}" if return_non_empty_field(cinnost,pocet_cinnosti) else ""}',
                        dovolena = f' {f" Dovolená: {return_non_empty_field(vybrana_dovolena_bool,vybrana_dovolena)}" if return_non_empty_field(vybrana_dovolena_bool,vybrana_dovolena) else ""}',
                        vybrane_prescasy = f' {f" Vybrané Přesčasy: {return_non_empty_field(vybrane_prescasy_bool,vybrane_prescasy)}" if return_non_empty_field(vybrane_prescasy_bool,vybrane_prescasy) else ""}',
                        nemoc_lekar = f' {f" Nemoc/Lékař: {return_non_empty_field(nemoc_lekar_bool,nemoc_lekar)}" if return_non_empty_field(nemoc_lekar_bool,nemoc_lekar) else ""}',
                        nep_volno = f' {f" Neplacené volno: {return_non_empty_field(neplacene_volno_bool,neplacene_volno)}" if return_non_empty_field(neplacene_volno_bool,neplacene_volno) else ""}',
                        plac_volno = f' {f" Placené volno/krev: {return_non_empty_field(placene_volno_krev_bool,placene_volno_krev)}" if return_non_empty_field(placene_volno_krev_bool,placene_volno_krev) else ""}',
                        svatek = f' {f" Svátek: {return_non_empty_field(svatek_bool,svatek)}" if return_non_empty_field(svatek_bool,svatek) else ""}',
                        prekazak = f' {f" Překážka: {return_non_empty_field(prekazka_bool,prekazka)}" if return_non_empty_field(prekazka_bool,prekazka) else ""}',
                        dorovod = f' {f" Doprovod: {return_non_empty_field(doprovod_k_lekari_bool,doprovod_k_lekari)}" if return_non_empty_field(doprovod_k_lekari_bool,doprovod_k_lekari) else ""}',
                        pohreb = f' {f" Pohřeb: {return_non_empty_field(pohreb_bool,pohreb)}" if return_non_empty_field(pohreb_bool,pohreb) else ""}',
                        prop_prescasy = f' {f" Proplacené přesčasy: {return_non_empty_field(proplacene_prescasy_bool,proplacene_prescasy)}" if return_non_empty_field(proplacene_prescasy_bool,proplacene_prescasy) else ""}',
                        poznamka = f' {f" Poznámka: {return_non_empty_field(textfield,textfield)}" if return_non_empty_field(textfield,textfield) else ""}',
                #datum = f'{datetime.today().month:02d}'
                            )

        else:
            return render_template('result.html',
                                   name = f'Je potřeba vybrat jednoho zaměstnance')


@app.route('/sort', methods=['GET'])
def sort():
    contracts = load_contracts('contracts.csv')
    sorted_contract_data = []

    def diff_days(dictionary):
        today = datetime.today().date()
        date_str = dictionary['date']
        date_obj = datetime.strptime(date_str, '%d.%m.%Y').date()
        return (date_obj - today).days
    sorted_data = sorted(contracts, key=diff_days)

    # Výpis seřazených slovníků
    for d in sorted_data:
        sorted_contract_data.append(d)

    save_contracts(sorted_contract_data, 'contracts.csv')
    return redirect('/contracts')

@app.route('/reverse', methods=['GET'])
def reverse():
    contracts = load_contracts('contracts.csv')
    reverse_contracts=contracts[::-1]
    save_contracts(reverse_contracts, 'contracts.csv')
    return redirect('/contracts')

@app.route('/clear_info_count', methods=['GET'])
def clear_info_count():
    user = get_current_user()
    file_path = 'static/login.csv'
    csv_data = read_csv(file_path)
    find_and_update_or_append(csv_data, user['access'])
    for i, row in enumerate(csv_data):
        if row[0] == user['user']:
            csv_data[i] = [user['user'], row[1], row[2], str(0)]
    write_csv(file_path, csv_data)
    return 'Nonthing'


cron = BackgroundScheduler(deamon=True)
cron.start()
scheduler = BackgroundScheduler()
trigger = CronTrigger(year="*", month="*", day="*", hour="23", minute="59")
job = scheduler.add_job(zip_and_send.zip_and_send_func, trigger=trigger)
scheduler.start()

atexit.register(lambda: cron.shutdown(wait=False))

if __name__=='__main__':
    app.run(debug=True)
