import dbManager as dbManager
import datetime

date = datetime.date(2020,11,12)
startTime = "11:00"
endTime = "12:00"
ticketNum = 100
cost = 10
remoteDBparams = {"dbname": "dbuwxucc", "user": "dbuwxucc", "password":"VNx-4S_lIaB4ZZ1NPhX3BpZW5MQDgA9C",
                    "host": "kandula.db.elephantsql.com", "port": "5432"}
conn = dbManager.connectDb(remoteDBparams)
dbManager.dBReset(conn,remoteDBparams["user"])
#eventID = dbManager.add(date, startTime, endTime, ticketNum, cost,conn)
#print(eventID)
#input()

#password = []
#for i in range(0,ticketNum):
#    password.append(str(i)) 
#dbManager.passwordFill(eventID, password)

eventInfo = {}
eventInfo["EN"] = {"name":"YOOOO","info":""}
eventInfo["IT"] = {"name":"","info":"plollo"}
eventInfo["PL"] = {"name":"sbenghi","info":"Hello there!"}
eventInfo["URLs"] = ["https:what?","nani?","ciocio"]
eventInfo["cost"] = 70
#dbManager.infoFill(eventID, eventInfo,conn)
date = datetime.date(2020,11,12)
#print(dbManager.dailySchedule(date,0,("PL","EN"),conn))
date = datetime.date(2020,10,12)
#print(dbManager.retreiveInfo(0, conn))
#dbManager.infoUpdate(0,eventInfo, conn)
#print(dbManager.retreiveInfo(0, conn))
#print(dbManager.dailySchedule(date,0,("PL","EN"),conn))
#passwrd = dbManager.ticketRetrieve(eventID,"ek29seiba@gmail.com")
#dbManager.gateAccess(eventID,passwrd)
#input()
#dbManager.deleteDate(date,conn)

#print(dbManager.retreiveCatalog(conn))

dbManager.disconnectDb(conn)
