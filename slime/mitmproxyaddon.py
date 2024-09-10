# Standard library
import time
import threading
import typing
import pickle
# Third party
import mitmproxy
import mitmproxy.addonmanager
import mitmproxy.http
import mitmproxy.log
import mitmproxy.tcp
import mitmproxy.websocket
from mitmproxy.script import concurrent
# Local
from slime.msgbroker import Bugs

class HttpManager:
    """SLIME addon for mitmproxy"""
    def __init__(self):
        self.q = Bugs("mitm", False, RABBIT_CREDENTIALS)
        self.q.initQueues()
        self.name = "MITM_NAME"
        self.target_domain = "DOMAIN_NAME"
        # check if target domain to filter was replaced, note mitmproxy also has domain filtering so the setting here will be deprecated
        if self.target_domain != "DOMAIN" + "_NAME":
            self.filter_domains = True
        else:
            self.filter_domains = False
        # help with non-determinism issues if another request comes in after the last was sent out and waiting for a probable reply
        self.timeout = 4  # time to wait until deciding the last response timed out/is dead
        self.lock = threading.Lock()
        # TODO, this lock is better since it can be shared accross multiple mitm, and not sure how mitmproxy does it's threading, this should be more reliable
        # import filelock
        # lock = filelock.FileLock(os.path.join(os.path.expanduser("~"), ".picosnitch_lock"), timeout=1)
        # try:
        #     lock.acquire()
        #     lock.release()
        # except filelock.Timeout:
        #     print("Error: another instance of this application is currently running", file=sys.stderr)
        #     sys.exit(1)

    # @concurrent
    def request(self, flow: mitmproxy.http.HTTPFlow):
        """
            The full HTTP request has been read.
        """
        flow.intercept()
        if self.filter_domains and self.target_domain not in str(flow.request.headers["host"]):
            return None
        msg_out = {
            "type": "request",
            "mitm": self.name,
            "msg": str(flow.request.get_text()),
            "cookies": [(k, v) for k, v in flow.request.cookies.items(multi=True)],
            "headers": [(k, v) for k, v in flow.request.headers.items(multi=True)],
            "authority": flow.request.authority,
            "host": flow.request.host,
            "pretty_host": flow.request.pretty_host,
            "url": flow.request.url,
            "pretty_url": flow.request.pretty_url,
            "path": flow.request.path
        }
        self.lock.acquire(blocking=True, timeout=self.timeout)
        self.q.send(pickle.dumps(msg_out, 0).decode())
        msg_pickle = self.q.listen()
        msg_in = pickle.loads(msg_pickle.encode())
        if msg_in["type"] == "clear_flows":
            self.q.requeue(msg_pickle)
            # self.q.send("ack_clear_flows")
            self.lock.release()
            return None
        if msg_in["mitm"] != self.name or msg_in["type"] != "cmd":
            self.q.send("ERROR")
            self.lock.release()
            return None
        if msg_in["msg"] == "killreq":
            flow.kill()
            self.lock.release()
        elif msg_in["msg"] == "replacereq":
            msg = msg_in["msg+"]
            flow.request.set_text(msg)
            if "cookies" in msg_in:
                flow.request.cookies.clear()
                for key, value in msg_in["cookies"]:
                    flow.request.cookies.add(key, value)
            # self.q.requeue(msg_pickle)
        elif msg_in["msg"] == "lowergetreq":
            class _SubRequest(mitmproxy.http.HTTPRequest):
                method = "get"
            flow.request.__class__ = _SubRequest
            flow.request.data.method = b"get"
        elif msg_in["msg"] == "allowreq":
            # nothing to do here, requeue cmd for response
            # self.q.requeue(msg_pickle)
            pass  # no longer requeue, will ask again at next stage
        else:
            self.q.send("ERROR")
        flow.resume()

    @concurrent
    def response(self, flow: mitmproxy.http.HTTPFlow):
        """
            The full HTTP response has been read.
        """
        # flow.intercept()
        if self.filter_domains and self.target_domain not in str(flow.request.headers["host"]):
            return None
        msg_out = {
            "type": "response",
            "mitm": self.name,
            "msg": str(flow.response.get_text()),
            "cookies": [(k, v) for k, v in flow.response.cookies.items(multi=True)],
            "headers": [(k, v) for k, v in flow.response.headers.items(multi=True)]
        }
        self.q.send(pickle.dumps(msg_out, 0).decode())
        msg_pickle = self.q.listen()
        try:
            self.lock.release()
        except:
            pass
        msg_in = pickle.loads(msg_pickle.encode())
        if msg_in["type"] == "clear_flows":
            self.q.requeue(msg_pickle)
            # self.q.send("ack_clear_flows")
            return None
        if msg_in["mitm"] != self.name or msg_in["type"] != "cmd":
            self.q.send("ERROR")
            return None
        if msg_in["msg"] == "killres":
            flow.kill()
        elif msg_in["msg"] == "replaceres":
            msg = msg_in["msg+"]
            flow.response.set_text(msg)
        elif msg_in["msg"] == "allowres":
            # flow completed
            pass
        else:
            self.q.send("ERROR")
        # flow.resume()


