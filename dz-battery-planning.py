
##################################################################################################################################
## start of Domoticz integration definition, update these lines to match your domoticz setup #####################################
## Domoticz user variables
securityTokenIDX=12                 # the IDX of the Domoticz user variable holding the API security token for transparency.entsoe.eu
maxBatteryCapacityIDX=14            # the IDX of the Domoticz user variable holding the value for the maximum available battery charge capacity
maxBatteryChargeSpeedIDX=15         # the IDX of the Domoticz user variable holding the value for the maximum charge speed
maxBatteryDischargeSpeedIDX=16      # the IDX of the Domoticz user variable holding the value for the maximum discharge speed
conversionEfficiencyIDX=20             # the IDX of the Domoticz user variable holding the value for the conversion efficiency percentage of the battery system
# following user variables are needed if PV panel forecast is to be included (use -p option on the commandline), otherwise set to 0
pvPanelAngleIDX=17                  # the IDX of the Domoticz user variable holding the value of the PV panel angle (horizontal = 0)
pvPanelAzimuthIDX=18                # the IDX of the Domoticz user variable holding the value of the PV panel azimuth (south = 0)
pvPanelMaxPeakIDX=19                # the IDX of the Domoticz user variable holding the value of the PV panel max peak kWH
## Domoticz device IDX numbers
planningDisplayIDX=111              # the IDX number of a Domoticz text device to use for display of the planning
batterySwitchIDX=112                # the IDX of the Domoticz selector switch for controlling the battery system actions (API commands to be set in the "selector action" fields of the device) 
batteryOffCode=0                    # the 3 level numbers as defined in the selector switch for Off/Charge/Discharge (0,10 and 20 by default)
batteryChargeCode=10
batteryDischargeCode=20
batteryChargeLevelIDX=113           # the IDX of the Domoticz device with updated actual battery charge level (should be updated through the battery system API)
## Domoticz server
domoticzIP="127.0.0.1"   # internal IP address of the Domoticz server. This assumes domoticz is run on the same system as this program (if not, use the external IP address).
domoticzPort="8080"      # Domoticz port
# all communication with domoticz devices/database is with JSON calls (like domoticz itself is doing)
baseJSON="http://"+domoticzIP+":"+domoticzPort+"/json.htm?"   # the base string for any JSON call.
## end of Domoticz integration definition ########################################################################################
##################################################################################################################################

from operator import itemgetter, attrgetter
from datetime import date,datetime,timedelta
import xml.etree.ElementTree as ET
import requests
import copy
import json
import time
import sys
import urllib.parse

today=date.today()
todayString=datetime.strftime(today,'%Y%m%d')
todayLongString=datetime.strftime(today,'%Y-%m-%d')

def getUserInput():
    # get user input, with limited (!!) input validation, used in standalone mode
    global initialCharge,maxBatteryCapacity,maxChargeSpeed,maxDischargeSpeed,startdate,enddate,starthour,securitytoken,conversionEfficiency
    startdate=input("Enter startdate as YYYYMMDD (default=today)   : ") or todayString
    enddate=input("Enter enddate as YYYYMMDD (default=startdate+1) : ") or datetime.strftime(datetime.strptime(startdate,'%Y%m%d')+timedelta(days=1),'%Y%m%d')
    starthour=int(input("Enter start hour as HH (default next hour)   : ") or datetime.strftime(datetime.now()+timedelta(hours=1),'%H'))
    initialCharge=int(input("Enter initial charge in Wh (default=0) :") or "0" )
    maxBatteryCapacity=int(input("Enter max capacity in Wh (default 5000) :") or 5000)
    maxChargeSpeed=int(input("Enter max charge speed in Watt (default 2000) :") or 2000)
    maxDischargeSpeed=int(input("Enter max discharge speed in Watt (default 1500) :") or 1500)
    conversionEfficiency=int(input("Enter conversion efficiency percentage (default 100) :") or 100)
    conversionEfficiency=float(conversionEfficiency)/100.0
    securitytoken='xxxxxx paste in your entsoe api token here xxxxxxx'  # paste in your own security token from entsoe.eu

def getPlanningInput():
    # read initial planning data from Domoticz variables and devices (instead of user input)
    global initialCharge,maxBatteryCapacity,maxChargeSpeed,maxDischargeSpeed,startdate,enddate,starthour,securitytoken,conversionEfficiency
    getPlanningInputSuccess=True

    startdate=todayString
    enddate=datetime.strftime(datetime.strptime(startdate,'%Y%m%d')+timedelta(days=1),'%Y%m%d')
    starthour=int(datetime.strftime(datetime.now(),'%H'))  # current hour. This assumes the program is called from domoticz at the start of the hour.

    responseResult,varValue=readBatteryChargeLevel()
    if responseResult: initialCharge=float(varValue)
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    responseResult,varValue=getUserVariable(maxBatteryCapacityIDX)
    if responseResult: maxBatteryCapacity=float(varValue)
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    responseResult,varValue=getUserVariable(maxBatteryChargeSpeedIDX)
    if responseResult: maxChargeSpeed=float(varValue) 
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    responseResult,varValue=getUserVariable(maxBatteryDischargeSpeedIDX)
    if responseResult: maxDischargeSpeed=float(varValue) 
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    responseResult,varValue=getUserVariable(conversionEfficiencyIDX)
    if responseResult: conversionEfficiency=float(varValue)/100.0
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    responseResult,securitytoken=getUserVariable(securityTokenIDX)
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    if getPlanningInputSuccess==False:
        print("ERROR: getting all required planning data failed.")
    return getPlanningInputSuccess


def getLocation():
    # function to get the value of a location defined in settings
    try:
        apiCall="type=settings"
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

def getPercentageDevice(varIDX):
    # function to get the value of a percentage device indicated by the varIDX number
    try:
        apiCall="type=devices&rid="+str(varIDX)
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


