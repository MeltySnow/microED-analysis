# Overview
Python script for automatically processing data logged from Mission Zero Technologies' microED test stand. Functionality covers:
- Downloading experiment metadata and raw data from a Notion dashboard
- Performing arithmetic to extract key performance metrics from the raw data
- Drawing interactive figures using Plotly and inserting them into a custom HTML wrapper

# Dependencies
python3 is required to run this script. It is recommended that you use the latest version of Python. The script has been tested and confirmed to work on version 3.11.

A `requirements.txt` file is provided. It is recommended that you install the required packages to a virtual environment using pip. On a UNIX-like system, this can be done by executing the following commands inside the cloned directory:
```
python3 -m venv venv
source ./venv/bin/activate
python3 -m pip install -r requirements.txt
```

Additionally, a `.env` file is required to run the script. This is not hosted on GitHub as it contains API secrets. If you need to run the script, ask me for a copy of the `.env` file.

# Use
The script can be run using the command:
```
python3 ./main.py [options]
```
Default behaviour is to pull metadata from every completed experiment in the [notion dashboard](https://www.notion.so/mzt/MicroED-AEM-crossover-screening-7f7b3d759880499394355da5333392cb) (with the "Start time", "End time", "CO2 logfile" and "Voltage logfile" columns filled). Experiments will be sorted into chronological order.
If passed any positional arguments, the program wil search the notion dashboard's "Exp Identifier" column for IDs matching the command line arguments, and pull only those entries for analysis. When postional arguments are given, the experiments will not be sorted, and will appear in the output graphs in the order that they are given.

Options are as follows:
```
-h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        Specify the name of the output file. Default is out.html
  -d DASHBOARD, --dashboard DASHBOARD
                        Specify the ID of the Notion dashboard to read from. The default is set in the .env file 
  -x, --exclude         Processes all completed experiments, excluding
                        those supplied as positional arguments
  --config-gen          Generate a config file named .conf with all
                        options set to their defaults and exits
  -c CONFIG, --config CONFIG
                        Specify the name of a config file from which configuration
                        options will be loaded. Options set in this file will
                        always be overridden by command line arguments
```
If the script runs successfully, it will produce a file named `out.html` by default which contains the rendered figures.

### Examples
Processes the experiments with Experiment IDs `MACS008`, `MACS009`, `MACS010` and `MACS011` and saves them to a file called `pei.html`:
```
python3 ./main.py -o pei.html MACS008 MACS009 MACS010 MACS011
```
Processes all completed experiments except for `MACS004`:
```
python3 ./main.py -x MACS004
```
