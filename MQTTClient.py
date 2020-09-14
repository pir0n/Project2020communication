import paho.mqtt.client as PahoMQTT
import time


class MQTT_client:

    def __init__(self, clientID, MQTTbroker, brokerPort = 1883, Qos = 2, subscribedTopics = None):
        self.ID = str(clientID)
        self.MQTTbroker = MQTTbroker
        self.Qos = Qos
        self.brokerPort = brokerPort
        self.MQTTclient = PahoMQTT.Client(self.ID, False)
        self.MQTTclient.on_connect = self.myOnConnect
        self.MQTTclient.on_message = self.myOnMessageReceived
        self.subscribedTopics = []
        if subscribedTopics is not None:
            if type(subscribedTopics) is list:
                for topic in subscribedTopics:
                    self.subscribedTopics.append(topic)
            else:
                self.subscribedTopics.append(subscribedTopics)

    def start(self):  # connect to broker and subscribe to topics in the list
        self.MQTTclient.connect(self.MQTTbroker, self.brokerPort)
        self.MQTTclient.loop_start()
        if len(self.subscribedTopics) > 0:
            for topic in self.subscribedTopics:
                self.MQTTclient.subscribe(topic, self.Qos)
                print(f"-{self.ID}-: subscribed to topic:{topic}")

    def stop(self):
        self.unsubscribe(unsubToAll=True)
        self.MQTTclient.loop_stop()
        self.MQTTclient.disconnect()
        print(f"-{self.ID}-: disconnected")

    def myOnConnect(self, client, userdata, flags, rc):
        print(f"-{self.ID}-: connected to {self.MQTTbroker} with result code {rc}")

    def myOnMessageReceived(self, client, userdata, msg):
        print(f"-{self.ID}-: received message with topic: {msg.topic}, Qos: {msg.qos}, payload: {msg.payload}")

    def publish(self, topic, message):
        self.MQTTclient.publish(topic, message, self.Qos)
        print(f"-{self.ID}-: published message with topic:{topic}, payload: {message}")

    def subscribe(self, topics):  # topics can be a string or a list of strings
        if type(topics) is list:
            for topic in topics:
                self.subscribedTopics.append(topic)
                self.MQTTclient.subscribe(topic, self.Qos)
                print(f"-{self.ID}-: subscribed to topic:{topic}")
        else:
            self.subscribedTopics.append(topics)
            self.MQTTclient.subscribe(topics, self.Qos)
            print(f"-{self.ID}-: subscribed to topic:{topics}")

    def unsubscribe(self, topics=None, unsubToAll=False):
        if unsubToAll:
            while len(self.subscribedTopics) != 0:
                topic = self.subscribedTopics.pop()
                self.MQTTclient.unsubscribe(topic)
        else:
            if type(topics) is list:
                for topic in topics:
                    if topic in self.subscribedTopics:
                        self.subscribedTopics.remove(topic)
                        self.MQTTclient.unsubscribe(topic)
                        print(f"-{self.ID}-: unsubscribed from topic:{topic}")
            else:
                if topics in self.subscribedTopics:
                    self.subscribedTopics.remove(topics)
                    self.MQTTclient.unsubscribe(topics)
                    print(f"-{self.ID}-: unsubscribed from topic:{topics}")


if __name__=='__main__':
    #  test script
    MQTTbroker = 'test.mosquitto.org'
    testPublisher1 = MQTT_client("testPub1", MQTTbroker)
    testSubscriber1 = MQTT_client("testSub1", MQTTbroker)
    testSubscriber2 = MQTT_client("testSub2", MQTTbroker)
    testTopics = ["test/topic/1", "test/topic/2", "test/topic/3"]
    # start clients
    testPublisher1.start()
    testSubscriber2.start()
    testSubscriber1.start()
    testSubscriber1.subscribe('test/+/2')  # receives all messages with topic starting with test/ and ending with /2
    time.sleep(1)
    testSubscriber2.subscribe('test/topic/#')  # receives all messages with topic starting with test/topic/
    time.sleep(1)
    for topic in testTopics:
        testPublisher1.publish(topic, "test payload")
    time.sleep(1)
    time.sleep(5)
    testPublisher1.stop()
    testSubscriber1.stop()
    testSubscriber2.stop()
