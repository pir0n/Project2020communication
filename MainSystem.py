import json
import time
import datetime
import threading
import schedule
import cherrypy
import pyqrcode
from fpdf import FPDF
import email, smtplib, ssl
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pswUpdateMQTTClient import PswMQTTClient
import dbManager.dbManager as dbManager
import os
import png
from systemConfigurationManager import SysConfig
testEV = 1  # enable fake events  for testing

# MAIN CONTROL OF THE BOOKING SYSTEM, ACCESSIBLE THROUGH REST APIs
# processes:
# password retrieval from database, conversion to QR code and delivery of code to user through email
# MQTT communication with multiple gates to send acceptable passwords

DEBUG = True
dailyEventsPswTable = None
catalogData = None
remoteDBparams = {"dbname": "dbuwxucc", "user": "dbuwxucc", "password":"VNx-4S_lIaB4ZZ1NPhX3BpZW5MQDgA9C",
                   "host": "kandula.db.elephantsql.com", "port": "5432"}
configFileName = "configFile.json"
DBconn = None  # connection object to access the database, instantiated by the start PUT command to the system

ERROR_IMG_NAME = "error_img.png"


class VirtualTicketHandler:
    global dailyEvents
    global DEBUG  # set to True to print debug messages

# class to control conversion of password to QR code and its delivery to client through e-mail
    def __init__(self, imagePath = "QRCode", pdfPath = "VirtualTicket.pdf"): #.png and .pdf
        self.imgPath = imagePath
        self.pdfPath = pdfPath

    def pswToQr(self, password, eventID, filepath):
        # create a .png image of the psw encoded as qr code
        ticketJSON = json.dumps({"eventID": eventID, "psw": password})
        if DEBUG:
            print("encoding:", ticketJSON)
        QRpsw = pyqrcode.create(ticketJSON)
        QRpsw.png(filepath+".png", scale=5, module_color=[0, 0, 0, 128], background=[0xff, 0xff, 0xcc])

    def generatePDF(self, n_tickets, scheduledTime, eventName):
        pdf = FPDF()
        if DEBUG:
            print("creating pdf")

        text = f"Virtual Ticket for event {eventName}, scheduled for time {scheduledTime[0]}-{scheduledTime[1]}"
        if n_tickets == 1:
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(0, 10, txt=text, ln=1, align="C")
            pdf.image(self.imgPath+".png", x=48, y=30, w=100)
            # pdf.ln(85)  # move 85 down
            pdf.output(self.pdfPath)
        else:
            i = 0
            while i < n_tickets:
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                pdf.cell(0, 10, txt=text, ln=1, align="C")
                pdf.image(self.imgPath+str(i)+".png", x=48, y=30, w=100)
                # pdf.ln(85)  # move 85 down
                i += 1
            pdf.output(self.pdfPath)

    # NOTE: to speed things up, a connection can be established only once instead of each time
    def sendMail(self, receiver_email, event, n_tickets):
        if DEBUG:
            print("sending e-mail")
        mailAddress = "BookingSystemTest2@gmail.com"
        psw = '3LV9gL7K9j4wp8i'
        port = 465  # For SSL

        # Create a secure SSL context
        context = ssl.create_default_context()

        with smtplib.SMTP_SSL("smtp.gmail.com", port, context=context) as server:
            server.login(mailAddress, psw)
            sender_email = mailAddress
            if n_tickets == 1:
                subject = f"Virtual ticket for event: {event}"
                body = f"""
                Your Virtual Ticket for the event: -{event}- is in the pdf attached to this e-mail
                """
            else:
                subject = f"Virtual tickets for event: {event}"
                body = f"""
                Your Virtual Tickets for the event: -{event}- are in the pdf attached to this e-mail
                """
            # Create a multipart message and set headers
            message = MIMEMultipart()
            message["From"] = sender_email
            message["To"] = receiver_email
            message["Subject"] = subject
            message["Bcc"] = receiver_email  # Recommended for mass emails
            # Add body to email
            message.attach(MIMEText(body, "plain"))

            filename = self.pdfPath  # In same directory as script

            # Open PDF file in binary mode
            with open(filename, "rb") as attachment:
                # Add file as application/octet-stream
                # Email client can usually download this automatically as attachment
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())

            # Encode file in ASCII characters to send by email
            encoders.encode_base64(part)

            # Add header as key/value pair to attachment part
            part.add_header(
                "Content-Disposition",
                f"attachment; filename= {filename}",
            )

            # Add attachment to message and convert message to string
            message.attach(part)
            text = message.as_string()

            # Log in to server using secure context and send email
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
                server.login(sender_email, psw)
                server.sendmail(sender_email, receiver_email, text)

    # wrapper function
    def sendTicket(self, mail_addr, event, passwordList, eventID, scheduledtime):
        if type(passwordList) is list:
            i = 0
            for el in passwordList:
                self.pswToQr(password=el, filepath=self.imgPath + str(i), eventID=eventID)  # generate a QR png for each psw
                i += 1
            self.generatePDF(len(passwordList), scheduledtime, event)  # pdf with 1 page per ticket
        else:
            self.pswToQr(password=passwordList, filepath=self.imgPath, eventID=eventID)  # generate a png file in the directory
            self.generatePDF(1, scheduledtime, event)  # generate a pdf containing the QR png in the directory

        self.sendMail(mail_addr, event, len(passwordList))


