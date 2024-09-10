cd /uptane
sed -i 's/IMAGE_REPO_PORT = 30301/IMAGE_REPO_PORT = 30302/g' /uptane/demo/__init__.py
sed -i 's/DIRECTOR_REPO_PORT = 30401/DIRECTOR_REPO_PORT = 30402/g' /uptane/demo/__init__.py
sed -i 's/DIRECTOR_SERVER_PORT = 30501/DIRECTOR_SERVER_PORT = 30502/g' /uptane/demo/__init__.py
sed -i 's/TIMESERVER_PORT = 30601/TIMESERVER_PORT = 30602/g' /uptane/demo/__init__.py
sed -i 's/PRIMARY_SERVER_DEFAULT_PORT = 30701/PRIMARY_SERVER_DEFAULT_PORT = 30702/g' /uptane/demo/__init__.py
sed -i 's/30701, 30702, 30703, 30704, 30705, 30706, 30707, 30708, 30709, 30710, 30711]/30701]/g' /uptane/demo/__init__.py
/Python-3.6.9/python start-client.py > /dev/null & echo $!
