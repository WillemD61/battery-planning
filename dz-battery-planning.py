
##################################################################################################################################
## start of Domoticz integration definition, update these lines to match your domoticz setup #####################################
## Domoticz user variables
securityTokenIDX=12                 # the IDX of the Domoticz user variable holding the API security token for transparency.entsoe.eu
maxBatteryCapacityIDX=14            # the IDX of the Domoticz user variable holding the value for the maximum available battery charge capacity
maxBatteryChargeSpeedIDX=15         # the IDX of the Domoticz user variable holding the value for the maximum charge speed
maxBatteryDischargeSpeedIDX=16      # the IDX of the Domoticz user variable holding the value for the maximum discharge speed
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

def getUserInput():
    # get user input, with limited (!!) input validation, used in standalone mode
    global initialCharge,maxChargeCapacity,maxChargeSpeed,maxDischargeSpeed,startdate,enddate,starthour,securitytoken
    startdate=input("Enter startdate as YYYYMMDD (default=today)   : ") or todayString
    enddate=input("Enter enddate as YYYYMMDD (default=startdate+1) : ") or datetime.strftime(datetime.strptime(startdate,'%Y%m%d')+timedelta(days=1),'%Y%m%d')
    starthour=int(input("Enter start hour as HH (default next hour)   : ") or datetime.strftime(datetime.now()+timedelta(hours=1),'%H'))
    initialCharge=int(input("Enter initial charge in Wh (default=0) :") or "0" )
    maxChargeCapacity=int(input("Enter max capacity in Wh (default 5000) :") or 5000)
    maxChargeSpeed=int(input("Enter max charge speed in Watt (default 2000) :") or 2000)
    maxDischargeSpeed=int(input("Enter max discharge speed in Watt (default 1500) :") or 1500)
    securitytoken=' ***** to be replaced by your API security token *****'  # paste in your own security token from entsoe.eu

def getPlanningInput():
    # read initial planning data from Domoticz variables and devices (instead of user input)
    global initialCharge,maxChargeCapacity,maxChargeSpeed,maxDischargeSpeed,startdate,enddate,starthour,securitytoken
    getPlanningInputSuccess=True

    startdate=todayString
    enddate=datetime.strftime(datetime.strptime(startdate,'%Y%m%d')+timedelta(days=1),'%Y%m%d')
    starthour=int(datetime.strftime(datetime.now(),'%H'))  # current hour. This assumes the program is called from domoticz at the start of the hour.

    responseResult,varValue=readBatteryChargeLevel()
    if responseResult: initialCharge=float(varValue)
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    responseResult,varValue=getUserVariable(maxBatteryCapacityIDX)
    if responseResult: maxChargeCapacity=float(varValue)
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    responseResult,varValue=getUserVariable(maxBatteryChargeSpeedIDX)
    if responseResult: maxChargeSpeed=float(varValue) 
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    responseResult,varValue=getUserVariable(maxBatteryDischargeSpeedIDX)
    if responseResult: maxDischargeSpeed=float(varValue) 
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    responseResult,securitytoken=getUserVariable(securityTokenIDX)
    getPlanningInputSuccess=getPlanningInputSuccess and responseResult

    if getPlanningInputSuccess==False:
        print("ERROR: getting all required planning data failed.")
    return getPlanningInputSuccess



# all communication with domoticz devices/database if with JSON calls (like domoticz itself is doing)
baseJSON="http://"+domoticzIP+":"+domoticzPort+"/json.htm?"   # the base string for any JSON call.

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
    # update the value of a text device and add an entry to the device log file
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
    # function to get the value of a user variable indicated by the varIDX number
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



