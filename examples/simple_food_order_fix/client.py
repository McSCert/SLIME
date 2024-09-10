import sys
import requests

HOST = 'localhost'
PORT = 9001

def send_request(request):
    url = f'http://{HOST}:{PORT}'
    headers = {'Content-Type': 'text/plain'}
    response = requests.post(url, data=request, headers=headers, timeout=2)
    return response.text

response = ""

# pretend there's a start session request here, any message in end, the server will no respond until the client restarts (end the client when one is seen to simplify the example)
end = ['NO_PENDING_ORDER', 'NO_PENDING_DEPOSIT', 'DEPOSIT_NOT_ALLOWED', 'PLACE_ORDER_NOT_ALLOWED', 'INVALID_REQUEST']

# Transfer money
response = send_request('DEPOSIT:10')
print(response)
if response in end:
    sys.exit()

# # Confirm deposit
response = send_request('CONFIRM_DEPOSIT')
print(response)
if response in end:
    sys.exit()

# Place order
response = send_request('PLACE_ORDER:10')
print(response)
if response in end:
    sys.exit()

# Confirm order
response = send_request('CONFIRM_ORDER')
print(response)
if response in end:
    sys.exit()
