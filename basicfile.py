#!/usr/bin/python

'''
	Author : Various Users
	Date : 06/11/2015
	Description : This will be a a relatively simple document breaking down the city_bash project

'''
##Necessary modules??

import openpyxl
import csv
import os


class CityBash(object):

	def __init__(self):
		pass


	def pull_csv(self):
		'''
		Pull CSV data into python and seperate the fields by variables
		'''
		os.chdir("//Documents/GitStuff/Project_Boston_Housing") # Depending on where we'll be pulling this from
		wb = load_workbook('initial.xlsx')
		print(wb)


	def get_geocoded_cordinates(self):
		pass



def main():
	print("###This should work")
	new = CityBash()
	new_csv = new.self.pull_csv()
	print(new_csv)

	#Run the intial pull_csv and 

main()
