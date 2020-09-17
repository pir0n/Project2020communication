def dailySchedule(date, remoteDBparams, passFlag):
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

        cur.execute("SELECT cost FROM events WHERE ID = %s;",(eventID,))
        dailyEvents[eventID]["cost"] = cur.fetchone()[0]

        cur.execute("SELECT ticketTot FROM events WHERE ID = %s;",(eventID,))
        dailyEvents[eventID]["ticketNum"] = cur.fetchone()[0]

        cur.execute("SELECT ticketLeft FROM events WHERE ID = %s;",(eventID,))
        dailyEvents[eventID]["ticketLeft"] = cur.fetchone()[0]

        cur.execute(sql.SQL("SELECT startTime FROM {} WHERE ID = %s;").format(sql.Identifier(str(date))),(eventID,))
        dailyEvents[eventID]["startTime"] = cur.fetchone()[0]

        cur.execute(sql.SQL("SELECT endTime FROM {} WHERE ID = %s;").format(sql.Identifier(str(date))),(eventID,))
        dailyEvents[eventID]["endTime"] = cur.fetchone()[0]

        tableInfo = "info "+str(eventID)
        types = ("EN","IT","PL",)

        for infoType in types:
            dailyEvents[eventID][infoType] = {}

            tempType = "name"+infoType
            cur.execute(sql.SQL("SELECT text FROM {} WHERE type = %s;").format(sql.Identifier(tableInfo)),(tempType,))
            dailyEvents[eventID][infoType]["name"] = cur.fetchone()[0]
            
            tempType = "info"+infoType
            cur.execute(sql.SQL("SELECT text, part FROM {} WHERE type = %s;").format(sql.Identifier(tableInfo)),(tempType,))
            info = cur.fetchall()
            text = ""
            for i in range(0,len(info)):
                for j in range(0,len(info)):
                    if info[j][1] == i:
                        text = text + info[j][0]
            dailyEvents[eventID][infoType]["info"] = text

        tempType = "URLs"
        cur.execute(sql.SQL("SELECT text, part FROM {} WHERE type = %s;").format(sql.Identifier(tableInfo)),(tempType,))
        urls = cur.fetchall()
        urlsList = []
        for i in range(0,len(urls)):
            for j in range(0,len(urls)):
                if urls[j][1] == i:
                    urlsList.append(urls[j][0])
        dailyEvents[eventID][tempType] = urlsList

    conn.commit()
    cur.close()
    conn.close()

    return dailyEvents 