class MainSystemMQTT(PswMQTTClient):
    # only difference with MQTT client of gate is that the daily pswTable is stored in dailyEventsPswTable global var
    def addPswEntry(self, newPswDict):
        global dailyEventsPswTable
        PswMQTTClient.addPswEntry(self, newPswDict)
        dailyEventsPswTable = self.pswTable  # update global variable

    def setPswUsed(self, usedPswDict):
        global dailyEventsPswTable
        PswMQTTClient.setPswUsed(self, usedPswDict)
        dailyEventsPswTable = self.pswTable  # update global variable

    def myOnMessageReceived(self, client, userdata, msg):
        global DEBUG
        global dailyEventsPswTable
        # main system won't subscribe to newPswTable topic
        if msg.topic == self.msgTopics["newPsw"]:
            # ADD THE ENTRY INSIDE THE PASSWORD TABLE
            newPswDict = json.loads(msg.payload.decode('utf-8'))
            try:
                self.addPswEntry(newPswDict)
            except:
                print("Received newPsw message with bad body format or for eventID not present in the table")
        elif msg.topic == self.msgTopics["pswUsed"]:
            # SET SPECIFIED PASSWORD AS USED
            usedPswDict = json.loads(msg.payload.decode('utf-8'))
            try:
                self.setPswUsed(usedPswDict)
                dailyEventsPswTable = self.pswTable
                if DEBUG:  # global debug variable
                    print(f"setting psw: {usedPswDict['psw']} of event: {usedPswDict['eventID']} as used")
                    for psw in dailyEventsPswTable[str(usedPswDict['eventID'])]["pswTable"]:
                        if psw["psw"] == usedPswDict['psw']:
                            print("psw entry in list:", psw)
                            break
            except:
                print("Received usedPsw message with bad body format")