def setBatteryAction(statusTXT):
    # set the action for the battery system on the selector switch
    # currently not used because battery is controlled via dzVents script
    try:
        if str(statusTXT):
            if str(statusTXT)=="Charge":
                responseResult=updateSelectorSwitch(batterySwitchIDX,batteryChargeCode)
            else:
                if str(statusTXT)=="Discharge":
                    responseResult=updateSelectorSwitch(batterySwitchIDX,batteryDischargeCode)
                else:
                    responseResult=updateSelectorSwitch(batterySwitchIDX,batteryOffCode)
            if responseResult==False:
                raise Exception
        else:
            print("ERROR: incorrect type of battery action text provided")
            raise Exception
    except:
        print("ERROR: unable to set battery switch with IDX ",batterySwitchIDX," to action ",str(statusTXT))
        responseResult=False
    return responseResult

def readBatteryChargeLevel():
    # read the charge level in percentage and return value in same units as maxBatteryCapacity
    # currently not used because battery is controlled via dzVents script
    chargeLevel=None
    try:
        responseResult,chargePercent=getPercentageDevice(batteryChargeLevelIDX)
        if responseResult:
            responseResult,maxBatteryCapacity=getUserVariable(maxBatteryCapacityIDX)
            if responseResult:
                chargeLevel=float(chargePercent/100*int(maxBatteryCapacity))
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

def loadPVforecast():
    # request the PV production forecast from forecast.solar and store in a file
    try:
        # url components for https feed from forecast.solar
        pvForecastFileName="solarforecast.json"
        urlwebsite='https://api.forecast.solar'
        urldoctype='/estimate/watthours/period'
        responseResult,latitude,longitude=getLocation()
        if responseResult:
            responseResult,pvAngle=getUserVariable(pvPanelAngleIDX)
            if responseResult:
                responseResult,pvAzimuth=getUserVariable(pvPanelAzimuthIDX)
                if responseResult:
                    responseResult,pvMaxPeak=getUserVariable(pvPanelMaxPeakIDX)
                    if responseResult:
                        url=urlwebsite+urldoctype+"/"+latitude+"/"+longitude+"/"+pvAngle+"/"+pvAzimuth+"/"+pvMaxPeak
                        response = requests.get(url)
                        if response.status_code == 200:
                            # saving the json file
                            with open(pvForecastFileName, 'wb') as f:
                                f.write(response.content)
                                fileReceived=True
                        else:
                            print("ERROR: no proper PV panel forecast file received")
                            raise Exception
                    else:
                        print("ERROR : required PV panel info not found in Domoticz")
                        raise Exception
                else:
                    print("ERROR : required PV panel info not found in Domoticz")
                    raise Exception
            else:
                print("ERROR : required PV panel info not found in Domoticz")
                raise Exception
        else:
            print("ERROR : required location not found in Domoticz settings")
            raise Exception
    except:
        print("ERROR: no proper PV panel forecast file received")
        fileReceived=False
    return fileReceived


def loadPrices(entsoeFileName,loadStartDate,loadEndDate):
    # request the prices from entsoe.eu and store in a file
    try:
        # url components for https feed from ENTSOE.EU
        urlwebsite='https://web-api.tp.entsoe.eu/api?'
        urltoken='securityToken='+securitytoken
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


def parseXMLintoPriceLists(xmlfile,runDate):
    # create pricelists out of entsoe xml file and, if applicable, the PV forecast file
    tree = ET.parse(xmlfile)
    root = tree.getroot()
    # create empty lists for prices
    HourPriceList=[]  # the actual list for hours available for optimsation
    displayList=[]    # the list for tracking and display of results
    sequenceNr=0      # sequence number counts number of lines from entsoe
    pvHRs=0           # additional lines for pv forecast
    if PVincl: 
        forecastList=parseJSONintoPVList()
    for item in root.iter():
        pvForecast=0
        if item.tag.find('price.amount')>0:
            price=float(item.text)
            if sequenceNr<=47: # never more than 2 days even if entsoe provides more than requested
                if debug: print("processing price ",item.text)
                datetimeString=datetime.strftime(runDate+timedelta(hours=sequenceNr),'%Y-%m-%d %H:%M:%S')
                if sequenceNr>=starthour or sequenceNr>23: # all prices after (and including) starthour on first day are put on hourpricelist, plus next day, if any
# list element will consist of sequenceNr,price,datetime,usedcapacity,usetype(usetype=Unclassified,Charge,Discharge),changechargeqty,changeamount,percentageused,pvForecast
                    ListElement=[sequenceNr+pvHRs,price,datetimeString,initialCharge,"unclassified",0,0,0,0] 
                    HourPriceList.append(ListElement)
                    if PVincl:
                        pvForecast=findPVforecast(datetimeString[0:10],int(datetimeString[11:13]),forecastList)
                        if pvForecast>0:
                            pvHRs+=1
                            pvListElement=[sequenceNr+pvHRs,0,datetimeString,initialCharge,"unclassified",0,0,0,pvForecast]
                            HourPriceList.append(pvListElement)
                    if debug: print("List with length ",len(HourPriceList)," ",HourPriceList)
                else:
                    ListElement=[sequenceNr+pvHRs,price,datetimeString,0,"unclassified",0,0,0,0]  # no initial charge before starthour
                displayList.append(ListElement)
                if PVincl and pvForecast>0:  
                    displayList.append(pvListElement)
# pv lines are always in the list after the price line of the same hour
            sequenceNr+=1
    return HourPriceList,displayList,sequenceNr

