########################################################################################################################################
## start of Domoticz integration definition, update these IDX numbers to match your domoticz setup #####################################

# USER VARIABLES ################
entsoeTokenIDX=12               # the IDX of the Domoticz user variable holding the API security token for transparency.entsoe.eu
## battery specs
ratedBatteryCapacityIDX=14      # the IDX of the Domoticz user variable holding the value for the rated/max battery capacity in Wh
minBatterySOCPctIDX=24          # the IDX of the Domoticz user variable holding the minimum SOC % that needs to be kept in the battery
maxBatteryChargeSpeedIDX=15     # the IDX of the Domoticz user variable holding the maximum charge speed in W
maxBatteryDischargeSpeedIDX=16  # the IDX of the Domoticz user variable holding the maximum discharge speed in W
RTEIDX=20                       # the IDX of the Domoticz user variable holding the value for the round trip conversion efficiency % of the battery system
MACaddressIDX=30                   # the IDX of the Domoticz user variable holding the MAC address of the Marstek battery (for use in mqtt)
# !!! to be added : MAC address
## price elements
energyTaxIDX=4                  # the IDX of the Domoticz user variable holding the energyTax per kWh, incl. VAT/BTW
vatIDX=13                       # the IDX of the Domoticz user variable holding the VAT/BTW percentage
supplierCostsIDX=22             # costs per kWh the electrity provider is charging (for example purchasing fee)
networkCostsIDX=25              # costs per kWh the network provider is charging (plans exist for NL after 2027, currently 0 per kWh)
cycleCostsIDX=29                # costs per kWh calculated from battery price, number of guaranteed cyles and max usable capacity (set to 0 to not have this included)

# DEVICES #######################
planningDisplayIDX=111          # the IDX number of a Domoticz text device to use for display of the planning
batterySOCIDX=372               # actual SOC pct
homeUsageIDX=178                # IDX of device holding real home usage kWh history (import + own usage PV + battery discharge) for calculation of expected load

# devices from the Marstek-Venus plugin
periodIDX=414                   # devices for holding configuration data for a manual mode activation
starttimeIDX=415
endtimeIDX=416
weekdayIDX=417
powerIDX=418
batterySwitchIDX=419            # the IDX of the Domoticz selector switch for controlling the battery system operation mode

#################################
# hard coded definition of pv panels groups (can be extended further)
# spec includes the following fields : [connection-type,angle-vs-horizontal,azimuth-vs-south,total-kWh-peak]
pvSpecGroup1=["indirect",55,58,2.75]    # "indirect" means connected to the house network, not directly to the battery
pvSpecGroup2=["direct",7,-30,0.82]      # "direct" means connected to the battery PV connections (MPPT or AC input)
pvGroups=[]
pvGroups.append(pvSpecGroup1)
pvGroups.append(pvSpecGroup2)
# repeat the above logic for each group of PV panels.

## Domoticz server
domoticzIP="192.168.178.218"    # IP address of the Domoticz server. Can be set to 127.0.0.1 if planning is run at domoticz system itself.
domoticzPort="8080"             # Domoticz port

# all communication with domoticz devices/database is with JSON calls 
baseJSON="http://"+domoticzIP+":"+domoticzPort+"/json.htm?"   # the base string for any JSON call.
## end of Domoticz integration definition ########################################################################################


# See below for configuration data of MQTT broker !!!!!!!!!!!!!!!!!!
# MQTT Broker settings
BROKER = "192.168.178.254"      # The IP address of the broker
PORT = 1883                     # The port of the broker, normally 1883
MQTT_SUB = "hame_energy/VNSA-0/device/" # the intial part of the MQTT subscribe string, please adjust device type (here VNSA-0)
MQTT_PUB = "hame_energy/VNSA-0/App/"    # the intial part of the MQTT publish string, please adjust device type (here VNSA-0)

##################################################################################################################################

from operator import itemgetter, attrgetter
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET
import requests
import copy
import json
import time, math
import sys
import urllib.parse
import pulp
import paho.mqtt.client as mqtt

import sqlite3
from sqlite3 import Error

today=date.today()
todayString=datetime.strftime(today,'%Y%m%d')
todayLongString=datetime.strftime(today,'%Y-%m-%d')

##### MQTT functions #####

def extract_mqtt_data(data):
    global initialCharge,commandAcknowlegde,modeAcknowledge,currentMode,periodDefinition
    working_status=["sleep","standby","charging","discharging","backup","ota upgrade","bypass"]
    working_mode=["automatic","manual","trading","passive","UPS","AI"]
    offonmode=["off","on"]
    onoffmode=["on","off"]
    initialCharge=None
    commandAcknowlegde=None
    modeAcknowledge=None
    currentMode=None
    periodDefinition=None
    if data!=None:
        for pair in data.split(","):
            key, value = pair.split("=", 1)
            if debug:
                if "|" in value:
                    print("key",key,"value",value.split("|"))
                else:
                    print("key",key,"value",value)
                if key=="tot_i": print("##########","total grid input energy: ",int(value)/100," kWh")
                elif key=="tot_o": print("##########","total grid output energy: ",int(value)/100, " kWh" )
                elif key=="grd_o": print("##########","combined power (in-/out+) :",value, " W")
                elif key=="grd_t": print("##########","working status :",working_status[int(value)])
                elif key=="cel_p": print("##########","actual capacity :",int(value)/100,"kWh")
                elif key=="cel_c": print("##########","SOC :",value," %")
                elif key=="wor_m": print("##########","working mode :",working_mode[int(value)])
                elif key=="mcp_w": print("##########","max charge :",value," W")
                elif key=="mdp_w": print("##########","max discharge :",value," W")
                elif key=="pv1": print("##########","pv1 power :",int(value.split("|")[0])/10," W")
                elif key=="pv2": print("##########","pv2 power :",int(value.split("|")[0])/10," W")
                elif key=="api": print("##########","api on/off :", offonmode[int(value)])
                elif key=="bl": print("##########","bluetooth lock on/off :", onoffmode[int(value)])
                elif key=="gp" : print("##########","power in(-)/out(+) from/to grid :",value)
                elif key=="bp" : print("##########","battery power in/out :", value)
                elif key=="rp" : print("##########","inverter power usage ? ",value, " W")
                elif key=="pv" : print("##########","pv energy today : ",int(value.split("|")[0])/100," kWh")
                elif key=="fu" : print("##########","surplus feed-in : ",offonmode[int(value.split("|")[0])])
            if key=="cel_p" : initialCharge=int(value)*10
            if key=="cd" : commandAcknowlegde=int(value)
            if key=="md" : modeAcknowledge=int(value)
            if key=="wor_m" : currentMode=working_mode[int(value)]
            if key=="tim_0": periodDefinition=str(value)
        if debug:
            print("key values received : initialCharge ",initialCharge," command acknowledge ",commandAcknowlegde," mode acknowledge",modeAcknowledge," current mode ",currentMode)


# Callback when the client connects to the broker
def on_mqtt_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        if debug: print("✅ Connected to MQTT Broker!")
        client.subscribe(TOPIC_SUB)
        if debug: print(f"📡 Subscribed to topic: {TOPIC_SUB}")
    else:
        if debug: print(f"❌ Failed to connect, reason code {reason_code}")

# Callback when a message is received
def on_mqtt_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8")
        if debug: print(f"📥 Received message from {msg.topic}: {payload}")
        extract_mqtt_data(payload)
    except UnicodeDecodeError:
        print("⚠ Received non-text message")

# Optional logging callback (updated signature)
def on_mqtt_log(client, userdata, level, buf):
    if debug: print(f"LOG: {buf}")

