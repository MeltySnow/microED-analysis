#Import pip packages
import typing
import pandas as pd
import datetime
import time
import sys
import copy
import requests

class ExperimentMeta(object):
	"""
	Member variables:

	char *label;
	float startTime;
	float stopTime;
	dict processedData;
	"""

	def __init__(self, notionDashboard: pd.Series) -> None:
		self.label: str = notionDashboard.loc["Label"]
		#self.label = notionDashboard.loc["Experiment ID"]
		#self.label: str = f'{notionDashboard.loc["Amine concentration / mol kg^{-1}"]}m {notionDashboard.loc["Amine"]}, {notionDashboard.loc["Current density / A m^{-2}"]} A / m2, Initial pH = {notionDashboard.loc["Capture pH initial"]}'
		startDatetimeString: datetime.datetime = notionDashboard.loc["Start time"].to_pydatetime()
		stopDatetimeString: datetime.datetime = notionDashboard.loc["End time"].to_pydatetime()
		self.current: float = notionDashboard.loc["Current / A"]
		self.airFlowRate: float = notionDashboard.loc["Air flow rate"]
		self.amine: str = notionDashboard.loc["Amine"]
		
		if len(notionDashboard.loc["CO2 logfile"]) < 1:
			raise Exception("WARNING: No CO2 logfile found for experiment: %s" % self.label)
		self.CO2LogfileURL: str = notionDashboard.loc["CO2 logfile"][0]

		if len(notionDashboard.loc["Voltage logfile"]) < 1:
			raise Exception("WARNING: No Voltage logfile found for experiment: %s" % self.label)
		self.voltageLogfileURL: str = notionDashboard.loc["Voltage logfile"][0]

		self.icLogfileURL: str = ""
		if len(notionDashboard.loc["IC data"]) >= 1:
			self.icLogfileURL = notionDashboard.loc["IC data"][0]

		# Convert times to UNIX epoch time (needed for InfluxDB query)
		self.startTime: float = self.ToUNIXTime(startDatetimeString)
		self.stopTime: float = self.ToUNIXTime(stopDatetimeString)

		#print (f"{self.label}: {self.startTime}, {self.stopTime}, {self.CO2LogfileURL}, {self.voltageLogfileURL}")

		#Initialize member variables as empty lists:
		self.processedData: dict = {
			"stackResistance" : [],
			"stackResistanceError" : [],
			"currentEfficiency" : [],
			"currentEfficiencyError" : [],
			"powerConsumption" : [],
			"powerConsumptionError" : [],
			"fluxCO2" : [],
			"fluxCO2Error" : [],
			"label" : [],
			"amineFlux" : [],
			"aminePerCO2" : []
		}

		self.timeResolvedData: dict = {
			"time_min" : [],
			"powerConsumption" : [],
			"powerConsumptionError" : [],
			"releaseAmineConc" : [],
			"label": []
		}

	@staticmethod
	def ToUNIXTime(ip: datetime.datetime) -> float:
		return time.mktime(ip.timetuple())

	# Comparison operator overloads for sorting experiments into chronolocical order
	def __gt__(self: ExperimentMeta, other: ExperimentMeta) -> bool:
		if self.startTime > other.startTime:
			return True
		return False

	def __lt__(self: ExperimentMeta, other: ExperimentMeta) -> bool:
		if self.startTime < other.startTime:
			return True
		return False

	def __ge__(self: ExperimentMeta, other: ExperimentMeta) -> bool:
		if self.startTime >= other.startTime:
			return True
		return False

	def __le__(self: ExperimentMeta, other: ExperimentMeta) -> bool:
		if self.startTime <= other.startTime:
			return True
		return False
