import os
import tables
from flask import Flask, session, request, render_template, redirect, url_for, make_response
from datetime import datetime, date, timedelta, time
import pytz
import gspread
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms.fields import SubmitField
from wtforms import TimeField, TextAreaField, SelectField, IntegerField, PasswordField, DateField, validators, StringField
from wtforms.validators import DataRequired, ValidationError
from wtforms_components import DateRange
import hashlib
import calendar
import csv

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
        return user_session

def user_records(user):
    user_records_list = []
    user_list = get_user_login_list()
    result = []
    # Vytvořte slovník pro uchování počtu výskytů jmen a seznamu dat
    count_dict = {}
    date_dict = {}

    # Projděte vnořený list a aktualizujte slovníky
    for item in user_list:
        name, the_date = item[0], item[1]

        if name in count_dict:
            count_dict[name] += 1
        else:
            count_dict[name] = 1

        if name in date_dict:
            date_dict[name].append(the_date)
        else:
            date_dict[name] = [the_date]

    # Případ 1: Seznam všech jmen s předposledními daty a počtem výskytů
    if user['role'] == 3:
        result_1 = []
        for name, count in count_dict.items():
            dates = date_dict[name]
            if count >= 1:
                second_last_date = dates[-2] if len(dates) >= 2 else dates[-1]
                result_1.append((name, second_last_date, count))

        for name, second_last_date, count in result_1:
            user_records_list.append(dict({'name': name, 'date': second_last_date, 'count': count}))


    # Případ 2: Získání předposledního data a počtu výskytů pro konkrétní jméno
    elif user['role'] != 3:
        target_name = user['user']  # Změňte na požadované jméno
        if target_name in count_dict:
           dates = date_dict[target_name]
           count = count_dict[target_name]
           second_last_date = dates[-2] if len(dates) >= 2 else dates[-1]
           user_records_list.append(dict({'name':target_name, 'date':second_last_date, 'count':count}))


    return user_records_list

@app.context_processor
def inject_globals():
    return dict({
        'current_month': datetime.now().month
    })

class AttendanceForm(FlaskForm):
    def validate_end_date(self, field):

        if datetime.strptime(self.startdate.raw_data[0], '%Y-%m-%d') > datetime.today() or datetime.strptime(self.startdate.raw_data[0], '%Y-%m-%d') < datetime.today() - timedelta(days=2):
            raise ValidationError("Max 2 dny zpět")

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
    selectfield = SelectField(u'Vyber činnost', choices=[("", "Vyber činnost .."), ('pila', 'PILA'), ('olepka', 'OLEPKA'), ('sklad', 'SKLAD'), ('zavoz', 'ZÁVOZ'), ('jine', 'JINÉ')],
                              validators=[DataRequired()])
    numberfield = IntegerField(label='Počty', render_kw={'placeholder': 'Počet desek / metrů ...'},
                               validators=[validators.Optional(strip_whitespace=True)])
    textfield = TextAreaField(render_kw={'placeholder': 'Zde napište počet řezání PD, čištění stroje, ...'})
    submit = SubmitField(label='Uložit')


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
            #print(row_data, file=sys.stdout)
            if hashlib.md5(password.encode()).hexdigest() == row_data[1]:
                session['user_name'] = row_data[4]
                session['role'] = int(row_data[2])
                if session['role'] == 4:
                    try:
                        f = open('static/login.csv', 'a', encoding='utf-8')
                        f.write(f"{row_data[4]};{datetime.now(pytz.timezone('Europe/Prague')).strftime('%d.%m.%Y/%H:%M')}\n")
                        f.close()
                        return redirect(url_for('attendence_all'))
                    except:
                        return False
                    finally:
                        f.close()
                else:
                    try:
                        f = open('static/login.csv', 'a', encoding='utf-8')
                        f.write(f"{row_data[4]};{datetime.now(pytz.timezone('Europe/Prague')).strftime('%d.%m.%Y/%H:%M')}\n")
                        f.close()
                        return redirect(url_for('attendence_individual'))
                    except:
                        return False
                    finally:
                        f.close()

            else:
                warning['login'] = 'Heslo je špatné'
                return render_template('login.html', page_title='login', login_text=warning["login"])
    else:
        return render_template('login.html', page_title='login')