# intial setup
def mqtt_setup():
    global client,initialCharge,commandAcknowlegde,modeAcknowledge,currentMode,periodDefinition,BROKER,PORT,TOPIC_SUB,TOPIC_PUB,CLIENT_ID
    TOPIC_SUB=MQTT_SUB+MACaddress+"/ctrl"
    TOPIC_PUB=MQTT_PUB+MACaddress+"/ctrl"
    CLIENT_ID = f"mqtt-client-{int(time.time())}"
    initialCharge=None
    commandAcknowlegde=None
    modeAcknowledge=None
    currentMode=None
    periodDefinition=None
    # Create MQTT client instance (API v2)
    client = mqtt.Client(
        client_id=CLIENT_ID,
        clean_session=True,
        protocol=mqtt.MQTTv311,
        transport="tcp",
        userdata=None,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )

    # Assign callbacks
    client.on_connect = on_mqtt_connect
    client.on_message = on_mqtt_message
    # client.on_log = on_mqtt_log  # Uncomment for debug logs

def mqtt_publish(message):
        result = client.publish(TOPIC_PUB, message, qos=1)
        status = result.rc  # Updated access
        if status == mqtt.MQTT_ERR_SUCCESS:
            if debug: print(f"📤 Sent message to {TOPIC_PUB}: {message}")
        else:
            if debug: print(f"❌ Failed to send message to {TOPIC_PUB}")

def mqtt_send_receive(message,expected_response):
    global commandAcknowlegde
    commandAcknowlegde=None
    try:
        # Connect to broker
        client.connect(BROKER, PORT, keepalive=60)

        # Start network loop
        client.loop_start()

        # Publish message
        mqtt_publish(message)
        time.sleep(3)

        # Keep running and repeat message until acknowledged
        print("Listening for incoming messages... Press Ctrl+C to exit.")
        while expected_response!=commandAcknowlegde:
            if debug: print(expected_response!=commandAcknowlegde,expected_response,commandAcknowlegde)
            time.sleep(30)
            if debug: print("Listening for incoming messages... Press Ctrl+C to exit.")
            mqtt_publish(message)
            time.sleep(3)

    except KeyboardInterrupt:
        if debug: print("\n🛑 Disconnecting from broker...")

    except Exception as e:
        if debug: print(f"⚠ Error: {e}")

    finally:
        client.loop_stop()
        client.disconnect()
##### End of MQTT function

##### Start of input data collection functions

def getUserInput():
    # get user input, with limited (!!) input validation, only used in standalone mode
    global initialCharge,ratedBatteryCapacity,maxChargeSpeed,maxDischargeSpeed,minBatterySOCPct,startdate,enddate,starthour,entsoeToken,onewayEff,energyTax,vatPCT,supplierCosts,networkCosts,cycleCosts,MACaddress
    startdate=input("Enter startdate as YYYYMMDD (default=today)   : ") or todayString
    enddate=input("Enter enddate as YYYYMMDD (default=startdate+1) : ") or datetime.strftime(datetime.strptime(startdate,'%Y%m%d')+timedelta(days=1),'%Y%m%d')
    starthour=int(input("Enter start hour as HH (default next hour)   : ") or datetime.strftime(datetime.now()+timedelta(hours=1),'%H'))
    initialCharge=int(input("Enter initial charge in Wh (default=0) :") or "0" )
    ratedBatteryCapacity=int(input("Enter rated capacity in Wh (default 2100) :") or 2100)
    minBatterySOCPct=int(input("Enter minimum SOC in percent (default 12) :") or 12)
    maxChargeSpeed=int(input("Enter max charge speed in Watt (default 1200) :") or 1200)
    maxDischargeSpeed=int(input("Enter max discharge speed in Watt (default 800) :") or 800)
    RTE=int(input("Enter conversion efficiency percentage RTE (default 85) :") or 85)
    onewayEff=float((100-(100-RTE)/2)/100)
    entsoeToken='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'  # paste in your own security token from entsoe.eu
    MACaddress="xxxxxxxxxxxxxxxxxx" # paste the MAC address of your battery system here.
    energyTax=float(input("Enter energy tax in Euro per kWh (default 0.11085) :") or 0.11085) # energy tax , incl btw, Euro per kWh
    supplierCosts=0.01682  # supplier/purchasing costs per kWh incl btw
    cycleCosts=0.052 # Example for ( 600 euro/6000 cycles) / (2 * 2.1 kWh * 88% Depth of Discharge)
    vatPCT=1.21  # VAT/BTW 21%
    networkCosts=0 # network costs per kWh, future development

def getPlanningInput():
    # read initial planning data from Domoticz variables and devices (instead of user input)
    global initialCharge,ratedBatteryCapacity,maxChargeSpeed,maxDischargeSpeed,minBatterySOCPct,startdate,enddate,starthour,entsoeToken,onewayEff,energyTax,vatPCT,supplierCosts,networkCosts,cycleCosts,MACaddress

    getPlanningInputSuccess=True

    startdate=todayString
    enddate=datetime.strftime(datetime.strptime(startdate,'%Y%m%d')+timedelta(days=1),'%Y%m%d')
    starthour=int(datetime.strftime(datetime.now(),'%H'))  # current hour. This assumes the program is called from domoticz at the start of the hour.


    responseResult,varValue=getUserVariable(MACaddressIDX)
    if responseResult: MACaddress=varValue
    print(MACaddress)
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    if mqttQuery: # get from Marstek cloud
        mqtt_setup()
        mqtt_send_receive("cd=01",1)
    else: # or get from Domoticz device created by Marstek Venus plugin
        responseResult,varValue=getBatteryChargeLevel() # actual charge in Wh
        if responseResult: initialCharge=float(varValue)
        getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    responseResult,varValue=getUserVariable(minBatterySOCPctIDX)
    if responseResult: minBatterySOCPct=float(varValue)
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    responseResult,varValue=getUserVariable(ratedBatteryCapacityIDX)
    if responseResult: ratedBatteryCapacity=float(varValue)
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    responseResult,varValue=getUserVariable(maxBatteryChargeSpeedIDX)
    if responseResult: maxChargeSpeed=float(varValue)
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    responseResult,varValue=getUserVariable(maxBatteryDischargeSpeedIDX)
    if responseResult: maxDischargeSpeed=float(varValue)
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    responseResult,varValue=getUserVariable(RTEIDX)
    if responseResult: onewayEff=float((100-(100-int(varValue))/2)/100.0)
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    responseResult,varValue=getUserVariable(energyTaxIDX)
    if responseResult: energyTax=float(varValue)
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    responseResult,varValue=getUserVariable(vatIDX)
    if responseResult: vatPCT=(float(varValue)+100.0)/100.0
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    responseResult,varValue=getUserVariable(supplierCostsIDX)
    if responseResult: supplierCosts=float(varValue)
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    responseResult,varValue=getUserVariable(networkCostsIDX)
    if responseResult: networkCosts=float(varValue)
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    responseResult,varValue=getUserVariable(cycleCostsIDX)
    if responseResult: cycleCosts=float(varValue)
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    responseResult,entsoeToken=getUserVariable(entsoeTokenIDX)
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    if getPlanningInputSuccess==False:
        print("ERROR: getting all required planning data failed.")
    return getPlanningInputSuccess

def getLocation():
    # function to get the value of a location defined in settings
    try:
        apiCall="type=command&param=getsettings"
        response = requests.get(baseJSON+apiCall)
        responseResult=str(response.json())
        if responseResult=="ERR":
            raise Exception
        else:
            latitude=response.json()["Location"]["Latitude"]
            longitude=response.json()["Location"]["Longitude"]
            responseResult=True
    except:
        print("ERROR: unable to retrieve the location settings")
        print("Response was : ",response.json())
        responseResult=False
        latitude=None
        longitude=None
    return responseResult,latitude,longitude

