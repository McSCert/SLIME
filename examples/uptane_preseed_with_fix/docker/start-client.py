import demo.demo_primary as dp
import demo.demo_secondary as ds
dp.clean_slate(vin='democar', ecu_serial='PRIMARY_ECU_1')
ds.clean_slate(vin='democar', ecu_serial='SECONDARY_ECU_1')
while True:
    try:
        dp.update_cycle()
    except:
        pass
    try:
        ds.update_cycle()
    except:
        pass
