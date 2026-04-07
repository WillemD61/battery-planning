
# Battery planning and control

Plan and optimise battery charging/discharging for maximised profit using hourly or 15-minute electricity prices, with the option to include solar panel production forecast and expected power usage. Normally used to plan day-ahead but can also simulate the past (provided certain conditions are met, see below).

It takes a linear programming optimisation approach for all intervals (15-min or hour) with a known price, so normally until 24:00 today or tomorrow (if tomorrows prices are already known, normally after 13:00).

The program is now designed to drive a Marstek battery, but can easily be adapted to drive other batteries, or run standalone without interface.

# Main Purpose

The main purpose of the program is to plan today and tomorrow. It can be re-run at any time to re-plan the remaining period, given the actual charge level of that moment. 

It is a python program that is started from a command line with various command line options to control behaviour. You can choose from:

* -t , -v , -q : tracing, verbose or quiet to specifiy output details for debuggin
* -d , -i, -s  : full domoticz integration (both input and output), integrated for input only with output to a file, standalone with manual input and output to a file
* -p : to include PV forecast (or actual for past dates)
* -u : to include estimate power usage, based on details available in domoticz short history
* -n : netting/saldering applied, affects price for return to grid
* -b : tax included (energytax and VAT/BTW)
* -z : zero import from grid (discouraged, might not always leed to optimised results)
* -h : hourly average price, otherwise 15-minute prices
* -m : use mqtt communication to Marstek cloud to get current capacity and to set mode , instead of Marstek Venus plugin via Open API. If using mqtt, please allow for the 30 seconds intervals between mqtt commands to complete. 

It can for example be scheduled from cron, from domoticz or run manually. It is specifically designed to run at the start of each price interval (for example hour) to set the battery mode for the coming interval, but taking into accouunt all know future prices etc. 

As an example, I currently use it with the following line in the crontab:
0 * * * * /usr/bin/python3 /home/pi/hame-relay/Marstek-planning.py -d -p -u -n -b -h -m >> /home/pi/hame-relay/batteryplanning.log 2>&1

The standalone mode will interactively request user input and provide feedback on the screen and in a file. The Domoticz mode will take the input from Domoticz variables and devices, load the planning onto a Domoticz text device for display and trigger the next action from the planning and send it to the battery. The standalone mode will only produce a planning (into a file) and not trigger any action.

It has the option to include solar panel production forecast in the planning for multiple pv panels groups (with the -p command line argument). It will take location and pv panel configuration data and request the forecast from forecast.solar website.

Prices will be taken from entsoe (eu transparency site) or, if not available or complete, from the energyzero website. An API token from entsoe is required, see below. Additional kWh pricing elements can be specified, such as energy tax, supplier purchase fee, network fee, cycle costs, VAT/BTW percentage.

The -m option can be used to circumvent the Marstek open API plugin setup and communicate directly with the Marstek cloud via mqtt. The hame relay setup is required for this (https://github.com/tomquist/hame-relay docker setup without home assistant) and the MAC address of the Marstek battery needs to be provided. Make sure hame-relay is tested (for example with mosquitto_sub and mosquitto_pub commands) and working before using the mqtt option here. 

Of course battery characteristics such as current charge, maximum and minimum capacity, maximum charge-speed and discharge-speed and conversion efficiency are taken into account.

# Simulate the past

It can also be used to run on historic price data to simulate what could have been achieved and to evaluate return on investment for a battery system. It will simulate and optimise each day, starting at 15:00 hrs to 24:00 the next day, for the total period requested.

If the price data from entsoe.eu has been downloaded before it can be re-used from existing files, instead of requesting it again. Note during simulation of the past the price data from the entsoe website is stored in local xml files with a timestamp and not automatically removed, so some manual maintenance of the file system will then be required at some point. 

For the past it can also include actual pv production and actual usage, if requested, but only if a database file with hourly data has been setup before running the program, so this is a very customised case. This is a database with the meter data of each data extracted from Domoticz backup databases and loaded into one big meter table in a separate database. (check the code for implementation). Only needed for runs on history, not for day-ahead planning.

# Domoticz integration mode

The program will take input from Domoticz variables and devices and will trigger output onto Domoticz devices. The idx numbers for the Domotic devices will need to be adapted in the program file as these differ for each operating environment.

The first 60 lines of the python program contain all references to the Domoticz installation, the PV panel setup and the Marstek plugin. These lines need to be read carefully and adapted for your local installation, for example settting up the relevant user variables and adapting the IDX numbers of the user variables in the python code.

Also, a confirmation email of the next planning will be sent via the Domoticz notification system. If not desired, please comment out that line.

# Solar/PV panel production integration

If the -p option is added to the call of the python program, then the forecasted production of the PV panels will be included in the planning. For this the location (latitude/longitude) settings and PV configuration (Angle, Azimuth, Total MaxPeak power) needs to be defined. Hard coded, as visible in the first 60 lines.

You can define whether the PV group is connected directly to the battery (always charging the battery) or only to the home electricity net.

As the PV production is a forecast only and actual PV production will deviate, it is recommended to re-run the planning frequently, but please note that the free API of forecast.solar will only allow 10 calls per hour.

The planning will determine whether it is financially beneficial to return surplus solar energy to the grid immediately or store it for later use or return.

# How to get your ENTSOE API token for retrieving electricity prices.

To get an API token (it is free):
1. Register for an account at https://transparency.entsoe.eu/dashboard/show
2. Send an email with subject "Restful API access" and your account email address in the body.
3. After receipt of their confirmation, go into your account and generate your token.
4. Copy and paste the token to replace the xxxxxx on the line indicated in the python program where it says securitytoken="xxxxxxxxxxx" (line 52). For the Domoticz mode copy and paste the token onto the Domoticz user variable.

Energyzero will be used of the entsoe data retrieval fails.

# Program internal logic

1) First collect all data needed for input into the planning and build the pricelist with each hour or 15-minute interval, the majority of the code.
2) Run the planning using linear optimisation across all intervals.
3) Provide the output to a file, Domoticz and the battery.(see examples below)









