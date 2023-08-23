#Import pip packages
from typing import Type, List
import requests, json
import numpy as np
import pandas as pd
import os
import time
import math
from datetime import datetime, timedelta
import notion_df
import sys
from dotenv import load_dotenv
import plotly.express as px
import plotly.io as pio
import argparse

#Import project files
from experiment_meta import ExperimentMeta
from ed_metric_calculations import EDMetricCalculations
from pc_metric_calculations import PCMetricCalculations

#Class with functionality that covers database queries, data processing and plotting graphs
class AnalysisManager(object):
	"""
	Member variables:

	pd.DataFrame notionDashboard;
	ExperimentMeta *Experiments;
	"""

	def __init__(self, config: dict) -> None:
		#Load local env variables into RAM
		try:
			self.LoadEnvironmentVariables()
		except Exception as e:
			print (e, file=sys.stderr)
			sys.exit(1)

		#Set defaults and override using the passed config
		self.outputFilename: str = "out.html"
		if config["output"]:
			self.outputFilename = config["output"]

		if config["dashboard"]:
			self.NOTION_DATABASE_ID = config["dashboard"]#this variable was already declared inside of the self.LoadEnvironmentVariables() function

		self.exclude: bool = config["exclude"]


		#Request experiment metadata from Notion API
		self.FetchExperimentDataFromNotion()
		self.Experiments: List[ExperimentMeta]= [] # Initialize list containing metadata for all experiments
		self.ParseExperimentMetadata(config["experimentIDs"])


		#Loop through Experiments list, request data from InfluxDB and process data
		self.ProcessData()


	#Reads .env file in local directory and saves env variables as member variables
	def LoadEnvironmentVariables(self) -> None:
		load_dotenv()
		self.NOTION_API_KEY = os.getenv("NOTION_API_KEY")
		self.NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

		#Throw exception if env variables failed to load
		if not (self.NOTION_API_KEY and self.NOTION_DATABASE_ID):
			raise Exception("ERROR: secrets could not be loaded from .env file")


#Queries Notion and loads dashboard as pandas DataFrame
	def FetchExperimentDataFromNotion(self) -> None:
		try:
			self.notionDashboard: pd.DataFrame = notion_df.download(self.NOTION_DATABASE_ID, api_key=self.NOTION_API_KEY)
		except:
			print ("There was an error communicating with the Notion API", file=sys.stderr)
			sys.exit(1)


	# Implementation of a merge sort algorithm
	@staticmethod
	def MergeSort(ip: list) -> list:
		# Divide the array into 2
		# Recursively call this function on them
		# Merge the two arrays, assuming they are themselves sorted

		# Define recursion endpoint condition
		ipLen: int = len(ip)
		if ipLen <= 1:
			return ip

		# Split the lists in half
		midpoint: int = int(len(ip) / 2.0)
		leftList: list = ip[0 : midpoint]
		rightList: list = ip[midpoint : len(ip)]

		# Recursively sort the list fragments
		leftList = AnalysisManager.MergeSort(leftList)
		rightList = AnalysisManager.MergeSort(rightList)

		# Merge the two sorted lists
		# Initialise variables for loop
		leftIndex: int = 0
		rightIndex: int = 0
		leftLen: int = len(leftList)
		rightLen: int = len(rightList)
		op: list = []

		while leftIndex + rightIndex < leftLen + rightLen:
			if (leftIndex < leftLen and rightIndex < rightLen):
				if leftList[leftIndex] <= rightList[rightIndex]:
					op.append(leftList[leftIndex])
					leftIndex += 1
				else:
					op.append(rightList[rightIndex])
					rightIndex += 1
			elif rightIndex >= rightLen:
				op.append(leftList[leftIndex])
				leftIndex += 1
			elif leftIndex >= leftLen:
				op.append(rightList[rightIndex])
				rightIndex += 1


		return op