def getUserVariable(varIDX):
    # function to get the value of a user variable indicated by the varIDX number
    try:
        apiCall="type=command&param=getuservariable&idx="+str(varIDX)
        response = requests.get(baseJSON+apiCall)
        responseResult=str(response.json()["status"])
        if responseResult=="ERR":
            raise Exception
        else:
            varValue=response.json()["result"][0]["Value"]
            responseResult=True
    except:
        print("ERROR: unable to retrieve the value of user variable with IDX ",varIDX)
        print("Response was : ",response.json())
        responseResult=False
        varValue=None
    return responseResult,varValue

def getPercentageDevice(varIDX):
    # function to get the value of a percentage device indicated by the varIDX number
    try:
        apiCall="type=command&param=getdevices&rid="+str(varIDX)
        response = requests.get(baseJSON+apiCall)
        responseResult=str(response.json()["status"])
        if responseResult=="ERR":
            raise Exception
        else:
            varString=response.json()["result"][0]["Data"]
            varValue=float(varString.split("%")[0])
            responseResult=True
    except:
        print("ERROR: unable to retrieve the value of device with IDX ",varIDX)
        print("Response was : ",response.json())
        responseResult=False
        varValue=None
    return responseResult,varValue

def clearTextDevice(textIDX):
    # clears the text of a text device and then clears the log entries
    responseResult=False
    if setTextDevice(textIDX,""):  # clear the text
        try:
            apiCall="type=command&param=clearlightlog&idx="+str(textIDX)
            response=requests.get(baseJSON+apiCall)
            responseResult=str(response.json()["status"])
            if responseResult=="ERR":
                raise Exception
            else:
                responseResult=True
        except:
            print("ERROR: log of text device with IDX ",textIDX," failed to clear.")
            responseResult=False
    return responseResult

def setTextDevice(textIDX,displayText):
    # update the value of a text device and adds an entry to the device log file
    try:
        if len(displayText)<=200:
            urlText=urllib.parse.quote(displayText)
            apiCall="type=command&param=udevice&idx="+str(textIDX)+"&nvalue=0&svalue="+urlText
            response=requests.get(baseJSON+apiCall)
            responseResult=str(response.json()["status"])
            if responseResult=="ERR":
                raise Exception
            else:
                responseResult=True
        else:
            print("ERROR: displayText too long (max 200 characters).")
            raise Exception
    except:
        print("ERROR: failed to update text device with IDX ",textIDX)
        print("Response was : ",response.json())
        responseResult=False
    return responseResult


def updatePowerDevice(deviceIDX,power):
    # update an electric power device
    try:
        apiCall="type=command&param=udevice&idx="+str(deviceIDX)+"&nvalue=0&svalue="+str(power)
        response=requests.get(baseJSON+apiCall)
        responseResult=str(response.json()["status"])
        if responseResult=="ERR":
            raise Exception
        else:
            responseResult=True
    except:
        print("ERROR: failed to update power device with IDX ",deviceIDX)
        print("Response was : ",response.json())
        responseResult=False
    return responseResult


def getHourlyDataFromShortHistory(varIDX):
    # get hourly history from meter device
    try:
        apiCall="type=command&param=graph&sensor=counter&idx="+str(varIDX)+"&range=day"
        response = requests.get(baseJSON+apiCall)
        responseResult=str(response.json()["status"])
        if responseResult=="ERR":
            raise Exception
        else:
            varString=response.json()["result"]
            responseResult=True
    except:
        print("ERROR: unable to retrieve the values of device with IDX ",varIDX)
        print("Response was : ",response.json())
        responseResult=False
        varString=None
    return responseResult,varString

def calcHourlyAvgUsage(varIDX,weightIncrease):
    # calculate hourly average values for meter device
    # weightIncrease >1 gives more weight to recent usage
    responseResult,varString=getHourlyDataFromShortHistory(varIDX)
    if responseResult:
        hourlyAvgs= [[f"{hour:02d}", 0] for hour in range(24)]
        weight=1
        totalWeight=weight
        firstHour=-1
        for interval in varString:
            for key,value in interval.items():
                if key=="d":
                    hour=int(value[11:13])
                if key=="v":
                    usage=int(float(value))
            if firstHour==-1:
                firstHour=hour
                nrDays=1
            else:
                if hour==firstHour:
                    nrDays+=1
                    weight+=weightIncrease
                    totalWeight+=weight
            hourlyAvgs[hour][1]+=int(usage*weight)
        for i in range(24):
            hourlyAvgs[i][1]=int(float(hourlyAvgs[i][1]/totalWeight))
    return responseResult,hourlyAvgs

def getBatteryChargeLevel():
    # get actual current battery charge level from SOC and MAX capacity
    chargeLevel=None
    try:
        responseResult,SOCPercent=getPercentageDevice(batterySOCIDX)
        if responseResult:
            responseResult,ratedBatteryCapacity=getUserVariable(ratedBatteryCapacityIDX)
            if responseResult:
                chargeLevel=float(SOCPercent/100*int(ratedBatteryCapacity))
                responseResult=True
            else:
                print("ERROR: retrieving max Capacity failed")
                raise Exception
        else:
            print("ERROR: retrieving actual charge percentage failed")
            raise Exception
    except:
        print("ERROR: cannot get or calculate battery charge level")
        print("Response was : ",responseResult)
        responseResult=False
    return responseResult,chargeLevel

def updateSelectorSwitch(varIDX,switchLevel):
    # update a selector switch to a switch level number
    try:
        if type(switchLevel)==int:
            apiCall="type=command&param=switchlight&idx="+str(varIDX)+"&switchcmd=Set%20Level&level="+str(switchLevel)
            # note : unable to check whether level is valid, even invalid level will return status OK
            response = requests.get(baseJSON+apiCall)
            responseResult=str(response.json()["status"])
            if responseResult=="ERR":
                raise Exception
            else:
                responseResult=True
        else:
            print("ERROR: incorrect type of switch level provided")
            raise Exception
    except:
        print("ERROR: unable to set the switch with IDX ",varIDX," to value ",switchLevel)
        print("Response was : ",response.json())
        responseResult=False
    return responseResult

