import dbManager
import datetime

date = datetime.date(2020,12,8)
startTime = 15
endTime = 20
name = "Immacolata"
ticketNum = 100
cost = 10

eventID = 0 #dbManager.add(date, startTime, endTime, name, ticketNum, cost)

password = []
for i in range(0,ticketNum):
    password.append(str(i)) 
print(dbManager.passwordFill(eventID, password))



eventInfo = {}
eventInfo["EN"] = "Hello there!"
eventInfo["IT"] = "ciao pippini mi sento molto felice                                                                                                                                                                                                                       ok qui dovrei avere il breakpoint"
eventInfo["PL"] = "I don't know Polish!"
eventInfo["URLs"] = "https:what?"
dbManager.infoFill(eventID, eventInfo)
print(dbManager.dailySchedule(date))

passwrd = dbManager.ticketRetrieve(eventID,"ek29seiba@gmail.com")
print(passwrd)

print(dbManager.gateAccess(eventID,passwrd))
input()
dbManager.delete(eventID)