#Takes experiment IDs and gets start and end timestamps from Notion database
	def ParseExperimentMetadata(self, experimentIDs: List[str]) -> None:
		if experimentIDs and not self.exclude:
			for n in range (0, len(experimentIDs)):
				experimentID = experimentIDs[n]
				dashboardRow: pd.DataFrame = self.notionDashboard[self.notionDashboard["Experiment ID"] == experimentID]
				if dashboardRow.empty:
					print ("Warning: No experiment with ID \"%s\" was found" % (experimentID), file=sys.stderr)
				else:
					try:
						self.Experiments.append(ExperimentMeta(dashboardRow.iloc[0]))
					except Exception as e:
						print (e, file=sys.stderr)


		#If no command arguments are passed, default to adding all experiments with the "CO2 logfile", "Voltage logfile", "Start time" and "End time" fields filled"
		else:
			#Filter irrelevant columns out of the dashboard
			self.notionDashboard = self.notionDashboard.dropna(subset=["Start time", "End time"])
			#dropna doesn't work for Notion's file fields as empty lists do not evaluate to NaN
			self.notionDashboard = self.notionDashboard[self.notionDashboard["CO2 logfile"].map(len) > 0]
			self.notionDashboard = self.notionDashboard[self.notionDashboard["Voltage logfile"].map(len) > 0]

			if self.notionDashboard.empty:
				print ("Error: No experiment IDs were passed, and no completed experiments were found in the Notion dashboard", file=sys.stderr)
				sys.exit(1)

			for index, row in self.notionDashboard.iterrows():
				if (not self.exclude) or (not (row.loc["Experiment ID"] in experimentIDs)):
					try:
						self.Experiments.append(ExperimentMeta(row))
					except Exception as e:
						print (e, file=sys.stderr)

			# Sort experiments in chronological order
			self.Experiments = self.MergeSort(self.Experiments)

	@staticmethod
	def StringToUNIXTime(ip: str) -> float:
		dt: datetime = datetime.strptime(ip, "%Y-%m-%d %H:%M:%S")
		op: float = time.mktime(dt.timetuple())
		#Need to correct for timezone because Vaisala and EasyLog cannot make software
		#op -= 3600.0
		return op

	def ProcessData(self) -> None:
		self.rawDataAll: pd.DataFrame = pd.DataFrame()
		for exp in self.Experiments:
			#Create DataFrame with data for a single experiment
			rawDataCO2: pd.DataFrame = pd.read_csv(exp.CO2LogfileURL, header=8, names=["timestamp", "co2_ppm"])
			rawDataVoltage: pd.DataFrame = pd.read_csv(exp.voltageLogfileURL, header=2, names=["data_index", "timestamp", "voltage_v", "high_alarm", "low_alarm"])

			#Create new columns with time since start of experiment in seconds
			rawDataCO2["runtime_s"] = rawDataCO2["timestamp"].apply(self.StringToUNIXTime)
			rawDataCO2["runtime_s"] = rawDataCO2["runtime_s"].apply(lambda x: x - exp.startTime)
			rawDataVoltage["runtime_s"] = rawDataVoltage["timestamp"].apply(self.StringToUNIXTime)
			rawDataVoltage["runtime_s"] = rawDataVoltage["runtime_s"].apply(lambda x: x - exp.startTime)

			#Discard data outside of the start/stop time
			rawDataCO2 = rawDataCO2[rawDataCO2["runtime_s"] >= 0.0]
			rawDataCO2 = rawDataCO2[rawDataCO2["runtime_s"] <= exp.stopTime - exp.startTime]
			rawDataVoltage = rawDataVoltage[rawDataVoltage["runtime_s"] >= 0.0]
			rawDataVoltage = rawDataVoltage[rawDataVoltage["runtime_s"] <= exp.stopTime - exp.startTime]

			#Drop unneeded columns
			rawDataCO2.drop("timestamp", axis=1, inplace=True)
			rawDataVoltage.drop(["data_index", "timestamp", "high_alarm", "low_alarm"], axis=1, inplace=True)

			#Merge dataframes into one
			rawDataExp: pd.DataFrame = pd.concat([rawDataCO2, rawDataVoltage], axis=0, ignore_index=True)

			#Add experiment ID labels to graph
			rawDataExp["label"] = exp.label

			#Finally, append all raw data to dataframe with class scope
			self.rawDataAll = pd.concat([self.rawDataAll, rawDataExp], axis=0, ignore_index=True)
			
			'''
			#Logic to remove outliers from the ED data (for instance when current/air pump shuts off during sampling)

			#First we're gonna lock in the initial timestamp
			initialTimestamp: float = EDMetricCalculations.ToUNIXTime(rawDataED["_time"][0])
			# Then we discard the first 30 minutes of data
			rawDataED = rawDataED.drop(list(range(0, 180))).reset_index()

			# Next we delete the data immediately after sampling while the system is re-equilibrating
			# Setup some constants for the loop
			currentSeries: pd.Series = rawDataED["current_PSU001"]
			#airFlowSeries: pd.Series = rawDataED["volumetric_flow_MFM001"]
			deletionIndices: List[int] = []
			thresholdCurrent: float = 0.9
			thresholdAirFlow: float = 2.5
			belowThreshold: bool = False
			#belowAirFlowThreshold: bool = False
			secondsToDelete: int = 300 #This is kinda overkill. Maybe better to do a second pass of the deletion loop, but with volumetric flowrate. Obviously much more computationally expensive but will give better data
			dataPointsToDelete: int = (int)(secondsToDelete/10)

			# Get the indices where the current returns to normal
			for n in range(0, currentSeries.size):
				if belowThreshold:
					if currentSeries[n] > thresholdCurrent:
						deletionIndices.append(n)
						belowThreshold = False
				else:
					if currentSeries[n] <= thresholdCurrent:
						belowThreshold = True

			#print (deletionIndices)
			# Now we delete the indices and the next minute worth of data
			for index in deletionIndices:
				rawDataED.drop(list(range(index, index + dataPointsToDelete)), inplace=True)
			
			rawDataED.reset_index(drop=True, inplace=True)


			# Now we delete the data points with 0 current and air flow
			rawDataED = rawDataED[rawDataED["current_PSU001"] > thresholdCurrent]
			rawDataED = rawDataED[rawDataED["volumetric_flow_MFM001"] > thresholdAirFlow]

			# For the purposes of smoothing, we're only gonna process a few data points at a time:
			edLowerBound: int = 0
			pcLowerBound: int = 0
			rowCountPC: int = rawDataPC.shape[0]
			rowCountED: int = rawDataED.shape[0]

			while edLowerBound < rowCountED:
				edUpperBound: int = edLowerBound + 100
				pcUpperBound: int = pcLowerBound + 100

				if edUpperBound > rowCountED:
					edUpperBound = rowCountED

				if pcUpperBound > rowCountPC:
					pcUpperBound = rowCountPC
				
				dataSlice: pd.DataFrame = rawDataED.iloc[edLowerBound : edUpperBound]
				pcDataSlice: pd.DataFrame = rawDataPC.iloc[pcLowerBound: pcUpperBound]

				edLowerBound = edUpperBound
				pcLowerBound = pcUpperBound

				#Get "inputs"
				metrics: EDMetricCalculations = EDMetricCalculations(dataSlice)

				exp.processedData["time"].append(((metrics.GetAverageUNIXTimestamp()) - initialTimestamp) / 3600)
				exp.processedData["releasepH"].append(dataSlice["pH_PH001"].mean())
				exp.processedData["capturepHED"].append(dataSlice["pH_PH002"].mean())

				#Get "outputs"

				#Get current efficiency
				currentEfficiencyTuple: Tuple[float, float] = metrics.GetCurrentEfficiency()

				#Ensure calculation was successful
				if math.isnan(currentEfficiencyTuple[0]) or math.isnan(currentEfficiencyTuple[1]):
					print ("Warning: error in calculating current efficiency for experiment labelled:\n\t\"%s\"" % (exp.label), file=sys.stderr)
					currentEfficiencyTuple = (0.0, 0.0)
				
				exp.processedData["currentEfficiency"].append(currentEfficiencyTuple[0])
				exp.processedData["currentEfficiencyError"].append(currentEfficiencyTuple[1])
				
				#Get power consumption
				powerConsumptionTuple: Tuple[float, float] = metrics.GetPowerConsumption()
				
				#Ensure calculation was successful
				if math.isnan(powerConsumptionTuple[0]) or math.isnan(powerConsumptionTuple[1]):
					print ("Warning: error in calculating power consumption for experiment labelled:\n\t\"%s\"" % (exp.label), file=sys.stderr)
					powerConsumptionTuple = (0.0, 0.0)
				
				exp.processedData["powerConsumption"].append(powerConsumptionTuple[0])
				exp.processedData["powerConsumptionError"].append(powerConsumptionTuple[1])
				
				#Get CO2 flux
				fluxCO2Tuple: Tuple[float, float] = metrics.GetCO2Flux()
				
				#Ensure calculation was successful
				if math.isnan(fluxCO2Tuple[0]) or math.isnan(fluxCO2Tuple[1]):
					print ("Warning: error in calculating CO2 flux for experiment labelled:\n\t\"%s\"" % (exp.label), file=sys.stderr)
					fluxCO2Tuple = (0.0, 0.0)
				
				exp.processedData["fluxCO2"].append(fluxCO2Tuple[0])
				exp.processedData["fluxCO2Error"].append(fluxCO2Tuple[1])
				
				#I don't like doing this, but plotly needs it
				exp.processedData["label"].append(exp.label)

				#Now it's time for the PC data
				pcMetrics: PCMetricCalculations = PCMetricCalculations(pcDataSlice, exp.contactingArea, exp.airFlowVelocity)

				exp.processedData["capturepHPC"].append(pcDataSlice["pH_PH001"].mean())


				captureFluxTuple: Tuple[float, float] = pcMetrics.GetCO2Flux()

				#Ensure calculation was successful
				if math.isnan(captureFluxTuple[0]) or math.isnan(captureFluxTuple[1]):
					print ("Warning: error in calculating capture flux for experiment labelled:\n\t\"%s\"" % (exp.label), file=sys.stderr)
					captureFluxTuple = (0.0, 0.0)
				
				exp.processedData["captureFlux"].append(captureFluxTuple[0])
				exp.processedData["captureFluxError"].append(captureFluxTuple[1])

				if "MPA" in exp.label:
					if exp.processedData["time"][-1] > 2.5 and exp.processedData["time"][-1] < 3.5:
						#exp.processedData["captureFlux"][-1] = exp.processedData["captureFlux"][-1] * (0.4/1.3)
						exp.processedData["captureFlux"][-1] = np.nan
				'''


	def PlotData(self) -> None:
		#Exit program if there are no valid experiments
		if not len(self.Experiments):
			raise Exception("Error: No valid experiments found")

		#Combine all processed data into 1 dataframe:
		'''
		allProcessedData: pd.DataFrame = pd.DataFrame()
		for exp in self.Experiments:
			allProcessedData = pd.concat([allProcessedData, pd.DataFrame(exp.processedData)], ignore_index=True)
		'''


		#Make list of plots:
		plots: List[px.plot] = []

		#Actual plotting code:
		plots.append(px.line(self.rawDataAll,
			x="runtime_s",
			y="voltage_v",
			color="label"
		))

		plots[0].update_layout(
			#title="Stack resistance",
			#legend_title="Capture solvent",
			xaxis_title="Time / s",
			yaxis_title="Voltage / V"
		)

		plots.append(px.line(self.rawDataAll,
			x="runtime_s",
			y="co2_ppm",
			color="label"
		))

		plots[1].update_layout(
			xaxis_title="Time / s",
			yaxis_title="[CO<sub>2</sub>] / ppm"
		)

		
		#plots[9].update_traces(connectgaps=True)
		#plots[10].update_traces(connectgaps=True)

