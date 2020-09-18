import dbManager as dbManager
import datetime

date = datetime.date(2020,12,8)
startTime = "15:00"
endTime = "20:00"
name = "Immacolata"
ticketNum = 100
cost = 10
remoteDBparams = {"dbname": "dbuwxucc", "user": "dbuwxucc", "password":"VNx-4S_lIaB4ZZ1NPhX3BpZW5MQDgA9C",
                    "host": "kandula.db.elephantsql.com", "port": "5432"}
dbManager.dBReset(remoteDBparams)
 #eventID = dbManager.add(date, startTime, endTime, ticketNum, cost,remoteDBparams)
print(eventID)
input()

password = []
for i in range(0,ticketNum):
    password.append(str(i)) 
dbManager.passwordFill(eventID, password)

eventInfo = {}
eventInfo["EN"] = "Hello there!"
eventInfo["IT"] = "Ciao!"
eventInfo["PL"] = "I don't know Polish!"
eventInfo["URLs"] = "https:what?"
dbManager.infoFill(eventID, eventInfo)
dbManager.dailySchedule(date)
passwrd = dbManager.ticketRetrieve(eventID,"ek29seiba@gmail.com")
dbManager.gateAccess(eventID,passwrd)
input()
dbManager.delete(eventID)