def loadHTTPS(entsoeFileName,loadStartDate,loadEndDate):
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
    # create pricelists out of xmlfile 
    tree = ET.parse(xmlfile)
    root = tree.getroot()
    # create empty lists for prices
    HourPriceList=[]  # the actual list for hours available for optimsation
    displayList=[]    # the list for tracking and display of results
    sequenceNr=0
    for item in root.iter():
        if item.tag.find('price.amount')>0:
            price=float(item.text)
            if sequenceNr<=47: # never more than 2 days even if entsoe provides more than requested
                if debug: print("processing price ",item.text)
                datetimeString=datetime.strftime(runDate+timedelta(hours=sequenceNr),'%Y-%m-%d %H:%M:%S')
                if sequenceNr>=starthour or sequenceNr>23: # all prices after (and including) starthour on first day are put on list, plus next day, if any
# list element will consist of sequenceNr,price,datetime,usedcapacity,usetype(usetype=Unclassified,Charge,Discharge),changechargeqty,changeamount,percentageused
                    ListElement=[sequenceNr,price,datetimeString,initialCharge,"unclassified",0,0,0] 
                    HourPriceList.append(ListElement)
                    if debug: print("List with length ",len(HourPriceList)," ",HourPriceList)
                else:
                    ListElement=[sequenceNr,price,datetimeString,0,"unclassified",0,0,0] 
                displayList.append(ListElement)
            sequenceNr+=1
    return HourPriceList,displayList,sequenceNr


def rebuildHourPriceList(displayList):
    # rebuild the HourPriceList using results from previous cycles as tracked in displayList 
    HourPriceList=[]
    if debug: print("rebuilding HourPriceList")
    for i in displayList:
        if i[0]>=starthour or i[0]>23: # all prices after (and including) starthour on first day are put on list
            if i[4]=="unclassified" or abs(i[7])<100: #  not fully used
                if debug: print("Appending hour ",i)
                HourPriceList.append(i)
    return HourPriceList


def priceField(element):
    return element[1]

def priceDiffminMaxField(element):
    return element[3],-1*element[1][0],-1*element[2][0]

def createPairList(HourPriceList):
    # create list of min/max and max/min hour pairs, sorted on pricediff between the two elements
    PairList=[]
    HourPriceList.sort(key=priceField)
    pairNr=0
    chargeDone=0
    pairAvailable=True
    for Element1 in HourPriceList:
        for Element2 in reversed(HourPriceList):
            if Element1[0]<Element2[0] : # Element1 needs to be earlier than Element2, check sequenceNr
                priceDifferential=(Element2[1]-Element1[1])
                if priceDifferential>0:  # contribution of paired action needs to be positive
                    # charge/discharge=min/max pair
                    Pair=[pairNr,Element1,Element2,priceDifferential,pairAvailable,chargeDone,"minmax"]  # 7 fields per pair
                    PairList.append(Pair)
                else:
                    if priceDifferential<0:
                        Pair=[pairNr,Element1,Element2,-1*priceDifferential,pairAvailable,chargeDone,"maxmin"]
                        PairList.append(Pair)
                pairNr+=1
    PairList.sort(key=priceDiffminMaxField,reverse=True)  # sorted by priceDiff and then earliest min and earliest max (using sequence nr)
    for i in PairList: 
        if debug: print(i)
    return PairList

def checkMaxChargeCapacity(minSeqNr,maxSeqNr,displayList):
    # determine max capacity available for charging 
    maxCharge=maxChargeSpeed # anyway limited by battery specs
    for i in displayList:
        # check available capacity on all elements between min and max
        if i[0]==minSeqNr:
            if i[4]=="Discharge":  # never reverse previously planned action
                maxCharge=0 
            availableCapacity=maxChargeSpeed-abs(i[5])  # remaining availability between previous plan and maxSpeed
            if availableCapacity<maxCharge: 
                maxCharge=availableCapacity
        if i[0]>=minSeqNr and i[0]<maxSeqNr:
            availableCapacity=maxChargeCapacity-i[3]  # remaining availability between previously planned charge and max battery charge
            if availableCapacity<maxCharge: 
                maxCharge=availableCapacity
        if i[0]==maxSeqNr: # discharge point
            availableCapacity=i[3]+maxCharge   # never more than previously planned load plus current plan 
            if availableCapacity<maxCharge: 
                maxCharge=availableCapacity
            availableCapacity=maxDischargeSpeed-abs(i[5])  # remaining availability between previous plan and maxSpeed
            if availableCapacity<maxCharge: 
                maxCharge=availableCapacity
            if i[4]=="Charge":  # never reverse previously planned action
                maxCharge=0 
    if debug: print("max charging capacity ",maxCharge)
    return maxCharge

