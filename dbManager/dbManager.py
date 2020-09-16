import psycopg2
from psycopg2 import sql
import datetime
from datetime import date
import time

# parameters: startTime limits in add(), psycopg2.connect() arguments
# remoteDBparams = {"dbname": "dbuwxucc", "user": "dbuwxucc", "password":"VNx-4S_lIaB4ZZ1NPhX3BpZW5MQDgA9C",
#                   "host": "kandula.db.elephantsql.com", "port": "5432"}


# argument "date" is a date object
def add(date, startTime, endTime, name, ticketNum, cost, remoteDBparams):
    conn = psycopg2.connect(dbname=remoteDBparams["dbname"], user=remoteDBparams["user"],
                            password=remoteDBparams["password"],
                            host=remoteDBparams["host"], port=remoteDBparams["port"])
        
    cur = conn.cursor()

    #check for date correctness
    today = date.fromtimestamp(time.time())
    if date <= today:
        print("Error: given date is invalid, please insert a future day.")
        return -1 

    dateName = str(date)

    #search if date is present in database
    cur.execute("SELECT date FROM events WHERE date = %s;",(date,))
    check = cur.fetchone()
    flag = 0
    if not check:
        flag = 1
        #create date table
        cur.execute(sql.SQL("CREATE TABLE {} (ID int, startTime int,\
                    endTime int);").format(sql.Identifier(dateName)))

    # I suppose startTime to be an int, startTime = int(startTime)
    if startTime < 8 or startTime > 19:
        print("Error: start time is out of time window limit, please insert a valid time (7<startTime<20)")
        return -1
 
    if endTime < 9 or endTime > 20:
        print("Error: end time is out of time window limit, please insert a valid time (8<endTime<21")
        return -1
    else:
        if startTime > endTime:
            print("Error: end time is before start time, please insert a valid hour")
            return -1
        else:
            if startTime == endTime:
                print("Error: end time is the same as start time, please insert a valid hour")
                return -1

    if not flag:
        #check for time window validity, and return in case of failure
        cur.execute(sql.SQL("SELECT startTime, endTime FROM {};").format(sql.Identifier(dateName)))
        usedTime = cur.fetchall()
        for i in range(len(usedTime)):
            if startTime==usedTime[i][0] or (startTime>usedTime[i][0] and startTime<usedTime[i][1])\
               or endTime==usedTime[i][1] or (endTime>usedTime[i][0] and endTime<usedTime[i][1])\
               or (startTime<usedTime[i][0] and endTime>usedTime[i][1]):
                print("Error: given time window is unavailable. The occupied slots will now be printed. Please retry with valid values.") 
                i = 8
                for i in range(8,20):
                    for j in range(len(usedTime)):
                        if usedTime[j][0] == i:
                            print("Slot from "+str(i)+" to "+str(usedTime[j][1])+";")
                return -1

    cur.execute("SELECT min(ID) FROM events;")
    newID = cur.fetchone()
    if type(newID[0]) == type(0):
        if newID[0] != 0:
            eventID = newID[0] - 1
        else:
            cur.execute("SELECT max(ID) FROM events;")
            newID = cur.fetchone()
            eventID = newID[0] + 1
    else:
        eventID = 0

    # ID, name, date, tickets_tot, tickets_left, cost
    cur.execute("INSERT INTO events VALUES (%s, %s, %s, %s, %s, %s);",(eventID,name,date,ticketNum,ticketNum,cost))

    cur.execute(sql.SQL("INSERT INTO {} VALUES (%s, %s, %s);").format(sql.Identifier(dateName)),(eventID,startTime,endTime))

    tableNamePass = "password "+str(eventID)
    cur.execute(sql.SQL("""CREATE TABLE {} (ticketNumber int, password varchar(255), 
        eMail varchar(255), usedFlag bool);""").format(sql.Identifier(tableNamePass)))
    
    tableNameInfo = "info "+str(eventID)
    cur.execute(sql.SQL("""CREATE TABLE {} (text varchar(255), 
        type varchar(255), part int);""").format(sql.Identifier(tableNameInfo)))

    conn.commit()
    cur.close()
    conn.close()

    return eventID


