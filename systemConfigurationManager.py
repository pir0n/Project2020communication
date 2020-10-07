import dbManager.dbManager as dbManager
import json
# class to manage and request configuration data stored in the database
class SysConfig:
    DBcursor = None
    retrievedData = False
    tableSet = False
    # attributes to store system config data
    urls = {}  # public URLs
    topics = {}
    broker = {}  # MQTT broker

    # PARAMETERS
    topic_indexes = {"newPsw": 0, "newPswTable": 1, "pswUsed": 2} # indexes of MQTT topics in DB

    def __init__(self, DBparams):
        self.DBparams = DBparams
        # connect to database
        self.connect()

    def connect(self):
        # connect to database
        if self.DBcursor is None:
            try:
                self.DBcursor = dbManager.connectDb(self.DBparams)
            except:
                print("ERROR: could not connect to DB")
        else:
            print("already connected to DB")

    def requestAll(self):
        if self.DBcursor is None:
            print("ERROR: connection to DB has not been established")
            return False
        catalogData = dbManager.retreiveCatalog(self.DBcursor)
        self.storeURLS(catalogData["urls"])
        self.urls["MQTTbroker"] = catalogData["urls"]["MQTTbroker"]
        self.storeMQTTtopics(catalogData["topics"])  # stores in self.topics
        self.retrievedData = True
        dbManager.disconnectDb(self.DBcursor)
        self.DBcursor = None
        return True

    def storeMQTTtopics(self, DBlist):
        MQTTtopics = DBlist[-3:]  # get 3 elements (newest inserted elements)
        for topic_i in list(self.topic_indexes.items()):
            self.topics[topic_i[0]] = MQTTtopics[topic_i[1]]

    def storeURLS(self, URLdict):
        self.urls["mainSystem"] = URLdict["mainSystem"]  # just store the URL for MainSys
        broker_ip_port = URLdict["MQTTbroker"].split(':')
        try:
            self.broker["ip"] = broker_ip_port[0]
            self.broker["port"] = int(broker_ip_port[1])
        except:
            print("MQTT broker stored in incorrect format")

    def getTopics(self):
        if not self.retrievedData:
            if not self.requestAll():
                print("ERROR: data was not retrieved and could not connect to DB")
                return None
        return self.topics  # return dictionary