def checkMaxDischargeCapacity(maxSeqNr,minSeqNr,displayList):
    # determine max capacity available for discharge
    maxDischarge=maxDischargeSpeed  # anyway limited by battery specs
    for i in displayList:
        # check available capacity on all elements between max and min
        if i[0]==maxSeqNr:
            if i[4]=="Charge":  # never reverse previously planned action
                maxDischarge=0
            availableCapacity=maxDischargeSpeed-abs(i[5])  # remaining availability between previous plan and maxSpeed
            if availableCapacity<maxDischarge: 
                maxDischarge=availableCapacity
        if i[0]>=maxSeqNr and i[0]<minSeqNr:
            availableCapacity=i[3]   # never more than previously planned load
            if availableCapacity<maxDischarge: 
                maxDischarge=availableCapacity
        if i[0]==minSeqNr:
            availableCapacity=maxChargeCapacity-i[3]+maxDischarge  # remaining availability between previously planned charge and max battery charge
            if availableCapacity<maxDischarge: 
                maxDischarge=availableCapacity
            availableCapacity=maxChargeSpeed-abs(i[5])  # remaining availability between previous plan and maxSpeed
            if availableCapacity<maxDischarge: 
                maxDischarge=availableCapacity
            if i[4]=="Discharge":  # never reverse previously planned action
                maxDischarge=0 
    if debug: print("max discharging capacity ",maxDischarge)
    return maxDischarge


def processTopDownReturns(PairList,displayList,HourPriceList):
    pairUsed=False
    totalAmount=0
    pairNr=0
    endPairNr=len(PairList)
    while pairNr<endPairNr:
    #for pairNr in range(len(PairList)):
        minMax=PairList[pairNr]
        maxMin=PairList[pairNr]
        if minMax[4]==True: # pair still available
            if minMax[6]=='minmax':
                minSeqNr=minMax[1][0]
                maxSeqNr=minMax[2][0]
                if debug: print("Procssing pair with minSeqNr ", minSeqNr," maxSeqNr ",maxSeqNr)
                maxCharge=checkMaxChargeCapacity(minSeqNr,maxSeqNr,displayList)
                if maxCharge>0:
                    # this pair can be used, implement it
                    totalAmount,displayList,minUsePct,maxUsePct=updateDisplayList(displayList,minSeqNr,maxSeqNr,maxCharge)
                    # update this pair and pairs with same min and max as result of usage 
                    pairAvailable=False
                    for elementNr,element in enumerate(PairList):
                        if minUsePct==100:
                            if element[1][0]==minSeqNr or element[2][0]==minSeqNr:
                                PairList[elementNr][4]=pairAvailable
                        if maxUsePct==100:
                            if element[1][0]==maxSeqNr or element[2][0]==maxSeqNr:
                                PairList[elementNr][4]=pairAvailable
                        if element[1][0]==minSeqNr and element[2][0]==maxSeqNr: 
                            PairList[elementNr][5]=PairList[elementNr][5]+maxCharge
                    pairUsed=True
            else:
                maxSeqNr=maxMin[1][0]
                minSeqNr=maxMin[2][0]
                if debug: print("Processing pair with maxSeqNr ", maxSeqNr," minSeqNr ",minSeqNr)
                maxDischarge=checkMaxDischargeCapacity(maxSeqNr,minSeqNr,displayList)
                if maxDischarge>0:
                    # this pair can be used, implement it
                    totalAmount,displayList,minUsePct,maxUsePct=updateDisplayList(displayList,maxSeqNr,minSeqNr,-1*maxDischarge)
                    # update this pair and pairs with same min and max as result of usage 
                    pairAvailable=False
                    for elementNr,element in enumerate(PairList):
                        if minUsePct==100:
                            if element[1][0]==minSeqNr or element[2][0]==minSeqNr:
                                PairList[elementNr][4]=pairAvailable
                        if maxUsePct==100:
                            if element[1][0]==maxSeqNr or element[2][0]==maxSeqNr:
                                PairList[elementNr][4]=pairAvailable
                        if element[1][0]==minSeqNr and element[2][0]==maxSeqNr: 
                            PairList[elementNr][5]=PairList[elementNr][5]+maxDischarge
                    pairUsed=True
        if pairUsed:
            pairNr=1  # start from top, check if previous unusable pairs can now be implemented
            pairUsed=False
        else:
            pairNr+=1
    return displayList,HourPriceList,totalAmount


