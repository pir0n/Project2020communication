import cv2
import numpy as np
import pyzbar.pyzbar as pyzbar
from DeviceCatalogManager import catalog
import time
from datetime import datetime
import json
from pswUpdateMQTTClient import PswMQTTClient
catalogData = None

class GateMQTT(PswMQTTClient):

    def ticketCheck(self, eventID, psw):
        # RETURN VALUES:
        # 0: password accepted and sent to other gates to set them as used
        # -1: eventID not in table, psw not in eventID psw list or it has been used already, curr time>endTime for event
        # 1: current time< startTime for event
        # check if the eventID is scheduled for current time
        # then check if the password is in the list and if it is not used

        # DEBUG VALUE FOR CURRENT TIME
        debugTimeStr = "12-10-2020 12:30"
        currTime = datetime.strptime(debugTimeStr, "%d-%m-%Y %H:%M")  # dd-mm-yyyy hh-mm
        # currTime = datetime.now()

        start, end = self.getEventTime(eventID)
        if start is None or end is None:
            if self.DEBUG:
                print(f"event:{eventID} not found in psw table")
            return -1  # eventID not found in table
        eventStart = currTime.replace(hour=start[0], minute=start[1])
        eventEnd = currTime.replace(hour=end[0], minute=end[1])
        if eventStart > currTime:
            if self.DEBUG:
                print(f"event:{eventID} start is scheduled for {eventStart.strftime('%H:%M')} now it's "
                      f"{currTime.strftime('%H:%M')}")
            return 1  # event is not happening at current time
        if eventEnd < currTime:
            if self.DEBUG:
                print(f"event:{eventID} end was scheduled for {eventEnd.strftime('%H:%M')} now it's "
                      f"{currTime.strftime('%H:%M')}")
            return -1
        if self.setPswUsedFromScan(eventID, psw):
            # password was not used
            self.sendPswUsed(eventID, psw)
        else:
            return -1
            # password is used or not present in the eventID list
        return True

    def getEventTime(self, eventID):
        # time is stored as HH:MM
        if eventID not in self.pswTable:
            return None, None
        # pswTable has format{“eventID”:{“startTime”:, “endTime”:, “pswTable”:, }; times are str of format HH:MM
        return self.pswTable[eventID]["startTime"].split(':'), self.pswTable[eventID]["endTime"].split(':')

    def setPswUsedFromScan(self, eventID, eventPsw):
        for psw in self.pswTable[eventID]["pswTable"]:
            if eventPsw == psw["psw"]:
                if psw["used"]:
                    if self.DEBUG:
                        print(f"password {psw} for event:{eventID} has already been used")
                    return False
                else:
                    psw["used"] = True
                    if self.DEBUG:
                        print(f"setting password {psw} for event:{eventID} as used")
                    return True
        return False

    def sendPswUsed(self, eventID, psw):
        global catalogData
        # send msg format: {"eventID":, "psw":}
        msg_body = json.dumps({"eventID": eventID, "psw": psw})
        self.publish(catalogData.topics["pswUsed"], msg_body)

class GateSystem:
    def __init__(self, clientID, MQTTbroker, msgTopics, brokerPort = 1883, Qos = 2, initialPswTable = None):
        global catalogData
        # gates subscribe to newPsw, newPswTable and pswUsed topics
        subscribedTopics = [catalogData.topics["newPsw"], catalogData.topics["newPswTable"], catalogData.topics["pswUsed"]]
        self.MQTT = GateMQTT(clientID, catalogData.broker["ip"], msgTopics=catalogData.topics,
                             brokerPort=catalogData.broker["port"], subscribedTopics=subscribedTopics, initialPswTable=initialPswTable)
        # start listener loop and subscribe to topics
        self.MQTT.start()

        # video capture
        self.cap = cv2.VideoCapture(0)
        self.font = cv2.FONT_HERSHEY_PLAIN
        self.stop = False

    # loop that checks the camera for qr codes
    def cameraLoop(self):
        while not self.stop:
            _, frame = self.cap.read()
            lastcheckedStr = ""
            decodedObjects = pyzbar.decode(frame)
            retryCount = 0
            for obj in decodedObjects:
                skip = False
                ticketJSON = obj.data.decode('utf-8')# expected format: {"eventID": eventID, "psw": password}
                if ticketJSON != lastcheckedStr:  # used so we dont call ticketCheck() multiple times
                    try:
                        ticketDict = json.loads(ticketJSON)
                    except:
                        print("encoded string is not in valid JSON format")
                        skip = True
                    if not skip:
                        try:
                            eventID = ticketDict["eventID"]
                            psw = ticketDict["psw"]
                        except:
                            print("JSON string doesn't have the correct keys")
                            skip = True
                        if not skip:
                            retVal = self.MQTT.ticketCheck(eventID, psw)
                            if retVal == 0 or retVal == -1:
                                # psw has been processed or is invalid
                                # stop processing this json str
                                lastcheckedStr = ticketJSON
                            if retVal == 1:
                                # event hasn't started yet
                                # display message with starting time of event
                                pass
                print("Decoded data", obj.data.decode('utf-8'), type(obj.data.decode('utf-8')))  # byte type
                # cv2.putText(frame, str(obj.data), (50, 50), font, 2,(255, 0, 0), 3)

            # show video capture
            cv2.imshow("Frame", frame)
            key = cv2.waitKey(1)


if __name__ == '__main__':
    # GET request to catalog for system info
    # GET request to main system for daily table
    # instatiate class and start MQTT client
    # start camera loop

    debugTimeStr = "12-10-2020 12:30"
    currTime = datetime.strptime(debugTimeStr, "%d-%m-%Y %H:%M")  # dd-mm-yyyy hh-mm
    print(currTime.strftime("%H:%M"))
    pass