def parseJSONintoPVList():
    # create PV forecast list out of json file 
    pvForecastFileName="solarforecast.json"
    with open(pvForecastFileName, "r") as read_file:
        forecastHRS = json.load(read_file)["result"]
        # list starts at sunrise and ends at sunset and shows two days
        # each line is interpreted as production up to that hour
        # first line for each day can be skipped, is production until sunrise = 0
        # for last item of each day the endHour=sunsetHR+1, unless minutes = 00
        firstItem=True 
        forecastList=[]
        seqNr=0
        for key, value in forecastHRS.items():
            if not firstItem:
                forecastDate=key[0:10]
                if forecastDate==firstDate:
                    endHr=int(key[11:13])
                    startHr=endHr-1
                    previousMinutes=int(key[14:16])
                    forecastWh=int(value)
                    forecastList.append([forecastDate,startHr,endHr,forecastWh])
                    seqNr+=1
                else:
                    # first item of next day
                    firstDate=key[0:10]
                    if previousMinutes!=0:  # sunset did coincide with the exact hour
                        forecastList[seqNr-1][1]=forecastList[seqNr-1][1]+1
                        forecastList[seqNr-1][2]=forecastList[seqNr-1][2]+1
            else:
                firstItem=False
                firstDate=key[0:10]
        if previousMinutes!=0:
            forecastList[seqNr-1][1]=forecastList[seqNr-1][1]+1
            forecastList[seqNr-1][2]=forecastList[seqNr-1][2]+1
        for i in forecastList:
            if debug: print("forecast ",i)
    return forecastList

def findPVforecast(searchDate,searchHR,forecastList):
    # find the pv forecast connected to a price line of the same hour
    pvForecast=0
    for i in forecastList:
        if i[0]==searchDate and i[1]==searchHR:
            pvForecast=i[3]
    return pvForecast


def rebuildHourPriceList(displayList):
    # rebuild the HourPriceList using results from previous cycles as tracked in displayList 
    HourPriceList=[]
    if debug: print("rebuilding HourPriceList")
    for i in displayList:
        if int(i[2][11:13])>=starthour or i[2][8:10]!=startdate[6:8]: # all prices after (and including) starthour on first day are put on list
            if i[4]=="unclassified" or abs(i[7])<100: #  not fully used
                if debug: print("Appending hour ",i)
                HourPriceList.append(i)
    return HourPriceList


def priceField(element):
# for sorting
    return element[1]

def priceDiffminMaxField(element):
# for sorting
    return element[3],element[1][0],-1*element[2][0]

def createPairList(HourPriceList):
    # create list of min/max and max/min hour pairs, sorted on pricediff between the two elements
    PairList=[]
    HourPriceList.sort(key=priceField)
    # note hourpricelist contains price lines and pv lines. PV lines are always one sequence nr higher than price lines at same hour.
    pairNr=0
    chargeDone=0
    pairAvailable=True
    for Element1 in HourPriceList:
        for Element2 in reversed(HourPriceList):
            if Element1[0]<Element2[0]: # Element1 needs to be earlier than Element2, check sequenceNr. 
                                        # PV line can pair with price line of same hour
                priceDifferential=(Element2[1]-Element1[1])
                if priceDifferential>0 and Element2[8]==0:  # contribution of paired action needs to be positive, and max should not be PV forecast line
                        # last element higher than first element, so charge/discharge=min/max=buy/sell pair
                    priceDifferential=(Element2[1]*conversionEfficiency - Element1[1]/conversionEfficiency)
                    if priceDifferential>0: # check if still positive after adjusting for conversion losses
                        Pair=[pairNr,Element1,Element2,priceDifferential,pairAvailable,chargeDone,"minmax"]  # 7 fields per pair
                        PairList.append(Pair)
                        if debug: print("pair appended,minmax        ",Pair)
                    else:
                        # no longer positive after conversion loss
                        Pair=[pairNr,Element1,Element2,priceDifferential,pairAvailable,chargeDone,"minmax"]
                        if debug: print("pair dropped, not usable    ",Pair)
                else:
                    if priceDifferential<0 and Element1[8]==0: #last element lower than first, so discharge/charge=max/min=sale/buyback pair
                        priceDifferential=(Element1[1]*conversionEfficiency - Element2[1]/conversionEfficiency)
                        if priceDifferential>0:
                            Pair=[pairNr,Element1,Element2,priceDifferential,pairAvailable,chargeDone,"maxmin"]  # can be pair with pv line a min
                            PairList.append(Pair)
                            if debug: print("pair appended,maxmin        ",Pair)
                        else:
                            # no longer maxmin after conversion loss
                            Pair=[pairNr,Element1,Element2,priceDifferential,pairAvailable,chargeDone,"maxmin"]
                            if debug: print("pair dropped, not usable    ",Pair)
                pairNr+=1
    PairList.sort(key=priceDiffminMaxField,reverse=True)  # sorted by priceDiff and then earliest min and earliest max (using sequence nr)
    if debug: print("*************************************new pairlist ***************************************")
    for i in PairList: 
        if debug: print("pair ",i)
    return PairList