def priceSeqNrField(element):
    return element[1],-1*element[0]
def sellFirst(displayList,HourPriceList):
    # sell available charge for top prices before checking pairs
    if debug: print(HourPriceList)
    minSeqNr=HourPriceList[len(HourPriceList)-1][0]+1 # for checking max charge on full list beyond maxSeqNr
    HourPriceList.sort(key=priceSeqNrField,reverse=True)
    for MaxHour in HourPriceList:
        maxSeqNr=MaxHour[0]
        maxDischarge=checkMaxDischargeCapacity(maxSeqNr,minSeqNr,displayList)
        if maxDischarge>0:
            totalAmount,displayList,minUsePct,maxUsePct=updateDisplayList(displayList,maxSeqNr,None,-1*maxDischarge)
    return displayList,HourPriceList,totalAmount

def updateDisplayList(displayList,SeqNr1,SeqNr2,extraCharge):
    # SeqNr2 can be empty, SeqNr1 position cannot
    if outputMode or debug : print("update displaylist between sequence numbers :",SeqNr1," and  ",SeqNr2," with charge ",extraCharge)
    minUsePct=0
    maxUsePct=0
    if extraCharge>0: # minMax
        minSeqNr=SeqNr1
        maxSeqNr=SeqNr2
        for i in range(len(displayList)):  
            if displayList[i][0]==minSeqNr:
                displayList[i][4]="Charge"
                displayList[i][3]=displayList[i][3]+extraCharge
                displayList[i][5]=displayList[i][5]+extraCharge
                displayList[i][6]=displayList[i][6]-1*displayList[i][1]/1000*extraCharge/1000
                displayList[i][7]=abs(displayList[i][5]/maxChargeSpeed*100)
                minUsePct=displayList[i][7]
            if displayList[i][0]>minSeqNr and displayList[i][0]<maxSeqNr:
                displayList[i][3]=displayList[i][3]+extraCharge
            if displayList[i][0]==maxSeqNr:
                displayList[i][4]="Discharge"
                displayList[i][5]=displayList[i][5]-extraCharge
                displayList[i][6]=displayList[i][6]+displayList[i][1]/1000*extraCharge/1000    
                displayList[i][7]=abs(-1*displayList[i][5]/maxDischargeSpeed*100)
                maxUsePct=displayList[i][7]
    else: # maxMin
        if SeqNr2==None:
            minSeqNr=len(displayList) # is beyond end of list so no new charge (in case of sale only)
        else:
            minSeqNr=SeqNr2
        maxSeqNr=SeqNr1
        for i in range(len(displayList)):  
            if displayList[i][0]==maxSeqNr:
                displayList[i][4]="Discharge"
                displayList[i][3]=displayList[i][3]+extraCharge
                displayList[i][5]=displayList[i][5]+extraCharge
                displayList[i][6]=displayList[i][6]-1*displayList[i][1]/1000*extraCharge/1000
                displayList[i][7]=abs(-1*displayList[i][5]/maxDischargeSpeed*100)
                maxUsePct=displayList[i][7]
            if displayList[i][0]>maxSeqNr and displayList[i][0]<minSeqNr:
                displayList[i][3]=displayList[i][3]+extraCharge
            if displayList[i][0]==minSeqNr:
                displayList[i][4]="Charge"
                displayList[i][5]=displayList[i][5]-extraCharge
                displayList[i][6]=displayList[i][6]+displayList[i][1]/1000*extraCharge/1000    
                displayList[i][7]=abs(displayList[i][5]/maxChargeSpeed*100)
                minUsePct=displayList[i][7]
    totalAmount=showList(displayList)
    if debug: input("Enter return to continue") 
    return totalAmount,displayList,minUsePct,maxUsePct