# password is a list with size = nTickets of eventID
def passwordFill(eventID, password, remoteDBparams):
    conn = psycopg2.connect(dbname=remoteDBparams["dbname"], user=remoteDBparams["user"],
                            password=remoteDBparams["password"],
                            host=remoteDBparams["host"], port=remoteDBparams["port"])
        
    cur = conn.cursor()

    tableNamePass = "password " + str(eventID) #if ID is int

    for i in range(0,len(password)):
        cur.execute(sql.SQL("INSERT INTO {} VALUES (%s, %s, %s, %s);").format(sql.Identifier(tableNamePass)),(i,password[i],"empty","false"))
    
    conn.commit()
    cur.close()
    conn.close()

    return eventID 


def infoFill(eventID, eventInfo, remoteDBparams):
    conn = psycopg2.connect(dbname=remoteDBparams["dbname"], user=remoteDBparams["user"],
                            password=remoteDBparams["password"],
                            host=remoteDBparams["host"], port=remoteDBparams["port"])
        
    cur = conn.cursor()

    tableNameInfo = "info "+str(eventID)

    types = ("EN","IT","PL","URLs")

    for infoType in types:
        flag = 0
        i = 0
        infoTemp = eventInfo[infoType]
        while flag == 0:
            if len(infoTemp)>255:
                info = infoTemp[0:255]
                cur.execute(sql.SQL("INSERT INTO {} VALUES (%s, %s, %s);").format(sql.Identifier(tableNameInfo)),(info,infoType,i))
                i = i + 1
                infoTemp = infoTemp[255:]
            else:
                info = infoTemp
                cur.execute(sql.SQL("INSERT INTO {} VALUES (%s, %s, %s);").format(sql.Identifier(tableNameInfo)),(info,infoType,i))
                flag = 1

    conn.commit()
    cur.close()
    conn.close()

    return eventID


def delete(eventID, remoteDBparams):
    conn = psycopg2.connect(dbname=remoteDBparams["dbname"], user=remoteDBparams["user"],
                            password=remoteDBparams["password"],
                            host=remoteDBparams["host"], port=remoteDBparams["port"])
        
    cur = conn.cursor()
    
    eventID = str(eventID) #check for string or int for commands

    cur.execute("SELECT date FROM events WHERE ID = %s;",(eventID,))
    date = str(cur.fetchone()[0])
    
    # delete from date table the entry related to the given event
    cur.execute(sql.SQL("DELETE FROM {} WHERE id = %s;").format(sql.Identifier(date)),(eventID,))

    # check if date table is empty
    cur.execute(sql.SQL("SELECT id FROM {} LIMIT 1;").format(sql.Identifier(date)))
    check = cur.fetchone()

    # if it is, delete it
    if not check:
        cur.execute(sql.SQL("DROP TABLE {}").format(sql.Identifier(date)))
    
    #delete both password and description tables
    tablePass = "password "+eventID
    cur.execute(sql.SQL("DROP TABLE {}").format(sql.Identifier(tablePass)))
    tableInfo = "info "+eventID
    cur.execute(sql.SQL("DROP TABLE {}").format(sql.Identifier(tableInfo)))

    #delete event table entry for given event
    cur.execute("DELETE FROM events WHERE ID = %s;",(eventID,))

    conn.commit()
    cur.close()
    conn.close()

    return eventID 