def setBatteryAction(action,scheduleDateTime,power,schedule):
# interface to Marstek battery, either via plugin or mqtt
    startHr=int(scheduleDateTime[11:13])
    startMin=int(scheduleDateTime[14:15])
    currentMinute=int(datetime.now().minute)
    power=int(float(power/(60-currentMinute))*60)
    if power>-100 and power<100 and power!=0:
        # in the app, 100 is a minimum setting for either charge or discharge
        # so in thsi case increase power but reduce time
        timepercent=float(abs(power/100))
        if hourAvgPlanning:
            endMin=int(round(60*timepercent,0))
            endHr=startHr
        else:
            endMin=int(startMin+round(15*timepercent,0))
            endHr=startHr
        if power>0:
            power=100
        else:
            power=-100
    else:
        if hourAvgPlanning:
            endHr=startHr+1
            if endHr==24: endHr=0
            endMin=startMin
        else:
            if startMin==00 or startMin==15 or startMin==30:
                endMin=startMin+15
                endHr=startHr
            else:
                endHr=startHr+1
                endMin=0
    if power>maxDischargeSpeed: power=maxDischargeSpeed
    if power<-maxChargeSpeed: power=-maxChargeSpeed
    starttimeString=f"{startHr:02d}:{startMin:02d}"
    endtimeString=f"{endHr:02d}:{endMin:02d}"
    weekdaySchedule="1111111"
    manualPeriodID="0"
    if mqttQuery:
        if action=="AutoSelf": # use auto
            message="cd=02,md=0"
            expected_response=2
        elif action=="AI": # use auto instead
            message="cd=02,md=0"
            expected_response=2
        elif action=="Manual":
            message="cd=03,md=1,nm=0,bt="+starttimeString+",et="+endtimeString+",wk=127,vv="+str(power)+",as=1"
            expected_response=3
        elif action=="Passive": # use manual zero power and disabled instead
            message="cd=03,md=1,nm=0,bt="+starttimeString+",et="+endtimeString+",wk=127,vv="+str(power)+",as=0"
            expected_response=3
        elif action=="UPS": # use manual charge full power instead
            message="cd=03,md=1,nm=0,bt="+starttimeString+",et="+endtimeString+",wk=127,vv="+"-"+str(maxChargeSpeed)+",as=1"
            expected_response=3
        if debug: print("MQTT message ",message," expected response ",expected_response)
        if debug: print("Waiting 30 seconds for next mqtt command.")
        time.sleep(30) # make sure at least 30 seconds have passed since previous mqtt message
        mqtt_send_receive(message,expected_response)
        if debug: print("Waiting 30 seconds for next mqtt command.")
        time.sleep(30)
        mqtt_send_receive("cd=01",1) # confirm request has been processed
        if debug: print("result of set battery action via mqtt : current Charge ",initialCharge," current Mode ",currentMode," period definition ",periodDefinition)
        responseResult=True
    else:
        try:
            clearTextDevice(periodIDX)
            setTextDevice(periodIDX,manualPeriodID)
            clearTextDevice(starttimeIDX)
            setTextDevice(starttimeIDX,starttimeString)
            clearTextDevice(endtimeIDX)
            setTextDevice(endtimeIDX,endtimeString)
            clearTextDevice(weekdayIDX)
            setTextDevice(weekdayIDX,weekdaySchedule)
            updatePowerDevice(powerIDX,power)
            if action=="AutoSelf": setLevel=10
            elif action=="AI": setLevel=20
            elif action=="Manual": setLevel=30
            elif action=="Passive": setLevel=40
            elif action=="UPS": setlevel=50
            updateSelectorSwitch(batterySwitchIDX,setLevel)
            responseResult=True
        except:
            print("ERROR: unable to update device for setting battery action")
            responseResult=False

    fullSchedule="<br>date_______time__pvD__pvI___use__nett_chrgD_chrg_dscg__soc__imp__exp_pr-buy_pr-sell__cost<br>"
    for nr,record in enumerate(schedule):
        fullSchedule=fullSchedule+"%16s %4d %4d %5d %5d %4d %4d %4d %4d %5d %5d %1.4f %1.4f %2.4f<br>" %(priceList[nr][3],priceList[nr][4],priceList[nr][5],priceList[nr][6],priceList[nr][6]-priceList[nr][5]-priceList[nr][4],priceList[nr][4],record["charge"],record["discharge"],record["soc"],record["import"],record["export"],priceList[nr][7],priceList[nr][8],record["costs"])
    fullSchedule=fullSchedule.replace(' ','_')  # JSON processing removes all duplicate spaces, so use underscore to get table format

    # send email confirmation via Domoticz email setup to confirm action set
    subject = "BATTERY: next action"+str(action)
    messageBody = "Battery set to "+str(action)+" from "+starttimeString+" to "+endtimeString+" with power "+str(power)+" ( note: <0 is charge )"
    messageBody=messageBody+fullSchedule
    url = "http://127.0.0.1:8080/json.htm?type=command&param=sendnotification"
    url += "&subject=\'" + subject + "\'"
    url += "&body=\'" + messageBody + "\'"
    sendemail = requests.get(url)

    return responseResult

def getHrValueFromBIGDB(runDate,device):
    # query the historic dbase with hourly values specifically created to re-run the past
    selectStart=datetime.strftime(runDate,'%Y-%m-%d 00:00:00')
    selectEnd=datetime.strftime(runDate+timedelta(days=2),'%Y-%m-%d 01:00:00')  # the extra hour is needed to get the start value of that hour
    db_file = r"/home/pi/dombigdb/domoticzbig.db"
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except Error as e:
        print(e)
    cur = conn.cursor()
    # the following select statement determines which devices to include.
    cur.execute("SELECT substr(date,1,13) hour,min(value) FROM meter WHERE DeviceRowID=? and date>=? and date<? group by hour order by hour",(device,selectStart,selectEnd,))
    rows = cur.fetchall()

    seqnr=1
    hourValue=0
    hourValueList=[]
    firstRecord=True
    for row in rows:
        if firstRecord:
            actDate=row[0][0:10]
            actHour=row[0][11:13]
            startValue=row[1]
            firstRecord=False
        else:
            hourValue=row[1]-startValue
            hourValueList.append([seqnr,actDate,actHour,hourValue])
            actDate=row[0][0:10]
            actHour=row[0][11:13]
            seqnr+=1
            startValue=row[1]
    cur.close()
    return hourValueList

def loadPVforecastIntoFile(groupSpec,pvForecastFileName):
    # request the PV production forecast from forecast.solar and store in a file
    try:
        # url components for https feed from forecast.solar
        urlwebsite='https://api.forecast.solar'
        urldoctype='/estimate/watthours/period'
        allResponseOK=True
        responseResult,latitude,longitude=getLocation()
        allResponseOK=allResponseOK and responseResult
        pvAngle=groupSpec[1]
        pvAzimuth=groupSpec[2]
        pvMaxPeak=groupSpec[3]
        if allResponseOK:
            url=urlwebsite+urldoctype+"/"+latitude+"/"+longitude+"/"+str(pvAngle)+"/"+str(pvAzimuth)+"/"+str(pvMaxPeak)+"?full=1"
            response = requests.get(url)
            if response.status_code == 200:
                # saving the json file
                with open(pvForecastFileName, 'wb') as f:
                    f.write(response.content)
                    fileReceived=True
            else:
                print("ERROR: no proper PV panel forecast file received")
                fileReceived=False
                raise Exception
        else:
            print("ERROR : required parameters for requesting PV forecast not found")
            raise Exception
    except:
        print("ERROR: no proper PV panel forecast file received")
        fileReceived=False
    return fileReceived

def loadPricesIntoFile(entsoeFileName,loadStartDate,loadEndDate):
    # request the prices from entsoe.eu and store in a file
    try:
        # url components for https feed from ENTSOE.EU
        urlwebsite='https://web-api.tp.entsoe.eu/api?'
        urltoken='securityToken='+entsoeToken
        urldoctype='&documentType=A44'
        urldomain='&in_Domain=10YNL----------L&out_Domain=10YNL----------L'
        urlperiod='&periodStart='+loadStartDate+'0000&periodEnd='+loadEndDate+'2300'
        url=urlwebsite+urltoken+urldoctype+urldomain+urlperiod
        # creating HTTP response object from given url
        if debug: print("Getting data from entsoe.eu for ",loadStartDate," to ",loadEndDate)
        if debug: print(url)
        response = requests.get(url)
        if response.status_code == 200:
            # saving the xml file
            with open(entsoeFileName, 'wb') as f:
                f.write(response.content)
            fileReceived=True
        else:
            print("ERROR: no proper price file received")
            fileReceived=False
    except:
        print("ERROR: no proper price file received")
        fileReceived=False
    return fileReceived

def parsePVforecastIntoList(groupSpec):
    # process PV forecast into a list
    pvForecastFileName="solarforecast.json"
    forecastList=[]
    if loadPVforecastIntoFile(groupSpec,pvForecastFileName):
        # create PV forecast list out of json file
        with open(pvForecastFileName, "r") as read_file:
            forecastHRS = json.load(read_file)["result"]
            firstItem=True
            seqNr=0
            for key, value in forecastHRS.items():
                if not firstItem:
                    forecastWh=int(value)
                    forecastList.append([seqNr,forecastDate,forecastHr,forecastWh]) # date and time of previous line
                    seqNr+=1
                else:
                    firstItem=False
                forecastDate=key[0:10]
                forecastHr=str(key[11:13])
            for i in forecastList:
                if debug: print("forecast ",i)
    return forecastList

