from typing import Type
import plotly.express as px

#literally just a struct allowing you to lump metadata into plotly plots
class PlotContainer(object):
	def __init__(self):
		self.plot: px.plot = None
		self.input: str = ""
		self.output: str = ""
		self.writeImage: bool = False
