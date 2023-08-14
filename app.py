import os
#import library
import tables
from flask import Flask, session, request, render_template, redirect, url_for
from datetime import datetime, date, timedelta, time
import gspread
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms.fields import SubmitField
from wtforms import DateField, TimeField, TextAreaField, SelectField,IntegerField, validators
from wtforms.validators import DataRequired
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
#create some credential using that scope and content of startup_funding.json
credential = ServiceAccountCredentials.from_json_keyfile_name('startup_funding.json',scope)

#create gspread authorize using that credential
client = gspread.authorize(credential)


#Now will can access our google sheets we call client.open on StartupName
workers_tab = client.open_by_key(tables.cridentials_table["users"])
workers_sheet = workers_tab.worksheet('users')
#user_data = workers_sheet.get_all_records()

def get_current_user():
    if 'user_name' in session:
        user = session['user_name']
        return user

class AttendenceForm(FlaskForm):
    startdate = DateField(label='Datum',
                          format='%Y-%m-%d',
                          default=datetime.today,
                          validators=[DataRequired(),DateRange(
                              min=(date.today() - timedelta(days=2 )),
                              max=date.today(),
                              message='Maximálně 3 dny nazpět!'),
                              ])
    starttime = TimeField('Začátek',validators=[DataRequired()])
    endtime = TimeField('Konec',validators=[DataRequired()])
    selectfield = SelectField(u'Vyber činnost', choices=[("","Vyber činnost .."),('pila', 'PILA'), ('olepka', 'OLEPKA'),('sklad','SKLAD'),('zavoz','ZÁVOZ'),('jine','JINÉ')],
                              validators=[DataRequired()])
    numberfield = IntegerField(label='Počty', render_kw={'placeholder': 'Počet desek / metrů ...'},validators=[validators.Optional(strip_whitespace=True)])
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
            if password == row_data[1]:
                session['user_name'] = row_data[4]
                session['role'] = row_data[2]
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

    form = AttendenceForm()
    # Attencence form data request
    if request.method == 'POST' and form.validate_on_submit():
        startdate = form.startdate.data.strftime('%d.%m.%Y')
        #month_range = form.startdate.data.monthrange()
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
        odd_time= time(hodiny_rozdil,minuty_rozdil)

        attendence_tab = client.open_by_key(tables.workers_table['workers']) # Access to google sheets
        attendece_sheet = attendence_tab.worksheet(user) # Chose current user sheet
        current_date = attendece_sheet.find(startdate) # Find current day cell
        date_row = current_date.row # Current day row

        cell_range = f'B{date_row}:H{date_row}' # Cell range as string
        attendece_sheet.update(cell_range, [[str(starttime),str(endtime),str(time_result),str(over_work_time),selectfield,numberfield,textfield]], value_input_option='USER_ENTERED' )


        return redirect(url_for('attendence_overview',select_month=datetime.now().month))

    return render_template('attendence_individual.html', page_title='Zadání docházky', user = user, role=role, form=form)

@app.route('/attendence_overview/<int:select_month>', methods=['GET', 'POST'])
def attendence_overview(select_month):
    user=session.get('user_name')
    role = int(session.get('role'))

    if request.method == 'GET':
        months = {1: '01.01.2023', 2: '01.02.2023', 3: '01.03.2023', 4: '01.04.2023', 5: '01.05.2023', 6: '01.06.2023',
                  7: '01.07.2023', 8: '01.08.2023', 9: '01.09.2023', 10: '01.10.2023', 11: '01.11.2023', 12: '01.12.2023'}
        months_name=['Leden', 'Únor', 'Březen', 'Duben', 'Květen', 'Červen', 'Červenec', 'Srpen', 'Září', 'Říjen', 'Listopad', 'Prosinec']
        currentYear = datetime.now().year

        currentMonth = select_month
        currentMonthRange = calendar.monthrange(currentYear,currentMonth)[1]

        attendence_tab = client.open_by_key(tables.workers_table['workers']) # Access to google sheets
        attendece_sheet = attendence_tab.worksheet(user) # Chose current user sheet

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
                               user = user,
                               role = role,
                               user_value = row_value,
                               user_month_values = months_values,
                               month_name=months_name[select_month-1],
                               found_strings = found_strings)



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

    user=session.get('user_name')
    role = int(session.get('role'))

    form = AttendenceAllForm()

    attendence_tab = client.open_by_key('1FiDYtNRIa4mMB6mZdDhxzNxcPTklPQhj8Of3PcqDbyc') # Access to google sheets
    workers_list = []
    for name in attendence_tab:
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


        return render_template('attendence_all.html',
                                user = user,
                                role = role,
                                page_title='Přehled všech',
                                form=form,
                                date_range=f'{startdate.strftime("%d.%m.%Y")} - {enddate.strftime("%d.%m.%Y")}',
                                head_text=f'Přehled ',
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

    found_strings = find_strings_in_nested_list(workers_result, target_strings)

    return render_template('attendence_all.html',
                       user = user,
                       role = role,
                       page_title='Přehled všech',
                       form=form,
                       head_text='Přehled včera všichni',
                       workers_list=enumerate(workers_list,0),
                       found_strings = found_strings,
                       workers_result=workers_result)

@app.route('/logout')
def logout():
    session['name'] = None
    return redirect("/")


if __name__=='__main__':
    app.run(debug=True)
