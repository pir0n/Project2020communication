import dbManager as dbManager
import datetime

date = datetime.date(2020,10,12)
startTime = "9:00"
endTime = "10:00"
ticketNum = 100
cost = 10
remoteDBparams = {"dbname": "dbuwxucc", "user": "dbuwxucc", "password":"VNx-4S_lIaB4ZZ1NPhX3BpZW5MQDgA9C",
                    "host": "kandula.db.elephantsql.com", "port": "5432"}
conn = dbManager.connectDb(remoteDBparams)
#dbManager.dBReset(conn)
eventID = dbManager.add(date, startTime, endTime, ticketNum, cost,conn)
#print(eventID)
#input()

#password = []
#for i in range(0,ticketNum):
#    password.append(str(i)) 
#dbManager.passwordFill(eventID, password)

eventInfo = {}
eventInfo["EN"] = {"name":"pippo","info":"Hello there!"}
eventInfo["IT"] = {"name":"goofey","info":"Hello there!"}
eventInfo["PL"] = {"name":"sbenghi","info":"Hello there!"}
eventInfo["URLs"] = ["https:what?","nani?"]
dbManager.infoFill(eventID, eventInfo,conn)
print(dbManager.dailySchedule(date,0,("IT","PL","EN"),conn))
#passwrd = dbManager.ticketRetrieve(eventID,"ek29seiba@gmail.com")
#dbManager.gateAccess(eventID,passwrd)
#input()
#dbManager.delete(eventID)
dbManager.disconnectDb(conn)