def showList(displayList):
    totalAmount=0
    if outputMode or debug: print("-seqNr----date-------time-----------price----usetype----------change---%speed------total--------amount")
    for i in displayList:
        if outputMode or debug: print("    "+"{:>2d}".format(i[0])+"    "+i[2]+"    "+"{:>+4.5f}".format(i[1]/1000)+"    "+"{:12}".format(i[4])+"    "+"{:>7.0f}".format(i[5])+"    "+"{:>+4.0f}".format(i[7])+"%    "+"{:>+7.0f}".format(i[3])+"      "+"{:>+5.5f}".format(i[6]))
        totalAmount=totalAmount+i[6]
    if outputMode or debug: print("------------------------------------------------------------------------------------------------------")
    if outputMode or debug: print("--------------------------------------------------------------------------------total-amount: %+5.5f" %(totalAmount))
    return totalAmount

def outputToFile(displayList,starthour,endhour,outputFileName,writeMode):
    fileHandle = open(outputFileName, writeMode)
    for i in displayList:
        if i[0]>=starthour and i[0]<=endhour:
            print("    "+"{:>2d}".format(i[0])+"    "+i[2]+"    "+"{:>+4.5f}".format(i[1]/1000)+"    "+"{:12}".format(i[4])+"    "+"{:>7.0f}".format(i[5])+"    "+"{:>+4.0f}".format(i[7])+"%    "+"{:>+7.0f}".format(i[3])+"      "+"{:>+5.5f}".format(i[6]), file=fileHandle)
    fileHandle.close()

def outputToDevice(displayList,starthour,endhour,writeMode):
    if writeMode=='w': 
        clearTextDevice(planningDisplayIDX)
    for i in reversed(displayList):
        if i[0]>=starthour and i[0]<=endhour:
            outputString="%2d  %s  %+4.5f  %12s  %+7.0f  %+4.0f   %+7.0f   %+5.5f" %(i[0],i[2],(i[1]/1000),i[4],i[5],i[7],i[3],i[6])
            outputString=outputString.replace(' ','_')  # JSON processing removes all duplicate spaces, so use underscore to get table format
            setTextDevice(planningDisplayIDX,outputString)
    timestamp=datetime.strftime(datetime.now(),'%Y%m%d %H:%M:%S"')
    setTextDevice(planningDisplayIDX,"**__date_______time_________price________action___change__%speed___total_____amount______ ******")
    setTextDevice(planningDisplayIDX,"****** planning created "+timestamp+" for period "+startdate+" "+str(starthour)+" hr to "+enddate+" 24:00 hr ******")

def processCLarguments():
    global debug,outputMode,runMode
    commandLineArg1=None
    commandLineArg2=None
    debug=False
    outputMode=False
    runMode="standalone"
    CLargSuccess=True
    try:
        if len(sys.argv)>1:
            commandLineArg1=sys.argv[1]
            if commandLineArg1 not in ["-t","-v","-q","-d","-s"]:
                raise Exception
            if commandLineArg1=="-t": 
                debug=True
                outputMode=True
            if commandLineArg1=="-v": 
                debug=False
                outputMode=True
            if commandLineArg1=="-q": 
                debug=False
                outputMode=False
            if commandLineArg1=="-d":
                runMode="domoticz"
            if commandLineArg1=="-s":
                runMode="standalone"
            if len(sys.argv)>2:
                commandLineArg2=sys.argv[2]
                if commandLineArg2 not in ["-t","-v","-q","-d","-s"]:
                    raise Exception
                if commandLineArg2=="-t": 
                    debug=True
                    outputMode=True
                if commandLineArg2=="-v": 
                    debug=False
                    outputMode=True
                if commandLineArg1=="-q": 
                    debug=False
                    outputMode=False
                if commandLineArg2=="-d":
                    runMode="domoticz"
                if commandLineArg2=="-s":
                    runMode="standalone"
                if len(sys.argv)>3:
                    raise Exception
    except:
        print("Only 0, 1 or 2 command line arguments are allowed.")
        print("Following command line arguments are recognised: -t,-v or -q and -d or -s")
        print("-t = full tracing, debug mode")
        print("-v = verbose mode, intermediate steps in planning are shown")
        print("-q = quiet mode (default), no intermediate feedback provided.")
        print(" ")
        print("-d = domoticz integration mode")
        print("-s = standalone mode, no domoticz integration (default)")
        CLargSuccess=False
    return CLargSuccess

