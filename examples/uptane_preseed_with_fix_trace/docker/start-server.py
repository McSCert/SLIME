import sys
import time
import threading
import demo
import demo.demo_timeserver as dt
import demo.demo_director as dd
import demo.demo_image_repo as di
from six.moves import xmlrpc_server
import readline, rlcompleter # for tab completion in interactive Python shell


def main():

  # Start demo Image Repo, including http server and xmlrpc listener (for
  # webdemo)
  di.clean_slate()

  firmware_fname = filepath_in_repo = 'firmware.img'
  open(firmware_fname, "w").write("HELLO WORLD!!!")
  di.add_target_to_imagerepo(firmware_fname, filepath_in_repo)
  di.write_to_live()

  # Start demo Director, including http server and xmlrpc listener (for
  # manifests, registrations, and webdemo)
  dd.clean_slate()

  vin='democar'
  ecu_serial='SECONDARY_ECU_1'

  # generate new timeserver keys ONLY when creating docker image
  image_creation = False
  if len(sys.argv) == 2:
    image_creation = True

  # Start demo Timeserver, including xmlrpc listener (for requests from demo
  # Primary)
  dt.listen(use_new_keys=image_creation)

  # make sure server is ready
  with open("/ready.txt", "w") as f:
    f.write("ready")

  while True:
    try:
      dd.add_target_to_director(firmware_fname, filepath_in_repo, vin, ecu_serial)
      dd.write_to_live(vin_to_update=vin)
      break
    except:
      pass

  # Keep server from terminating
  while True:
    time.sleep(1)





if __name__ == '__main__':
  readline.parse_and_bind('tab: complete')
  main()
