from operator import itemgetter, attrgetter
from datetime import date,datetime,timedelta
import xml.etree.ElementTree as ET
import requests
import copy

debug=False  # determines whether to print in-between results for debugging/tracing

today=date.today()
todayString=datetime.strftime(today,'%Y%m%d')


def getUserInput():
    # get user input, with limited (!!) input validation
    global initialCharge,maxChargeCapacity,maxChargeSpeed,maxDischargeSpeed,startdate,enddate,starthour,securitytoken
    startdate=input("Enter startdate as YYYYMMDD (default=today)   : ") or todayString
    enddate=input("Enter enddate as YYYYMMDD (default=startdate+1) : ") or datetime.strftime(datetime.strptime(startdate,'%Y%m%d')+timedelta(days=1),'%Y%m%d')
    starthour=int(input("Enter start hour as HH (default next hour)   : ") or datetime.strftime(datetime.now()+timedelta(hours=1),'%H'))
    initialCharge=int(input("Enter initial charge in Wh (default=0) :") or "0" )
    maxChargeCapacity=int(input("Enter max capacity in Wh (default 5000) :") or 5000)
    maxChargeSpeed=int(input("Enter max charge speed in Watt (default 2000) :") or 2000)
    maxDischargeSpeed=int(input("Enter max discharge speed in Watt (default 1500) :") or 1500)
    securitytoken='xxxxx-replace-this-with-your-api-token-xxxxx'  # paste in your own security token from entsoe.eu


def loadHTTPS(entsoeFileName,loadStartDate,loadEndDate):
    # url components for https feed from ENTSOE.EU
    urlwebsite='https://web-api.tp.entsoe.eu/api?'
    urltoken='securityToken='+securitytoken
    urldoctype='&documentType=A44'
    urldomain='&in_Domain=10YNL----------L&out_Domain=10YNL----------L'
    urlperiod='&periodStart='+loadStartDate+'0000&periodEnd='+loadEndDate+'2300'
    url=urlwebsite+urltoken+urldoctype+urldomain+urlperiod
    # creating HTTP response object from given url
    print("Getting data from entsoe.eu for ",loadStartDate," to ",loadEndDate)
    print(url)
    response = requests.get(url)
    if response.status_code == 200:
        # saving the xml file
        with open(entsoeFileName, 'wb') as f:
            f.write(response.content)
    else:
        print("no proper price file received")


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
    print("update displaylist between sequence numbers :",SeqNr1," and  ",SeqNr2," with charge ",extraCharge)
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
    print("--seqNr----date-------time-----------price---total-at-end----usetype----------change-------amount----%speed")
    for i in displayList:
        print("    "+"{:>3d}".format(i[0])+"    "+i[2]+"    "+"{:>+4.5f}".format(i[1]/1000)+"         "+"{:>6d}".format(i[3])+"    "+"{:12}".format(i[4])+"    "+"{:>+7d}".format(i[5])+"     "+"{:>+5.5f}".format(i[6])+"      "+"{:>+4.0f}".format(i[7]))
        totalAmount=totalAmount+i[6]
    print("-----------------------------------------------------------------------------------------------------------")
    print("--------------------------------------------------------------------------total-amount:  %+5.5f  --------" %(totalAmount))
    return totalAmount

def outputToFile(displayList,starthour,endhour,outputFileName,writeMode):
    fileHandle = open(outputFileName, writeMode)
    for i in displayList:
        if i[0]>=starthour and i[0]<=endhour:
            print("    "+"{:>3d}".format(i[0])+"    "+i[2]+"    "+"{:>+4.5f}".format(i[1]/1000)+"         "+"{:>6d}".format(i[3])+"    "+"{:12}".format(i[4])+"    "+"{:>+7d}".format(i[5])+"     "+"{:>+5.5f}".format(i[6])+"      "+"{:>+4.0f}".format(i[7]), file=fileHandle)
    fileHandle.close()





def main():
    global startdate,enddate,initialCharge,starthour

    # get all input
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
    outputFileName="entsoe-output"+startdate+".txt"


    # if startdate==enddate then optimise from starthour till end-of-day
    # else
    # first optimise from startdate,starthour till startdate+1, end-of-day
    # then optimise from next day, 15:00 till nextday+1, end-of-day
    # and in that case the initial charge is the previously planned charge at 15:00
    

    runDate=startDateObject

    while runDate<endDateObject or runDate==startDateObject:
 
        print("Processing : ",runDate)

        fileNameDate=datetime.strftime(runDate,'%Y%m%d')
        entsoeFileName="entsoe"+fileNameDate+".xml"

        if startdate==enddate:
            if loadFile[0]!="Y" and loadFile[0]!="y":
                loadStartDate=datetime.strftime(runDate,'%Y%m%d')
                loadEndDate=loadStartDate
                loadHTTPS(entsoeFileName,loadStartDate,loadEndDate)
        else:
            if loadFile[0]!="Y" and loadFile[0]!="y":
                print("rundate ",datetime.strftime(runDate,'%Y%m%d'))
                loadStartDate=datetime.strftime(runDate,'%Y%m%d')
                loadEndDate=datetime.strftime(runDate+timedelta(days=1),'%Y%m%d')
                loadHTTPS(entsoeFileName,loadStartDate,loadEndDate)

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
        outputToFile(displayList,startOutputHour,endOutputHour,outputFileName,writeMode)

        if maxSeqNr<38:
            initialCharge=0
        else:
            initialCharge=displayList[38][3]
        starthour=15
        writeMode='a'
        runDate=runDate+timedelta(days=1)

        print("next runDate ",datetime.strftime(runDate,'%Y%m%d')," with initialCharge ",initialCharge," at 15:00")

        if debug: input("Enter to continue ... *****************************************************************************************************************************************************************************************************")
    # last day optimsation is already included in previous day run, just need to output remainder of the day after 15:00
    if startdate!=enddate:
        outputToFile(displayList,39,47,outputFileName,writeMode)



if __name__ == '__main__':
    main()

