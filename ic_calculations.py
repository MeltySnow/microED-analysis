import pandas as pd
import sys
import math
from typing import Type, Tuple

def LinearRegression(xSeries: pd.Series, ySeries: pd.Series) -> Tuple[float, float]:
	nElements: int = (xSeries.size, ySeries.size)[xSeries.size > ySeries.size]

	xTotal: float = 0
	yTotal: float = 0
	xSquaredTotal: float = 0
	ySquaredTotal: float = 0
	xyTotal: float = 0

	for n in range(0, nElements):
		xTotal += xSeries.iloc[n]
		yTotal += ySeries.iloc[n]

		xSquaredTotal += xSeries.iloc[n] * xSeries.iloc[n]
		ySquaredTotal += ySeries.iloc[n] * ySeries.iloc[n]

		xyTotal += xSeries.iloc[n] * ySeries.iloc[n]
	
	xBar: float = xTotal / nElements
	yBar: float = yTotal / nElements

	sxx: float = xSquaredTotal - (nElements * xBar * xBar)
	#syy: float = ySquaredTotal - (nElements * yBar * yBar)
	sxy: float = xyTotal - (nElements * xBar * yBar)

	slope: float = sxy / sxx
	offset: float = (-1.0 * slope * xBar) + yBar
	#pmcc: float = sxy / math.sqrt(sxx * syy)
	#rSquared: float = pmcc * pmcc

	return (slope, offset)

def CrossingFlux(molPerMinute: float, amine: str) -> float:
	#Converts crossing rate in mol per minute to crossing flux in mg / m^2 s

	#First determine the molar mass of the amine in g / mol
	amineMolarMassMap: dict[str, float] = {
		"MEA": 61.08,
		"MDEA": 119.16,
		"PEI-800": 43.07,
		"PEI": 43.07,
		"PEI-2000": 43.07,
		"T2HPED": 292.41,
		"Arginine": 174.2,
		"MPA": 75.11
	}

	molarMass: float = 0.0

	try:
		molarMass = amineMolarMassMap[amine]
	except Exception as e:
		print ("WARNING: molar mass of \"%s\" was not found" % (amine), file=sys.stderr)
	
	#Convert mol per minute to mol per s
	op: float = molPerMinute / 60.0

	#Convert rate to flux
	membraneArea: float = 0.006 #m^2
	op = op / membraneArea

	#convert mol to mg
	op = op * (molarMass * 1000)

	return op
