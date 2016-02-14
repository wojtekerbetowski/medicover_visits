import os, sys, locale, io
import requests
from bs4 import BeautifulSoup
import json
import dateutil.parser
from pprint import pprint
import yaml
import time
from datetime import datetime

def login(login, password):
	session = requests.Session()

	# Get verification token
	r = session.get('https://mol.medicover.pl/')
	r.raise_for_status()
	bs = BeautifulSoup(r.content)

	verification_token = bs.select('input[name="__RequestVerificationToken"]')[0]['value']

	r = session.post('https://mol.medicover.pl/Users/Account/LogOn?ReturnUrl=%2F',
		data={
			'userNameOrEmail': username,
			'password': password,
			'__RequestVerificationToken': verification_token
		})
	r.raise_for_status()

	return session

def load_form(session, **kwargs):
	r = session.get(
		"https://mol.medicover.pl/api/MyVisits/SearchFreeSlotsToBook/FormModel",
		headers={
				'X-Requested-With': 'XMLHttpRequest'
			},
			params=dict(regionId=204, **kwargs)
	)
	r.raise_for_status()
	return r.json()

def input_inicode():
	return raw_input(
		"\nChoose: "
		).decode(sys.stdin.encoding or locale.getpreferredencoding(True))

def specify(field, form_data):
	options = form_data[field]
	print("\nChoices:")
	for option in options:
		print(option["text"])

	choice = input_inicode()

	return next(x for x in options if x["text"] == choice)

def search_free_slots(session, **kwargs):
	r = session.post('https://mol.medicover.pl/api/MyVisits/SearchFreeSlotsToBook',
			headers={
				'X-Requested-With': 'XMLHttpRequest'
			},
	        data=dict(
	            regionId=204,
	            bookingTypeId=2,
	            languageId=-1,
	            searchSince="2015-11-21T07:00:00.000Z",
	            searchForNextSince=None,
	            periodOfTheDay=0,
	            isSetBecauseOfPcc=False,
	            isSetBecausePromoteSpecialization=False,
				**kwargs
				),
	        params={
	            "language": 'pl-PL',
	        }
	        )
	r.raise_for_status()
	return r.json()

def first_available_slot(slots):
	try:
		return min(slots["items"], key=lambda x: dateutil.parser.parse(x["appointmentDate"]))
	except ValueError:
		return None


if __name__=="__main__":
	config = yaml.load(open("config.yml"))
	username = config["accounts"]["wojtek"]["login"]
	password = config["accounts"]["wojtek"]["password"]

	session = login(username, password)

	specialization = specify("availableSpecializations", load_form(session))

	place = specify(
		"availableClinics",
		load_form(session, specializationId=specialization["id"]))

	doctor = specify(
		"availableDoctors",
		load_form(session, specializationId=specialization["id"], clinicId=place["id"]))

	starting_point = first_available_slot(
		search_free_slots(session,
			specializationId=specialization["id"],
			clinicId=place["id"],
			doctorId=doctor["id"]
			))

	if starting_point is None:
		print("No visit found. ooking for any")
	else:
		print("Looking for a visit before {}".format(
			dateutil.parser.parse(starting_point["appointmentDate"]).strftime("%H:%M %a, %d/%m/%Y")
		))

	while True:
		time.sleep(15)

		session = login(username, password)
		newest = first_available_slot(
			search_free_slots(session,
				specializationId=specialization["id"],
				clinicId=place["id"],
				doctorId=doctor["id"]
				))

		if newest is not None:
			if starting_point is None:
				break # found any visit

			def found_newer_slot():
				return dateutil.parser.parse(newest["appointmentDate"]) < dateutil.parser.parse(starting_point["appointmentDate"])

			if found_newer_slot():
				break

		print("{}: Waiting some more...".format(datetime.now().strftime("%H:%M")))

	message = u"Found new visit: {} in {} at {}".format(
			dateutil.parser.parse(newest["appointmentDate"]).strftime("%H:%M %a, %d/%m/%Y"),
			newest["doctorName"],
			newest["clinicName"],
			)

	print(message)
	with io.open('info.txt', 'w',encoding='utf-8') as info_file:
		info_file.write(message)