def checkMaxChargeCapacity(minSeqNr,maxSeqNr,displayList):
    # determine max capacity available for charging 
    minHR=displayList[minSeqNr][2][11:13]
    maxHR=displayList[maxSeqNr][2][11:13]
    if int(minHR)==starthour and displayList[minSeqNr][2][0:10]==todayLongString :
        hourMaxCharge=maxChargeSpeed*(60-int(datetime.strftime(datetime.now(),'%M')))/60  # part of the starthour might have passed already
        if debug: print("max charge in starthour", hourMaxCharge)
    else:
        hourMaxCharge=maxChargeSpeed # anyway limited by battery specs

    if int(maxHR)==starthour  and displayList[maxSeqNr][2][0:10]==todayLongString :
        hourMaxDischarge=maxDischargeSpeed*(60-int(datetime.strftime(datetime.now(),'%M')))/60  # part of the starthour might have passed already
        if debug: print("max discharge in starthour", hourMaxDischarge)
    else:
        hourMaxDischarge=maxDischargeSpeed # anyway limited by battery specs
    maxCap=hourMaxCharge
    for i in displayList:
        # check available capacity on all elements between min and max (min/max pair=charge/discharge pair)
        currentChange=abs(i[5])
        currentTotal=i[3]
        PVforecast=i[8]
        currentAction=i[4]
        if i[0]==minSeqNr:                                                        # the candidate for extra charge
            if currentAction=="Discharge": maxCap=0                               # never reverse previously planned action
            maxCap=min(maxCap,hourMaxCharge-currentChange)                        # never more than remaining chargespeed
            maxCap=min(maxCap,maxBatteryCapacity-currentTotal)                    # never more than remaining battery capacity
            if PVforecast>0:                                                      # charge candidate is a solar forecast line
                maxCap=min(maxCap,PVforecast-currentChange)                       # never more than remaining PVforecast
            ChargeSpeedAtMin=currentChange                                        # keep for later in case of PV line  # should this be currentChange+maxCap ????????????????
        if (i[0]==minSeqNr+1 and i[2][11:13]==minHR):                             # this is solar forecast at same hour as the charge candidate
            if currentAction=="Charge":                                           # PV discharge/return does not take up battery capacity/time
                maxCap=min(maxCap,hourMaxCharge-currentChange-ChargeSpeedAtMin)   # never more than remaining chargespeed when combined with charge candidate
        if i[0]>minSeqNr and i[0]<maxSeqNr:                                       # for all lines in between min and max
            maxCap=min(maxCap,maxBatteryCapacity-currentTotal)                    # should be able to hold the extra charge planned on min
        if i[0]==maxSeqNr :                                                       # discharge point
            if currentAction=="Charge": maxCap=0                                  # never reverse previously planned action
            maxCap=min(maxCap,hourMaxDischarge-currentChange)                     # remaining availability between previous planned discharge and max discharge speed
            if PVforecast>0:                                                      # discharge point is line with PV forecast 
                maxCap=0                                                          # cannot discharge on line of PV forecast (PV line can be max candidate if grid price is negative)
            DischargeSpeedAtMax=currentChange
        if (i[0]==maxSeqNr+1 and i[2][11:13]==maxHR):                             # this is PV forecast line connected to proposed discharge candidate
            if currentAction=="Charge":                                           # discharge can still be done, minus time needed for already planned charge
                maxCap=min(maxCap,hourMaxDischarge*(1-currentChange/hourMaxCharge)-DischargeSpeedAtMax) 
        maxCap=round(maxCap,0)
        if debug: print("for minSeqNr,minHR",minSeqNr," ",minHR," and maxSeqNr,maxHR ",maxSeqNr," ",maxHR," max charging capacity is ",maxCap," after evaluating ",i)
        if maxCap==0: break # no point of testing the rest of displayList
    return maxCap

def checkMaxDischargeCapacity(maxSeqNr,minSeqNr,displayList):
    # determine max capacity available for discharge
    if minSeqNr>=len(displayList)-1: 
        minHR=displayList[minSeqNr-1][2][11:13]
    else:
        minHR=displayList[minSeqNr][2][11:13]
    maxHR=displayList[maxSeqNr][2][11:13]
    if int(minHR)==starthour and displayList[minSeqNr][2][0:10]==todayLongString :
        hourMaxCharge=maxChargeSpeed*(60-int(datetime.strftime(datetime.now(),'%M')))/60  # part of the starthour might have passed already
        if debug: print("max charge in starthour", hourMaxCharge)
    else:
        hourMaxCharge=maxChargeSpeed # anyway limited by battery specs
    if int(maxHR)==starthour  and displayList[maxSeqNr][2][0:10]==todayLongString :
        hourMaxDischarge=maxDischargeSpeed*(60-int(datetime.strftime(datetime.now(),'%M')))/60  # part of the starthour might have passed already
        if debug: print("max discharge in starthour", hourMaxDischarge)
    else:
        hourMaxDischarge=maxDischargeSpeed # anyway limited by battery specs
    maxCap=hourMaxDischarge
    if (minHR==maxHR):  # special case where PV is discharged/returned at price of same hour, (max is priceline, min is pv line)
        # instead of discharge on max and charge on min, this is only discharge/return on max
        maxCap=displayList[minSeqNr][8]
    else:
        for i in displayList:
            # check available capacity on all elements between max and min   (max/min pair=discharge/charge pair)
            currentChange=abs(i[5])
            currentTotal=i[3]
            PVforecast=i[8]
            currentAction=i[4]
            if i[0]==maxSeqNr:
                if currentAction=="Charge": maxCap=0                                  # never reverse previously planned action
                maxCap=min(maxCap,hourMaxDischarge-currentChange)                     # remaining availability between previous planned discharge and max discharge speed
                maxCap=min(maxCap,currentTotal)                                       # never more than current battery charge
                if PVforecast>0:                                                      # discharge point is line with PV forecast
                    maxCap=0                                                          # cannot discharge on line of PV forecast (PV line can be max candidate if grid price is negative)
                DischargeSpeedAtMax=currentChange
            if (i[0]==maxSeqNr+1 and i[2][11:13]==maxHR):                             # this is PV forecast line connected to proposed discharge candidate
                if currentAction=="Charge":                                           # discharge can still be done, minus time needed for already planned charge
                    maxCap=min(maxCap,hourMaxDischarge*(1-currentChange/hourMaxCharge)-DischargeSpeedAtMax)
            if i[0]>maxSeqNr and i[0]<minSeqNr and not (i[0]==maxSeqNr+1 and i[2][11:13]==maxHR): # for all lines in between max and min, except PV line
                maxCap=min(maxCap,currentTotal)                                       # should be able to hold the extra charge planned on min

            if i[0]==minSeqNr:                                                        # the candidate for extra charge
                if currentAction=="Discharge": maxCap=0                               # never reverse previously planned action
                maxCap=min(maxCap,hourMaxCharge-currentChange)                        # never more than remaining chargespeed
                if PVforecast>0:                                                      # charge candidate is a solar forecast line
                    maxCap=min(maxCap,PVforecast-currentChange)                       # never more than remaining PVforecast
                ChargeSpeedAtMin=currentChange                                        # keep for later in case of PV lin
            if (i[0]==minSeqNr+1 and i[2][11:13]==minHR):                             # this is solar forecast at same hour as the charge candidate
                if currentAction=="Charge":
                    maxCap=min(maxCap,hourMaxCharge-currentChange-ChargeSpeedAtMin)  # never more than remaining chargespeed when combined with charge candidate
            maxCap=round(maxCap,0)
            if debug: print("for maxSeqNr,maxHR",maxSeqNr," ",maxHR," and minSeqNr,minHR ",minSeqNr," ",minHR," max discharging capacity is ",maxCap," after evaluating ",i)
            if maxCap==0: break # no point of testing the rest of displayList
    return maxCap

