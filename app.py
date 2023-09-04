import os
import tables
from flask import Flask, session, request, render_template, redirect, url_for, make_response
from datetime import datetime, date, timedelta, time
import gspread
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms.fields import SubmitField
from wtforms import TimeField, TextAreaField, SelectField, IntegerField, PasswordField, DateField, validators
from wtforms.validators import DataRequired, ValidationError
from wtforms_components import DateRange
import hashlib
import calendar

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
workers_tab = client.open_by_key(tables.cridentials_table["users"])
workers_sheet = workers_tab.worksheet('users')

def get_current_user():
    user_session = {}
    if 'user_name' in session:
        user_session['user'] = session['user_name']
        user_session['role'] = session['role']
        return user_session

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
                    return redirect(url_for('attendence_all'))
                else:
                    return redirect(url_for('attendence_individual'))
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
                                    user=user['user'],
                                    role=int(user['role']),
                                    workers_list=worker_values,
                                    head_text=f'Heslo pro {worker_name} uloženo!',
                                    form=form)

        return 'Something went wrong!'

    return render_template('change_password.html',
                           title='Změna hesla',
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
                           page_title='Zadání docházky',
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
    startdate = DateField(label='Od',
                          format='%Y-%m-%d',
                          default=datetime.today,
                          validators=[DateRange(),DataRequired()])
    enddate = DateField(label='Do',
                        format='%Y-%m-%d',
                        default=datetime.today,
                        validators=[DateRange(),DataRequired()])

    submit = SubmitField(label='Zobrazit')

    def validate(self, **kwargs):
        # Standard validators
        rv = FlaskForm.validate(self)
        # Ensure all standard validators are met
        if rv:
            # Ensure end date >= start date
            if self.startdate.data > self.enddate.data:
                self.enddate.errors.append('Toto datum musí mít nižší hodnotu!')
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
                pila += int(data[7])
            elif data[6] == 'olepka':
                olepka += int(data[7])

        def timedelta_to_string(convert_time):
            hours = convert_time.days * 24 + convert_time.seconds // 3600
            minutes = (convert_time.seconds % 3600) // 60
            return(f"{hours:02d}:{minutes:02d}")


        found_strings_selection = find_strings_in_nested_list(workers_result_selection, target_strings)

        date_range_text = f'{startdate.strftime("%d.%m.%Y")} - {enddate.strftime("%d.%m.%Y")}'
        return render_template('attendence_all.html',
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
            pila += int(data[7])
        elif data[6] == 'olepka':
            olepka += int(data[7])

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


if __name__=='__main__':
    app.run(debug=True)