#		pio.write_image(plots[10], "./captureFlux_vs_capturepH.png", engine="kaleido", scale=2)
#		pio.write_image(plots[0], "./currentEfficiency_vs_time.png", engine="kaleido", scale=2)
#		pio.write_image(plots[1], "./currentEfficiency_vs_capturepH.png", engine="kaleido", scale=2)
#		pio.write_image(plots[2], "./currentEfficiency_vs_releasepH.png", engine="kaleido", scale=2)
#		pio.write_image(plots[5], "./powerConsumption_vs_releasepH.png", engine="kaleido", scale=2)
#
		#Add plots to HTML doc:
		with open(self.outputFilename, 'w', encoding="utf-8") as Writer:
			Writer.write("""\
<!DOCTYPE html>
<html>
<head>
	<title>ED results</title>
	<style>
		.graph-column{
			width: 45%;
			float: left;
			padding: 5px 12px 0px 0px;
		}
	</style>
</head>
<body>
	<div class=\"graph-row\">\n"""
		)
			
			for n in range(0, len(plots)):
				Writer.write("<div class=\"graph-column\">\n")
				Writer.write(plots[n].to_html(full_html=False))
				Writer.write("</div>")
				if n % 2 == 1:
					Writer.write("\t</div>\n")
					if n < (len(plots) - 1):
						Writer.write("\t<div class=\"graph-row\">\n")

			Writer.write("</body>\n</html>")