def dailySchedule(date, remoteDBparams):
    conn = psycopg2.connect(dbname=remoteDBparams["dbname"], user=remoteDBparams["user"],
                            password=remoteDBparams["password"],
                            host=remoteDBparams["host"], port=remoteDBparams["port"])
        
    cur = conn.cursor()
    
    cur.execute("SELECT ID FROM events WHERE date = %s;",(date,))
    IDtuples = cur.fetchall()
    listID = []
    for couple in IDtuples:
        listID.append(couple[0])

    dailyEvents = {}

    for eventID in listID:
        dailyEvents[eventID] = {}
        # eventInfo = {}

        cur.execute("SELECT name FROM events WHERE ID = %s;",(eventID,))
        dailyEvents[eventID]["name"] = cur.fetchone()[0]

        cur.execute("SELECT cost FROM events WHERE ID = %s;",(eventID,))
        dailyEvents[eventID]["cost"] = cur.fetchone()[0]

        cur.execute("SELECT ticketTot FROM events WHERE ID = %s;",(eventID,))
        dailyEvents[eventID]["ticketNum"] = cur.fetchone()[0]

        cur.execute(sql.SQL("SELECT startTime FROM {} WHERE ID = %s;").format(sql.Identifier(str(date))),(eventID,))
        dailyEvents[eventID]["startTime"] = cur.fetchone()[0]

        cur.execute(sql.SQL("SELECT endTime FROM {} WHERE ID = %s;").format(sql.Identifier(str(date))),(eventID,))
        dailyEvents[eventID]["endTime"] = cur.fetchone()[0]

        tableInfo = "info "+str(eventID)
        types = ("EN","IT","PL","URLs")

        for infoType in types:
            cur.execute(sql.SQL("SELECT text, part FROM {} WHERE type = %s;").format(sql.Identifier(tableInfo)),(infoType,))
            info = cur.fetchall()
            text = ""
            for i in range(0,len(info)):
                for j in range(0,len(info)):
                    if info[j][1] == i:
                        text = text + info[j][0]
            dailyEvents[eventID][infoType] = text

    conn.commit()
    cur.close()
    conn.close()

    return dailyEvents 


def ticketRetrieve(eventID, eMail, remoteDBparams):

    conn = psycopg2.connect(dbname=remoteDBparams["dbname"], user=remoteDBparams["user"],
                            password=remoteDBparams["password"],
                            host=remoteDBparams["host"], port=remoteDBparams["port"])
        
    cur = conn.cursor()

    tablePass = "password "+str(eventID)
    
    cur.execute(sql.SQL("SELECT password FROM {} WHERE eMail = %s LIMIT 1;").format(sql.Identifier(tablePass)),("empty",))
    try:
        password = cur.fetchone()[0]
    except:
        return None
    cur.execute(sql.SQL("UPDATE {} SET eMail = %s WHERE password = %s;").format(sql.Identifier(tablePass)),(eMail,password))

    conn.commit()
    cur.close()
    conn.close()

    return password


def gateAccess(eventID, password, remoteDBparams):

    conn = psycopg2.connect(dbname="dbuwxucc",user="dbuwxucc",password="VNx-4S_lIaB4ZZ1NPhX3BpZW5MQDgA9C",
        host="kandula.db.elephantsql.com",port="5432")
        
    cur = conn.cursor()

    tablePass = "password "+str(eventID)
    
    cur.execute(sql.SQL('SELECT usedFlag FROM {} WHERE password = %s;').format(sql.Identifier(tablePass)),(password,))
    flag = cur.fetchone()[0]
    if flag:
        print("Error: ticket already used.")
        return [-1]

    cur.execute(sql.SQL("UPDATE {} SET usedFlag = true WHERE password = %s;").format(sql.Identifier(tablePass)),(password,))

    cur.execute("SELECT ticketLeft FROM events WHERE ID = %s;",(eventID,))
    ticketNum = cur.fetchone()[0] - 1

    cur.execute("UPDATE events SET ticketLeft = %s WHERE ID = %s;",(ticketNum,eventID))

    conn.commit()
    cur.close()
    conn.close()

    return eventID  