def main():
    global startdate,enddate,initialCharge,starthour

    if not processCLarguments():
        quit()

    if runMode=="domoticz":
    # get all input
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


    # if startdate==enddate then optimise from starthour till end-of-day
    # else
    # first optimise from startdate,starthour till startdate+1, end-of-day
    # then optimise from next day, 15:00 till nextday+1, end-of-day
    # and in that case the initial charge is the previously planned charge at 15:00
    

    runDate=startDateObject

    while runDate<endDateObject or runDate==startDateObject:
 
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
                if not loadHTTPS(entsoeFileName,loadStartDate,loadEndDate):
                    print("ERROR: Something wrong with getting price data")
                    quit()
        else:
            if loadFile[0]!="Y" and loadFile[0]!="y":
                if outputMode or debug: print("rundate ",datetime.strftime(runDate,'%Y%m%d'))
                loadStartDate=datetime.strftime(runDate,'%Y%m%d')
                loadEndDate=datetime.strftime(runDate+timedelta(days=1),'%Y%m%d')
                if not loadHTTPS(entsoeFileName,loadStartDate,loadEndDate):
                    print("ERROR: Something wrong with getting price data")
                    quit()

        HourPriceList,displayList,maxSeqNr=parseXMLintoPriceLists(entsoeFileName,runDate)
        if initialCharge>0:
            displayList,HourPriceList,totalAmount=sellFirst(displayList,HourPriceList)
            HourPriceList=rebuildHourPriceList(displayList)

        PairList=createPairList(HourPriceList)
        displayList,HourPriceList,totalAmount=processTopDownReturns(PairList,displayList,HourPriceList)

        if startdate==enddate:
            startOutputHour=starthour
            endOutputHour=23
        else:
            startOutputHour=starthour
            endOutputHour=38

        if runMode=="standalone":
            outputToFile(displayList,startOutputHour,endOutputHour,outputFileName,writeMode)

        if maxSeqNr<38:
            initialCharge=0
        else:
            initialCharge=displayList[38][3]
        starthour=15
        writeMode='a'
        runDate=runDate+timedelta(days=1)

        if outputMode or debug: print("next runDate ",datetime.strftime(runDate,'%Y%m%d')," with initialCharge ",initialCharge," at 15:00")

        if debug: input("Enter to continue ... *****************************************************************************************************************************************************************************************************")
    # last day optimsation is already included in previous day run, just need to output remainder of the day after 15:00
    if startdate!=enddate:
        if runMode=="domoticz":
            outputToDevice(displayList,startOutputHour,47,'w')
            # print output for next hour in JSON format so this can be picked up in domoticz dzvents script
            print("{\n \"date\" : \"",displayList[startOutputHour][2][0:10],"\",","\n","\"hour\" : \"",displayList[startOutputHour][2][11:13],"\",\n","\"action\" : \"",displayList[startOutputHour][4],"\",","\n","\"change\" :",displayList[startOutputHour][5],",\n","\"total\" :",displayList[startOutputHour][3],"\n}",sep="")
        else:
            outputToFile(displayList,39,47,outputFileName,writeMode)
            print("planning completed")


if __name__ == '__main__':
    main()


