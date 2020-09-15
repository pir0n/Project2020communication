import json
import time
import datetime
import threading
import schedule
import cherrypy
import pyqrcode
from fpdf import FPDF
import email, smtplib, ssl
import png
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pswUpdateMQTTClient import PswMQTTClient
from DeviceCatalogManager import catalog

testEV = 1  # enable fake events  for testing
# MAIN CONTROL OF THE BOOKING SYSTEM, ACCESSIBLE THROUGH REST APIs
# processes:
# password table generation and retrieval from database, conversion to QR code and delivery of code to user through email
# MQTT communication with (possibly) multiple gates to send acceptable passwords
# MORE
DEBUG = True
dailyEventsPswTable = None
catalogData = None


class VirtualTicketHandler:
    global dailyEvents
    global DEBUG  # set to True to print debug messages

# class to control conversion of password to QR code and its delivery to client through e-mail
    def __init__(self, imagePath = "QRCode", pdfPath = "VirtualTicket.pdf"): #.png and .pdf
        self.imgPath = imagePath
        self.pdfPath = pdfPath

    def pswToQr(self, password, filepath):
        # create a .png image of the psw encoded as qr code
        if DEBUG:
            print("encoding:", password)
        QRpsw = pyqrcode.create(password)
        QRpsw.png(filepath+".png", scale=5, module_color=[0, 0, 0, 128], background=[0xff, 0xff, 0xcc])

    def generatePDF(self, n_tickets):
        pdf = FPDF()
        if DEBUG:
            print("creating pdf")
        if n_tickets == 1:
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(0, 10, txt="Virtual Ticket: ", ln=1, align="C")
            pdf.image(self.imgPath+".png", x=48, y=30, w=100)
            # pdf.ln(85)  # move 85 down
            pdf.output(self.pdfPath)
        else:
            i = 0
            while i < n_tickets:
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                pdf.cell(0, 10, txt="Virtual Ticket: ", ln=1, align="C")
                pdf.image(self.imgPath+str(i)+".png", x=48, y=30, w=100)
                # pdf.ln(85)  # move 85 down
                i += 1
            pdf.output(self.pdfPath)

    # NOTE: to speed things up, a connection can be established only once instead of each time
    def sendMail(self, name, receiver_email, event):
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
            subject = f"Virtual ticket for event: {event}"
            body = f"""Dear {name},\n
            Your Virtual Ticket for the event: -{event}- is in the pdf attached to this e-mail
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
    def sendTicket(self, name, mail_addr, event, passwordList):
        if type(passwordList) is list:
            i = 0
            for el in passwordList:
                self.pswToQr(el, self.imgPath + str(i))  # generate a QR png for each psw
                i += 1
            self.generatePDF(len(passwordList)) # pdf with 1 page per ticket
        else:
            self.pswToQr(passwordList, self.imgPath)  # generate a png file in the directory
            self.generatePDF(1)  # generate a pdf containing the QR png in the directory

        self.sendMail(name, mail_addr, event)

    def getPassword(self):
        # TO-DO
        # retrieve a valid password from the table and mark it as used
        pass


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
            except:
                print("Received usedPsw message with bad body format")


# thread for scheduled jobs (daily table request and delivery)
class JobSchedulerThread(threading.Thread):
    # TO-DO: add API call to retrieve database data in method getDailyTable,
    theadStop = False  # stops the thread when set to True
    on = False #indicates if the MQTT client is on

    def __init__(self, dailyEvents, Rtime, subTopics = None):
        # Rtime must be a string of format HH:MM, indicating the time at which the system will update the daily event list
        global catalogData
        global dailyEventsPswTable
        threading.Thread.__init__(self)
        self.eventList = dailyEvents
        self.requestTime = Rtime

        # start MQTT client
        self.MQTTClient = MainSystemMQTT(clientID="MainSystem", brokerPort=catalogData.broker["port"],
                                         MQTTbroker=catalogData.broker["ip"], msgTopics=catalogData.topics,
                                         subscribedTopics=subTopics, initialPswTable=dailyEventsPswTable)
        self.MQTTClient.start()
        self.startSchedule()
        self.on = True

    def getDailyTable(self):
        global dailyEventsPswTable
        today = datetime.date.today()
        # get current date
        currDay = today.day
        currMonth = today.month
        #
        # TO-DO retrieve the daily schedule from the data base
        #
        receivedDailyEvents = {}  # list of dictionaries (from the json formatted string rx by the DB)
        # update global variable dailyEvents
        # self.eventList.clear()
        # update daily event list
        # {“eventID”:{“startTime”:, “endTime”:, “pswTable”:, }
        self.sendDailyTable()  # send daily psw table to MQTT to gates

    def startSchedule(self, Rtime=None, url=None):
        if url is not None:
            self.DailyScheduleURL = url  # allows to change url
        if Rtime is not None:
            self.requestTime = Rtime
        self.on = True
        schedule.every().day.at(self.requestTime).do(self.getDailyTable)
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
        schedule.every().day.at(self.requestTime).do(self.getDailyTable)

    def sendDailyTable(self):
        # send  the daily psw table through MQTT
        global catalogData
        self.MQTTClient.publish(catalogData.topics["newPswTable"], json.dumps(dailyEventsPswTable))


# RESTful interface exposed through cherrypy
class MainSystemREST(object):
    # generate some TEST events
    global testEV
    global dailyEventsPswTable  # on activation the backend should request the daily table to database
    #its a dictionary with format:
    # "eventID":{"pswList": ["","",..], "eventDesc":{"EN":..,"IT":..,"PL":..},"imgURL":..,"eventInfo":{"timeslot":..,"cost":..,etc.}}
    # "eventDesc" contains info that needs to be localized, "language": {"name":.., "desc":..}# TO-DO: add remaining tickets
    if testEV:
        DebugEvents = {
            "0": {"pswList": [], "eventDesc": {
                "EN": {"name": "Fire and Forget at KW Institute for Contemporary Art", "desc": "ENtestdesc0"},
                "PL": {"name": "Pożar i zapomnij w KW Institute for Contemporary Art", "desc": "PLtestdesc0"},
                "IT": {"name": "Fuoco e Dimentica al KW Institute for Contemporary Art", "desc": "ITtestdesc0"}},
                  "imgURL": [], "eventInfo": {"timeslot": [], "cost": "11"}},
            "1": {"pswList": [], "eventDesc": {
                "EN": {"name": "The Natural History Museum", "desc": "ENtestdesc1"},
                "PL": {"name": "Muzeum Historii Naturalnej", "desc": "PLtestdesc1"},
                "IT": {"name": "Il Museo di storia naturale", "desc": "ITtestdesc1"}},
                  "imgURL": [], "eventInfo": {"timeslot": [], "cost": "9"}},
        }

    global DEBUG
    exposed = True
    gateTopics = {"new_psw": "ticketPassword"}  # MQTT topics (for communication with gates)
    DBrequestsURL = {"daily_schedule": "placeholder"}
    # initiate classes
    virtualTicketHandler = VirtualTicketHandler()
    requestScheduler = None # this class must be initialized through the REST API
    initialized = False

    def GET(self, *uri):
        global dailyEventsPswTable
        # requests URL formats:
        # used for commands sent by the GUI(user side) or the system management interface that request a resource
        if len(uri) != 0:
            if uri[0] == "customer":
                if uri[1] == "Events":
                    # return list of daily events
                    if uri[2] == "EN" or uri[2] == "IT" or uri[2] == "PL":
                        language = uri[2]  # EN,IT or PL
                    else:
                        raise cherrypy.HTTPError(404, "invalid URL")
                    outputEventsList = []  # list of dictionaries
                    for event in list(dailyEvents.items()):
                        eventID = event[0]
                        data = event[1]
                        full_desc = data["eventDesc"]
                        loc_desc = full_desc[language]
                        info = data["eventInfo"]
                        outputEventsList.append({"id":eventID, "name": loc_desc["name"], "description": loc_desc["desc"],
                                                 "price": info["cost"]})
                    return json.dumps(outputEventsList)
                else:
                    raise cherrypy.HTTPError(404, "incorrect URL")
            if DEBUG:
                print("GET request received")
            if uri[0] == "gate": # requests made by the gate
                if uri[1] == "pswTable":
                    if dailyEventsPswTable is None:
                        raise cherrypy.HTTPError(500, "daily event table is empty")
                    else:
                        raise json.dumps(dailyEventsPswTable)

    def PUT(self, *uri, **param):
        global dailyEventsPswTable
        global testEV
        global catalogData
        # sent by GUI or system interface to request an action
        if len(uri) != 0:

            # customer services
            if uri[0] == "customer":
                if uri[1] == "newTicket":  # return the chosen password
                    if not self.requestScheduler.on:
                        raise cherrypy.HTTPError(500, "MQTT client is not active")
                    # NOTE: this request takes about 3 seconds to complete
                    # send the virtual ticket to specified address, expects name, address, eventName in the request
                    # body must be a string in the following format
                    # format {"Eventname":"", "mailAddress":"", "event_ID":, "n_tickets":}
                    rawPayload = cherrypy.request.body.read()
                    ReqjsonStr = rawPayload.decode("utf-8")
                    Reqdict = json.loads(ReqjsonStr)
                    # check format of body
                    if not("name" in Reqdict.keys() and "mailAddress" in Reqdict.keys() and "event_name" in Reqdict.keys() \
                            and "event_ID" in Reqdict.keys() and "timeslot" in Reqdict.keys() and "n_tickets" in Reqdict.keys()):
                        raise cherrypy.HTTPError(500, "invalid request format")
                    # send eventID, timeslot, e-mail, n_tickets to DB, DB returns n passwords (JSON  list)
                    # send password to the user
                    if testEV:
                        sel_psws = ["test1", "test2"]  # placeholder password because database not yet implemented
                    if DEBUG:
                        print(f'sending QR code to {Reqdict["name"]}, mail:{Reqdict["mailAddress"]} for event: {Reqdict["event_name"]}')

                    self.virtualTicketHandler.sendTicket(Reqdict["name"], Reqdict["mailAddress"], Reqdict["event_name"],
                                                         sel_psws)
                    # insert password in daily table and send to gates IF the event is in daily table
                    if Reqdict["event_ID"] in dailyEventsPswTable:  # check if event in daily table
                        # insert psw in daily psw table and then send a "newPsw" MQTT message to gates
                        if type(sel_psws) is list:
                            for psw in sel_psws:
                                dailyEventsPswTable[Reqdict["event_ID"]]["pswTable"].append({"psw": psw, "used": False})
                                # send the password to the gates through MQTT
                                # msg format : {"eventID":, "psw":}
                                dict_msg = {"eventID": Reqdict["event_ID"], "psw":psw}
                                json_msg = json.dumps(dict_msg)
                                self.requestScheduler.MQTTClient.publish(catalogData.topics["newPsw"], json_msg)
                        else:
                            dailyEventsPswTable[Reqdict["event_ID"]]["pswTable"].append({"psw": sel_psws, "used": False})                            # send the password to the gates through MQTT
                            # msg format : {"eventID":, "psw":}
                            dict_msg = {"eventID": Reqdict["event_ID"], "psw": sel_psws}
                            json_msg = json.dumps(dict_msg)
                            self.requestScheduler.MQTTClient.publish(catalogData.topics["newPsw"], json_msg)

            # system management
            if uri[0] == "system":
                # management of the MQTT client
                if uri[1] == "start":  # THIS SHOULD ALWAYS BE CALLED AFTER SCRIPT IS EXECUTED
                    if not self.initialized:
                        #
                        # TO-DO: request daily schedule from DB
                        #
                        dailyEventPsw = {}
                        self.requestScheduler = JobSchedulerThread(dailyEventPsw, "00:00", catalogData.topics["pswUsed"])
                        self.requestScheduler.startSchedule()

                # if uri[1] == "MQTTclient": # TO:DO- update part
                #     if uri[2] == "start":
                #         if self.mqtt.on:
                #             raise cherrypy.HTTPError(403, "the MQTT client is already on")
                #         else:
                #             self.mqtt.start()
                #             self.mqtt.on = True
                #     elif uri[2] == "stop":
                #         if not self.mqtt.on:
                #             raise cherrypy.HTTPError(403, "the MQTT client is already off")
                #         else:
                #             self.mqtt.stop()
                #             self.mqtt.on = False
                #     elif uri[2] == "status":
                #         return str(self.mqtt.on)
                #     else:
                #         raise cherrypy.HTTPError(404, "invalid request")

                # management of the scheduler
                if uri[1] == "scheduler":
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
                            # TO-DO take new time from parameters
                            if "newTime" in param.keys():
                                newTime = param["newTime"]
                                if DEBUG:
                                    print("new daily table request time scheduled at ", newTime)
                                self.requestScheduler.changeTime(newTime)
                            else:
                                raise cherrypy.HTTPError(403, "incorrect parameter format")


if __name__ == '__main__':
    catalogData = catalog()
    catalogData.requestAll()
    conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tool.session.on': True
        }
    }
    cherrypy.tree.mount(MainSystemREST(), '/', conf)
    cherrypy.engine.start()
    cherrypy.engine.block()