def parsePricesIntoList(runDate,hourAverage=False,local_tz="Europe/Amsterdam"):
    # process prices into a list, either per hour or per 15-minute interval
    loadStartDate=datetime.strftime(runDate,'%Y%m%d')
    loadEndDate=datetime.strftime(runDate+timedelta(days=1),'%Y%m%d')

    priceList = []
    quarter_times = []
    processed_times = set()
    period_counter = 1
    hour_sum = 0.0
    hour_sum_usage = 0.0
    hour_sum_return = 0.0
    hour_count = 0
    hour_start = None

    # first get and parse the entsoe prices
    if runMode=="standalone" or runMode=="integrated":
        fileNameDate=datetime.strftime(runDate,'%Y%m%d')
        entsoeFileName="entsoe"+fileNameDate+".xml"
    else:
        # runMode=="domoticz"
        entsoeFileName="entsoe.xml" # no date in filename to prevent file system filling up

    if xmlAvailable[0]!="Y" and xmlAvailable[0]!="y":
        if not loadPricesIntoFile(entsoeFileName,loadStartDate,loadEndDate):
            print("ERROR: Something wrong with getting price data")
            return priceList

    ns = {"ns": "urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3"}
    root = ET.parse(entsoeFileName).getroot()
    local_zone = ZoneInfo(local_tz)

    # ---- filter days derived from rundate ----
    rundate_local = runDate.astimezone(local_zone).date()
    next_day_local = rundate_local + timedelta(days=1)

    periods = root.findall(".//ns:Period", ns)
    periods_sorted = sorted(
        periods,
        key=lambda p: datetime.fromisoformat(
            p.find("ns:timeInterval/ns:start", ns).text.replace("Z", "+00:00")
        )
    )
    for period in periods_sorted:
        start_text = period.find("ns:timeInterval/ns:start", ns).text
        end_text = period.find("ns:timeInterval/ns:end", ns).text
        start_dt = datetime.fromisoformat(start_text.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_text.replace("Z", "+00:00"))
        resolution=period.find("ns:resolution", ns).text
        if resolution=="PT15M":
            step=timedelta(minutes=15)
        else:
            step=timedelta(minutes=60)
        interval_count = int((end_dt - start_dt) / step)
        points = {
            int(p.find("ns:position", ns).text):
            float(p.find("ns:price.amount", ns).text)
            for p in period.findall("ns:Point", ns)
        }
        prev_price = None

        for pos in range(1, interval_count + 1):
            if pos in points:
                prev_price = points[pos]
            if prev_price is None:
                continue
            start_time = start_dt + (pos - 1) * step
            if start_time in processed_times:
                continue
            processed_times.add(start_time)
            quarter_times.append(start_time)
            price_kwh = prev_price / 1000.0
            if includeTax:
                price_usage=price_kwh*vatPCT+energyTax+supplierCosts+networkCosts
                if saldering:
                    price_return=price_usage
                else:
                    price_return=price_kwh*vatPCT
            else:
                price_usage=price_kwh
                price_return=price_usage


            start_local = start_time.astimezone(local_zone)
            # ---- filter: rundate and rundate + 1 ----
            if start_local.date() not in (rundate_local, next_day_local):
                continue
            if not hourAverage or resolution=="PT60M":
                priceList.append([
                    period_counter,                         # sequential nr
                    price_kwh,                              # market price
                    start_time.strftime("%Y-%m-%d %H:%M"),  # period start time UTC
                    start_local.strftime("%Y-%m-%d %H:%M"), # period staret time local
                    0,                                      # pvforecast direct
                    0,                                      # pvforecast_indirect
                    0,                                      # forecast_homeusage
                    price_usage,                            # price usage
                    price_return                           # price return
                ])
                period_counter += 1
            else:
                if hour_count == 0:
                    hour_start = start_time
                hour_sum += price_kwh
                hour_sum_usage += price_usage
                hour_sum_return += price_return
                hour_count += 1
                if hour_count == 4:
                    hour_local = hour_start.astimezone(local_zone)
                    if hour_local.date() in (rundate_local, next_day_local):
                        priceList.append([
                            period_counter,
                            hour_sum / 4,
                            hour_start.strftime("%Y-%m-%d %H:%M"),
                            hour_local.strftime("%Y-%m-%d %H:%M"),
                            0,
                            0,
                            0,
                            hour_sum_usage / 4,
                            hour_sum_return / 4
                        ])
                        period_counter += 1
                    hour_sum = 0.0
                    hour_sum_usage=0.0
                    hour_sum_return=0.0
                    hour_count = 0

    return priceList

def getPricesFromEnergyZero(runDate,hourAvgPlanning,local_tz="Europe/Amsterdam"):
    # get prices from energyzero if entsoe not available or not complete
    loadStartDate=datetime.strftime(runDate,'%d-%m-%Y')
    utc = ZoneInfo("UTC")
    local_zone = ZoneInfo(local_tz)
        # ---- filter days derived from rundate ----
    rundate_local = runDate.astimezone(local_zone).date()
    next_day_local = rundate_local + timedelta(days=1)

    result= []
    # energyzero will return requested date and day before and day after
    if hourAvgPlanning or runDate<datetime.strptime("20251001","%Y%m%d"): # it can provide qtr prices even on last days of september, but we want hourly prices still
        url = "https://public.api.energyzero.nl/public/v1/prices?date="+loadStartDate+"&interval=INTERVAL_HOUR&energyType=ENERGY_TYPE_ELECTRICITY"
    else:
        url = "https://public.api.energyzero.nl/public/v1/prices?date="+loadStartDate+"&interval=INTERVAL_QUARTER&energyType=ENERGY_TYPE_ELECTRICITY"

    response=requests.get(url)
    if response.status_code == 200:
        basePrices=json.loads(response.text)
        period_counter=1
        for entry in basePrices.get("base", []):
            # Parse UTC timestamp
            start_utc = datetime.fromisoformat(entry["start"].replace("Z", "+00:00")).replace(tzinfo=utc)
            # Convert to local timezone
            start_local = start_utc.astimezone(local_zone)

            price_kwh = float(entry["price"]["value"])

            if includeTax:
                price_usage=price_kwh*vatPCT+energyTax+supplierCosts+networkCosts
                if saldering:
                    price_return=price_usage
                else:
                    price_return=price_kwh*vatPCT #!!! to be done: include supplier and network costs?
            else:
                price_usage=price_kwh
                price_return=price_usage

            if start_local.date() in (rundate_local, next_day_local):
                result.append([
                    period_counter,                         # sequential nr
                    price_kwh,                              # market price
                    start_utc.strftime("%Y-%m-%d %H:%M"),  # period start time UTC
                    start_local.strftime("%Y-%m-%d %H:%M"), # period staret time local
                    0,                                      # pvforecast direct
                    0,                                      # pvforecast_indirect
                    0,                                      # forecast_homeusage
                    price_usage,                            # price usage
                    price_return                           # price return
                ])

                period_counter+=1

    return result

def findForecast(intervalDate,intervalHr,forecastList):
    # find forecast of a specific hour in the list
    notFound=True
    nrElements=len(forecastList)
    elementNr=0
    forecastWh=0
    while notFound and elementNr<nrElements:
        if forecastList[elementNr][1]==intervalDate and forecastList[elementNr][2]==intervalHr:
            notFound=False
            forecastWh=forecastList[elementNr][3]
        elementNr+=1
    return forecastWh

