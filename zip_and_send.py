import os
import zipfile
import yagmail
import gmail_pass
from datetime import datetime

def get_curr_time():
    return datetime.now().strftime("%d%m%Y%H%M")

name_zipped_file = f"Záloha-{get_curr_time()}.zip"

def zip_files():

    source_files = ['contract_id.csv',
                    'contracts.csv',
                    'login.csv',
                    'notes.csv',
                    'statistics.json',
                    ]

    # Create a zipfile
    zip_object = zipfile.ZipFile(f'static/{name_zipped_file}', 'w')

    # Add multiple files to the zip file
    for file in source_files:
        zip_object.write(f'static/{file}', compress_type=zipfile.ZIP_DEFLATED)

    # Close zipfile
    zip_object.close()


def send_files():
    PASSWORD = gmail_pass.EMAIL_CRIDENTIALS['PASSWORD_GENERAL']

    sender = gmail_pass.EMAIL_CRIDENTIALS['sender']
    reciever = gmail_pass.EMAIL_CRIDENTIALS['reciever']

    def subjects(count=None):
        return(f'Záloha DC_{get_curr_time()}')

    def content(name=None, curr_time=None, count=None, file=None):
        return([f'''
            Ahoj,
            posílám zálohu pro docházku DC
            ''',f'static/{name_zipped_file}'])
    yag = yagmail.SMTP(user=sender, password=PASSWORD)
    yag.send(to=reciever, subject=subjects(), contents=content())
    yag.send

def zip_and_send_func():
    zip_files()
    send_files()
    os.remove(f'static/{name_zipped_file}')

