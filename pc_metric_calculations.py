#import pip packages
from typing import Type, Tuple
import pandas as pd
import math
import time
import datetime

class PCMetricCalculations(object):
	def __init__(self, inputDataWindow: pd.DataFrame, ipContactingArea: float, ipAirVelocity: float):
		# Define constants used in calculations
		self.CO2_DENSITY: float = 1.815 #g dm^{-3}
		self.CO2_MOLAR_MASS: float = 44.01 #g mol^{-1}

		# Initialise member variables
		airInletDiameter: float = 0.1 #m
		self.airVolumetricFlow: float = math.pi * ((airInletDiameter/2)**2) * ipAirVelocity #m^3 s^{-1}
		self.contactingArea: float = ipContactingArea
		self.dataWindow: pd.DataFrame = inputDataWindow


#########################################################
#DEFINE STATIC FUNCTIONS WITH BASIC ARITHMETIC OPERATIONS
#########################################################
	#Division, with functionality for combining errors
	@staticmethod
	def ErrorDivide(a: Tuple[float, float], b: Tuple[float, float]) -> Tuple[float, float]:
		outputValue = a[0] / b[0]
		relativeError = (a[1]/a[0]) + (b[1]/b[0]) 
		outputError = outputValue * relativeError 
		return (outputValue, outputError)

	#Multiplication, with functionality for combining errors
	@staticmethod
	def ErrorMultiply(a: Tuple[float, float], b: Tuple[float, float]) -> Tuple[float, float]:
		outputValue = a[0] * b[0]
		relativeError = (a[1]/a[0]) + (b[1]/b[0]) 
		outputError = outputValue * relativeError 
		return (outputValue, outputError)

	#Converts a datetime-type string to a float representing its UNIX timestamp in seconds
	@staticmethod
	def ToUNIXTime(dateString: datetime) -> float:
		return time.mktime(dateString.timetuple())

	#Integrates series y wrt series x by drawing trapezia between each set of data points and adding their areas
	@staticmethod
	def Integrate(xSeries: pd.Series, ySeries: pd.Series) -> Tuple[float, float]:
		#Initialize variables for integration loop
		integral: float = 0.0
		x: float = 0.0
		y: float = 0.0
		x1: float = xSeries.iloc[0]
		y1: float = ySeries.iloc[0]
		seriesLength: int = xSeries.size

		#Ensure the length of the two series matches. If not, sets seriesLength to that of the smaller series so as to avoid an index out of range error in the loop
		if seriesLength != ySeries.size:
			print ("WARNING: integration error: lengths of x and y series do not match", file=sys.stderr)
			if seriesLength > ySeries.size:
				seriesLength = ySeries.size
		
		#Actual integration loop
		for n in range(1, seriesLength):
			x = x1
			y = y1
			x1 = xSeries.iloc[n]
			y1 = ySeries.iloc[n]

			trapeziumArea: float = ((y + y1) / 2.0) * (x1 - x)
			integral += trapeziumArea
		
		error = ySeries.size * ySeries.std()
		return (integral, error)

###############################
#DEFINE PUBLIC MEMBER FUNCTIONS
###############################
	def GetCO2Flux(self) -> Tuple[float, float]:
		#Select the relevant series
		co2DeltaSeries: pd.Series = self.dataWindow["CO2_PPM_CO2001"].subtract(self.dataWindow["CO2_PPM_CO2002"])
		co2DeltaSeries = co2DeltaSeries.apply(lambda x: x / 1000000.0)

		timeSeries: pd.Series = self.dataWindow["_time"].apply(self.ToUNIXTime)

		co2Flux: Tuple[float, float] = self.Integrate(timeSeries, co2DeltaSeries) # ppm s
		#print ("Breakpoint 1: %f ppm s" % co2Flux[0])
		co2Flux = self.ErrorMultiply(co2Flux, (self.airVolumetricFlow, 0.0)) # m^3
		#print ("Breakpoint 2: %f m^3" % co2Flux[0])
		co2Flux = self.ErrorMultiply(co2Flux, (1000, 0.0)) # dm^3
		#print ("Breakpoint 3: %f dm^3" % co2Flux[0])
		co2Flux = self.ErrorMultiply(co2Flux, (self.CO2_DENSITY, 0.0)) # g
		#print ("Breakpoint 4: %f g" % co2Flux[0])
		co2Flux = self.ErrorMultiply(co2Flux, (1000, 0.0)) # mg
		#print ("Breakpoint 5: %f mg" % co2Flux[0])
		co2Flux = self.ErrorDivide(co2Flux, (self.contactingArea, 0.0)) # mg m^{-2}
		#print ("Breakpoint 6: %f mg m^{-2})" % co2Flux[0])
		deltaTime: float = timeSeries.iloc[timeSeries.size - 1] - timeSeries.iloc[0]
		#print ("Breakpoint 7: deltatime = %f s" % deltaTime)
		co2Flux = self.ErrorDivide(co2Flux, (deltaTime, 0.0))
		#print ("Breakpoint 8: %f mg m^{-2} s^{-1}" % co2Flux[0])

		return co2Flux
