#Import pip packages
from typing import Type, List, Tuple
import requests, json
import numpy as np
import pandas as pd
import os
import time
import math
from datetime import datetime, timedelta
import notion_df # type: ignore
import sys
from dotenv import load_dotenv
import plotly.express as px # type: ignore
import plotly.io as pio # type: ignore
import argparse

#Import project files
from experiment_meta import ExperimentMeta
from ed_metric_calculations import EDMetricCalculations
import ic_calculations
from plot_container import PlotContainer
from file_to_string import ftos

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
		#I don't think that Vaisala nor EasyLog account for timezone, so this will probably break once we go back to GMT lmao
		return op

	def ProcessData(self) -> None:
		self.rawDataAll: pd.DataFrame = pd.DataFrame()
		self.rawDataICAll: pd.DataFrame = pd.DataFrame()
		for exp in self.Experiments:
			#Create DataFrame with data for a single experiment
			rawDataCO2: pd.DataFrame = pd.read_csv(exp.CO2LogfileURL, header=8, names=["timestamp", "co2_ppm"])
			rawDataVoltage: pd.DataFrame = pd.read_csv(exp.voltageLogfileURL, header=2, names=["data_index", "timestamp", "voltage_v", "high_alarm", "low_alarm"])
			if exp.icLogfileURL:
				rawDataIC: pd.DataFrame = pd.read_csv(exp.icLogfileURL, header=0, names=["time_min", "amine_area", "k+_area", "amine_ppm", "amine_mol/kg", "amine_mol"])

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

			#Reset indices so that the dataframes are correctly 0-indexed:
			rawDataCO2.reset_index(drop=True, inplace=True)
			rawDataVoltage.reset_index(drop=True, inplace=True)

			#Drop unneeded columns
			rawDataCO2.drop("timestamp", axis=1, inplace=True)
			rawDataVoltage.drop(["data_index", "timestamp", "high_alarm", "low_alarm"], axis=1, inplace=True)
			if exp.icLogfileURL:
				#rawDataIC.drop(["amine_area", "k+_area", "amine_ppm", "amine_mol/kg"], axis=1, inplace=True)
				rawDataIC.drop(["amine_area", "k+_area", "amine_ppm"], axis=1, inplace=True)
				rawDataIC["amine_mol/kg"] = rawDataIC["amine_mol/kg"].apply(lambda x: x if x >= 0.0 else 0.0)
				rawDataIC["amine_mol"] = rawDataIC["amine_mol"].apply(lambda x: x if x >= 0.0 else 0.0)

			#Discard outliers using a rolling average
			rollWindowSize: int = 5
			thresholdTolerance: float = 0.15
			#CO2 data
			co2ppmSeries: pd.Series = rawDataCO2["co2_ppm"]
			co2ppmSeriesRoll: pd.Series = co2ppmSeries.rolling(rollWindowSize).median()

			roll: list[float] = []
			nextToReplace: int = 0
			for n in range(0, rollWindowSize):
				roll.append(co2ppmSeries[n])

			for n in range(rollWindowSize, co2ppmSeries.size):
				sortedRoll: list[float] = self.MergeSort(roll)
				rollingMedian: float = sortedRoll[(int)(rollWindowSize / 2.0)]

				if co2ppmSeries.iloc[n] > rollingMedian * (1.0 + thresholdTolerance) or co2ppmSeries.iloc[n] < rollingMedian * (1.0 - thresholdTolerance):
					rawDataCO2.drop(n, axis=0, inplace=True)
				else:
					roll[nextToReplace % rollWindowSize] = co2ppmSeries.iloc[n]
					nextToReplace += 1

			#Drop outliers for voltage data
			if exp.current > 0.0:
				voltageSeries: pd.Series = rawDataVoltage["voltage_v"]
				startIndex: int = 0
				nextToReplace = 0
				
				while voltageSeries[startIndex] <= 0.01:
					rawDataVoltage.drop(startIndex, axis=0, inplace=True)
					startIndex += 1

				for n in range(startIndex, startIndex + rollWindowSize):
					roll[nextToReplace] = voltageSeries[n]
					nextToReplace += 1

				for n in range(startIndex + rollWindowSize, voltageSeries.size):
					sortedRoll = self.MergeSort(roll)
					rollingMedian = sortedRoll[(int)(rollWindowSize / 2.0)]

					if voltageSeries.iloc[n] > rollingMedian * (1.0 + thresholdTolerance) or voltageSeries.iloc[n] < rollingMedian * (1.0 - thresholdTolerance):
						rawDataVoltage.drop(n, axis=0, inplace=True)
					else:
						roll[nextToReplace % rollWindowSize] = voltageSeries.iloc[n]
						nextToReplace += 1


			rawDataCO2.reset_index(drop=True, inplace=True)
			rawDataVoltage.reset_index(drop=True, inplace=True)

			#Merge dataframes into one
			rawDataExp: pd.DataFrame = pd.concat([rawDataCO2, rawDataVoltage], axis=0, ignore_index=True)

			#Add experiment ID labels to graph
			rawDataExp["label"] = exp.label
			if exp.icLogfileURL:
				rawDataIC["label"] = exp.label

			#Finally, append all raw data to dataframe with class scope for plotting later
			self.rawDataAll = pd.concat([self.rawDataAll, rawDataExp], axis=0, ignore_index=True)
			if exp.icLogfileURL:
				self.rawDataICAll = pd.concat([self.rawDataICAll, rawDataIC], axis=0, ignore_index=True)


			#Now we start processing the data
			kpm = EDMetricCalculations(rawDataExp, exp)

			stackResistanceTuple: Tuple[float, float] = (0.0, 0.0)
			currentEfficiencyTuple: Tuple[float, float] = (0.0, 0.0)
			powerConsumptionTuple: Tuple[float, float] = (0.0, 0.0)
			fluxCO2Tuple: Tuple[float, float] = (0.0, 0.0)

			if exp.current > 0.0:
				try:
					stackResistanceTuple = kpm.GetStackResistance()
				except Exception as e:
					print (e, file=sys.stderr)

				try:
					currentEfficiencyTuple = kpm.GetCurrentEfficiency()
				except Exception as e:
					print (e, file=sys.stderr)

				try:
					powerConsumptionTuple = kpm.GetPowerConsumption()
				except Exception as e:
					print (e, file=sys.stderr)

			try:
				fluxCO2Tuple = kpm.GetCO2Flux()
			except Exception as e:
				print (e, file=sys.stderr)
			
			exp.processedData["stackResistance"].append(stackResistanceTuple[0])
			exp.processedData["stackResistanceError"].append(stackResistanceTuple[1])

			exp.processedData["currentEfficiency"].append(currentEfficiencyTuple[0])
			exp.processedData["currentEfficiencyError"].append(currentEfficiencyTuple[1])
			
			exp.processedData["powerConsumption"].append(powerConsumptionTuple[0])
			exp.processedData["powerConsumptionError"].append(powerConsumptionTuple[1])
			
			exp.processedData["fluxCO2"].append(fluxCO2Tuple[0])
			exp.processedData["fluxCO2Error"].append(fluxCO2Tuple[1])

			#Now process the amine crossing data:
			if exp.icLogfileURL:
				crossingRate: float = ic_calculations.LinearRegression(rawDataIC["time_min"], rawDataIC["amine_mol"])[0]
				exp.processedData["amineFlux"].append(ic_calculations.CrossingFlux(crossingRate, exp.amine))
			else:
				exp.processedData["amineFlux"].append(0.0)

			currentProcessedDataIndex: int = len(exp.processedData["amineFlux"]) - 1
			exp.processedData["aminePerCO2"].append(exp.processedData["amineFlux"][currentProcessedDataIndex] / exp.processedData["fluxCO2"][currentProcessedDataIndex])
			
			#I don't like doing this, but plotly needs it
			exp.processedData["label"].append(exp.label)

			#Now we loop through and get some metrics with a higher time resolution
			if exp.icLogfileURL and exp.current > 0.0:
				timeWindow: int = 900
				windowDuration: int = 300
				while timeWindow + (windowDuration / 2) < rawDataExp["runtime_s"].iloc[rawDataExp["runtime_s"].size - 1]:
					dataFrameWindow: pd.DataFrame = rawDataExp[rawDataExp["runtime_s"] > timeWindow - (windowDuration / 2)]
					dataFrameWindow= dataFrameWindow[dataFrameWindow["runtime_s"] < timeWindow + (windowDuration / 2)]
					if dataFrameWindow["co2_ppm"].dropna().size > 0 and dataFrameWindow["voltage_v"].dropna().size > 0:
						trm: EDMetricCalculations = EDMetricCalculations(dataFrameWindow, exp)
						
						trPowerConsumptionTuple: Tuple[float, float] = (0.0, 0.0)
						try:
							trPowerConsumptionTuple = trm.GetPowerConsumption()
						except Exception as e:
							print (e, file=sys.stderr)

						releaseAmineConcTuple: Tuple[float, float] = ic_calculations.LinearRegression(rawDataIC["time_min"], rawDataIC["amine_mol/kg"])
						releaseAmineConc: float = releaseAmineConcTuple[0] * (float(timeWindow) / 60.0) + releaseAmineConcTuple[1]

						if releaseAmineConc >= 0.0:
							exp.timeResolvedData["time_min"].append((float(timeWindow) / 60.0))
							exp.timeResolvedData["powerConsumption"].append(trPowerConsumptionTuple[0])
							exp.timeResolvedData["powerConsumptionError"].append(trPowerConsumptionTuple[1])
							exp.timeResolvedData["label"].append(exp.label)
							exp.timeResolvedData["releaseAmineConc"].append(releaseAmineConc)

					timeWindow += windowDuration



	def PlotData(self) -> None:
		#Exit program if there are no valid experiments
		if not len(self.Experiments):
			raise Exception("Error: No valid experiments found")

		#Combine all processed data into 1 dataframe:
		allProcessedData: pd.DataFrame = pd.DataFrame()
		allTimeResolvedData: pd.DataFrame = pd.DataFrame()
		for exp in self.Experiments:
			allProcessedData = pd.concat([allProcessedData, pd.DataFrame(exp.processedData)], ignore_index=True)
			allTimeResolvedData = pd.concat([allTimeResolvedData, pd.DataFrame(exp.timeResolvedData)], ignore_index=True)


		#Make list of plots:
		plots: List[PlotContainer] = []

		#Actual plotting code:
		currentPlot: PlotContainer = PlotContainer()

		currentPlot.plot = px.line(self.rawDataAll,
			x="runtime_s",
			y="voltage_v",
			color="label"
		)
		currentPlot.plot.update_layout(
			title=dict(text="Voltage vs time", font=dict(size=18)),
			legend_title="Capture solvent",
			xaxis_title=dict(text="Time / s", font=dict(size=18)),
			yaxis_title=dict(text="Voltage / V", font=dict(size=18))
		)
		currentPlot.input = "time"
		currentPlot.output = "voltage"
		plots.append(currentPlot)
		currentPlot = PlotContainer()

		currentPlot.plot = px.line(
			self.rawDataAll,
			x="runtime_s",
			y="co2_ppm",
			color="label"
		)
		currentPlot.plot.update_layout(
			title=dict(text="Release CO<sub>2</sub> concentration vs time", font=dict(size=18)),
			xaxis_title=dict(text="Time / s", font=dict(size=18)),
			yaxis_title=dict(text="[CO<sub>2</sub>] / ppm", font=dict(size=18)),
			legend_title="Capture solvent"
		)
		currentPlot.input = "time"
		currentPlot.output = "co2ppm"
		plots.append(currentPlot)
		currentPlot = PlotContainer()

		currentPlot.plot = px.line(
			self.rawDataICAll,
			x="time_min",
			y="amine_mol",
			color="label"
		)
		currentPlot.plot.update_layout(
			title=dict(text="Total amine crossover vs time", font=dict(size=18)),
			xaxis_title=dict(text="Time / min", font=dict(size=18)),
			yaxis_title=dict(text="Total amine crossover / mol", font=dict(size=18)),
			legend_title="Capture solvent"
		)
		currentPlot.input = "time"
		currentPlot.output = "amineCrossed"
		plots.append(currentPlot)
		currentPlot = PlotContainer()

		currentPlot.plot = px.bar(
			allProcessedData,
			x="label",
			y="stackResistance",
			error_y="stackResistanceError"
		)
		currentPlot.plot.update_layout(
			title=dict(text="Average stack resistance", font=dict(size=18)),
			yaxis_title=dict(text="Stack resistance / Ω", font=dict(size=18)),
			xaxis_title=""
		)
		currentPlot.input = "experimentalAverage"
		currentPlot.output = "stackResistance"
		plots.append(currentPlot)
		currentPlot = PlotContainer()

		currentPlot.plot = px.bar(
			allProcessedData,
			x="label",
			y="currentEfficiency",
			error_y="currentEfficiencyError"
		)
		currentPlot.plot.update_layout(
			title=dict(text="Average current efficiency", font=dict(size=18)),
			yaxis_title=dict(text="Current efficiency / %", font=dict(size=18)),
			xaxis_title=""
		)
		currentPlot.input = "experimentalAverage"
		currentPlot.output = "currentEfficiency"
		plots.append(currentPlot)
		currentPlot = PlotContainer()

		currentPlot.plot = px.bar(
			allProcessedData,
			x="label",
			y="powerConsumption",
			error_y="powerConsumptionError"
		)
		currentPlot.plot.update_layout(
			title=dict(text="Average power consumption", font=dict(size=18)),
			yaxis_title=dict(text="Power consumption / kWh t<sup>-1</sup> CO<sub>2</sub>", font=dict(size=18)),
			xaxis_title=""
		)
		currentPlot.input = "experimentalAverage"
		currentPlot.output = "powerConsumption"
		plots.append(currentPlot)
		currentPlot = PlotContainer()

		currentPlot.plot = px.bar(
			allProcessedData,
			x="label",
			y="fluxCO2",
			error_y="fluxCO2Error"
		)
		currentPlot.plot.update_layout(
			title=dict(text="Average CO<sub>2</sub> flux", font=dict(size=18)),
			yaxis_title=dict(text="Release flux / mg m<sup>-2</sup> s<sup>-1</sup>", font=dict(size=18)),
			xaxis_title=""
		)
		currentPlot.input = "experimentalAverage"
		currentPlot.output = "releaseFlux"
		plots.append(currentPlot)
		currentPlot = PlotContainer()

		currentPlot.plot = px.bar(
			allProcessedData,
			x="label",
			y="amineFlux"
		)
		currentPlot.plot.update_layout(
			title=dict(text="Amine crossover flux", font=dict(size=18)),
			yaxis_title=dict(text="Amine crossover flux / mg m<sup>-2</sup> s<sup>-1</sup>", font=dict(size=18)),
			xaxis_title=""
		)
		currentPlot.input = "experimentalAverage"
		currentPlot.output = "amineFlux"
		plots.append(currentPlot)
		currentPlot = PlotContainer()

		allProcessedData["aminePerCO2"] = allProcessedData["aminePerCO2"].apply(lambda x : x * 1000)
		currentPlot.plot = px.bar(
			allProcessedData,
			x="label",
			y="aminePerCO2"
		)
		currentPlot.plot.update_layout(
			title=dict(text="Amine crossing vs CO<sub>2</sub> captured", font=dict(size=18)),
			yaxis_title=dict(text="Amine crossover per CO2 captured / kg ton<sup>-1</sup>", font=dict(size=18)),
			xaxis_title=""
		)
		currentPlot.input = "experimentalAverage"
		currentPlot.output = "aminePerCO2"
		plots.append(currentPlot)
		currentPlot = PlotContainer()

		currentPlot.plot = px.line(
			allTimeResolvedData,
			x="releaseAmineConc",
			y="powerConsumption",
			error_y="powerConsumptionError",
			color="label"
		)
		currentPlot.plot.update_layout(
			title=dict(text="Power consumption vs release amine concentration", font=dict(size=18)),
			xaxis_title=dict(text="Release amine concentration / mol kg<sup>-1</sup>", font=dict(size=18)),
			yaxis_title=dict(text="Power consumption / kWh t<sup>-1</sup> CO<sub>2</sub>", font=dict(size=18)),
			legend_title="Amine"
		)
		currentPlot.input = "releaseAmineConc"
		currentPlot.output = "powerConsumption"
		plots.append(currentPlot)
		
		#Add plots to HTML doc:
		with open(self.outputFilename, 'w', encoding="utf-8") as Writer:
			Writer.write(f"""\
<!DOCTYPE html>
<html>
<head>
	<title>microED results</title>
	<style>
		{ftos("graphsheet.css")}
	</style>
	<script>
		{ftos("filter.js")}
	</script>
</head>
<body onload="PageLoadInit()">
	<div class="filter-row">
		<div class="filter-list" style="margin: 0% -25% 0% 0%;">
			<p class="filter-title">Filter by input</p>
			<input type="checkbox" class="input" value="input-time" checked="true"/>
			<label>Time</label><br>
			<input type="checkbox" class="input" value="input-experimentalAverage" checked="true"/>
			<label>Experimental average</label><br>
			<input type="checkbox" class="input" value="input-releaseAmineConc" checked="true"/>
			<label>Release amine concentration</label><br>
			<button onclick="TickAll('input', true)">Select all</button><br>
			<button onclick="TickAll('input', false)">Deselect all</button><br>
		</div>
		<div class="filter-list">
			<p class="filter-title">Filter by output</p>
			<input type="checkbox" class="output" value="output-voltage" checked="true"/>
			<label>Voltage</label><br>
			<input type="checkbox" class="output" value="output-co2ppm" checked="true"/>
			<label>CO<sub>2</sub> ppm</label><br>
			<input type="checkbox" class="output" value="output-powerConsumption" checked="true"/>
			<label>Power Consumption</label><br>
			<input type="checkbox" class="output" value="output-currentEfficiency" checked="true"/>
			<label>Current Efficiency</label><br>
			<input type="checkbox" class="output" value="output-releaseFlux" checked="true"/>
			<label>Release flux</label><br>
			<input type="checkbox" class="output" value="output-amineFlux" checked="true"/>
			<label>Amine crossing flux</label><br>
			<input type="checkbox" class="output" value="output-aminePerCO2" checked="true"/>
			<label>Amine crossed per unit CO2</label><br>
			<input type="checkbox" class="output" value="output-amineCrossed" checked="true"/>
			<label>Total amine crossed</label><br>
			<input type="checkbox" class="output" value="output-stackResistance" checked="true"/>
			<label>Stack resistance</label><br>
			<button onclick="TickAll('output', true)">Select all</button><br>
			<button onclick="TickAll('output', false)">Deselect all</button><br>
		</div>
	</div>
	<div class=\"graph-row\">\n"""
		)
			
			for n in range(0, len(plots)):
				Writer.write(f"<div class=\"graph-column input-{plots[n].input} output-{plots[n].output}\">\n")
				Writer.write(plots[n].plot.to_html(full_html=False))
				Writer.write("</div>")
				if n % 2 == 1:
					Writer.write("\t</div>\n")
					if n < (len(plots) - 1):
						Writer.write("\t<div class=\"graph-row\">\n")

			Writer.write("</body>\n</html>")
