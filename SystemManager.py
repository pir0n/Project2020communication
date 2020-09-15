# simple interface to manage system parameters, add/remove events in the database, manage MainSystem through REST cmd
# event info can be written directly or read from a json file

import dbManager.dbManager as dbManager
import json
import datetime

remoteDBparams = {"dbname": "dbuwxucc", "user": "dbuwxucc", "password":"VNx-4S_lIaB4ZZ1NPhX3BpZW5MQDgA9C",
                   "host": "kandula.db.elephantsql.com", "port": "5432"}

class SystemManagerInterface:
    expectedEventKeys = ["nTickets", "price", "info", "URLs"]
    expectedEventInfoKeys = {"languages": ["IT", "EN", "PL"], "info": ["name", "desc"]}

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
            elif queryString.startswith("addEvent"):
                cmdArgs = queryString.split()  # separate input string by spaces
                self.addEvent(cmdArgs[1:len(cmdArgs)])
            elif queryString.startswith("printEvents"):
                cmdArgs = queryString.split()
                self.printEvents(cmdArgs[1:len(cmdArgs)])
            elif queryString == "-exit":
                print("Exiting application")
                self.stop = True
            else:
                print("invalid command string, type '-help' for a list commands")

    def printCmd(self):
        print("Command strings\n"
              "Adding events with info taken from JSON file: addEvent date startTIme endTime -f FileName\n"
              "Adding events with info inserted manually: addEvent date startTIme endTime -m\n"
              "Printing all events scheduled for specified date: printEvents date")

    def printEvents(self, cmdArgs):
        global remoteDBparams
        try:
            dateStr = cmdArgs[0]
        except:
            print("Error: input string does not have enough arguments, follow this command format to add events:\n"
                  "[ printEvents date ]")
            return
        eventDate = self.getDate(dateStr)  # returns date object
        if eventDate is None:  # dateStr had incorrect format
            return
        eventList = dbManager.dailySchedule(eventDate, remoteDBparams)
        print(eventList)

    # cmdArgs is a list of arguments for the command
    # date startTIme endTime -f FileName # event info is taken from file FileName
    # date startTIme endTime -m # event info will be inserted manually
    # data format of eventInfo in the file:
    # {"nTickets: n", ""}
    def addEvent(self, cmdArgs):
        global remoteDBparams
        try:
            dateStr = cmdArgs[0]
            startTimeStr = cmdArgs[1]
            endTimeStr = cmdArgs[2]
            infoType = cmdArgs[3]
        except:
            print("Error: input string does not have enough arguments, follow this command format to add events:\n"
                  "[ addEvent date startTIme endTime -f FileName ] OR [ addEvent date startTIme endTime -m ]")
            return
        # date format
        eventDate = self.getDate(dateStr)  # returns date object
        if eventDate is None:  # dateStr had incorrect format
            return
        # time
        startTime, endTime = self.getEventTime(startTimeStr, endTimeStr)
        if startTime is None or endTime is None:
            return

        if infoType == "-f":
            # load info from file
            try:
                fileName = cmdArgs[4]
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
                if expectedKey == "cost": # check if numerical keys are correct
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
        eventID = dbManager.add(eventDate, startTime=startTime, endTime=endTime, name=eventInfoDict["info"]["EN"]["name"],
                                cost=eventInfoDict["price"], ticketNum=eventInfoDict["nTickets"],
                                remoteDBparams=remoteDBparams)
        if eventID == -1:
            print("Error: could not add event to database")
            return
        # generate and insert password table
        passwordList = self.generatePswTable(eventInfoDict["nTickets"])
        dbManager.passwordFill(eventID, passwordList, remoteDBparams=remoteDBparams)
        # insert event description and img URLs
        # eventDict = eventInfoDict["info"]
        eventDict = {"EN": eventInfoDict["info"]["EN"]["desc"], "IT": eventInfoDict["info"]["IT"]["desc"],
                     "PL": eventInfoDict["info"]["PL"]["desc"]}
        eventDict["URLs"] = eventInfoDict["URLs"]
        dbManager.infoFill(eventID, eventDict, remoteDBparams=remoteDBparams)
        print(f"Event successfully inserted in database with eventID = {eventID}")

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
            startT = int(startT_list[0])
            endT = int(endT_list[0])
        except:
            print("Error: specified hours for end and start time are not valid numbers")
            return None, None
        if (23 >= startT >= 0) and (23 >= endT >= 0):
            if startT > endT:
                print("Error: specified hour for start time is larger than the one for end time")
                return None, None
        else:
            print("Error: specified hours for end and start time are out of bounds")
            return None, None
        return startT, endT  # return only the hour, will be changed in the future


if __name__ == "__main__":
    # test cmd to add event addEvent 12-12-2020 13:30 15:00 -f eventInfo.json
    UI = SystemManagerInterface()
    UI.cmdConsole()
    # addEvent 12-10-2020 13:30 15:00 -f eventInfo.json, gave eventID = 4
    # addEvent 12-10-2020 16:30 18:00 -f eventInfo.json, gave eventID = 5

