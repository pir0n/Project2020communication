import psycopg2
from psycopg2 import sql
import datetime
from datetime import date
import time

# parameters: startTime limits in add(), psycopg2.connect() arguments
# remoteDBparams = {"dbname": "dbuwxucc", "user": "dbuwxucc", "password":"VNx-4S_lIaB4ZZ1NPhX3BpZW5MQDgA9C",
#                   "host": "kandula.db.elephantsql.com", "port": "5432"}


def connectDb(remoteDBparams):
    conn = psycopg2.connect(dbname=remoteDBparams["dbname"], user=remoteDBparams["user"],
                            password=remoteDBparams["password"],
                            host=remoteDBparams["host"], port=remoteDBparams["port"])
    return conn


def disconnectDb(conn):
    conn.close()
    return 0


def add(date, startTime, endTime, ticketNum, cost, conn):
    
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
        cur.execute(sql.SQL("CREATE TABLE {} (ID int, startTime varchar(6),\
                    endTime varchar(5));").format(sql.Identifier(dateName)))

    startList = startTime.split(":")
    startList[0] = int(startList[0])
    startList[1] = int(startList[1])
    if startList[0] > 23:
        print("Error: start time hour is invalid (00<=startHour<=23)")
        return -1
    if startList[1] > 59:
        print("Error: start time minutes are invalid (00<=startMinutes<=59)")
        return -1
    if startList[0] == 23 and startList[1] == 59:
        print("Error: max start time is 23:58")
        return -1

    endList = endTime.split(":")
    endList[0] = int(endList[0])
    endList[1] = int(endList[1])
    if endList[0] > 23:
        print("Error: end time hour is invalid (00<=endHour<=23)")
        return -1
    if endList[1] > 59:
        print("Error: end time minutes are invalid (00<=endMinutes<=59)")
        return -1
    if endList[0] == 00 and endList[1] == 00:
        print("Error: min end time is 00:01")
        return -1
    
    startMinutes = startList[0]*60+startList[1]
    endMinutes = endList[0]*60+endList[1]
    
    if startMinutes > endMinutes:
        print("Error: end time is before start time, please insert a valid hour")
        return -1
    else:
        if startMinutes == endMinutes:
            print("Error: end time is the same as start time, please insert a valid hour")
            return -1

    if not flag:
        #check for time window validity, and return in case of failure
        cur.execute(sql.SQL("SELECT startTime, endTime FROM {};").format(sql.Identifier(dateName)))
        usedTime = cur.fetchall()
        for i in range(len(usedTime)):
            tempStart = usedTime[i][0].split(":")
            usedStart = int(tempStart[0])*60+int(tempStart[1])
            tempEnd = usedTime[i][1].split(":")
            usedEnd = int(tempEnd[0])*60+int(tempEnd[1])
            if startMinutes==usedStart or (startMinutes>usedStart and startMinutes<usedEnd)\
               or endMinutes==usedEnd or (endMinutes>usedStart and endMinutes<usedEnd)\
               or (startMinutes<usedStart and endMinutes>usedEnd):
                print("Error: given time window is unavailable. The occupied slots will now be printed. Please retry with valid values.") 
                i = 8
                for i in range(len(usedTime)):
                    print("Slot from "+usedTime[i][0]+" to "+usedTime[i][1]+";")
                return -1

    cur.execute("SELECT min(ID) FROM events;")
    newID = cur.fetchone()[0]
    if type(newID) == type(0):
        if newID != 0:
            eventID = newID - 1
        else:
            cur.execute("SELECT max(ID) FROM events;")
            newID = cur.fetchone()[0]
            eventID = newID + 1
    else:
        eventID = 0
    # ID, date, tickets_tot, tickets_left, cost
    cur.execute("INSERT INTO events VALUES (%s, %s, %s, %s, %s);", (eventID, date, ticketNum, ticketNum, cost))

    cur.execute(sql.SQL("INSERT INTO {} VALUES (%s, %s, %s);").format(sql.Identifier(dateName)),(eventID,startTime,endTime))

    tableNamePass = "password "+str(eventID)
    cur.execute(sql.SQL("""CREATE TABLE {} (ticketNumber int, password varchar(255), 
        eMail varchar(255), usedFlag bool);""").format(sql.Identifier(tableNamePass)))
    
    tableNameInfo = "info "+str(eventID)
    cur.execute(sql.SQL("""CREATE TABLE {} (text varchar(255), 
        type varchar(255), part int);""").format(sql.Identifier(tableNameInfo)))

    conn.commit()
    cur.close()

    return eventID


# password is a list with size = nTickets of eventID
def passwordFill(eventID, password, conn):
     
    cur = conn.cursor()

    tableNamePass = "password " + str(eventID) #if ID is int

    for i in range(0,len(password)):
        cur.execute(sql.SQL("INSERT INTO {} VALUES (%s, %s, %s, %s);").format(sql.Identifier(tableNamePass)),(i,password[i],"empty","false"))
    
    conn.commit()
    cur.close()

    return eventID 


