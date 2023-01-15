# Battery planning and control

Optimise battery charging/discharging with hourly electricity prices for maximised profit.

# Purpose

This is a python program that creates a planning for charging and discharging a home battery system to optimise profit. It can be run in standalone mode or in Domoticz integration mode. 

The standalone mode will interactively request user input and provide feedback on the screen. The Domoticz mode will take the input from Domoticz variables and devices, load the planning onto a Domoticz text device for display and trigger the next action from the planning. The standalone mode will only produce a planning and not trigger any action.

# Stand alone mode

The program will need as input:
1) **Your own API token** from transparancy.entsoe.eu (to be adapted in the program, see below)
2) The planning period
3) The battery characteristics: maximum capacity and maximum charge and discharge speed

The program is intended to be used to plan the rest of today and tomorrow (if the prices for tomorrow are already available, normally after 15:00 hours). However, it can also be run every hour to re-plan the remaining period, given a starting/current charge of that moment. It can even be used to run on historic data to simulate what could have been achieved. At the end of the planning period the remaining charge will be zero and profit optimised.

If the price data from entsoe.eu has been downloaded before it can be re-used from existing files, instead of requesting it again.

The progress, intermediate steps and finals results will be displayed on screen and an output file will be created that can be loaded into a spreadsheet. The level of output can be controlled by command line arguments:
1) -t for tracing. This is a debug mode with full display of intermediate steps and results.
2) -v for verbose. This still shows each next step in the planning and the impact on the overall plan.
3) -q for quiet. Minimal output. Default.

-s is the command line argument for standalone mode and is the default.

# Domoticz integration mode

The program will take input from Domoticz variables and devices and will trigger output onto Domoticz devices as well. The idx numbers for these devices will need to be adapted in the program and in the Domoticz script(s) as these differ for each operating environment.

The following Domoticz variables and devices need to be set up and adapted in the python program:
# variables 
securityTokenIDX=12                 # the IDX of the Domoticz user variable holding the API security token for transparency.entsoe.eu
maxBatteryCapacityIDX=14            # the IDX of the Domoticz user variable holding the value for the maximum available battery charge capacity
maxBatteryChargeSpeedIDX=15         # the IDX of the Domoticz user variable holding the value for the maximum charge speed
maxBatteryDischargeSpeedIDX=16      # the IDX of the Domoticz user variable holding the value for the maximum discharge speed
## devices
planningDisplayIDX=111              # the IDX number of a Domoticz text device to use for display of the planning
batterySwitchIDX=112                # the IDX of the Domoticz selector switch for controlling the battery system actions 
                                    # (API commands for control of the battery system need to be set in the "selector action" fields of the device)
batteryOffCode=0                    # the 3 level numbers as defined in the selector switch for Off/Charge/Discharge (0,10 and 20 by default)
batteryChargeCode=10
batteryDischargeCode=20
batteryChargeLevelIDX=113           # the IDX of the Domoticz device with updated actual battery charge level (should be updated through the battery system API)

The Domoticz integration mode is trigger by the Domoticz dzVents script. The script requires also some of the same idx numbers. The Domoticz integration mode can also be run from the Unix command line for testing using the "-d" command line argument (so type "python3 dz-battery-planning.py -d"). The Domoticz mode only creates a planning for maximum one day ahead, depending on availablity of prices.

Every time a new planning is created, the next required action is fed back into the dzVents script and then the relevant API commands are given to the battery system.

Note that the current version is for simulation purposes only so no actual battery interface is present and the interface is assumed to be very simple. The abttery system sends a current charge level and can receive three commands: Off, Charge, Discharge.

# Limitation of the program

It does not take into account any tax effects in the planning as these will differ strongly from country to country, but this could easily be added.

It assumes a 100% efficiency in the process, i.e. the energy received and paid for from the grid is fully stored in the battery (and vice versa). Once a real efficiency is known, this should be included in the profitability calculation of each charge/discharge and discharge/charge action pair.

It does not yet plan for electricity consumption or production (solar) in the home network. It can however be used to re-plan after a situation has changed as result of consumption or production.

# Get your API token for retrieving electricity prices.

To get an API token (it is free):
1. Register for an account at https://transparency.entsoe.eu/dashboard/show
2. Send an email with subject "Restful API access" and your account email address in the body.
3. After receipt of their confirmation, go into your account and generate your token.
4. Copy and paste the token to replace the xxxxxx on line 23 of the python program where it says securitytoken="xxxxxxxxxxx" 

# Program internal logic

A short description of the internals of the program:
1. Prices are loaded onto a hourPriceList and a displayList. The displayList is for display and for tracking of the results. The hourPriceList is used for the planning process.
2. The hourPriceList is combined with itself to form pairs of charge-discharge and discharge-charge actions. These are put onto the pairList and are sorted top-down for maximum profitability.
3. The pairList is run down from top to bottom to select the pairs that still fit onto the planning, taking into account previously planned actions and maximum battery capacity and maximum charge and discharge speeds. It restarts from the top after each action, since a discharge/charge action could open up capacity for a charge/discharge that did not exist before due to maximum capacity. This continues until the end of the list is reached.
4. The next period is processed by re-starting at step 1.

