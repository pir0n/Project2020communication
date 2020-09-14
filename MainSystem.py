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
from MQTTClient import MQTT_client

testEV = 1  # enable fake events  for testing
# MAIN CONTROL OF THE BOOKING SYSTEM, ACCESSIBLE THROUGH REST APIs
# processes:
# password table generation and retrieval from database, conversion to QR code and delivery of code to user through email
# MQTT communication with (possibly) multiple gates to send acceptable passwords
# MORE
DEBUG = True
dailyEvents = None

class VirtualTicketHandler:
    global dailyEvents
    global DEBUG  # set to True to print debug messages

# class to control conversion of password to QR code and its delivery to client and (possibly) gate
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
    def sendTicket(self, name, mail_addr, event, timeslot, passwordList):
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

class MQTT_MSclient(MQTT_client):
    on = False

# thread for scheduled jobs (daily table request and delivery)
class JobSchedulerThread(threading.Thread):
    theadStop = False  # stops the thread when set to True
    on = False

    def __init__(self, DailyScheduleURL, dailyEvents, Rtime):
        threading.Thread.__init__(self)
        self.DailyScheduleURL = DailyScheduleURL
        self.eventList = dailyEvents
        self.requestTime = Rtime

    def getDailyTable(self):
        today = datetime.date.today()
        # get current date
        currDay = today.day
        currMonth = today.month
        #
        # TO-DO retrieve the daily schedule from the data base
        #
        receivedEvents = [] # list of dictionaries (from the json formatted string rx by the DB)
        # format: eventinfo = {"EN":.., "IT":..., "PL":...,}
        self.eventList.clear()
        # update daily event list
        for event in receivedEvents:
            self.eventList.append(event)

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


# RESTful interface exposed through cherrypy
class MainSystemREST(object):
    # generate some TEST events
    global testEV
    global dailyEvents  # on activation the backend should request the daily table to database
    #its a dictionary with format:
    # "eventID":{"pswList": ["","",..], "eventDesc":{"EN":..,"IT":..,"PL":..},"imgURL":..,"eventInfo":{"timeslot":..,"cost":..,etc.}}
    # "eventDesc" contains info that needs to be localized, "language": {"name":.., "desc":..}# TO-DO: add remaining tickets
    if testEV:
        dailyEvents = {
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
    requestScheduler = JobSchedulerThread(DBrequestsURL["daily_schedule"], dailyEvents, "23:59")
    mqtt = MQTT_MSclient("MainSystem", "test.mosquitto.org")

    def GET(self, *uri):
        global dailyEvents
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

    def PUT(self, *uri, **param):
        global dailyEvents
        global testEV
        # sent by GUI or system interface to request an action
        if len(uri) != 0:

            # customer services
            if uri[0] == "customer":
                if uri[1] == "newTicket":  # return the chosen password
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
                                                         Reqdict["timeslot"], sel_psws)
                    # insert password in daily table and send to gates IF the event is in daily table
                    if Reqdict["event_ID"] in list(dailyEvents.keys()):  # check if event in daily table
                        # to-do timeslot manamgemet (event with multiple timeslots)
                        # for multiple tickets, each one is handled independently
                        if type(sel_psws) is list:
                            for psw in sel_psws:
                                event = dailyEvents[Reqdict["event_ID"]]
                                event["pswList"].append(psw)
                            # send the password to the gates through MQTT
                                if self.mqtt.on:
                                        dict_msg = {"password": psw, "event_ID": Reqdict["event_ID"], "email": Reqdict["mailAddress"]}
                                        json_msg = json.dumps(dict_msg)
                                        self.mqtt.publish(self.gateTopics["new_psw"], json_msg)
                        else:
                            event = dailyEvents[Reqdict["event_ID"]]
                            event["pswList"].append(sel_psws)
                            # send the password to the gates through MQTT
                            if self.mqtt.on:
                                dict_msg = {"password": sel_psws, "event_ID": Reqdict["event_ID"],
                                            "email": Reqdict["mailAddress"]}
                                json_msg = json.dumps(dict_msg)
                                self.mqtt.publish(self.gateTopics["new_psw"], json_msg)

            # system management
            if uri[0] == "system":
                # management of the MQTT client
                if uri[1] == "MQTTclient":
                    if uri[2] == "start":
                        if self.mqtt.on:
                            raise cherrypy.HTTPError(403, "the MQTT client is already on")
                        else:
                            self.mqtt.start()
                            self.mqtt.on = True
                    elif uri[2] == "stop":
                        if not self.mqtt.on:
                            raise cherrypy.HTTPError(403, "the MQTT client is already off")
                        else:
                            self.mqtt.stop()
                            self.mqtt.on = False
                    elif uri[2] == "status":
                        return str(self.mqtt.on)
                    else:
                        raise cherrypy.HTTPError(404, "invalid request")

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
    conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tool.session.on': True
        }
    }
    cherrypy.tree.mount(MainSystemREST(), '/', conf)
    cherrypy.engine.start()
    cherrypy.engine.block()





