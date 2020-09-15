from MQTTClient import MQTT_client
import json


class PswMQTTClient(MQTT_client):

    def __init__(self, clientID, MQTTbroker, msgTopics, brokerPort = 1883, Qos = 2, subscribedTopics = None, initialPswTable = None):
        MQTT_client.__init__(clientID, MQTTbroker, brokerPort, Qos, subscribedTopics)
        if not("newPsw" in msgTopics and "newPswTable" in msgTopics and "pswUsed" in msgTopics):
            raise KeyError("msgTopics dict has incorrect keys")
        else:
            self.msgTopics = msgTopics
        if initialPswTable is not None:
            self.pswTable = initialPswTable

    def myOnMessageReceived(self, client, userdata, msg):
        # main system won't subscribe to newPswTable topic
        if msg.topic == self.msgTopics["newPsw"]:
            newPswDict = json.loads(msg.payload.decode('utf-8'))
            try:
                self.addPswEntry(newPswDict)
            except:
                print("Received newPsw message with bad body format or for eventID not present in the table")
            # ADD THE ENTRY INSIDE THE PASSWORD TABLE
            pass
        elif msg.topic == self.msgTopics["pswUsed"]:
            # SET SPECIFIED PASSWORD AS USED
            usedPswDict = json.loads(msg.payload.decode('utf-8'))
            try:
                self.setPswUsed(usedPswDict)
            except:
                print("Received usedPsw message with bad body format")
        elif msg.topic == self.msgTopics["newPswTable"]:
            # OVERWRITE PSW TABLE
            newPswTable = json.loads(msg.payload.decode('utf-8'))
            try:
                self.setPswTable(newPswTable)
            except:
                print("Received newPswTable message with bad table format")

    def addPswEntry(self, newPswDict):
        # msg format : {"eventID":, "psw":}
        if "eventID" in newPswDict and "psw" in newPswDict:
            if newPswDict["eventID"] in self.pswTable:
                self.pswTable[newPswDict["eventID"]]["pswTable"].append({"psw": newPswDict["psw"], "used": False})
            else:
                raise KeyError(f"id: {newPswDict['eventID']} not present in psw table")
        else:
            raise KeyError(f"incorrect data format")

    def setPswUsed(self, usedPswDict):
        # msg format : {"eventID":, "psw":}
        if "eventID" in usedPswDict and "psw" in usedPswDict:
            if usedPswDict["eventID"] in self.pswTable:
                found = False
                for psw in self.pswTable[usedPswDict["eventID"]]:  # search in the psw list
                    if usedPswDict["psw"] == psw["psw"]:
                        psw["used"] = True
                        found = True
                        break
                if not found:
                    print(f"password {usedPswDict['psw']} not found in {usedPswDict['eventID']} list")
            else:
                raise KeyError(f"id: {usedPswDict['eventID']} not present in psw table")
        else:
            raise KeyError(f"incorrect data format")

    def setPswTable(self, newPswTable):
        # msg format : {“eventID”:{“startTime”:, “endTime”:, “pswTable”:, }}
        # PswTable has format {“psw”:numericalPsw, “used”:boolVar}
        # check if format is correct
        for event in list(newPswTable.items()):
            if not("startTime" in event[1] and "endTime" in event[1] and "pswTable" in event[1]):
                raise KeyError(f"{event[0]} has a bad data format")
        self.pswTable.clear()
        self.pswTable = newPswTable