class form_check_pass(FlaskForm):
        oldPassword = PasswordField('Staré heslo', validators=[DataRequired()])
        newPassword = PasswordField('Nové heslo', validators=[DataRequired()])
        checkPassword = PasswordField('Nové heslo znovu ', validators=[DataRequired()])
        submit = SubmitField(label='Uložit')


@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    user = get_current_user()

    if not user or user['role'] != 3:
       return redirect('/')

    worker_values = workers_sheet.get_all_values()

    form = form_check_pass()
    if request.method == 'POST' and form.validate_on_submit:
        worker_id = request.form['worker']
        oldPassword = request.form['oldPassword'].strip()
        newPassword = request.form['newPassword'].strip()
        checkPassword = request.form['checkPassword'].strip()
        print(type(worker_id))
        for value in worker_values:
            if (value[1] == hashlib.md5(newPassword.encode()).hexdigest()) and (int(worker_id) == int(value[7])) and (newPassword == checkPassword):
                worker_name = value[4]
                cell = workers_sheet.find(value[7])
                workers_sheet.update_cell(cell.row, 2, hashlib.md5(newPassword.encode()).hexdigest())

                return render_template('change_password.html',
                                    title='Změna akceptována',
                                    worker_list=user_records(user),
                                    user=user['user'],
                                    role=int(user['role']),
                                    workers_list=worker_values,
                                    head_text=f'Heslo pro {worker_name} uloženo!',
                                    form=form)

        return 'Something went wrong!'

    return render_template('change_password.html',
                           title='Změna hesla',
                           worker_list=user_records(user),
                           user=user['user'],
                           role=int(user['role']),
                           workers_list=worker_values,
                           head_text='Změna hesla',
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
                               role=int(user['role']))

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
                               role=int(user['role']))

