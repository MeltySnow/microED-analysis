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
		self.label: str = copy.deepcopy(notionDashboard.loc["Experiment ID"])
		startDatetimeString: datetime = notionDashboard.loc["Start time"].to_pydatetime()
		stopDatetimeString: datetime = notionDashboard.loc["End time"].to_pydatetime()
		
		if len(notionDashboard.loc["CO2 logfile"]) < 1:
			raise Exception("WARNING: No CO2 logfile found for experiment: %s" % self.label)
		self.CO2LogfileURL = notionDashboard.loc["CO2 logfile"][0]

		if len(notionDashboard.loc["Voltage logfile"]) < 1:
			raise Exception("WARNING: No Voltage logfile found for experiment: %s" % self.label)
		self.voltageLogfileURL = notionDashboard.loc["Voltage logfile"][0]

		# Convert times to UNIX epoch time (needed for InfluxDB query)
		self.startTime: float = self.ToUNIXTime(startDatetimeString)
		self.stopTime: float = self.ToUNIXTime(stopDatetimeString)

		#print (f"{self.label}: {self.startTime}, {self.stopTime}, {self.CO2LogfileURL}, {self.voltageLogfileURL}")

		#Initialize member variables as empty lists:
		self.processedData: dict = {
			#"currentDensityActual" : [],
			#"currentDensityCategorical" : [], #"stackResistance" : [],
			#"stackResistanceError" : [],
			"currentEfficiency" : [],
			"currentEfficiencyError" : [],
			"powerConsumption" : [],
			"powerConsumptionError" : [],
			"fluxCO2" : [],
			"fluxCO2Error" : [],
			"label" : [],
			"time" : [],
			"releasepH" : [],
			"capturepHED" : [],
			"capturepHPC" : [],
			"captureFlux" : [],
			"captureFluxError" : []
			#"capturepHRange" : []
		}

	@staticmethod
	def ToUNIXTime(ip: datetime) -> float:
		return time.mktime(ip.timetuple())

	# Comparison operator overloads for sorting experiments into chronolocical order
	def __gt__(self, other):
		if self.startTime > other.startTime:
			return True
		return False

	def __lt__(self, other):
		if self.startTime < other.startTime:
			return True
		return False

	def __ge__(self, other):
		if self.startTime >= other.startTime:
			return True
		return False

	def __le__(self, other):
		if self.startTime <= other.startTime:
			return True
		return False