def processTopDownReturns(PairList,displayList,HourPriceList):
    # central routine to run down the pairlist from top to bottom until all options exhausted
    pairUsed=False
    totalAmount=0
    pairNr=0
    endPairNr=len(PairList)
    while pairNr<endPairNr:
        minMax=PairList[pairNr]
        maxMin=PairList[pairNr]
        if minMax[4]==True: # pair still available
            if minMax[6]=='minmax':
                minSeqNr=minMax[1][0]
                maxSeqNr=minMax[2][0]
                if debug: print("Procssing charge/discharge pair with minSeqNr ", minSeqNr," maxSeqNr ",maxSeqNr)
                maxCharge=checkMaxChargeCapacity(minSeqNr,maxSeqNr,displayList)
                if maxCharge>0:
                    # this pair can be used, implement it
                    totalAmount,displayList,minUsePct,maxUsePct=updateDisplayList(displayList,minSeqNr,maxSeqNr,maxCharge)
                    # update this pair and pairs with same min and max as result of usage 
                    pairAvailable=False
                    for elementNr,element in enumerate(PairList):
                        if debug: print("Checking pair ",element[1][0]," with ",element[2][0],"while minUsePct=",minUsePct," and maxUsePct=",maxUsePct)
                        if minUsePct==100:
                            if element[1][0]==minSeqNr or element[2][0]==minSeqNr:
                                if debug: print("removing from pairlist pair ",element[1][0]," with ",element[2][0])
                                PairList[elementNr][4]=pairAvailable
                        if maxUsePct==100:
                            if element[1][0]==maxSeqNr or element[2][0]==maxSeqNr:
                                if debug: print("removing from pairlist pair ",element[1][0]," with ",element[2][0])
                                PairList[elementNr][4]=pairAvailable
                        if element[1][0]==minSeqNr and element[2][0]==maxSeqNr: 
                            PairList[elementNr][5]=PairList[elementNr][5]+maxCharge
                            if debug: print("updating change to ",PairList[elementNr][5]," for pair ",element[1][0]," with ",element[2][0])
                    pairUsed=True
            else:
                maxSeqNr=maxMin[1][0]
                minSeqNr=maxMin[2][0]
                if debug: print("Processing discharge/charge pair with maxSeqNr ", maxSeqNr," minSeqNr ",minSeqNr)
                maxDischarge=checkMaxDischargeCapacity(maxSeqNr,minSeqNr,displayList)
                if maxDischarge>0:
                    # this pair can be used, implement it
                    totalAmount,displayList,minUsePct,maxUsePct=updateDisplayList(displayList,maxSeqNr,minSeqNr,-1*maxDischarge)
                    # update this pair and pairs with same min and max as result of usage 
                    pairAvailable=False
                    for elementNr,element in enumerate(PairList):
                        if debug: print("Checking pairlist for ",element[1][0]," with ",element[2][0],"while minUsePct=",minUsePct," and maxUsePct=",maxUsePct)
                        if minUsePct==100:
                            if element[1][0]==minSeqNr or element[2][0]==minSeqNr:
                                PairList[elementNr][4]=pairAvailable 
                                if debug: print("removing from pairlist pair ",element[1][0]," with ",element[2][0])
                        if maxUsePct==100:
                            if element[1][0]==maxSeqNr or element[2][0]==maxSeqNr:
                                PairList[elementNr][4]=pairAvailable
                                if debug: print("removing from pairlist pair ",element[1][0]," with ",element[2][0])
                        if element[1][0]==minSeqNr and element[2][0]==maxSeqNr: 
                            PairList[elementNr][5]=PairList[elementNr][5]+maxDischarge
                            if debug: print("updating change to ",PairList[elementNr][5]," for pair ",element[1][0]," with ",element[2][0])
                    pairUsed=True
        if pairUsed:
            pairNr=1  # start from top, check if previous unusable pairs can now be implemented
            pairUsed=False
        else:
            pairNr+=1
    return displayList,HourPriceList,totalAmount


def priceSeqNrField(element):
# for sorting
    return element[1],-1*element[0]

def sellFirst(displayList,HourPriceList):
    # sell available charge for top prices before checking pairs
    minSeqNr=HourPriceList[len(HourPriceList)-1][0] # for checking max discharge on full list beyond maxSeqNr
    HourPriceList.sort(key=priceSeqNrField,reverse=True)
    for MaxHour in HourPriceList:
        maxSeqNr=MaxHour[0]
        maxDischarge=checkMaxDischargeCapacity(maxSeqNr,minSeqNr,displayList)
        if maxDischarge>0:
            totalAmount,displayList,minUsePct,maxUsePct=updateDisplayList(displayList,maxSeqNr,None,-1*maxDischarge)
    return displayList,HourPriceList,totalAmount