def mergeForecastWithPricelist(groupSpec,forecastList):
    # merge forecast onto pricelist as separate fields
    global priceList
    for intervalNr,interval in enumerate(priceList):
        intervalDate=interval[3][0:10] # date of local time in pricelist
        intervalHr=interval[3][11:13]  # hour of local time in pricelist
        if hourAvgPlanning:
            pvForecast=findForecast(intervalDate,intervalHr,forecastList)
        else:
            pvForecast=int(findForecast(intervalDate,intervalHr,forecastList)/4) # some rounding is o.k.
        if groupSpec[0]=="direct":
            priceList[intervalNr][4]+=pvForecast
        else:
            priceList[intervalNr][5]+=pvForecast
    if outputMode:
        for record in priceList:
            print ("merged forecast ",record)

def findAvgUsage(intervalHr,usageList):
    # find usage estimate of a specific hour in the list
    notFound=True
    nrElements=len(usageList)
    elementNr=0
    usageWh=0
    while notFound and elementNr<nrElements:
        if usageList[elementNr][0]==intervalHr:
            notFound=False
            usageWh=usageList[elementNr][1]
        else:
            elementNr+=1
    return usageWh

def mergeUsageWithPriceList(usageList):
    # merge usage estimate onto pricelist as separate fields
    global priceList
    for intervalNr,interval in enumerate(priceList):
        intervalHr=interval[3][11:13]  # hour of local time in pricelist
        if hourAvgPlanning:
            hrAvgUsage=findAvgUsage(intervalHr,usageList)
        else:
            hrAvgUsage=int(findAvgUsage(intervalHr,usageList)/4) # some rounding will occur, no poblem
        priceList[intervalNr][6]+=hrAvgUsage
    if outputMode:
        for record in priceList:
            print ("merged usage",record)

def findActual(intervalDate,intervalHr,usageList):
    # find actual usage of the past in the list
    notFound=True
    nrElements=len(usageList)
    elementNr=0
    usageWh=0
    while notFound and elementNr<nrElements:
        if usageList[elementNr][1]==intervalDate and usageList[elementNr][2]==intervalHr:
            notFound=False
            usageWh=usageList[elementNr][3]
        elementNr+=1
    return usageWh

def mergeActualWithPricelist(actualList):
    # merge actual usage onto pricelist as separate fields
    global priceList
    for intervalNr,interval in enumerate(priceList):
        intervalDate=interval[3][0:10] # date of local time in pricelist
        intervalHr=interval[3][11:13]  # hour of local time in pricelist
        if hourAvgPlanning:
            actual=findActual(intervalDate,intervalHr,actualList)
        else:
            actual=int(findActual(intervalDate,intervalHr,actualList)/4) # some rounding is o.k.
        priceList[intervalNr][6]+=actual
    if outputMode:
        for record in priceList:
            print ("merged actual ",record)

def dropHistoryFromPricelist(runHour):
    # discard intervals of pricelist before starthour of the planning
    global priceList
    if hourAvgPlanning or runDate<datetime.strptime("20251001","%Y%m%d"):
        maxDrop=runHour
    else:
        maxDrop=4*runHour
    for interval in range(maxDrop):
        priceList.pop(0)

def getSOC(findHour,schedule):
    # find the SOC for the given hour
    # searching backwards
    checkRecord=len(priceList)
    while int(priceList[checkRecord-1][3][11:13])!=findHour and checkRecord>0:
        checkRecord+=-1
    SOC=schedule[checkRecord-1]["soc"]
    return SOC

def buildInitialPlanningList():
    # build complete list with prices, PV, usage and empty fields
        global priceList
        # start with pricelist as basis build the full list of planning intervals
        if outputMode or debug: print("Building initial list for : ",runDate)

        priceList=parsePricesIntoList(runDate,hourAvgPlanning)
        if outputMode:
            for record in priceList:
                print ("initial ",record)

        # check whether entsoe provided all expected prices, if not, get them from energyzero
        if runDate.date()==today:
            currentTime=datetime.now()
            currentHour=currentTime.hour
            if currentHour>=15:
                expectedIntervals=48
            else:
                expectedIntervals=24
        else:
            expectedIntervals=48
        if not hourAvgPlanning and runDate>=datetime.strptime("20251001","%Y%m%d"): expectedIntervals=expectedIntervals*4
        # note past intervals/hours will be dropped from list later
        if len(priceList)<expectedIntervals:
            priceList=getPricesFromEnergyZero(runDate,hourAvgPlanning)
            if outputMode:
                for record in priceList:
                    print ("energyzero ",record)

        # add the PV forecasts
        # with a separate field for total direct and total indirect connected PV panels

        if len(priceList)>0 and runDate.date()==today:
            if includePV:
                for groupSpec in pvGroups:
                    forecastList=parsePVforecastIntoList(groupSpec)
                    if len(forecastList)>0:
                        mergeForecastWithPricelist(groupSpec,forecastList)
                    if outputMode:
                        for record in priceList:
                            print ("merged pv ",record)

        # add the hourly usage forecast
            if includeUsage:
                dataFound,usageList=calcHourlyAvgUsage(homeUsageIDX,0.1)
                if dataFound:
                    mergeUsageWithPriceList(usageList)
                if outputMode:
                    for record in priceList:
                        print ("merged usage ",record)

            if outputMode:
                for record in priceList:
                    print ("merged ",record)

            dropHistoryFromPricelist(runHour)

        else:
            # get PV and actual usage for dates in the past
            if len(priceList)>0:
                if includePV:
                    pvList=getHrValueFromBIGDB(runDate,3) # pv house
                    if len(pvList)>0:
                        groupSpec=["indirect",0,0,0] # dummy
                        mergeForecastWithPricelist(groupSpec,pvList)
                    if outputMode:
                        for record in priceList:
                            print ("merged pv ",record)
                    pvList=getHrValueFromBIGDB(runDate,210) # pv blokhut
                    if len(pvList)>0:
                        groupSpec=["direct",0,0,0] # dummy
                        mergeForecastWithPricelist(groupSpec,pvList)
                    if outputMode:
                        for record in priceList:
                            print ("merged pv ",record)
                if includeUsage:
                    usageList=getHrValueFromBIGDB(runDate,22) # pv blokhut
                    if len(usageList)>0:
                        mergeActualWithPricelist(usageList)

                dropHistoryFromPricelist(runHour)

        if outputMode:
            for record in priceList:
                print ("without history ",record)
##### end of all function to collect input data   #####

#### the actual optimsation function  #####

