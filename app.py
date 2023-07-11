import os

#import library
from flask import Flask, jsonify, request, abort
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
spread_sheet = client.open_by_key('19UBIonRYVjlAPu7nWfRUD69oFeUV32sUuk_LeJK-AyM')
work_sheet = spread_sheet.worksheet('users')

@app.route('/', methods=['GET'])
def index():
    return jsonify(work_sheet.get_all_records())

if __name__=='__main__':
    app.run(debug=True)