def updateDisplayList(displayList,SeqNr1,SeqNr2,extraCharge):
    # update the displaylist/trackinglist
    # SeqNr2 can be empty, SeqNr1 position cannot
    if outputMode or debug : print("update displaylist between sequence numbers :",SeqNr1," and  ",SeqNr2," with charge ",extraCharge)
    minUsePct=0
    maxUsePct=0
    if extraCharge>0: # minMax
        minSeqNr=SeqNr1
        maxSeqNr=SeqNr2
        minHR=displayList[minSeqNr][2][11:13]
        maxHR=displayList[maxSeqNr][2][11:13]
        for i in range(len(displayList)):  
            if displayList[i][0]==minSeqNr:
                displayList[i][4]="Charge"
                displayList[i][3]=displayList[i][3]+extraCharge
                displayList[i][5]=displayList[i][5]+extraCharge
                displayList[i][6]=displayList[i][6]-1*displayList[i][1]/1000*extraCharge/1000/conversionEfficiency
                if int(minHR)==starthour and displayList[i][2][0-10]==todayLongString:
                    minutesPassed=int(datetime.strftime(datetime.now(),'%M'))
                else:
                    minutesPassed=0
                minutesPV=0
                if i<len(displayList)-1: # i+1 exists, so i could be followed by PV forecast line with planned charge action that already takes up time
                    if displayList[i+1][4]=="Charge" and displayList[i+1][8]>0:
                        minutesPV=abs(displayList[i+1][5]/maxChargeSpeed)*60
                hourMaxCharge=maxChargeSpeed*(60-minutesPassed-minutesPV)/60
                if displayList[i][8]>0:  # pv forecast
                    displayList[i][7]=max((displayList[i][5]/displayList[i][8])*100,abs(displayList[i][5]/hourMaxCharge*100))
                else:
                    displayList[i][7]=abs(displayList[i][5]/hourMaxCharge*100)
                minUsePct=int(displayList[i][7])
            if displayList[i][0]>minSeqNr and displayList[i][0]<maxSeqNr:
                displayList[i][3]=displayList[i][3]+extraCharge
            if displayList[i][0]==maxSeqNr:
                displayList[i][4]="Discharge"
                displayList[i][5]=displayList[i][5]-extraCharge
                displayList[i][6]=displayList[i][6]+displayList[i][1]/1000*extraCharge/1000*conversionEfficiency
                if int(maxHR)==starthour and displayList[i][2][0-10]==todayLongString:
                    minutesPassed=int(datetime.strftime(datetime.now(),'%M'))
                else:
                    minutesPassed=0
                minutesPV=0
                if i<len(displayList)-1: # i+1 exists, so i could be followed by PV forecast line with planned charge action that already takes up time
                    if displayList[i+1][4]=="Charge" and displayList[i+1][8]>0:
                        minutesPV=abs(displayList[i+1][5]/maxChargeSpeed)*60
                hourMaxDischarge=maxDischargeSpeed*(60-minutesPassed-minutesPV)/60
                if displayList[i][8]>0:  # pv forecast
                    displayList[i][7]=max((displayList[i][5]/displayList[i][8])*100,abs(displayList[i][5]/hourMaxDischarge*100))
                else:
                    displayList[i][7]=abs(displayList[i][5]/hourMaxDischarge*100)
                maxUsePct=int(displayList[i][7])
    else: # maxMin
        if SeqNr2==None:  # a SellFirst action
            minSeqNr=len(displayList) # is beyond end of list so no new charge (in case of sale only)
            minHR=displayList[minSeqNr-1][2][11:13]
        else:
            minSeqNr=SeqNr2
            minHR=displayList[minSeqNr][2][11:13]
        maxSeqNr=SeqNr1
        maxHR=displayList[maxSeqNr][2][11:13]
        if (minHR==maxHR) and SeqNr2!=None:  # special case where PV is discharged/returned at price of same hour, max is priceline, min is pv line
        # instead of discharge on max and charge on min, this is only discharge/return on max
            displayList[minSeqNr][4]="Discharge"
            displayList[minSeqNr][5]=extraCharge
            displayList[minSeqNr][6]=abs(extraCharge)/1000*displayList[maxSeqNr][1]/1000*conversionEfficiency
            displayList[minSeqNr][7]=100
            minUsePct=100
            maxUsePct=displayList[maxSeqNr][7]
        else:
            for i in range(len(displayList)):
                if displayList[i][0]==maxSeqNr:
                    displayList[i][4]="Discharge"
                    displayList[i][3]=displayList[i][3]+extraCharge
                    displayList[i][5]=displayList[i][5]+extraCharge
                    displayList[i][6]=displayList[i][6]-1*displayList[i][1]/1000*extraCharge/1000*conversionEfficiency
                    if int(maxHR)==starthour and displayList[i][2][0-10]==todayLongString:
                        minutesPassed=int(datetime.strftime(datetime.now(),'%M'))
                    else:
                        minutesPassed=0
                    minutesPV=0
                    if i<len(displayList)-1: # i+1 exists, so i could be followed by PV forecast line with planned charge action that already takes up time
                        if displayList[i+1][4]=="Charge" and displayList[i+1][8]>0:
                            minutesPV=abs(displayList[i+1][5]/maxChargeSpeed)*60
                    hourMaxDischarge=maxDischargeSpeed*(60-minutesPassed-minutesPV)/60
                    if displayList[i][8]>0:  # pv forecast
                        displayList[i][7]=max((displayList[i][5]/displayList[i][8])*100,abs(displayList[i][5]/hourMaxDischarge*100))
                    else:
                        displayList[i][7]=abs(displayList[i][5]/hourMaxDischarge*100)
                    maxUsePct=int(displayList[i][7])
                if displayList[i][0]>maxSeqNr and displayList[i][0]<minSeqNr:
                    displayList[i][3]=displayList[i][3]+extraCharge
                if displayList[i][0]==minSeqNr:
                    displayList[i][4]="Charge"
                    displayList[i][5]=displayList[i][5]-extraCharge
                    displayList[i][6]=displayList[i][6]+displayList[i][1]/1000*extraCharge/1000/conversionEfficiency
                    if int(minHR)==starthour and displayList[i][2][0-10]==todayLongString:
                        minutesPassed=int(datetime.strftime(datetime.now(),'%M'))
                    else:
                        minutesPassed=0
                    minutesPV=0
                    if i<len(displayList)-1: # i+1 exists, so i could be followed by PV forecast line with planned charge action that already takes up time
                        if displayList[i+1][4]=="Charge" and displayList[i+1][8]>0:
                            minutesPV=abs(displayList[i+1][5]/maxChargeSpeed)*60
                    hourMaxCharge=maxChargeSpeed*(60-minutesPassed-minutesPV)/60
                    if displayList[i][8]>0:  # pv forecast
                        displayList[i][7]=max((displayList[i][5]/displayList[i][8])*100,abs(displayList[i][5]/hourMaxCharge*100))
                    else:
                        displayList[i][7]=abs(displayList[i][5]/hourMaxCharge*100)
                    minUsePct=int(displayList[i][7])
    totalAmount=showList(displayList)
    return totalAmount,displayList,minUsePct,maxUsePct