# thread for scheduled jobs (daily table request and delivery)
class JobSchedulerThread(threading.Thread):
    theadStop = False  # stops the thread when set to True
    on = False  # indicates if the MQTT client is on
    dailyTableTMS = None  # datetime obj storing time at which the last dailytable has been received

    def __init__(self, Rtime, subTopics = None):
        # Rtime must be a string of format HH:MM, indicating the time at which the system will update the daily event list
        global catalogData
        global dailyEventsPswTable
        threading.Thread.__init__(self)
        self.requestTime = Rtime
        subTopics = catalogData.topics["pswUsed"]
        # start MQTT client
        self.MQTTClient = MainSystemMQTT(clientID="MainSystem", brokerPort=int(catalogData.broker["port"]),
                                         MQTTbroker=catalogData.broker["ip"], msgTopics=catalogData.getTopics(),
                                         subscribedTopics=subTopics, initialPswTable=dailyEventsPswTable)
        try:
            self.MQTTClient.start()
            pass
        except:
            raise Exception("Could not start MQTT client, check if the configuration is correct")
        self.on = True
        # self.startSchedule() # now called by the start PUT request

    def getDailyTable(self):
        global DBconn
        global dailyEventsPswTable
        global remoteDBparams
        eventDate = datetime.date(2020, 10, 12)  # 12-10-2020, DEBUG DATE
        # eventDate = datetime.date.today()
        print("Retrieving daily table from database...")
        receivedDailyEvents = dbManager.dailySchedule(eventDate, passFlag=True, conn=DBconn, languages=None)
        print("Daily table retrieved")
        self.dailyTableTMS = datetime.datetime.now().date()  # get date of current day
        # received dictionary:
        # {eventid: {'name':, 'cost':, 'ticketNum':, 'startTime':, 'endTime':, 'EN':,
        #      'IT':, 'PL':, 'URLs': '{testurl1,testurl2}'}
        tmpDict = {}
        pswList = []
        for event in list(receivedDailyEvents.items()):
            eventID = str(event[0])  # eventID always cast as string
            value = event[1]
            pswList.clear()
            for psw in value["passTable"]:
                # list of el with format: [psw, email]
                pswList.append({"psw": psw[0], "used": False})
            # important: insert psw list by values
            tmpDict[eventID] = {"startTime": value["startTime"], "endTime": value["endTime"], "pswTable": pswList[:]}

        # ADDING A PASSWORD FOR DEBUG
        # testPSWentry_d = {"psw": '5', "used": False}
        # tmpDict['8']['pswTable'].append(testPSWentry_d)

        # {“eventID”:{“startTime”:, “endTime”:, “pswTable”:, }
        # update daily event list
        dailyEventsPswTable = tmpDict
        self.MQTTClient.pswTable = dailyEventsPswTable  # update MQTT client table
        print("received daily event table: ", dailyEventsPswTable)

    def startSchedule(self, Rtime=None):
        # schedule the daily table rest and start the scheduler thread
        if Rtime is not None:
            self.requestTime = Rtime
        self.on = True
        schedule.every().day.at(self.requestTime).do(self.setDailyTable)
        self.start()

    def run(self):
        while not self.theadStop:
            # NOTE: schedule is shared among threads
            schedule.run_pending()

    def stop(self):
        self.on = False
        self.theadStop = True
        schedule.clear()
        self.join()

    def changeTime(self, newTime):
        self.requestTime = newTime
        schedule.clear()
        schedule.every().day.at(self.requestTime).do(self.setDailyTable)

    def setDailyTable(self):
        # WARNING: this method will remove events from the database!
        # get the daily table from DB and then send it to all gates through MQTT
        global catalogData
        global DBconn
        yesterday = self.dailyTableTMS
        # THIS API CALL DELETES DATA FROM THE DB
        dbManager.deleteDate(yesterday, DBconn)
        # retrieve the new daily table from DB
        self.getDailyTable()
        # send the new daily table to gate
        self.MQTTClient.publish(catalogData.topics["newPswTable"], json.dumps(dailyEventsPswTable))


