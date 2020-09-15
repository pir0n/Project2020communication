import dbManager
import datetime

date = datetime.date(2020,12,8)
startTime = 15
endTime = 20
name = "Immacolata"
ticketNum = 100
cost = 10

eventID = dbManager.add(date, startTime, endTime, name, ticketNum, cost)

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
