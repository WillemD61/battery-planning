# Battery planning and control

Plan and optimise battery charging/discharging for maximised profit using hourly electricity prices, with the option to include solar panel production forecast. Either plan the day ahead or simulate the past.

NOTE: the program has been adapted to handle 15 minute prices but at the moment only using a workaround: 15 minute prices are converted to hourly averages and then optimisation takes place with those hourly prices.

# Purpose

This is a python program that creates a planning for charging and discharging a home battery system to optimise profit. It can be run in standalone mode or in Domoticz integration mode. (with the -s or -d command line argument)

The standalone mode will interactively request user input and provide feedback on the screen. The Domoticz mode will take the input from Domoticz variables and devices, load the planning onto a Domoticz text device for display and trigger the next action from the planning. The standalone mode will only produce a planning (into a file and onto the screen) and not trigger any action.

The domoticz version has the option to include solar panel production forecast in the planning (with the -p command line argument). It will take location and pv panel configuration data from domoticz variables and obtain production forecast for current and next day from the website forecast.solar

Call: python3 dz-battery-planning.py

Command line options:
*    -d or -s for domoticz or standalone mode
*    -t, -v or -q to contol the level of output
*    -p for inclusion of solar panel production (only in domoticz mode)

# Stand alone mode

The program will need as input:
1) **Your own API token** from transparancy.entsoe.eu (to be adapted in the program, see below)
2) The planning period
3) The battery characteristics: maximum capacity, maximum charge and discharge speed, conversion efficiency

The main purpose of the program is to plan today and tomorrow (if the prices for tomorrow are already available, normally after 15:00 hours). It can be re-run at any time to re-plan the remaining period, given an initial charge of that moment. 

It can however also be used to run on historic price data to simulate what could have been achieved and to evaluate return on investment for a battery system. At the end of the planning period the remaining charge will be zero and profit optimised.

If the price data from entsoe.eu has been downloaded before it can be re-used from existing files, instead of requesting it again.

The progress, intermediate steps and finals results will be displayed on screen and an output file will be created that can be loaded into a spreadsheet. The level of output can be controlled by command line arguments:
* -t for tracing. This is a debug mode with full display of intermediate steps and results.
* -v for verbose. This still shows each next step in the planning and the impact on the overall plan.
* -q for quiet. Minimal output. Default.

-s is the command line argument for standalone mode and is the default.

Note the price data from the entsoe website is stored in local xml files with a timestamp and not automatically removed, so some manual maintenance of the file system will be required at some point.

# Domoticz integration mode

For this integration both the python program and the dzVents scripts (published here as .txt files) are needed. The dzVents file contents should be copied and pasted into a script via the Domoticz interface. The python program is expected in the domoticz/python folder (please adapt the dzVents script if a different folder is used)

The program will take input from Domoticz variables and devices and will trigger output onto Domoticz devices. The idx numbers show below for these devices will need to be adapted in the program and in the Domoticz script(s) as these differ for each operating environment.

The following Domoticz variables and devices need to be set up and adapted in the python program:

Variables: 
* securityTokenIDX=12                 # the IDX of the Domoticz user variable holding the API security token for transparency.entsoe.eu
* maxBatteryCapacityIDX=14            # the IDX of the Domoticz user variable holding the value for the maximum available battery charge capacity (in Wh)
* maxBatteryChargeSpeedIDX=15         # the IDX of the Domoticz user variable holding the value for the maximum charge speed (in W)
* maxBatteryDischargeSpeedIDX=16      # the IDX of the Domoticz user variable holding the value for the maximum discharge speed (in W)
* conversionEfficiency=20             # the IDX of the Domoticz user variable holding the value for the conversion efficiency percentage
  
Devices:
* planningDisplayIDX=111              # the IDX number of a Domoticz text device to use for display of the planning
* batterySwitchIDX=112                # the IDX of the Domoticz selector switch for controlling the battery system actions 
                                      # (API commands for control of the battery system need to be set in the "selector action" fields of the device)
* batteryOffCode=0                    # the 3 level numbers as defined in the selector switch for Off/Charge/Discharge (0,10 and 20 by default)
* batteryChargeCode=10
* batteryDischargeCode=20
* batteryChargeLevelIDX=113           # the IDX of the Domoticz device with updated actual battery charge level, in percent (should be updated through the battery system API)

The Domoticz integration mode is normally triggered by a call from the Domoticz dzVents script. The dzVents script requires also some of the same idx numbers as the python program (so please adapt for your environment). The Domoticz integration mode can also be run from the Unix command line for testing purposes using the "-d" command line argument (so type "python3 dz-battery-planning.py -d"). The Domoticz mode creates a planning for maximum one day ahead, depending on availability of prices.

Every time a new planning is created, the next required action is fed back into the dzVents script and then the relevant API commands are given to the battery system by the script. The total planning is displayed in the log of the text device and also highlights the top 5 lowest prices in the remaining free/unclassified hours (provided those are below the average price of the day). Those are the best times for heavy electricity consumers, like tumbledryers, washing machines, electric cars etc. 

