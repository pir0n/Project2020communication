# simple interface to manage system parameters, add/remove events in the database, manage MainSystem through REST cmd
# event info can be written directly or read from a json file

import dbManager.dbManager as dbManager
import json
import datetime
import traceback

remoteDBparams = {"dbname": "dbuwxucc", "user": "dbuwxucc", "password":"VNx-4S_lIaB4ZZ1NPhX3BpZW5MQDgA9C",
                   "host": "kandula.db.elephantsql.com", "port": "5432"}


class SystemManagerInterface:
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
                self.delateAllEventsFromDate(cmdArgs)
            elif queryString == "-exit":
                print("Exiting application")
                self.stop = True
            else:
                print("invalid command string, type '-help' for a list commands")

    def printCmd(self):
        print("Command strings\n"
              "Add event with info taken from JSON file: -addEvent date startTIme endTime -f FileName\n"
              "Add event with info inserted manually: -addEvent date startTIme endTime -m\n"
              "Print all events scheduled for specified date: -printEvents date\n"
              "Delet an event using its id: -deleteEvent eventID\n"
              "Delete all events scheduled for the specified date: -deleteDate date\n"
              "Delete all events in the database: -deleteALL\n"
              "Exit the program: -exit")

    def printEvents(self, cmdArgs):
        global remoteDBparams
        try:
            dateStr = cmdArgs[1]
        except:
            print("Error: input string does not have enough arguments, follow this command format to print events:\n"
                  "[ -printEvents date ]")
            return
        eventDate = self.getDate(dateStr)  # returns date object
        if eventDate is None:  # dateStr had incorrect format
            return
        eventList = dbManager.dailySchedule(eventDate, passFlag=False, remoteDBparams=remoteDBparams)
        print(eventList)

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
        eventID = dbManager.add(eventDate, startTime=startTime.strftime(self.timeInputDBformat),
                                endTime=endTime.strftime(self.timeInputDBformat), cost=eventInfoDict["price"],
                                ticketNum=eventInfoDict["nTickets"], remoteDBparams=remoteDBparams)
        if eventID == -1:
            print("Error: could not add event to database")
            return
        # generate and insert password table
        passwordList = self.generatePswTable(eventInfoDict["nTickets"])
        dbManager.passwordFill(eventID, passwordList, remoteDBparams=remoteDBparams)
        # insert event description and img URLs
        # eventDict = eventInfoDict["info"]
        eventDict = eventInfoDict["info"]
        # eventDict must have format {"EN":{"name":, "info":}, "URLs":[]}
        dbManager.infoFill(eventID, eventInfo=eventDict, remoteDBparams=remoteDBparams)
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
            dbManager.delete(eventID, remoteDBparams)
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
                dbManager.deleteAll(remoteDBparams)
                print("all events have successfully erased from the database")
                stop = True
            elif answer == "n":
                stop = True
            else:
                print("invalid string, type 'y' to delete events 'n' to go back")
            answer = input()

    def delateAllEventsFromDate(self, cmdArgs):
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
                dbManager.deleteDate(eventDate, remoteDBparams)
                print(f"all events scheduled date: {eventDate} have successfully erased from the database")
                stop = True
            elif answer == "n":
                stop = True
            else:
                print("invalid string, type 'y' to delete events 'n' to go back")
            answer = input()


if __name__ == "__main__":
    # UI = SystemManagerInterface()
    # UI.cmdConsole()
    # -addEvent 12-10-2020 9:30 10:00 -f eventInfo.json (eventID=0)-9 tickets have been booked
    # -addEvent 12-10-2020 11:15 13:30 -f eventInfo.json (eventID=1)

    # DEBUG print
    dateList = [12,10,2020]
    testD = datetime.date(int(dateList[2]), int(dateList[1]), int(dateList[0]))
    pswTable = dbManager.dailySchedule(testD, passFlag=True, remoteDBparams = remoteDBparams)
    print(pswTable)