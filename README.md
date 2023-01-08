# battery-planning
optimise battery charging/discharging with hourly electricity prices

# Purpose

This is a stand-alone python program that creates a planning for charging and discharging a home battery system to optimise profit.
It needs as input:
1) **Your own API token** from transparancy.entsoe.eu (see below)
2) The planning period
3) The battery characteristics: maximum capacity and maximum charge and discharge speed

The program is intended to be used to plan the rest of today and tomorrow (if the prices for tomorrow are already available, normally after 15:00 hours). It can also be run every hour to re-plan the remaining period, given a starting/current charge of that moment. It can even be used to run on historic data to simulate what could have been achieved.

If the price data from entsoe.eu has been downloaded before it can be re-used, instead of requesting it again.

The progress, intermediate steps and finals results will be displayed on screen and an output file will be created that can be loaded into a spreadsheet.

# Limitation

It does not take into account any tax effects as these will differ strongly from country to country, but this could easily be added.

# Get your API token

To get an API token (it is free):
1. Register for an account at https://transparency.entsoe.eu/dashboard/show
2. Send an email with subject "Restful API access" and your account email address in the body.
3. After receipt of their confirmation, go into your account and generate your token.
4. Copy and paste the token to replace the xxxxxx on line 22 of the python program where it says securitytoken="xxxxxxxxxxx" 

# Future dvelopment

This program will be developed further to integrate into domoticz home automation software.

# Program internal logic

A short description of the internals of the program:
1. Prices are loaded onto a hourPriceList and a displayList. The displayList is for display and for tracking of the results. The hourPriceList is used for the planning process.
2. The hourPriceList is combined with itself to form pairs of charge-discharge and discharge-charge actions. These are put onto the pairList and are sorted top-down for maximum profitability.
3. The pairList is run down from top to bottom to select the pairs that still fit onto the planning, taking into account previously planned actions and maximum battery capacity and maximum charge and discharge speeds. It restarts from the top after each action, since a discharge/charge action could open up capacity for a charge/discharge that did not exist before due to maximum capacity. This continues until the end of the list is reached.
4. The next period is processed by re-starting at step 1.