Note that the current version is for simulation purposes only so no actual battery interface is present and the interface is assumed to be very simple, as follows: battery system sends a current charge level and can receive three commands: Off, Charge, Discharge. The controlling script will send those commands depending on the action and the target charge level received from the planning program verus current charge level.

A separate dzVents script is created to simulate a battery system in absence of a real setup. 

With some more work Domoticz scripts could be create to interface to a real battery system. Or you could use to check your current battery system behaviour against the optimised plan.

The Domoticz mode re-uses the entsoe.xml file (without timestamp in the name) for storing price data so no manual maintenance of the file system is required.

# Solar/PV panel production integration

If the -p option is added to the call of the python program, then the forecasted production of the PV panels will be included in the planning. For this the location (latitude/longitude) settings in Domoticz need to be defined and the following user variables need to be set up (with IDX numbers adapted to the environment)

* pvPanelAngleIDX=17                  # the IDX of the Domoticz user variable holding the value of the PV panel angle (in degrees, horizontal = 0)
* pvPanelAzimuthIDX=18                # the IDX of the Domoticz user variable holding the value of the PV panel azimuth (in degrees, south = 0)
* pvPanelMaxPeakIDX=19                # the IDX of the Domoticz user variable holding the value of the PV panel max peak kWH

The forecast will be obtained from forecast.solar and shown as separate lines in the planning. For each line it will be defined whether to store the production in the battery system or to return it to the grid. The charge/discharge action related to the price line in the same hour will be adapted accordingly.

As the PV production is a forecast only and actual PV production will deviate, it is recommended to re-run the planning frequently, but please note that the free API of forecast.solar will only allow 10 calls per hour.

The control of the battery system will be based on target charge level for the hour, including the PV forecast.

# Conversion efficiency

Latest addition to the program is the conversion efficiency, i.e. a percentage indicating the difference between the quantities measured from/to the grid and the quantities charged/discharged by the battery system.

For example, a conversion efficiency percentage of 90 indicates:
1) to store 1 kWh in the battery one would have to import 1/0.9=1.1 kWh from the grid
2) a discharge of 1 kWh from the battery would result in a return of 1*0.9=0.9 kWh to the grid
so in this example one would be paying for 1.1 kWh and getting paid for 0.9 kWh.
As result, some combinations of hourly prices will no longer be profitable.

# Limitations of the program

It does not take into account any tax effects in the planning as these will differ strongly from country to country, but this could easily be added.

It also assumes a linear charge/discharge curve (for example when calculating remaining charge/discharge capacity for part of an hour).

It does not plan for electricity consumption in the home network. It can however be used to re-plan after a situation has changed as result of consumption. It also indicates the remaining cheapest hours without any planned action (with low_1, low_2 etc).

# Get your API token for retrieving electricity prices.

To get an API token (it is free):
1. Register for an account at https://transparency.entsoe.eu/dashboard/show
2. Send an email with subject "Restful API access" and your account email address in the body.
3. After receipt of their confirmation, go into your account and generate your token.
4. Copy and paste the token to replace the xxxxxx on the line indicated in the python program where it says securitytoken="xxxxxxxxxxx" (line 52). For the Domoticz mode copy and paste the token onto the Domoticz user variable.

# Program internal logic

A short description of the internals of the program:
1. Prices are loaded onto a hourPriceList and a displayList. The displayList is for display and for tracking of the results. The hourPriceList is used for the planning process.
2. The hourPriceList is combined with itself to form pairs of charge-discharge and discharge-charge actions. These are put onto the pairList and are sorted top-down for maximum profitability.
3. The pairList is run down from top to bottom to select the pairs that still fit onto the planning, taking into account previously planned actions and maximum battery capacity and maximum charge and discharge speeds. It restarts from the top after each action, since a discharge/charge action could open up capacity for a charge/discharge that did not exist before due to maximum capacity. This continues until the end of the list is reached.
4. The next period is processed by re-starting at step 1.

# dzVents scripts

Two dzVents scripts are provided. One to trigger the launch of the python program, receive the resulting action and send the command to the battery system, and a second to simulate a battery system charging/discharging and providing a current charge level back through the interface.

The tracking of actual profit will be added as next step.

# Domoticz setup images and screenshots

The switch for manually triggering the planning
![image](https://user-images.githubusercontent.com/96531991/212547487-329c83ae-4070-46af-86eb-f4ed0b6f3b70.png)

The user variables (except for the security token)
![image](https://user-images.githubusercontent.com/96531991/212547552-32353be2-04bb-4c5a-b441-3728d2ee0f08.png)

The battery selector switch icon
![image](https://user-images.githubusercontent.com/96531991/212547623-95a5eac5-0fa3-4787-9d9d-a73fd867da6b.png)

and the setup of the selector switch
![image](https://user-images.githubusercontent.com/96531991/212547837-f85c898f-fba8-40c4-a4a3-3976ba3605f1.png)

The icon of the text display device for the planning
![image](https://user-images.githubusercontent.com/96531991/212548033-fbec377b-8001-4a6b-a14e-a2da203b418c.png)

And the detail log of the text display device (note the domoticz font was changed to monospace to get a tabular format)
![image](https://user-images.githubusercontent.com/96531991/212548120-105a24e5-d3b8-4ff6-a8e9-4460c3a9ab04.png)