def showList(displayList):
# show displaylist on screen
    totalAmount=0
    if outputMode or debug: print("-seqNr----date-------time-----------price----usetype----------change---%max--------total--------amount-----PV")
    for i in displayList:
        if outputMode or debug: print("    "+"{:>2d}".format(i[0])+"    "+i[2]+"    "+"{:>+4.5f}".format(i[1]/1000)+"    "+"{:12}".format(i[4])+"    "+"{:>7.0f}".format(i[5])+"    "+"{:>+4.0f}".format(i[7])+"%    "+"{:>+7.0f}".format(i[3])+"      "+"{:>+5.5f}".format(i[6])+"  "+"{:>+5.0f}".format(i[8]))
        totalAmount=totalAmount+i[6]
    if outputMode or debug: print("------------------------------------------------------------------------------------------------------")
    if outputMode or debug: print("--------------------------------------------------------------------------------total-amount: %+5.5f" %(totalAmount))
    return totalAmount

def reclassifyPV(displayList):
# adapt action description for pv lines on final displaylist and calculate pv return amounts
    predecessorPrice=0
    for i in displayList:
        if i[8]>0:
            if i[4]=="Charge":
                i[4]="Store"
            else:
                if i[4]=="Discharge" or i[4]=="unclassified":
                    i[4]="Return"
                    i[5]=i[8]
                    i[6]=abs(i[5])/1000*predecessorPrice/1000
                    i[7]=100
        predecessorPrice=i[1]
    totalAmount=showList(displayList)
    return totalAmount,displayList

def getCharge(displayList,findHour):
# find the target total charge value for the given hour
    hrCounter=0
    previousHr=0
    returnCharge=0
    for i in displayList:
        if int(i[2][11:13])!=previousHr:
            hrCounter+=1
            previousHr=int(i[2][11:13])
        if hrCounter==findHour:
            returnCharge=i[3]
    return returnCharge


def outputToFile(displayList,starthour,endhour,outputFileName,writeMode):
# output displaylist to a file
    fileHandle = open(outputFileName, writeMode)
    hrCounter=0
    previousHr=0
    for i in displayList:
        if hrCounter>=starthour and hrCounter<=endhour:
            print("    "+"{:>2d}".format(i[0])+"    "+i[2]+"    "+"{:>+4.5f}".format(i[1]/1000)+"    "+"{:12}".format(i[4])+"    "+"{:>7.0f}".format(i[5])+"    "+"{:>+4.0f}".format(i[7])+"%    "+"{:>+7.0f}".format(i[3])+"      "+"{:>+5.5f}".format(i[6])+"  "+"{:>+5.0f}".format(i[8]), file=fileHandle)
        if int(i[2][11:13])!=previousHr:
            hrCounter+=1
            previousHr=int(i[2][11:13])
    fileHandle.close()

def outputToDevice(displayList,starthour,writeMode):
# output displaylist to domoticz text device
    if writeMode=='w': 
        clearTextDevice(planningDisplayIDX)
    unclassifiedList=markTopLowPrices(displayList,starthour)
    for i in reversed(displayList):
        if int(i[2][11:13])>=starthour or i[2][0:10]>todayLongString:
            outputString="%2d  %s  %+4.5f  %12s  %+7.0f  %+4.0f   %+7.0f   %+5.5f   %+5.0f" %(i[0],i[2],(i[1]/1000),i[4],i[5],i[7],i[3],i[6],i[8])
            if i[4]=="unclassified":
                for u in unclassifiedList:
                    if i[0]==u[0]: 
                        outputString=outputString+u[2]
            outputString=outputString.replace(' ','_')  # JSON processing removes all duplicate spaces, so use underscore to get table format
            setTextDevice(planningDisplayIDX,outputString)
    timestamp=datetime.strftime(datetime.now(),'%Y%m%d %H:%M:%S')
    setTextDevice(planningDisplayIDX,"**__date_______time_________price________action___change__%max_____total_____amount______PV___******")
    setTextDevice(planningDisplayIDX,"****** planning created "+timestamp+" for period "+startdate+" "+str(starthour)+" hr to "+enddate+" 24:00 hr ******")

def outputJSONnextHr(displayList,startOutputHour):
    # print output for next hour in JSON format so this can be picked up in domoticz dzvents script as next action to execute
    hrCounter=0
    previousHr=0
    for i in displayList:
        if int(i[2][11:13])!=previousHr:
            hrCounter+=1
            previousHr=int(i[2][11:13])
        if hrCounter==startOutputHour:
            saveI=i
    # only output a single record for an hour. If PV line exists, then it is the PV line, otherwise the price line.
    print("{\n \"date\" : \"",saveI[2][0:10],"\",","\n","\"hour\" : \"",saveI[2][11:13],"\",\n","\"action\" : \"",saveI[4],"\",","\n","\"change\" :",saveI[5],",\n","\"target\" :",saveI[3],"\n}",sep="")


def markTopLowPrices(displayList,starthour):
    # mark the (max) 5 lowest prices of the remaining unclassified items, provided price is below avg
    unclassifiedList=[]
    averagePrice=0
    counter=0
    for i in displayList:
        if i[0]>=starthour:
            averagePrice+=i[1]
            counter+=1
            if i[4]=="unclassified":
                unclassifiedList.append([i[0],i[1],""])
    unclassifiedList.sort(key=priceField)
    averagePrice=float(averagePrice/counter)
    if len(unclassifiedList)>=5:
        endList=5
    else:
        endList=len(unclassifiedList)
    for i in range(endList):
        if unclassifiedList[i][1]<=averagePrice: unclassifiedList[i][2]="   low "+str(i+1)
    return unclassifiedList


