# resource catalog web service: exposing the data to others by GET; the web page can be updated by POST

import cherrypy
import json
dataFileName = "catalogData.json"

class resourceCatalog(object):
    exposed = True
    def GET(self, *uri, **params):
        global dataFileName
        # reading the file with the informations
        try:
            file = open(dataFileName, "r")
            self.jsonString = file.read()
            file.close()
        except:
            raise KeyError("* resourceCatalog: ERROR IN READING INITIAL DATA *")
        self.jsonDic = json.loads(self.jsonString)
        # item will contain the request information
        try:
            item = uri[0]
            if (item in self.jsonDic):
                result = self.jsonDic[item]
                requestedData = json.dumps(result)
                return requestedData
            elif (item == "all"):
                return self.jsonString
            else:
                raise cherrypy.HTTPError(404, "invalid url")
        except:
            raise cherrypy.HTTPError(404, "invalid url")


if __name__ == '__main__':
    # reading the config file to set the url and the port on which expose the web service
    file = open("configFile.json", "r")
    jsonString = file.read()
    file.close()
    data = json.loads(jsonString)
    ip = data["resourceCatalog"]["ip"]
    port = data["resourceCatalog"]["port"]
    # client = mqtt.Client()
    # configuration for the web service
    conf = { '/': { 'request.dispatch': cherrypy.dispatch.MethodDispatcher(), 'tools.sessions.on': True } }
    cherrypy.tree.mount(resourceCatalog(), '/', conf)
    cherrypy.config.update({"server.socket_host": str(ip), "server.socket_port": int(port)})
    cherrypy.engine.start()
    cherrypy.engine.block()