def LPoptimization():
    # lineair programming optimisationusing pulp library
    nrIntervals = len(priceList)

    # BATTERY PARAMETERS, RTE split into equal parts for charge and discharge
    Effcharge = onewayEff
    Effdischarge = onewayEff

    # Indices for fields in priceList to make the code below more readable
    forecastDirectIndex=4
    forecastIndirectIndex=5
    forecastUsageIndex=6
    buyPriceIndex=7
    sellPriceIndex=8

    # LP PROBLEM, we are aiming for maximum financial return
    prob = pulp.LpProblem("Battery_Optimization", pulp.LpMaximize)


    # VARIABLES
    chargeWh = pulp.LpVariable.dicts("charge", range(nrIntervals), lowBound=0, upBound=maxChargeSpeed) # this is indirect charge from PV not connected directly
    dischargeWh = pulp.LpVariable.dicts("discharge", range(nrIntervals), lowBound=0, upBound=maxDischargeSpeed)
    sockWh = pulp.LpVariable.dicts("soc", range(nrIntervals), lowBound=int(float(minBatterySOCPct/100*ratedBatteryCapacity)), upBound=ratedBatteryCapacity)
    importWh = pulp.LpVariable.dicts("import", range(nrIntervals), lowBound=0)
    exportWh = pulp.LpVariable.dicts("export", range(nrIntervals), lowBound=0)
    costsEuro = pulp.LpVariable.dicts("costs", range(nrIntervals))

    # OBJECTIVE, maximise income minus costs
    # note variables contain Wh values and all prices are kWh prices, so should be divided by factor 1000, but optimisation
    # in extreme cases does not optimise properly then (due to small floating point numbers), so the factor 1000 is removed (does not matter for optimisation)
    # costsEuro variable is calculated with correct factor 1000, see below
    prob += pulp.lpSum(
        priceList[t][sellPriceIndex] * exportWh[t] - priceList[t][buyPriceIndex] * importWh[t] - dischargeWh[t]* cycleCosts # note factor 1000 on all costs removed
        for t in range(nrIntervals)
    )


    # CONSTRAINTS
    for t in range(nrIntervals):
        # Energy balance , note could remove priceList[t][forecastDirectindex] on both sides of == sign
        prob += (
            priceList[t][forecastDirectIndex] + priceList[t][forecastIndirectIndex] + importWh[t] + dischargeWh[t]
            ==
            priceList[t][forecastUsageIndex] + exportWh[t] + chargeWh[t] + priceList[t][forecastDirectIndex]
        )

        # Charge / discharge limits
        if hourAvgPlanning:
            prob += chargeWh[t] <= maxChargeSpeed
            prob += dischargeWh[t] <= maxDischargeSpeed
        else:
            prob += chargeWh[t] <= maxChargeSpeed/4
            prob += dischargeWh[t] <= maxDischargeSpeed/4

        # SOC evolution, make the connection between intervals
        if t == 0:
            prob += sockWh[t] == initialCharge + priceList[t][forecastDirectIndex]+Effcharge * chargeWh[t] - dischargeWh[t] / Effdischarge
        else:
            prob += sockWh[t] == sockWh[t-1] + priceList[t][forecastDirectIndex]+Effcharge * chargeWh[t] - dischargeWh[t] / Effdischarge


        # calculate actuals costs  with correct factor 1000
        costsEuro[t]=priceList[t][sellPriceIndex]/1000 * exportWh[t] - priceList[t][buyPriceIndex]/1000 * importWh[t]

        # constraint if import from grid is not allowed (but note optimisation might not be possible then)
        if zeroGridCharge:
            prob += importWh[t]==0

    # SOLVE, run the solver
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    optimisationStatus=pulp.LpStatus[prob.status]

    # OUTPUT, put the variables for each interval onto a list called "schedule"
    schedule = []
    for t in range(nrIntervals):
        schedule.append({
            "interval": t,
            "charge": int(chargeWh[t].value()),
            "discharge": int(dischargeWh[t].value()),
            "soc": int(sockWh[t].value()),
            "import": int(importWh[t].value()),
            "export": int(exportWh[t].value()),
            "costs" : int(costsEuro[t].value()*10000)/10000
            })

    return optimisationStatus,schedule

#### end of optimisation, beginning of output functions   #####

def outputOptimisationResult(optimisationStatus,schedule,outputFileName,writeMode):
    # output to a file
    fileHandle = open(outputFileName, writeMode)
    if optimisationStatus!="Optimal":
        print ("ATTENTION: no optimal solution achieved, status is ",optimisationStatus," on date ",runDate,file=fileHandle)
    if runDate==startDateObject:
        print("date        time   pvD   pvI   use  nett chrgD  chrg dschg   soc   imp   exp  pr-buy pr-sell    cost",file=fileHandle)
    totalCosts=0

    if runDate+timedelta(days=1)==endDateObject:
        # output everything on the list
        for nr,record in enumerate(schedule):
            totalCosts+=record["costs"]
            printIntervalToFile(nr,record,fileHandle)
        print("Total costs ",totalCosts)
    else:
        if runDate==startDateObject:
            # output until 15:00 next day (excl)
            runDateString=datetime.strftime(runDate,'%Y-%m-%d')
            for nr,record in enumerate(schedule):
                if priceList[nr][3][0:10]==runDateString or str(priceList[nr][3][11:13])<"15":
                    totalCosts+=record["costs"]
                    printIntervalToFile(nr,record,fileHandle)
        else:
            # output from 15:00 runDate (incl) till 15:00 next day (excl)
            runDateString=datetime.strftime(runDate,'%Y-%m-%d')
            nextDateString=datetime.strftime(runDate+timedelta(days=1),'%Y-%m-%d')
            for nr,record in enumerate(schedule):
                if ((priceList[nr][3][0:10]==runDateString and str(priceList[nr][3][11:13])>="15") or (priceList[nr][3][0:10]==nextDateString and str(priceList[nr][3][11:13])<"15")):
                    totalCosts+=record["costs"]
                    printIntervalToFile(nr,record,fileHandle)

    fileHandle.close()

def printIntervalToFile(nr,record,fileHandle):
    # output one single line to a file
    print( priceList[nr][3]+" "+"{:>5d}".format(priceList[nr][4])+" "+"{:>5d}".format(priceList[nr][5])+" "+"{:>5d}".format(priceList[nr][6])+" "+"{:>5d}".format(priceList[nr][6]-priceList[nr][5]-priceList[nr][4]), end=" ",file=fileHandle)
    print("{:>5d}".format(priceList[nr][4])+" "+"{:>5d}".format(record["charge"])+" "+"{:>5d}".format(record["discharge"])+" "+"{:>5d}".format(record["soc"])+" "+"{:>5d}".format(record["import"])+" "+"{:>5d}".format(record["export"]),end=" ",file=fileHandle)
    print("{:>+1.6f}".format(priceList[nr][7])+" "+"{:>+1.6f}".format(priceList[nr][8])+" "+"{:>+2.6f}".format(record["costs"]),file=fileHandle)

def outputToTextDevice(schedule,starthour,writeMode,optimisationStatus):
    # output to domoticz text device
    if writeMode=='w':
        clearTextDevice(planningDisplayIDX)
    totalCosts=0
    for nrReversed,record in enumerate(reversed(schedule)):
            nr=len(priceList)-nrReversed-1
            outputString="%10s %5d %5d %5d %5d %5d %5d %5d %5d %6d %6d  %1.4f  %1.4f  %2.4f" %(priceList[nr][3],priceList[nr][4],priceList[nr][5],priceList[nr][6],priceList[nr][6]-priceList[nr][5]-priceList[nr][4],priceList[nr][4],record["charge"],record["discharge"],record["soc"],record["import"],record["export"],priceList[nr][7],priceList[nr][8],record["costs"])
            outputString=outputString.replace(' ','_')  # JSON processing removes all duplicate spaces, so use underscore to get table format
            setTextDevice(planningDisplayIDX,outputString)
            totalCosts+=record["costs"]
    timestamp=datetime.strftime(datetime.now(),'%Y%m%d %H:%M:%S')
    setTextDevice(planningDisplayIDX,"date________time___pvD___pvI___use___nett__chrgD__chrg__dscg___soc____imp____exp___pr-buy__pr-sell____cost")
    if optimisationStatus!="Optimal":
        setTextDevice(planningDisplayIDX,"ATTENTION: no optimal solution achieved, status is "+optimisationStatus)
    setTextDevice(planningDisplayIDX,"total costs "+str(totalCosts))
    setTextDevice(planningDisplayIDX,"****** planning created "+timestamp+" for period "+startdate+" "+str(starthour)+" hr to "+enddate+" 24:00 hr ******")

