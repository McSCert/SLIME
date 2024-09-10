# Standard library
import time
import csv
import socket
import typing
# Third party
import pika


class QuickSocketServer:
    def __init__(self, port):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.bind(("localhost", port))
        self.s.listen(1)
        (self.client, self.address) = self.s.accept()
        self.stack = []

    def push(self, msg):
        self.stack.append(msg)

    def listen(self) -> str:
        if self.stack:
            return self.stack.pop()
        try:
            msg = self.client.recv(1024).strip()
            if type(msg) == bytes:
                msg = msg.decode()
            return msg
        except:
            print("LISTEN ERROR")

    def send(self, msg):
        try:
            msg = msg + "\n"
            self.client.sendall(msg.encode('utf-8'))
        except:
            print("SEND ERROR")

    def close(self):
        self.client.close()
        self.s.close()


class QuickSocketClient:
    def __init__(self, port):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.connect(("localhost", port))
        self.stack = []

    def push(self, msg):
        self.stack.append(msg)

    def listen(self) -> str:
        if self.stack:
            return self.stack.pop()
        msg = self.s.recv(1024).strip()
        if type(msg) == bytes:
            msg = msg.decode()
        return msg

    def send(self, msg):
        msg = msg + "\n"
        self.s.sendall(msg.encode('utf-8'))

    def close(self):
        self.s.close()


class FakeSocketClient:
    def __init__(self, fname = "logs/queries.csv"):
        with open(fname, "r", newline='') as f:  
            # reader = csv.reader(x.replace('\0', '') for x in f) when using encoding='utf-16'
            reader = csv.reader(f)
            self.data = list(reader)
            self.i = 0

    def listen(self) -> str:
        if self.i < len(self.data):
            if len(self.data[self.i]) >= 1:
                query = self.data[self.i][0]
                self.i += 1
                if query:
                    return query
        return None

    def send(self, msg):
        pass

    def close(self):
        pass

class QuickSocketSimulator:
    # for testing interactively over console
    def __init__(self, port):
        self.port = port

    def listen(self):
        msg = input(">")
        return str(msg).strip()

    def send(self, msg):
        print(msg)

    def close(self):
        print("test socket closed (this does nothing!)")