@app.route('/attendence_individual', methods=['GET', 'POST'])
def attendence_individual():

    user = get_current_user()

    if not user:
       return redirect('/')

    attendence_tab = client.open_by_key(tables.workers_table['workers']) # Access to google sheets
    workers_list = []
    for name in attendence_tab:
        if name.title == 'mustr':
            pass
        else:
            workers_list.append(name.title)

    form = AttendanceForm()
    # Attencence form data request
    if form.validate_on_submit():
        startdate = form.startdate.data.strftime('%d.%m.%Y')
        starttime = form.starttime.data.strftime('%H:%M')
        endtime = form.endtime.data.strftime('%H:%M')
        selectfield = form.selectfield.data
        numberfield = form.numberfield.data
        textfield = form.textfield.data

        hodiny_start, minuty_start = map(int, starttime.split(':'))
        hodiny_end, minuty_end = map(int,endtime.split(':'))
        come_time = time(hodiny_start, minuty_start)
        end_time = time(hodiny_end, minuty_end)

        break_time = timedelta(days=0,hours=0,minutes=30)
        work_time = timedelta(days=0, hours=8, minutes=0)
        work_hour_limit = timedelta(days=0, hours=4, minutes=30)

        timedelta1 = timedelta(hours = come_time.hour, minutes = come_time.minute)
        timedelta2 = timedelta(hours=end_time.hour, minutes=end_time.minute)
        delta_time = timedelta2-timedelta1

        if delta_time > work_hour_limit:
            time_result = delta_time-break_time
        else:
            time_result = delta_time

        if time_result > work_time:
            over_work_time = time_result-work_time
        else:
            over_work_time = ''

        # Získání hodin a minut z rozdílu
        hodiny_rozdil = time_result.seconds // 3600
        minuty_rozdil = (time_result.seconds // 60) % 60

        attendence_tab = client.open_by_key(tables.workers_table['workers']) # Access to google sheets
        attendece_sheet = attendence_tab.worksheet(user['user']) # Chose current user sheet
        current_date = attendece_sheet.find(startdate) # Find current day cell
        date_row = current_date.row # Current day row

        cell_range = f'B{date_row}:H{date_row}' # Cell range as string
        attendece_sheet.update(cell_range, [[str(starttime),str(endtime),str(time_result),str(over_work_time),selectfield,numberfield,textfield]], value_input_option='USER_ENTERED' )


        return redirect(url_for('attendence_overview',select_month=datetime.now().month))

    return render_template('attendence_individual.html',
                           select_month=datetime.now().month,
                           page_title='Zadání docházky',
                           worker_list=user_records(user),
                           user=user['user'],
                           role=int(user['role']),
                           form=form)

@app.route('/attendence_overview/<int:select_month>', methods=['GET', 'POST'])
def attendence_overview(select_month):
    user = get_current_user()

    if not user:
       return redirect('/')

    if request.method == 'GET':

        months = {1: '01.01.2023', 2: '01.02.2023', 3: '01.03.2023', 4: '01.04.2023', 5: '01.05.2023', 6: '01.06.2023',
                  7: '01.07.2023', 8: '01.08.2023', 9: '01.09.2023', 10: '01.10.2023', 11: '01.11.2023', 12: '01.12.2023'}
        months_name=['Leden', 'Únor', 'Březen', 'Duben', 'Květen', 'Červen', 'Červenec', 'Srpen', 'Září', 'Říjen', 'Listopad', 'Prosinec']
        currentYear = datetime.now().year

        currentMonth = select_month
        currentMonthRange = calendar.monthrange(currentYear,currentMonth)[1]

        attendence_tab = client.open_by_key(tables.workers_table['workers']) # Access to google sheets
        attendece_sheet = attendence_tab.worksheet(user['user']) # Chose current user sheet

        current_date = attendece_sheet.find(months[currentMonth]) # Find current day cell
        date_row = current_date.row # Current day row
        row_value = attendece_sheet.row_values(current_date.row)
        current_table_range = f'A{date_row}:H{(date_row+currentMonthRange)-1}'
        months_values = attendece_sheet.batch_get((current_table_range,))
        #return '{}'.format(currentMonth)
        #print(months_values, file=sys.stdout)

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

        target_strings = ['pila', 'olepka', 'zavoz', 'sklad', 'kancl', 'jine']

        found_strings = find_strings_in_nested_list(months_values, target_strings)

        return render_template('attendece_overview.html',
                               page_title = 'Přehled',
                               worker_list=user_records(user),
                               user=user['user'],
                               role=int(user['role']),
                               user_value=row_value,
                               user_month_values=months_values,
                               month_name=months_name[select_month-1],
                               found_strings=found_strings)
@app.route('/generate_pdf', methods=['GET'])
def generate_pdf():
    pass

class AttendenceAllForm(FlaskForm):
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

@app.route('/attendence_all', methods=['GET', 'POST'])
def attendence_all():

    user = get_current_user()

    if not user or user['role'] < 2:
       return redirect('/')

    form = AttendenceAllForm()

    attendence_tab = client.open_by_key(tables.workers_table['workers']) # Access to google sheets
    workers_list = []
    for name in attendence_tab:
        if name.title == 'mustr':
            pass
        else:
            workers_list.append(name.title)

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

    target_strings = ['pila', 'olepka', 'zavoz', 'sklad', 'kancl', 'jine']

    if request.method == 'POST' and form.validate_on_submit():
        result = request.form.getlist('worker')
        startdate = form.startdate.data
        enddate =  form.enddate.data

        time_difference = enddate-startdate
        count_days = time_difference.days
        result = [int(i) for i in result]

        date_range = [startdate + timedelta(days=i) for i in range((enddate - startdate).days+1)]
        date_string_range=[]
        for i in date_range:
            date_string_range.append(i.strftime('%d.%m.%Y'))

        workers_result_selection = []

        for worker in range(len(result)):
            employee_sheet = attendence_tab.worksheet(workers_list[result[worker]]).get_all_values()

            for day in employee_sheet:
                for d in date_string_range:
                    if d in day:
                        day.insert(0,workers_list[result[worker]])
                        workers_result_selection.append(day)
        workers_result_selection.sort(key=lambda x: x[1])

        def shorten_time(time_str):
            parts = time_str.split(":")
            if len(parts) > 2:
                parts.pop()
            d = timedelta(hours=int(parts[0]), minutes=int(parts[1]))
            return(d)

        pila = 0
        olepka = 0
        work_time = timedelta()
        ower_time = timedelta()
        for data in workers_result_selection:
            if data[4]:
                work_time += shorten_time(data[4])

            if data[5]:
                ower_time += shorten_time(data[5])

            if data[6] == 'pila':
                value = data[7]
                if value == "":
                    value = 0
                else:
                    value = int(data[7])
                pila += value
            elif data[6] == 'olepka':
                value = data[7]
                if value == "":
                    value = 0
                else:
                    value = int(data[7])
                olepka += value

        def timedelta_to_string(convert_time):
            hours = convert_time.days * 24 + convert_time.seconds // 3600
            minutes = (convert_time.seconds % 3600) // 60
            return(f"{hours:02d}:{minutes:02d}")


        found_strings_selection = find_strings_in_nested_list(workers_result_selection, target_strings)

        date_range_text = f'{startdate.strftime("%d.%m.%Y")} - {enddate.strftime("%d.%m.%Y")}'
        return render_template('attendence_all.html',
                                worker_list=user_records(user),
                                user=user['user'],
                                role=int(user['role']),
                                page_title='Přehled všech',
                                form=form,
                                head_text=f'Přehled { date_range_text }',
                                workers_list=enumerate(workers_list,0),
                                found_strings = found_strings_selection,
                                workers_result=workers_result_selection,
                                pila = pila,
                                olepka = olepka,
                                sum_work_hour = timedelta_to_string(work_time),
                                sum_ower_work_hour = timedelta_to_string(ower_time))


    workers_result = []
    lookup_date = (date.today()-timedelta(days=1)).strftime('%d.%m.%Y')

    for worker in range(len(workers_list)):
        attendece_sheet = attendence_tab.worksheet(workers_list[worker]).get_all_values()
        for item in attendece_sheet:
            if item[0] == lookup_date:
                item.insert(0,workers_list[worker])
                workers_result.append(item)

    def shorten_time(time_str):
            parts = time_str.split(":")
            if len(parts) > 2:
                parts.pop()
            d = timedelta(hours=int(parts[0]), minutes=int(parts[1]))
            return(d)

    pila = 0
    olepka = 0
    work_time = timedelta()
    ower_time = timedelta()
    for data in workers_result:
        if data[4]:
            work_time += shorten_time(data[4])

        if data[5]:
            ower_time += shorten_time(data[5])

        if data[6] == 'pila':
            value = data[7]
            if value == '':
                value = 0
            else:
                value = int(data[7])
            pila += value
        elif data[6] == 'olepka':
            value = data[7]
            if value == '':
                value = 0
            else:
                value = int(data[7])
            olepka += value

    found_strings = find_strings_in_nested_list(workers_result, target_strings)

    def timedelta_to_string(convert_time):
            hours = convert_time.days * 24 + convert_time.seconds // 3600
            minutes = (convert_time.seconds % 3600) // 60
            return(f"{hours:02d}:{minutes:02d}")

    date_range_text = 'včera'

    return render_template('attendence_all.html',
                       user=user['user'],
                       role=int(user['role']),
                       page_title='Přehled všech',
                       worker_list=user_records(user),
                       date_range=date_range_text,
                       form=form,
                       head_text=f'Přehled {date_range_text} všichni',
                       workers_list=enumerate(workers_list,0),
                       found_strings = found_strings,
                       pila = pila,
                       olepka = olepka,
                       workers_result=workers_result,
                       sum_work_hour = timedelta_to_string(work_time),
                       sum_ower_work_hour = timedelta_to_string(ower_time))

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
    customer_cut = IntegerField(label='Řezání',
                                render_kw={"placeholder": "Řezání"})
    customer_glue = IntegerField(label='Olepování',
                                 render_kw={"placeholder": "Olepování"})
    customer_date_finish = DateField(label='Termín zakázky',
                          format='%Y-%m-%d',
                          default=validate_default_date,
                          validators=[DateRange(),DataRequired()])


    submit = SubmitField(label='Nová zakázka')


def load_contracts(filename):
    contracts = []
    try:
        with open(f'static/{filename}', 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if row:
                    contracts.append({'id':row[0],
                                      'contract': row[1],
                                      'note': row[2],
                                      'cut': int(row[3]),
                                      'glue': int(row[4]),
                                      'date_create':row[5],
                                      'date': row[6],
                                      'finished': int(row[7])
                                      })
    except FileNotFoundError:
        pass
    return contracts

def save_contracts(contracts, filename):
    with open(f'static/{filename}', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        for contract in contracts:
            writer.writerow([contract['id'],
                             contract['contract'],
                             contract['note'],
                             contract['cut'],
                             contract['glue'],
                             contract['date_create'],
                             contract['date'],
                             contract['finished']])

@app.route('/contracts', methods=['GET'])
def contracts():
    form=ContractForm()
    if request.method == 'GET':
        contracts = load_contracts('contracts.csv')
        #completed_contracts = load_contracts('archived_contracts.csv')
        cut_count = 0
        glue_count = 0

        for contract in contracts:
            if contract['finished'] == 0:
                cut_count += int(contract['cut'])
                glue_count += int(contract['glue'])
        return render_template('contracts.html',
                               contracts=contracts,
                               #completed_contracts=completed_contracts,
                               cut_count = cut_count,
                               glue_count = glue_count,
                               page_title='Zakázky',
                               form=form)

@app.route('/add_contract', methods=['POST'])
def add_contract():

    form = ContractForm()
    if form.validate_on_submit():
        customer_name = request.form['customer_name']
        customer_note = request.form['customer_note']
        contract_cut = request.form['customer_cut']
        contract_glue = request.form['customer_glue']
        contract_date = form.customer_date_finish.data.strftime('%d.%m.%Y')
        if not contract_cut:
            contract_cut = 0
        if not contract_glue:
            contract_glue = 0

        if customer_name:
            new_contracts = load_contracts('contracts.csv')
            if not new_contracts:
                new_id = 230000
            else:
                check_id = 0
                for contract in new_contracts:
                    if int(contract['id']) > check_id:
                        check_id = int(contract['id'])
                new_id = check_id + 1

            new_contracts.append(dict({'id': new_id,
                                       'contract': customer_name,
                                       'note': customer_note,
                                       'cut': contract_cut,
                                       'glue': contract_glue,
                                       'date_create':datetime.today().strftime('%d.%m.%Y'),
                                       'date': contract_date,
                                       'finished': 0}))
            save_contracts(new_contracts, 'contracts.csv')
            return redirect('/contracts')

@app.route('/complete_contract/<int:contract_index>')
def complete_contract(contract_index):
    contracts = load_contracts('contracts.csv')
    if 0 <= contract_index < len(contracts):
        contracts[contract_index]['finished'] = 1
        save_contracts(contracts, 'contracts.csv')
    return redirect('/contracts')


@app.route('/archive_contracts')
def archive_contracts():
    contracts = load_contracts('contracts.csv')
    completed_contracts = [contract for contract in contracts if contract['finished'] == 1]

    try:
        #with open('static/archived_contracts.csv', 'a', newline='',encoding='utf-8') as csvfile:
        #    writer = csv.writer(csvfile)
        #    for contract in completed_contracts:
        #        writer.writerow([contract['id'], contract['contract'], contract['note'], contract['finished']])

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


if __name__=='__main__':
    app.run(debug=True)