def outputToBattery(schedule,starthour,result):
    # send required action for next hour to the battery
    scheduleCurrentHr=schedule[0]
    priceListCurrentHr=priceList[0]
    scheduleDateTime=priceListCurrentHr[3]
    pvDirect=priceListCurrentHr[4]
    pvIndirect=priceListCurrentHr[5]
    usageForecast=priceListCurrentHr[6]
    chargeIndirect=scheduleCurrentHr["charge"]
    discharge=scheduleCurrentHr["discharge"]
    importWh=scheduleCurrentHr["import"]
    exportWh=scheduleCurrentHr["export"]
    soc=scheduleCurrentHr["soc"]
    # !!! to be done: this assume the planning is done at the beginning of the hour, to be adapted for partial hours when running at random time
    if importWh==0 and exportWh==0: #self-consumption
        print("next hour",priceListCurrentHr[3]," action ","self-consumption")
        setBatteryAction("AutoSelf",scheduleDateTime,0,schedule)
    else:
        if chargeIndirect==0 and discharge==0: # passive
            print("next hour",priceListCurrentHr[3]," action ","passive")
            setBatteryAction("Passive",scheduleDateTime,0,schedule)
        else:
            if chargeIndirect>0: # manual charge
                print("next hour",priceListCurrentHr[3]," action ","manual charge ",-1*chargeIndirect) # charge must be negative value
                setBatteryAction("Manual",scheduleDateTime,-1*chargeIndirect,schedule)
            else:
                if discharge>0: # manual discharge
                    if discharge==maxDischargeSpeed or round((soc-discharge/onewayEff)/ratedBatteryCapacity,0)==minBatterySOCPct:
                        print("next hour",priceListCurrentHr[3]," action ","self-consumption",discharge)
                        setBatteryAction("AutoSelf",scheduleDateTime,0,schedule)
                    else:
                        print("next hour",priceListCurrentHr[3]," action ","manual discharge ",discharge)
                        setBatteryAction("Manual",scheduleDateTime,discharge,schedule)
                else:
                    print("next hour",priceListCurrentHr[3]," action ","don't know")
                    # don't know, should not exist

def processCLarguments():
    # get command line arguments to determine the run modes
    global debug,outputMode,runMode,includePV,includeUsage,zeroGridCharge,includeTax,saldering,hourAvgPlanning,mqttQuery
    debug=False
    outputMode=False
    runMode="standalone"
    includePV=False
    includeUsage=False
    zeroGridCharge=False
    includeTax=False
    saldering=False
    hourAvgPlanning=False
    CLargSuccess=True
    mqttQuery=False
    try:
        for i in range(len(sys.argv)-1):
            if sys.argv[i+1] not in ["-t","-v","-q","-d","-s","-i","-p","-u","-z","-b","-n","-h","-m"]:
                raise Exception
            # use one of the 3 next arguments to set output level
            if sys.argv[i+1]=="-t": # trace
                debug=True
                outputMode=True
            if sys.argv[i+1]=="-v": # verbose
                debug=False
                outputMode=True
            if sys.argv[i+1]=="-q": # quiet
                debug=False
                outputMode=False
            # choose between domoticz integrated or standalone
            if sys.argv[i+1]=="-d": # domoticz
                runMode="domoticz"
            if sys.argv[i+1]=="-s": # standalone
                runMode="standalone"
            if sys.argv[i+1]=="-i": # integrated (=from command line but data from domoticz)
                runMode="integrated"

            # include PV forecast/actual
            if sys.argv[i+1]=="-p": # include PV forecast/actual
                includePV=True

            # include usage estimate/actual
            if sys.argv[i+1]=="-u": # include usage
                includeUsage=True

            # block charging from grid
            if sys.argv[i+1]=="-z": # zero grid
                zeroGridCharge=True # charging from grid is not allowed, only from PV

            # include tax elements in price
            if sys.argv[i+1]=="-b": # belasting
                includeTax=True

            # set whether saldering/netting applies
            if sys.argv[i+1]=="-n": # netting/saldering
                saldering=True

            # set planning interval qtr (=15min) or hour
            if sys.argv[i+1]=="-h": # plan with hr avg even if 15 min data available
                hourAvgPlanning=True

            if sys.argv[i+1]=="-m": # mqtt marstek querying
                mqttQuery=True

    except:
        print("Following command line arguments are recognised: -t,-v,-q and -d,-s and -p and -z and -b and -n and -h")
        print("-t = full tracing, debug mode")
        print("-v = verbose mode, intermediate steps in planning are shown")
        print("-q = quiet mode (default), no intermediate feedback provided.")
        print(" ")
        print("-d = domoticz integration mode")
        print("-s = standalone mode, no domoticz integration (default)")
        print(" ")
        print("-p = PV to be included (default NO)")
        print("     When running domoticz mode , PV forecast is included, otherwise PV actual surplus")
        print("     Note that actual PV surplus data is retrieved from Domoticz even if standalone")
        print("-u = include expected usage estimate.")
        print("-z = zero charging from grid")
        print("-b = include tax elements in price")
        print("-n = saldering/netting applicable")
        print("-h = plan hourly intervals instead of 15 minute")
        print("-m = use Marstek mqtt query to get required start data")
        print("     ")
        CLargSuccess=False
    return CLargSuccess

def main():
    # main contrrol loop
    global startdate,enddate,starthour,initialCharge,includePV,includeUsage,zeroGridCharge,runDate,runHour,includeTax,energyTax,vatPCT,xmlAvailable,hourAvgPlanning,startDateObject,endDateObject

    if not processCLarguments():
        quit()

    if runMode=="domoticz" or runMode=="integrated":
        if not getPlanningInput():
            print("ERROR: Something wrong with getting all planning input data.")
            quit() # no point in going further
        xmlAvailable="N"
        overwrite="Y"
    else:
        getUserInput()
        xmlAvailable=input("Is the xml-data already available in the file(s) Y/N ? (default N) ") or "N"
        overwrite=input("Overwrite previous output file(s) Y/N ? (default Y) ") or "Y"
    if overwrite=="Y" or overwrite=="y":
        writeMode='w'
    else:
        writeMode='a'

    if runMode=="standalone" or runMode=="integrated":
        outputFileName="entsoe-output"+startdate+".txt"
        fileHandle = open(outputFileName, writeMode)
        #print("date        time   pv   pv  use nett chrg dscg  soc   imp   exp  pr-buy pr-sell    cost",file=fileHandle)
        fileHandle.close()
        writeMode='a'
    else:
        outputFileName=None

    # prepare objects for use of the for-loop
    startDateObject=datetime.strptime(startdate,'%Y%m%d')
    endDateObject=datetime.strptime(enddate,'%Y%m%d')
    runDate=startDateObject
    runHour=starthour

    while runDate<endDateObject or runDate==startDateObject:

        # setting the output variables and getting external data
        if outputMode or debug: print("Processing : ",runDate," from hour ",runHour)

        buildInitialPlanningList()
        result,schedule=LPoptimization()
        if runMode!="domoticz":
            print(datetime.strftime(runDate,'%Y%m%d'))
            outputOptimisationResult(result,schedule,outputFileName,writeMode)
        # prepare for next day run
        runDate=runDate+timedelta(days=1)
        if runDate<endDateObject:
            runHour=15
            initialCharge=getSOC(runHour-1,schedule)
            writeMode='a'
            if outputMode or debug: print("ready for next runDate ",datetime.strftime(runDate,'%Y%m%d')," with initialCharge ",initialCharge," at 15:00")

            if debug: input("Enter to continue ... *****************************************************************************************************************************************************************************************************")


    if runMode=="domoticz":
        outputToTextDevice(schedule,starthour,'w',result)
        outputToBattery(schedule,starthour,result)

if __name__ == '__main__':
    main()