#new rabbit client, possibly call main program Fudd, because it hunts for bugs, fuzzing/finding unknown deployment ??? debugging??? (this can be the name of the class that reads the state machine to find bugs)
class Bugs:
    """wrapper for pika to easily connect with rabbitmq"""
    def __init__(self, queue: str, server: bool, remote_credentials: dict = None):
        # s-queue: mail that goes to server
        # c-queue: mail that goes to client
        if server:
            self.sendq = "c-" + queue
            self.recvq = "s-" + queue
        else:
            self.sendq = "s-" + queue
            self.recvq = "c-" + queue
        self.lastmsg = ""
        self.qresmsg = ""
        self.log = []
        if remote_credentials is None or type(remote_credentials) != dict:
            self.pika_parameters = pika.ConnectionParameters(host='localhost')
        else:
            credentials = pika.PlainCredentials(remote_credentials["user"], remote_credentials["pass"])
            self.pika_parameters = pika.ConnectionParameters(remote_credentials["host"], remote_credentials["port"], '/', credentials)

    def initQueues(self):
        self.logAppend("init-queues", "start")
        self.send("")
        self.sendq, self.recvq = self.recvq, self.sendq
        self.send("")
        self.sendq, self.recvq = self.recvq, self.sendq
        self.clear()
        self.logAppend("init-queues", "end")

    def logAppend(self, entryLabel, entryString):
        # self.log.append([entryLabel, entryString, time.time()])
        # todo: use https://docs.python.org/3/howto/logging-cookbook.html
        pass

    def encode(self, msg):
        # messages need to be encoded as bytes and terminate with a \n
        msg = str(msg) + "\n"
        return msg.encode('utf-8')

    def decode(self, msg):
        msg = msg.strip() # remove \n from encoding, may remove extra whitespace too but this is fine
        if type(msg) == bytes:
            msg = msg.decode()
        return msg

    def callback(self, ch, method, properties, body):
        ch.stop_consuming()
        self.lastmsg = self.decode(body)

    def listen(self, timeout:float = None) -> str:
        connection = pika.BlockingConnection(self.pika_parameters)
        channel = connection.channel()
        channel.queue_declare(queue=self.recvq)
        if timeout == None:
            channel.basic_consume(on_message_callback = self.callback, queue=self.recvq, auto_ack = True)
            channel.start_consuming()
        else:
            # https://pika.readthedocs.io/en/stable/examples/blocking_consumer_generator.html
            for method_frame, properties, body in channel.consume(queue=self.recvq, auto_ack = True, inactivity_timeout=timeout):
                if body == None:
                    self.lastmsg = "TIMEOUT"
                    break
                else:
                    self.lastmsg = self.decode(body)
                    # channel.basic_ack(method_frame.delivery_tag)
                    break
        # Cancel the consumer and return any pending messages
        # requeued_messages = channel.cancel()
        # channel.close()
        connection.close()
        self.logAppend("listen", str(self.lastmsg))
        return self.lastmsg

    def get(self):
        connection = pika.BlockingConnection(self.pika_parameters)
        channel = connection.channel()
        method_frame, header_frame, body = channel.basic_get(self.recvq)
        if method_frame:
                #print(method_frame, header_frame, body)
                channel.basic_ack(method_frame.delivery_tag)
                connection.close()
                self.lastmsg = self.decode(body)
                self.logAppend("get", str(self.lastmsg))
                return self.lastmsg
        else:
                connection.close()
                return None

    def send(self, msg):
        self.logAppend("send", str(msg))
        connection = pika.BlockingConnection(self.pika_parameters)
        channel = connection.channel()

        channel.queue_declare(queue=self.sendq)

        channel.basic_publish(exchange='',
            routing_key=self.sendq,
            body=self.encode(msg))
        connection.close()

    def requeue(self, msg):
        self.logAppend("requeue", str(msg))
        connection = pika.BlockingConnection(self.pika_parameters)
        channel = connection.channel()

        channel.queue_declare(queue=self.recvq)

        channel.basic_publish(exchange='',
            routing_key=self.recvq,
            body=self.encode(msg))
        connection.close()

    def getlastmsg(self):
        return self.lastmsg

    def qlen(self, recv = True):
        connection = pika.BlockingConnection(self.pika_parameters)
        channel = connection.channel()
        if recv:
            q = channel.queue_declare(self.recvq)
        else:
            q = channel.queue_declare(self.sendq)
        q_len = q.method.message_count
        connection.close()
        return q_len

    def clear(self, sendq = True, recvq = True):
        if sendq:
            self.logAppend("clear-sendq", "start")
            self.sendq, self.recvq = self.recvq, self.sendq
        tmp = self.get()
        self.logAppend("clear", str(tmp))
        while (tmp != None):
            tmp = self.get()
            self.logAppend("clear", str(tmp))
        tmp = self.get()
        self.logAppend("clear", str(tmp))
        if sendq:
            self.sendq, self.recvq = self.recvq, self.sendq
            self.logAppend("clear-sendq", "end")
        if recvq:
            self.logAppend("clear-recvq", "start")
            tmp = self.get()
            self.logAppend("clear", str(tmp))
            while (tmp != None):
                tmp = self.get()
                self.logAppend("clear", str(tmp))
            tmp = self.get()
            self.logAppend("clear", str(tmp))
            self.logAppend("clear-recvq", "end")

    def getLog(self):
        return self.log

    def writeLog(self, time = False):
        log = self.log
        if time:
            j = 3
        else:
            j = 2
        with open("logs/" + self.recvq + "-log.csv", "w", newline='') as f:
            writer = csv.writer(f)
            for i in range(len(log)):
                entry = log[i][:j]
                writer.writerow(entry)