# RESTful interface exposed through cherrypy
class MainSystemREST(object):
    ERROR_IMG_NAME = "error_img.png"
    schedulerActive = False  # flag to keep track of scheduler thread
    # generate some TEST events
    global testEV
    global dailyEventsPswTable  # on activation the backend should request the daily table to database
    #its a dictionary with format:
    # "eventID":{"pswList": ["","",..], "eventDesc":{"EN":..,"IT":..,"PL":..},"imgURL":..,"eventInfo":{"timeslot":..,"cost":..,etc.}}
    # "eventDesc" contains info that needs to be localized, "language": {"name":.., "desc":..}# TO-DO: add remaining tickets
    if testEV:
        DebugEvents = [
            {"0": {"pswList": [], "eventDesc": {
                "EN": {"name": "Fire and Forget at KW Institute for Contemporary Art", "desc": "ENtestdesc0"},
                "PL": {"name": "Pożar i zapomnij w KW Institute for Contemporary Art", "desc": "PLtestdesc0"},
                "IT": {"name": "Fuoco e Dimentica al KW Institute for Contemporary Art", "desc": "ITtestdesc0"}},
                  "imgURL": [], "eventInfo": {"timeslot": [], "cost": 10, "ticketLeft": 9}}},
            {"1": {"pswList": [], "eventDesc": {
                "EN": {"name": "The Natural History Museum", "desc": "ENtestdesc1"},
                "PL": {"name": "Muzeum Historii Naturalnej", "desc": "PLtestdesc1"},
                "IT": {"name": "Il Museo di storia naturale", "desc": "ITtestdesc1"}},
                  "imgURL": [], "eventInfo": {"timeslot": [], "cost": 12, "ticketLeft": 9}}}
        ]

    global DEBUG
    exposed = True
    gateTopics = {"new_psw": "ticketPassword"}  # MQTT topics (for communication with gates)
    DBrequestsURL = {"daily_schedule": "placeholder"}
    # initiate classes
    virtualTicketHandler = VirtualTicketHandler()
    requestScheduler = None  # this class must be initialized through the REST API
    initialized = False

    storedImgs = []  # list of stored image names
    storedImgsDirChecked = False

    def GET(self, *uri, **params):
        global dailyEventsPswTable
        # requests URL formats:
        # used for commands sent by the GUI(user side) or the system management interface that request a resource
        # gates can also call a GET req to retrieve the daily psw table
        if len(uri) != 0:
            if len(uri) == 1:
                raise cherrypy.HTTPError(404, "invalid url")
            if uri[0] == "img":  # image repository
                print(self.storedImgs)
                if uri[1] not in self.storedImgs:  # check if requested image is in repository
                    if not self.storedImgsDirChecked:
                        # see if directory has already been checked
                        self.storedImgs.clear()
                        # get list of stored imgs in directory
                        self.storedImgs = os.listdir("eventImgs")
                        self.storedImgsDirChecked = True
                        if uri[1] not in self.storedImgs:
                            return cherrypy.HTTPError(404, "image not found")
                    else:
                        return cherrypy.HTTPError(404, "image not found")

                cherrypy.response.headers['Content-Type'] = "image/png"  # specify response is image in the header
                with open('eventImgs/'+uri[1], "rb") as imageFile:
                    return imageFile.read()  # return byte object

            if uri[0] == "customer":
                if not self.initialized:
                    raise cherrypy.HTTPError(500, "system not initialized, call the PUT request to initialize")
                if uri[1] == "Events":
                    # return list of daily events
                    if uri[2] == "EN" or uri[2] == "IT" or uri[2] == "PL" or uri[2] == "all":
                        language = uri[2]  # EN, IT or PL
                    else:
                        raise cherrypy.HTTPError(404, "invalid URL")
                    if "date" not in params:
                        raise cherrypy.HTTPError(500, 'missing parameter "date" in the request')
                    eventDate = self.getDate(params["date"])
                    outputEventsList = self.getEventList(eventDate, language)
                    # return "[{ 'id': '0', name: 'Fire and Forget at KW Institute for Contemporary Art', patch_img: 'img/events/event1_1.jpg', patch_img2: 'img/events/event1_2.jpg', patch_img3: 'img/events/event1_3.jpg', description: 'Test desc 0', price: '0' }]"
                    # outputDict = [{"id": '0', "name": "Fire and Forget at KW Institute for Contemporary Art", "patch_img": 'img/events/event1_1.jpg', "patch_img2": 'img/events/event1_2.jpg', "patch_img3": 'img/events/event1_3.jpg', "description": 'Test desc 0', "price": '0'}]
                    # outputDict = [{"id": '0', "name": "Fire and Forget at KW Institute for Contemporary Art", "patch_img": 'https://i.imgur.com/PvL7PAw.jpg', "patch_img2": 'https://i.imgur.com/AKZI0JO.jpg', "patch_img3": 'https://i.imgur.com/qmrQAKk.jpg', "description": 'Test desc 0', "price": '0'}]
                    # return json.dumps(outputDict)
                    if outputEventsList is None:
                        return ""
                    return json.dumps(outputEventsList)
                else:
                    raise cherrypy.HTTPError(404, "incorrect URL")
            if DEBUG:
                print("GET request received")
            if uri[0] == "gate":  # requests made by the gate
                if uri[1] == "pswTable":
                    if dailyEventsPswTable is None:
                        raise cherrypy.HTTPError(500, "daily event table is empty")
                    else:
                        return json.dumps(dailyEventsPswTable)
                else:
                    raise cherrypy.HTTPError(404, "invalid url")
            else:
                raise cherrypy.HTTPError(404, "invalid url")

    def PUT(self, *uri, **param):
        global remoteDBparams
        global dailyEventsPswTable
        global testEV
        global catalogData
        global DBconn
        global DEBUG
        # sent by GUI or system interface to request an action
        if len(uri) != 0:
            if len(uri) == 1:
                raise cherrypy.HTTPError(404, "invalid url")
            # customer services
            if uri[0] == "customer":
                if uri[1] == "newTicket":  # return the chosen password
                    if not self.initialized:
                        raise cherrypy.HTTPError(500, "system not initialized")
                    if not self.requestScheduler.on:
                        raise cherrypy.HTTPError(500, "MQTT client is not active")
                    # NOTE: this request takes about 3 seconds to complete
                    # send the virtual ticket to specified address, expects name, address, eventName in the request
                    # body must be a string in the following format
                    # format {"Eventname":"", "mailAddress":"", "event_ID":, "n_tickets":}
                    rawPayload = cherrypy.request.body.read()
                    ReqjsonStr = rawPayload.decode("utf-8")
                    try:
                        Reqdict = json.loads(ReqjsonStr)
                    except:
                        raise cherrypy.HTTPError(500, "could not load JSON string in body")
                    if DEBUG:
                        print("received new ticket req with body: ", Reqdict)
                    # check format of body
                    if not("eMail" in Reqdict and "language" in Reqdict and "eventID" in Reqdict and "n_tickets" in Reqdict):
                        raise cherrypy.HTTPError(500, "invalid request format")
                    # send eventID, timeslot, e-mail, n_tickets to DB, DB returns n passwords (JSON  list)

                    # ACCESS DB THROUGH APIs TO RETRIEVE TICKETS
                    if int(Reqdict["n_tickets"]) > 1:
                        # DB API CALL
                        ticket_remaining = int(dbManager.ticketLeftCheck(Reqdict["eventID"], conn=DBconn))
                        if int(Reqdict["n_tickets"]) > ticket_remaining:
                            return "no ticket available"
                        sel_psw = []
                        for i in range(0, int(Reqdict["n_tickets"])):
                            returnVal = dbManager.ticketRetrieve(Reqdict["eventID"], Reqdict["eMail"], conn=DBconn)
                            if returnVal is None:
                                break  # no more tickets
                                # return sel_psw
                            sel_psw.append(returnVal)
                    else:
                        # DB API CALL
                        ticket_remaining = int(dbManager.ticketLeftCheck(Reqdict["eventID"], conn=DBconn))
                        if ticket_remaining == 0:
                            return "no ticket available"
                        sel_psw = dbManager.ticketRetrieve(int(Reqdict["eventID"]), Reqdict["eMail"], conn=DBconn)
                        # NOTE: eventID is an int for now, might change in future
                        if sel_psw is None:
                            return "no ticket available"
                    # send password to the user
                    if DEBUG:
                        print(f'sending QR code to mail:{Reqdict["eMail"]}, language {Reqdict["language"]}')

                    print("sending psw list:", sel_psw)
                    # DB API to retrieve name in specified language
                    rx_info = dbManager.retreiveInfo(str(Reqdict["eventID"]), DBconn)
                    if Reqdict["language"] == "uk":
                        lang = "EN"
                    elif Reqdict["language"] == "pl":
                        lang = "PL"
                    elif Reqdict["language"] == "pl":
                        lang = "IT"
                    else:
                        lang = "EN"
                    self.virtualTicketHandler.sendTicket(Reqdict["eMail"], rx_info[lang]["name"], sel_psw,
                                                         Reqdict["eventID"], (rx_info["startTime"], rx_info["endTime"]))

                    # insert password in daily table and send to gates IF the event is in daily table
                    if str(Reqdict["eventID"]) in dailyEventsPswTable:  # check if event in daily table
                        # insert psw in daily psw table and then send a "newPsw" MQTT message to gates
                        if type(sel_psw) is list:
                            for psw in sel_psw:
                                dailyEventsPswTable[Reqdict["eventID"]]["pswTable"].append({"psw": psw, "used": False})
                                # send the password to the gates through MQTT
                                # msg format : {"eventID":, "psw":}
                                dict_msg = {"eventID": Reqdict["eventID"], "psw": psw}
                                json_msg = json.dumps(dict_msg)
                                self.requestScheduler.MQTTClient.publish(catalogData.topics["newPsw"], json_msg)
                        else:
                            dailyEventsPswTable[Reqdict["eventID"]]["pswTable"].append({"psw": sel_psw, "used": False})
                            # msg format : {"eventID":, "psw":}
                            dict_msg = {"eventID": Reqdict["eventID"], "psw": sel_psw}
                            json_msg = json.dumps(dict_msg)
                            self.requestScheduler.MQTTClient.publish(catalogData.topics["newPsw"], json_msg)
                    return json.dumps(sel_psw)  # return the passwords
                else:
                    raise cherrypy.HTTPError(404, "invalid url")
            # system management
            if uri[0] == "system":
                if len(uri) == 1:
                    raise cherrypy.HTTPError(404, "invalid url")
                # management of the MQTT client
                if uri[1] == "start":  # THIS SHOULD ALWAYS BE CALLED AFTER SCRIPT IS EXECUTED
                    print("received start request")
                    if not self.initialized:
                        # instantiate the scheduler and initialize its MQTT client
                        try:
                            self.requestScheduler = JobSchedulerThread("00:00:01", catalogData.topics["pswUsed"])
                        except:
                            raise cherrypy.HTTPError(500, "could not start MQTT client")
                        try:
                            DBconn = dbManager.connectDb(remoteDBparams)
                        except:
                            raise cherrypy.HTTPError(500, "could not connect to the remote database")
                        self.requestScheduler.getDailyTable()  # get daily table from DB
                        self.requestScheduler.startSchedule()
                        # {"eventID" : {'cost': 11, 'ticketNum': 20, 'startTime': 16, 'endTime': 18}}
                        self.initialized = True

                # management of the scheduler
                if uri[1] == "MQTT":
                    # sent currently stored daily table to all subscribed gates
                    if uri[2] == "sendDailyTable":
                        if not self.initialized:
                            raise cherrypy.HTTPError(500, "MQTT client not initialized")
                        # self.requestScheduler.getDailyTable() # TO-DO: function to send daily table through MQTT

                if uri[1] == "scheduler":
                    if not self.initialized:
                        raise cherrypy.HTTPError(500, "scheduler initialized")
                    if uri[2] == "start":
                        if self.requestScheduler.on:
                            raise cherrypy.HTTPError(403, "the scheduler is already on")
                        else:
                            print("starting scheduler")
                            self.requestScheduler.startSchedule()
                    if uri[2] == "stop":
                        if not self.requestScheduler.on:
                            raise cherrypy.HTTPError(403, "the scheduler is already off")
                        else:
                            print("stopping scheduler")
                            self.requestScheduler.stop()
                    if uri[2] == "info":  # return the scheduled time
                        return str(self.requestScheduler.requestTime)
                    if uri[2] == "changeTime":
                        # the new time must be put in the url as parameter with name "newTime"
                        if not self.requestScheduler.on:
                            raise cherrypy.HTTPError(403, "the scheduler is off")
                        else:
                            if "newTime" in param.keys():
                                newTime = param["newTime"]
                                if DEBUG:
                                    print("new daily table request time scheduled at ", newTime)
                                self.requestScheduler.changeTime(newTime)
                            else:
                                raise cherrypy.HTTPError(403, "incorrect parameter format")
            else:
                raise cherrypy.HTTPError(404, "invalid url")

    # THIS REST METHOD IS ONLY USED BY THE SYSTEM MANAGER TO UPLOAD IMAGES
    def POST(self, *uri, **param):
        if len(uri) != 0:
            if len(uri) == 1:
                raise cherrypy.HTTPError(404, "invalid url")
            if uri[0] == "img":
                imgName = uri[1]
                if imgName not in self.storedImgs:
                    self.storedImgs.append(imgName)
                raw_payload = cherrypy.request.body.read()
                # print(type(raw_payload))
                with open('eventImgs/'+imgName, "wb") as fp:
                    fp.write(raw_payload)  # write object file as img
            else:
                raise cherrypy.HTTPError(404, "invalid url")

    def getEventList(self, date, language):
        global DBconn
        global catalogData
        # date is a datetime.date object
        # format {1: {'ticketNum': 100, 'ticketLeft': 100, 'cost': 10, 'startTime': '03:00', 'endTime': '04:00',
        # 'EN': {'name': 'EN_test_name', 'info': 'EN_test_desc'}, 'IT': {'name': 'IT_test_name', 'info': 'IT_test_desc'}
        # , 'PL': {'name': 'PL_test_name', 'info': 'PL_test_desc'}, 'URLs': ['testurl1', 'testurl2']}
        if language == "all":
            reqLanguage = ["EN","IT","PL"]
        else:
            reqLanguage = [language]
        eventDict = dbManager.dailySchedule(date, passFlag=False, conn=DBconn, languages=reqLanguage)
        if not eventDict:
            # dictionary is empty
            return None
        else:
            # order events by start time
            sortedEvents = sorted(list(eventDict.items()), key=lambda x: int(x[1]["startTime"].split(':')[0])) # ascending by start hour
            outputList = []
            for event in sortedEvents:
                eventID = event[0]
                dataDict = event[1]
                if language == "all":
                    # send name and desc of all languages
                    tmpDict = {str(eventID): {"IT": dataDict["IT"], "EN": dataDict["EN"], "PL": dataDict["PL"],
                                              "ticketLeft": dataDict["ticketLeft"], "cost": dataDict["cost"],
                                              "time": [dataDict["startTime"], dataDict["endTime"]], "URLs": dataDict["URLs"]}}
                else:
                    languageInfo = dataDict[language]
                    tmpDict = {"id": str(eventID), "name": languageInfo["name"], "description": languageInfo["info"],
                               "price": str(dataDict["cost"]), "ticketLeft": int(dataDict["ticketLeft"])}
                    # TO-DO: add ticketLeft, start and end time once they are implemented in interface
                    # add img urls
                    imgURL_prefix = catalogData.urls["mainSystem"]+'/img/'
                    if dataDict["URLs"][0] is None:
                        tmpDict["patch_img"] = imgURL_prefix+self.ERROR_IMG_NAME
                    else:
                        tmpDict["patch_img"] = imgURL_prefix + dataDict["URLs"][0]

                    if dataDict["URLs"][1] is None:
                        tmpDict["patch_img2"] = imgURL_prefix+self.ERROR_IMG_NAME
                    else:
                        tmpDict["patch_img2"] = imgURL_prefix + dataDict["URLs"][1]

                    if dataDict["URLs"][2] is None:
                        tmpDict["patch_img3"] = imgURL_prefix+self.ERROR_IMG_NAME
                    else:
                        tmpDict["patch_img3"] = imgURL_prefix + dataDict["URLs"][2]
                outputList.append(tmpDict)
            return outputList

    def getDate(self, dateStr):
        cutDateStr = dateStr[0:10]
        print("CUT STR:", cutDateStr)
        dateList = cutDateStr.split('-')
        try:
            return datetime.date(int(dateList[0]), int(dateList[1]), int(dateList[2]))
        except:
            print("incorrect date format, use DD-MM-YYYY")
            raise cherrypy.HTTPError(500, "Error: incorrect date format, use DD-MM-YYYY")


if __name__ == '__main__':
    # open configuration file
    with open(configFileName, "r") as fp:
        config = json.load(fp)
    if "DBparams" not in config:
        raise KeyError("access parameters to the remote DB are missing from the configuration file, "
                       "('DBparams' key is missing)")
    catalogData = SysConfig(config["DBparams"])
    catalogData.requestAll()
    conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tool.session.on': True
        }
    }
    cherrypy.tree.mount(MainSystemREST(), '/', conf)
    ip = config["MainSystem"]["ip"]
    port = config["MainSystem"]["port"]
    cherrypy.config.update({"server.socket_host": str(ip), "server.socket_port": int(port)})
    cherrypy.engine.start()
    cherrypy.engine.block()