def infoFill(eventID, eventInfo, conn):
        
    cur = conn.cursor()

    tableNameInfo = "info "+str(eventID)

    types = ("EN","IT","PL")

    for infoType in types:

        infoTemp = eventInfo[infoType]["name"]
        cur.execute(sql.SQL("INSERT INTO {} VALUES (%s, %s, %s);").format(sql.Identifier(tableNameInfo)),(infoTemp,infoType,0))

        flag = 0
        i = 0
        infoTemp = eventInfo[infoType]["info"]

        while flag == 0:
            if len(infoTemp) > 255:
                info = infoTemp[0:255]
                cur.execute(sql.SQL("INSERT INTO {} VALUES (%s, %s, %s);").format(sql.Identifier(tableNameInfo)),(info,infoType,i))
                i = i + 1
                infoTemp = infoTemp[255:]
            else:
                info = infoTemp
                cur.execute(sql.SQL("INSERT INTO {} VALUES (%s, %s, %s);").format(sql.Identifier(tableNameInfo)),(info,infoType,i))
                flag = 1
    
    i = 0
    infoType = "URLs"
    for url in eventInfo[infoType]:
        cur.execute(sql.SQL("INSERT INTO {} VALUES (%s, %s, %s);").format(sql.Identifier(tableNameInfo)),(url,infoType,i))
        i = i + 1

    conn.commit()
    cur.close()

    return eventID


def delete(eventID, conn):
        
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

    return eventID 


def deleteDate(date, conn):
        
    cur = conn.cursor()

    cur.execute("SELECT ID FROM events WHERE date = %s;",(date,))
    IDtuples = cur.fetchall()

    conn.commit()
    cur.close()

    for eventID in IDtuples:
        delete(eventID[0], conn)

    return 0


def deleteAll(conn):

    cur = conn.cursor()

    cur.execute("SELECT ID FROM events;")
    IDtuples = cur.fetchall()

    conn.commit()
    cur.close()

    for eventID in IDtuples:
        delete(eventID[0], conn)

    return 0


def dailySchedule(date, passFlag, languages, conn):

    cur = conn.cursor()
    
    cur.execute(sql.SQL("SELECT ID, startTime, endTime, ticketTot,\
                         ticketLeft, cost FROM events INNER JOIN {} USING(ID)").format(sql.Identifier(str(date))))
    tuplesID = cur.fetchall()

    dailyEvents = {}

    for couple in tuplesID:
        eventID = couple[0]

        dailyEvents[eventID] = {}
        dailyEvents[eventID]["startTime"] = couple[1]
        dailyEvents[eventID]["endTime"] = couple[2]
        dailyEvents[eventID]["ticketNum"] = couple[3]
        dailyEvents[eventID]["ticketLeft"] = couple[4]
        dailyEvents[eventID]["cost"] = couple[5]
        
        if passFlag:
            tablePass = "password "+str(eventID)
            cur.execute(sql.SQL("SELECT password, eMail FROM {} WHERE usedFlag = true;").format(sql.Identifier(tablePass)))
            dailyEvents[eventID]["passTable"] = cur.fetchall()
        else:
            tableInfo = "info "+str(eventID)
            if len(languages) == 1:    
                cur.execute(sql.SQL("SELECT text, part FROM {} WHERE type in (%s,%s);").format(sql.Identifier(tableInfo)),(languages[0],"URLs"))
                eventInfo = cur.fetchall()
            if len(languages) == 2:    
                cur.execute(sql.SQL("SELECT text, part FROM {} WHERE type in (%s,%s,%s);").format(sql.Identifier(tableInfo)),(languages[0],languages[1],"URLs"))
                eventInfo = cur.fetchall()
            if len(languages) == 3:    
                cur.execute(sql.SQL("SELECT text, part FROM {};").format(sql.Identifier(tableInfo)))
                eventInfo = cur.fetchall()

            temp = []
            if "EN" in languages:
                temp.append("EN")
            if "IT" in languages:
                temp.append("IT")
            if "PL" in languages:
                temp.append("PL")
            languages = temp

            i = 0
            for infoType in languages:
                dailyEvents[eventID][infoType] = {}
            
                dailyEvents[eventID][infoType]["name"] = eventInfo[i][0]
                i = i + 1

                text = ""
                flag = 0
                while(flag == 0):
                    text = text + eventInfo[i][0]
                    i = i + 1
                    if eventInfo[i][1] == 0:
                        flag = 1
                dailyEvents[eventID][infoType]["info"] = text

            infoType = "URLs"
            urlsList = []

            for j in range(i,len(eventInfo)):
                urlsList.append(eventInfo[j][0])
            dailyEvents[eventID][infoType] = urlsList

    conn.commit()
    cur.close()

    return dailyEvents 


def ticketRetrieve(eventID, eMail, conn):
        
    cur = conn.cursor()

    tablePass = "password "+str(eventID)
    
    cur.execute(sql.SQL("SELECT password FROM {} WHERE eMail = %s LIMIT 1;").format(sql.Identifier(tablePass)),("empty",))
    try:
        password = cur.fetchone()[0]
    except:
        return None
    cur.execute(sql.SQL("UPDATE {} SET eMail = %s, usedFlag = true WHERE password = %s;").format(sql.Identifier(tablePass)),(eMail,password))
    
    cur.execute("UPDATE events SET ticketLeft = ticketLeft - 1 WHERE ID = %s;",(ticketNum,eventID))

    conn.commit()
    cur.close()

    return password

def ticketLeftCheck(eventID, conn):
        
    cur = conn.cursor()

    cur.execute("SELECT ticketLeft FROM events where ID = %s;",(eventID,))
    ticketLeft = cur.fetchone()[0]

    conn.commit()
    cur.close()

    return ticketLeft


def dBReset(conn):

    deleteAll(conn)
        
    cur = conn.cursor()

    cur.execute('DROP TABLE events')
    cur.execute("CREATE TABLE events (ID int, date date, ticketTot int, ticketLeft int, cost int);")

    conn.commit()
    cur.close()

    return 0
