# simple interface to manage system parameters, add/remove events in the database, manage MainSystem through REST cmd
# event info can be written directly or read from a json file

import dbManager.dbManager as dbManager
import json
import datetime
import traceback
import secrets
import string
import time as t

remoteDBparams = {"dbname": "dbuwxucc", "user": "dbuwxucc", "password":"VNx-4S_lIaB4ZZ1NPhX3BpZW5MQDgA9C",
                   "host": "kandula.db.elephantsql.com", "port": "5432"}


# function to generate list of secure string psw
def random_secure_string(nPsw, strLength):
    secureStrList = []
    for _ in range(nPsw):
        secureStrList.append(''.join((secrets.choice(string.ascii_lowercase + string.ascii_uppercase + string.digits + string.punctuation)
                             for _ in range(strLength))))
    return secureStrList

class SystemManagerInterface:
    DEBUGtime = True
    expectedEventKeys = ["nTickets", "price", "info"]
    expectedEventInfoKeys = {"languages": ["IT", "EN", "PL"], "info": ["name", "info"]}
    timeInputDBformat = "%H:%M"  # hh:mm 0-padded
    # eventFile: json format file, {"event"}
    # commands:
    # printEvents DD/MM/YYYY [LIST OF LANGUAGES] # print events data of specified date, info is printed in given languages
    # addEvent date startTIme endTime -f FileName # event info is taken from file FileName
    # addEvent date startTIme endTime -m # event info will be inserted manually
    # -exit to exit the script

    def __init__(self, configFile=None):
        global remoteDBparams
        # connect to database
        self.DBconn = dbManager.connectDb(remoteDBparams)  # DB connection, to be given as arg to each DB API call
        # TO-DO: get configuration from file
        # with open(configFile, "r") as config:
        #     pass
        self.stop = False
        pass

    def cmdConsole(self):
        print("type '-help' for a list commands")
        while not self.stop:
            queryString = input()
            if queryString == "-help":
                self.printCmd()
            elif queryString.startswith("-addEvent"):
                cmdArgs = queryString.split()  # separate input string by spaces
                self.addEvent(cmdArgs)
            elif queryString.startswith("-printEvents"):
                cmdArgs = queryString.split()
                self.printEvents(cmdArgs)
            elif queryString.startswith("-deleteEvent"):
                cmdArgs = queryString.split()
                self.deleteEvent(cmdArgs)
            elif queryString == "-deleteALL":
                self.deleteAllEvents()
            elif queryString.startswith("-deleteDate"):
                cmdArgs = queryString.split()
                self.deleteAllEventsFromDate(cmdArgs)
            elif queryString == "-exit":
                print("Exiting application")
                self.stop = True
                dbManager.disconnectDb(self.DBconn)
            else:
                print("invalid command string, type '-help' for a list commands")

    def printCmd(self):
        print("Command strings\n"
              "Add event with info taken from JSON file: -addEvent date startTIme endTime -f FileName\n"
              "Add event with info inserted manually: -addEvent date startTIme endTime -m\n"
              "Print all events scheduled for specified date displaying info in all languages: -printEvents date\n"
              "Print all events scheduled for specified date displaying info in one language: -printEvents date language\n"
              "Print all events scheduled for specified date displaying no info: -printEvents date nodesc\n"
              "Delet an event using its id: -deleteEvent eventID\n"
              "Delete all events scheduled for the specified date: -deleteDate date\n"
              "Delete all events in the database: -deleteALL\n"
              "Exit the program: -exit")

    def printEvents(self, cmdArgs):
        # format
        global remoteDBparams
        try:
            dateStr = cmdArgs[1]
            if len(cmdArgs) == 3:
                language = cmdArgs[2]
                if language not in self.expectedEventInfoKeys["languages"] and language != "nodesc":
                    print("Error: unrecognized language, acceptable languages are ", self.expectedEventInfoKeys["languages"]
                          , "alternatevely put 'nodesc' to show no event info")
                    return
            else:
                language = "all"
        except:
            print("Error: input string does not have enough arguments, follow this command format to print events:\n"
                  "[ -printEvents date ]")
            return
        eventDate = self.getDate(dateStr)  # returns date object
        if eventDate is None:  # dateStr had incorrect format
            return
        if self.DEBUGtime:
            start = t.time()
        eventList = dbManager.dailySchedule(eventDate, passFlag=False, conn=self.DBconn)
        if self.DEBUGtime:
            end = t.time()
            print('DEBUG: dailySchedule() request duration:', end-start)
        if not eventList:
            # dictionary is empty
            print("no scheduled event found for this date")
        else:
            sortedEvents = sorted(list(eventList.items()),
                                  key=lambda x: int(x[1]["startTime"].split(':')[0]))  # sort ascending by start hour
            outputList = []
            print("Printing events scheduled for ", eventDate)
            for event in sortedEvents:
                eventID = event[0]
                dataDict = event[1]
                infoStr = ""
                if language == "all":
                    # name and desc of all languages
                    for lan in self.expectedEventInfoKeys["languages"]:
                        info = dataDict[lan]
                        infoStr += f'\n{lan}: event name: {info["name"]}, event description: {info["info"]}'
                elif language != "nodesc":
                    info = dataDict[language]
                    infoStr = f'event name: {info["name"]}, event description: {info["info"]}'
                else:
                    infoStr = f'event name: {dataDict["EN"]["name"]}'
                print(f'EventID: {eventID}, start: {dataDict["startTime"]}, end: {dataDict["endTime"]}, '
                      f'tickets left:{dataDict["ticketLeft"]}/{dataDict["ticketNum"]}, cost: {dataDict["cost"]}', infoStr)



    # cmdArgs is a list of arguments for the command
    # date startTIme endTime -f FileName # event info is taken from file FileName
    # date startTIme endTime -m # event info will be inserted manually
    # data format of eventInfo in the file:
    # {"nTickets: n", ""}
    def addEvent(self, cmdArgs):
        global remoteDBparams
        try:
            dateStr = cmdArgs[1]
            startTimeStr = cmdArgs[2]
            endTimeStr = cmdArgs[3]
            infoType = cmdArgs[4]
        except:
            print("Error: input string does not have enough arguments, follow this command format to add events:\n"
                  "[ addEvent date startTIme endTime -f FileName ] OR [ addEvent date startTIme endTime -m ]")
            return
        # date format
        eventDate = self.getDate(dateStr)  # returns date object
        if eventDate is None:  # dateStr had incorrect format
            return
        # time
        startTime, endTime = self.getEventTime(startTimeStr, endTimeStr)  # returns 2 datetime objects
        if startTime is None or endTime is None:
            return

        if infoType == "-f":
            # load info from file
            try:
                fileName = cmdArgs[5]
            except:
                print("Error: file name is missing, specify file name after -f")
                return
            try:
                fp = open(fileName)
            except:
                print("Error: could not open the file")
                return
            try:
                jsonDict = json.load(fp)
            except:
                print("Error: file is not in correct JSON format")
                return
            # check outer level keys
            for expectedKey in self.expectedEventKeys:
                if not(expectedKey in jsonDict):
                    print(f"Error: {expectedKey} not present in the json file")
                    return
                if expectedKey == "cost":  # check if numerical keys are correct
                    if expectedKey == "cost" and (jsonDict[expectedKey] is not int or jsonDict[expectedKey] is not float):
                        print(f'Error: value of "{expectedKey}" should be an integer or a float')
                if expectedKey == "nTickets" and type(jsonDict[expectedKey]) is not int:
                    print(f'Error: value of "{expectedKey}" should be an integer')
            # check keys inside "info"
            # check if there is an entry for each language
            for expectedLanguage in self.expectedEventInfoKeys["languages"]:
                if not(expectedLanguage in jsonDict["info"]):
                    print(f"Error: no info for language {expectedLanguage}")
                    return
                # check if all "info" fields are correct
                for expectedInfoKey in self.expectedEventInfoKeys["info"]:
                    if not(expectedInfoKey in jsonDict["info"][expectedLanguage]):
                        print(f"Error: key {expectedInfoKey} is missing for language {expectedLanguage}")
                        return
            # check if the there is the URL list
            if "URLs" not in jsonDict["info"]:
                print(f'Error: key "URLs" is missing in the dictionary of the "info" value field')
                return
            # if all format checks are passed, store the dictionary in eventInfoDict
            eventInfoDict = jsonDict

        elif infoType == "-m":
            # TO-DO: query user the event info
            # output of the operation should be eventInfoDict={"nTickets":, "price":, "info": {"IT": {"name":,"desc":},
            # "EN": {"name":,"desc":,""},"PL":{"name": "","desc":}}}
            eventInfoDict = {}
            pass

        else:
            print("Error: incorrect input string, follow this command format to add events:\n"
                  "[ addEvent date startTIme endTime -f FileName ] OR [ addEvent date startTIme endTime -m ]")
            return

        # ACCESS DATABASE THROUGH APIs
        # create DB entry for event
        if self.DEBUGtime:
            start = t.time()
            totstart = t.time()
        eventID = dbManager.add(eventDate, startTime=startTime.strftime(self.timeInputDBformat),
                                endTime=endTime.strftime(self.timeInputDBformat), cost=eventInfoDict["price"],
                                ticketNum=eventInfoDict["nTickets"], conn=self.DBconn)
        if self.DEBUGtime:
            end = t.time()
            print('DEBUG: add() request duration:', end-start)

        if eventID == -1:
            print("Error: could not add event to database")
            return
        # generate and insert password table
        passwordList = self.generatePswTable(eventInfoDict["nTickets"])
        if self.DEBUGtime:
            start = t.time()
        dbManager.passwordFill(eventID, passwordList, conn=self.DBconn)
        if self.DEBUGtime:
            end = t.time()
            print('DEBUG: passwordFill() request duration:', end-start)
        # insert event description and img URLs
        # eventDict = eventInfoDict["info"]
        eventDict = eventInfoDict["info"]
        # eventDict must have format {"EN":{"name":, "info":}, "URLs":[]}
        if self.DEBUGtime:
            start = t.time()
        dbManager.infoFill(eventID, eventInfo=eventDict, conn=self.DBconn)

        if self.DEBUGtime:
            end = t.time()
            print('DEBUG: infoFill() request duration:', end-start)
            print('DEBUG: total API access duration:', end-totstart)
        print(f"Event successfully inserted in database with eventID = {eventID}")

    def deleteEvent(self, cmdArgs):
        try:
            eventID = cmdArgs[1]
        except:
            print("Error: input string does not have enough arguments, follow this command format to delete events:\n"
                  "[ deleteEvent eventID ]")
            return
        # ACCESS DB THROUGH API
        try:
            if self.DEBUGtime:
                start = t.time()
            dbManager.delete(eventID, conn=self.DBconn)
            if self.DEBUGtime:
                end = t.time()
                print('DEBUG: delete() request duration:', end - start)
        except:
            print("Error accessing the DB")
            traceback.print_exc()

    def getDate(self, dateStr):
        dateList = dateStr.split('-')
        try:
            return datetime.date(int(dateList[2]), int(dateList[1]), int(dateList[0]))
        except:
            print("Error: incorrect date format, use DD-MM-YYYY")
            return None

    def generatePswTable(self, nTickes):
        # TEMPORAY SOLUTION
        pswList = []
        for i in range(0, nTickes):
            pswList.append(str(i))
        return pswList

    def getEventTime(self, startTimeStr, endTimeStr):
        # expected format hh:mm or hh:mm:ss (but only hh:mm is considered)
        # return None,None if there are errors
        try:
            startT_list = startTimeStr.split(':')
            endT_list = endTimeStr.split(':')
        except:
            print("Error: time format, start and end time should have format hh:mm or hh:mm:ss")
            return None, None
        try:
            startH = int(startT_list[0])
            endH = int(endT_list[0])
            startM = int(startT_list[1])
            endM = int(endT_list[1])
        except:
            print("Error: specified hours for end and start time are not valid numbers")
            return None, None
        currTime = datetime.datetime.now()
        try:
            eventStart = currTime.replace(hour=startH, minute=startM)
            eventEnd = currTime.replace(hour=endH, minute=endM)
        except ValueError:
            print("Error: specified hours for end and start time are out of bounds")
            return
        except:
            print("Error: unexpected exception when creating datetime object for start and end time of the event")
            return
        if eventStart >= eventEnd:
            print("Error: specified event starting time is equal or after the specified ending time")
        return eventStart, eventEnd  # a couple of datetime objects

    def deleteAllEvents(self):
        global remoteDBparams
        print("WARNING: you will delete all scheduled events and their information contained the database\n")
        answer = input("THIS ACTION CANNOT BE UNDONE, delete all events? (y/n)")
        stop = False
        while not stop:
            if answer == "y":
                # RIP events
                print("deleting events...")
                if self.DEBUGtime:
                    start = t.time()
                dbManager.deleteAll(conn=self.DBconn)
                if self.DEBUGtime:
                    end = t.time()
                    print('DEBUG: deleteAll() request duration:', end - start)

                print("all events have successfully erased from the database")
                stop = True
            elif answer == "n":
                stop = True
            else:
                print("invalid string, type 'y' to delete events 'n' to go back")
            answer = input()

    def deleteAllEventsFromDate(self, cmdArgs):
        global remoteDBparams
        try:
            dateStr = cmdArgs[1]
        except:
            print("Error: input string does not have enough arguments, follow this command format:\n"
                  "[ -deleteDate date ]")
            return
        # date format
        eventDate = self.getDate(dateStr)  # returns date object
        if eventDate is None:  # dateStr had incorrect format
            return
        print(f"WARNING: you will delete all scheduled events for date: {eventDate}\n")
        answer = input("THIS ACTION CANNOT BE UNDONE, delete all events? (y/n)")
        stop = False
        while not stop:
            if answer == "y":
                # RIP events
                print("deleting events...")
                if self.DEBUGtime:
                    start = t.time()
                dbManager.deleteDate(eventDate, conn=self.DBconn)
                if self.DEBUGtime:
                    end = t.time()
                    print('DEBUG: deleteDate() request duration:', end - start)
                print(f"all events scheduled date: {eventDate} have successfully erased from the database")
                stop = True
            elif answer == "n":
                stop = True
            else:
                print("invalid string, type 'y' to delete events 'n' to go back")
            answer = input()


