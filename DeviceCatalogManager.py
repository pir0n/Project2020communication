import json
import requests


# class to implement communication with the home catalog
# and store its information
# to retrieve all information from the home catalog call method requestALL()
# information can be accessed through the attributes .topics, .urls, .broker; dictionary keys are the same as in the
# catalog data .json file
class catalog:
    requestsFormat = {"urls request": "/urls", "topics request": "/topics",
                      "broker url request": "/broker", "all": "/all", "db parameters":"/dbParams"}

    def __init__(self, homeCatalogURL, homeCatalogPort, requestsFormat = None):
        if not homeCatalogURL.startswith("http://"):
            self.catalogURL = "http://"+homeCatalogURL+':'+str(homeCatalogPort)
        else:
            self.catalogURL = homeCatalogURL+':'+str(homeCatalogPort)
        self.topics = {}
        self.urls = {}
        self.broker = {}
        self.dbParams = {}

    def requestURLS(self):
        r = requests.get(self.catalogURL+self.requestsFormat["urls request"])
        rawData = r.content
        self.urls = json.loads(rawData)

    def requestTopics(self):
        r = requests.get(self.catalogURL + self.requestsFormat["topics request"])
        rawData = r.content
        self.topics = json.loads(rawData)

    def requestBrokerInfo(self):
        r = requests.get(self.catalogURL + self.requestsFormat["topics request"])
        rawData = r.content
        self.broker = json.loads(rawData)

    def requestDbParams(self):
        r = requests.get(self.catalogURL + self.requestsFormat["db parameters"])
        rawData = r.content
        self.dbParams = json.loads(rawData)

    def requestAll(self):  # get broker urls, topics and urls
        r = requests.get(self.catalogURL + self.requestsFormat["all"])
        if r.status_code != 200:  # expected status code
            raise ConnectionError("unexpected status code from home catalog")
        rawData = r.content
        jsonDict = json.loads(rawData.decode('utf-8'))
        try:
            self.urls = jsonDict["urls"]
        except:
            raise KeyError("data from home catalog has no 'urls' key")
        try:
            self.topics = jsonDict["topics"]
        except:
            raise KeyError("data from home catalog has no 'topics' key")
        try:
            self.broker = jsonDict["broker"]
        except:
            raise KeyError("data from home catalog has no 'broker' key")
        try:
            self.dbParams = jsonDict["dbParams"]
        except:
            raise KeyError("data from home catalog has no 'dbParams' key")
        return True


