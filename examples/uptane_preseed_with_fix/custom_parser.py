import xmltodict
from slime.msgparser import MessageParser

class uptane_xml_parser(MessageParser):
    def parser(self, response, message_type: str):
        xml_response = xmltodict.parse(response)
        try:
            response_parsed = xml_response["methodCall"]["methodName"]
        except:
            response_parsed = self.recursiveDictKeys(xml_response)
        return response_parsed