def processCLarguments():
# get command line arguments to determine the run modes
    global debug,outputMode,runMode,PVincl
    commandLineArg1=None
    commandLineArg2=None
    debug=False
    outputMode=False
    PVincl=False
    runMode="standalone"
    CLargSuccess=True
    try:
        for i in range(len(sys.argv)-1):
            if sys.argv[i+1] not in ["-t","-v","-q","-d","-s","-p"]:
                raise Exception
            if sys.argv[i+1]=="-t": 
                debug=True
                outputMode=True
            if sys.argv[i+1]=="-v": 
                debug=False
                outputMode=True
            if sys.argv[i+1]=="-q": 
                debug=False
                outputMode=False
            if sys.argv[i+1]=="-d":
                runMode="domoticz"
            if sys.argv[i+1]=="-s":
                runMode="standalone"
            if sys.argv[i+1]=="-p":
                PVincl=True
        if runMode=="standalone": 
            PVincl=False
    except:
        print("Only 0 to 3 command line arguments are allowed.")
        print("Following command line arguments are recognised: -t,-v or -q and -d or -s and -p")
        print("-t = full tracing, debug mode")
        print("-v = verbose mode, intermediate steps in planning are shown")
        print("-q = quiet mode (default), no intermediate feedback provided.")
        print(" ")
        print("-d = domoticz integration mode")
        print("-s = standalone mode, no domoticz integration (default)")
        print(" ")
        print("-p = PV forecast to be included (default NO)")
        print("     Only allowed when running domoticz mode")
        print("     and startdate is today")
        CLargSuccess=False
    return CLargSuccess

def main():
    global startdate,enddate,initialCharge,starthour,PVincl

    if not processCLarguments():
        quit()

    if runMode=="domoticz":
        if not getPlanningInput():
            print("ERROR: Something wrong with getting all planning input data.")
            quit() # no point in going further
        loadFile="N"
        writeMode="Y"
    else:
        getUserInput()
        loadFile=input("Is the xml-data already available in the file(s) Y/N ? (default N) ") or "N"
        writeMode=input("Overwrite previous output file(s) Y/N ? (default Y) ") or "Y"

    if writeMode=="Y" or writeMode=="y":
        writeMode='w'
    else:
        writeMode='a'

    # prepare objects for use of the for-loop
    startDateObject=datetime.strptime(startdate,'%Y%m%d')
    endDateObject=datetime.strptime(enddate,'%Y%m%d')
    if runMode=="standalone":
        outputFileName="entsoe-output"+startdate+".txt"

    if PVincl:
        if startdate!=todayString:
            print("PV forecast only when startdate>=today")
            PVincl=False
        else:
            if not loadPVforecast():
                print("PV forecast not received, continuing without...")
                PVincl=False


    # if startdate==enddate then optimise from starthour till end-of-day
    # else
    # first optimise from startdate,starthour till startdate+1, end-of-day
    # then optimise from next day, 15:00 till nextday+1, end-of-day
    # and in that case the initial charge is the previously planned charge at 15:00


    runDate=startDateObject

    while runDate<endDateObject or runDate==startDateObject:

        # setting the output variables and getting external data
        if outputMode or debug: print("Processing : ",runDate)
        if runMode=="standalone":
            fileNameDate=datetime.strftime(runDate,'%Y%m%d')
            entsoeFileName="entsoe"+fileNameDate+".xml"
        else:
            # runMode=="domoticz"
            entsoeFileName="entsoe.xml" # no date in filename to prevent file system filling up
        if startdate==enddate:
            if loadFile[0]!="Y" and loadFile[0]!="y":
                loadStartDate=datetime.strftime(runDate,'%Y%m%d')
                loadEndDate=loadStartDate
                if not loadPrices(entsoeFileName,loadStartDate,loadEndDate):
                    print("ERROR: Something wrong with getting price data")
                    quit()
        else:
            if loadFile[0]!="Y" and loadFile[0]!="y":
                if outputMode or debug: print("rundate ",datetime.strftime(runDate,'%Y%m%d'))
                loadStartDate=datetime.strftime(runDate,'%Y%m%d')
                loadEndDate=datetime.strftime(runDate+timedelta(days=1),'%Y%m%d')
                if not loadPrices(entsoeFileName,loadStartDate,loadEndDate):
                    print("ERROR: Something wrong with getting price data")
                    quit()
        HourPriceList,displayList,priceHrs=parseXMLintoPriceLists(entsoeFileName,runDate)
        if outputMode: print ("initial list")
        for i in displayList:
            if outputMode or debug: print(i)

        # first sell existing charge at best price
        if initialCharge>0:
            displayList,HourPriceList,totalAmount=sellFirst(displayList,HourPriceList)
            HourPriceList=rebuildHourPriceList(displayList)

        # create charge/discharge and discharge/charge pairs and then implement most profitable pairs
        # this is the core of the program,i.e. the planning process
        PairList=createPairList(HourPriceList)
        displayList,HourPriceList,totalAmount=processTopDownReturns(PairList,displayList,HourPriceList)
        if PVincl: totalAmount,displayList=reclassifyPV(displayList)

        # output the results, depending on running mode
        if startdate==enddate:
            startOutputHour=starthour
            endOutputHour=23
        else:
            startOutputHour=starthour
            endOutputHour=38  # 23+15
        if runMode=="standalone":
            outputToFile(displayList,startOutputHour,endOutputHour,outputFileName,writeMode)

        # prepare for next day run
        if priceHrs<38:
            initialCharge=0
        else:
            initialCharge=getCharge(displayList,38)
        starthour=15
        writeMode='a'
        runDate=runDate+timedelta(days=1)

        if outputMode or debug: print("next runDate ",datetime.strftime(runDate,'%Y%m%d')," with initialCharge ",initialCharge," at 15:00")

        if debug: input("Enter to continue ... *****************************************************************************************************************************************************************************************************")
    if startdate!=enddate:
        if runMode=="domoticz":
            outputToDevice(displayList,startOutputHour,'w')
            outputJSONnextHr(displayList,startOutputHour)
        else:
            # last day optimisation is already included in previous day run, just need to output remainder of the day after 15:00
            outputToFile(displayList,39,47,outputFileName,writeMode)
            print("planning completed")


if __name__ == '__main__':
    main()


