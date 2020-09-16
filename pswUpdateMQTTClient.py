from MQTTClient import MQTT_client
import json
import time


class PswMQTTClient(MQTT_client):
    DEBUG = False
    pswTable = {}

    def __init__(self, clientID, MQTTbroker, msgTopics, brokerPort = 1883, Qos = 2, subscribedTopics = None, initialPswTable = None):
        MQTT_client.__init__(self, clientID, MQTTbroker, brokerPort, Qos, subscribedTopics)
        if not("newPsw" in msgTopics and "newPswTable" in msgTopics and "pswUsed" in msgTopics):
            raise KeyError("msgTopics dict has incorrect keys")
        else:
            self.msgTopics = msgTopics
        if initialPswTable is not None:
            self.pswTable = initialPswTable

    def myOnMessageReceived(self, client, userdata, msg):
        # main system won't subscribe to newPswTable topic
        if msg.topic == self.msgTopics["newPsw"]:
            # ADD THE ENTRY INSIDE THE PASSWORD TABLE
            newPswDict = json.loads(msg.payload.decode('utf-8'))
            try:
                self.addPswEntry(newPswDict)
                if self.DEBUG:
                    print("added new password entry:", newPswDict)
                    print(f'psw list for {str(newPswDict["eventID"])}: {self.pswTable[str(newPswDict["eventID"])]["pswTable"]}')
            except:
                print("Received newPsw message with bad body format or for eventID not present in the table")
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
                if self.DEBUG:
                    print("received newPswTable msg, updated psw table: ", self.pswTable)
            except:
                print("Received newPswTable message with bad table format")

    def addPswEntry(self, newPswDict):
        # msg format : {"eventID":, "psw":}
        if "eventID" in newPswDict and "psw" in newPswDict:
            if str(newPswDict["eventID"]) in self.pswTable:
                self.pswTable[str(newPswDict["eventID"])]["pswTable"].append({"psw": newPswDict["psw"], "used": False})
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
                        if self.DEBUG:
                            print(f"setting psw: {psw['psw']} of event: {usedPswDict['eventID']} as used")
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
        if self.DEBUG:
            print("received psw table:", newPswTable)
        for event in list(newPswTable.items()):
            if not("startTime" in event[1] and "endTime" in event[1] and "pswTable" in event[1]):
                print(f"{event[0]} has a bad data format: {event[1]}")
                #raise KeyError(f"{event[0]} has a bad data format")
        self.pswTable.clear()
        self.pswTable = newPswTable

if __name__=="__main__":
    # test psw used command
    msgTopics = {"newPsw": "pswTable/newPsw", "newPswTable": "pswTable/newTable", "pswUsed": "pswTable/pswUsed"}
    test2 = PswMQTTClient("gateTest1", "test.mosquitto.org", msgTopics= msgTopics, subscribedTopics = ["pswTable/newPsw", "pswTable/newTable"])
    test2.DEBUG = True
    test2.start()
    pswUsed = {"eventID": '8', "psw": '5'}
    time.sleep(10)
    test2.publish("pswTable/pswUsed", json.dumps(pswUsed))