class TcpManager:
    """SLIME addon for mitmproxy"""
    def __init__(self):
        self.q = Bugs("mitm", False, RABBIT_CREDENTIALS)
        self.q.initQueues()
        self.name = "MITM_NAME"
        # help with non-determinism issues if another request comes in after the last was sent out and waiting for a probable reply
        self.timeout = 4  # time to wait until deciding the last response timed out/is dead
        self.lock = threading.Lock()
        # TODO, this lock is better since it can be shared accross multiple mitm, and not sure how mitmproxy does it's threading, this should be more reliable
        # import filelock
        # lock = filelock.FileLock(os.path.join(os.path.expanduser("~"), ".picosnitch_lock"), timeout=1)
        # try:
        #     lock.acquire()
        #     lock.release()
        # except filelock.Timeout:
        #     print("Error: another instance of this application is currently running", file=sys.stderr)
        #     sys.exit(1)

    def tcp_message(self, flow: mitmproxy.tcp.TCPFlow):
        # print("flow start")
        # print(f"client: {flow.client_conn.address}")
        # print(f"server: {flow.server_conn.address}")
        # print(f"message no: {len(flow.messages)}")
        # print(f"message from: {flow.messages[-1].from_client}")
        # print(f"message: {flow.messages[-1].content}")
        # # flow.messages[-1].content = b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"
        # print("flow end")
        if flow.messages[-1].from_client:
            flow.intercept()
            msg_out = {
                "type": "request",
                "mitm": self.name,
                "msg": str(flow.messages[-1].content.decode()),
                "cookies": [],
                "headers": [],
                "authority": "",
                "host": "",
                "pretty_host": "",
                "url": "",
                "pretty_url": "",
                "path": ""
            }
            self.lock.acquire(blocking=True, timeout=self.timeout)
            self.q.send(pickle.dumps(msg_out, 0).decode())
            msg_pickle = self.q.listen()
            msg_in = pickle.loads(msg_pickle.encode())
            if msg_in["type"] == "clear_flows":
                self.q.requeue(msg_pickle)
                # self.q.send("ack_clear_flows")
                self.lock.release()
                return None
            if msg_in["mitm"] != self.name or msg_in["type"] != "cmd":
                self.q.send("ERROR")
                self.lock.release()
                return None
            if msg_in["msg"] == "killreq":
                flow.kill()
                self.lock.release()
            elif msg_in["msg"] == "replacereq":
                msg = msg_in["msg+"]
                flow.messages[-1].content = msg.encode()
                # self.q.requeue(msg_pickle)
            elif msg_in["msg"] == "allowreq":
                # nothing to do here, requeue cmd for response
                # self.q.requeue(msg_pickle)
                pass  # no longer requeue, will ask again at next stage
            else:
                self.q.send("ERROR")
            flow.resume()
        else:
            msg_out = {
                "type": "response",
                "mitm": self.name,
                "msg": str(flow.messages[-1].content.decode()),
                "cookies": [],
                "headers": []
            }
            self.q.send(pickle.dumps(msg_out, 0).decode())
            msg_pickle = self.q.listen()
            try:
                self.lock.release()
            except:
                pass
            msg_in = pickle.loads(msg_pickle.encode())
            if msg_in["type"] == "clear_flows":
                self.q.requeue(msg_pickle)
                # self.q.send("ack_clear_flows")
                return None
            if msg_in["mitm"] != self.name or msg_in["type"] != "cmd":
                self.q.send("ERROR")
                return None
            if msg_in["msg"] == "killres":
                flow.kill()
            elif msg_in["msg"] == "replaceres":
                msg = msg_in["msg+"]
                flow.messages[-1].content = msg.encode()
            elif msg_in["msg"] == "allowres":
                # flow completed
                pass
            else:
                self.q.send("ERROR")
            # flow.resume()

addons = [
    # choose HttpManager() or TcpManager()
]