if __name__ == "__main__":
    UI = SystemManagerInterface()
    UI.DEBUGtime = True  # enable debug messages for execution time of DB APIs
    UI.cmdConsole()
    # -addEvent 12-10-2020 9:30 10:00 -f eventInfo.json (eventID=0)-9 tickets have been booked
    # -addEvent 12-10-2020 11:15 13:30 -f eventInfo.json (eventID=1)
    # -printEvents 12-10-2020 # 11 events (id 0 to 10), time 1.9-2 s
    # -printEvents 13-10-2020 # 3 events (id 11 to 13),
    # -printEvents 14-10-2020 # 7 events (id 14 to 21)



    # DEBUG
    # add some events
    #
    # dateList = [13,10,2020]
    # debugConn = dbManager.connectDb(remoteDBparams)
    # # # # #
    # start = t.time()
    # datenow = datetime.datetime.now().date()
    # dbManager.deleteDate(datenow, debugConn)
    # # # # testD = datetime.date(int(dateList[2]), int(dateList[1]), int(dateList[0]))
    # # # # testDstr = '12-10-2020'
    # # # # for i in range(1,24,2):
    # # # #     startT = str(i)+':00'
    # # # #     endT = str(i+1)+':00'
    # # # #     cmdStr = f'-addEvent {testDstr} {startT} {endT} -f eventInfo.json'
    # # # #     UI.addEvent(cmdStr.split())
    # # # # # # # # utput= dbManager.dailySchedule(testD, passFlag=False, conn=debugConn), 3.5-3.7 s with passFlag = False, 2-2.5 with passFlag = True
    # # # # output = dbManager.ticketRetrieve(0, "testmail1@test.test", conn=debugConn)
    # end = t.time()
    # print("elapsed time:", end-start)
    # # print(output)
    # # # # print(pswTable)