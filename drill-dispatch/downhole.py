import time, termcolor, binascii

import pyvesc
from packets import *

from termcolor import colored
from log import logger, tohex

def downhole_worker(arguments, redis_conn, transport):
    logger.info("Downhole worker started")

    redis_pubsub = redis_conn.pubsub()
    redis_pubsub.subscribe("downhole")
    
    for item in redis_pubsub.listen():
        if (item["type"] == 'message' and item["channel"] == b'downhole'):
            data = item["data"].decode('ascii').split(":")
            message = None
            
            if data[0] == 'ping':
                message = Ping()

            elif data[0] == 'motor-stop':
                message = MotorStop()
                
                
            elif data[0] == 'motor-pwm':
                duty = int(data[1])

                if (duty > 255):
                    duty = 255

                if (duty < -255):
                    duty = -255

                print(colored("set motor %d pwm" % (duty), 'red'))

                message = MotorStartPWM()
                message.pwm = duty

            elif data[0] == 'motor-rpm':
                speed = int(data[1])

                if (speed > 120):
                    speed = 120

                if (speed < -120):
                    speed = -120

                print(colored("set motor %d rpm" % (speed), 'red'))
                message = MotorStartRPM()
                message.rpm = speed

            elif data[0] == 'motor-config':
                config_id = None
                
                if data[1] == 'parvalux':
                    config_id = 0
                elif data[1] == 'skateboard':
                    config_id = 1
                elif data[1] == 'hacker':
                    config_id = 2
                elif data[1] == 'plettenberg':
                    config_id = 3

                if config_id is not None:
                    print(colored("set config %d" % (config_id), 'red'))
                    message = MotorFlashConfig()
                    message.motor_config_id = int(config_id)

            elif data[0] == 'set-alarm':
                alarm_id = None
                
                if data[1] == 'gyro':
                    alarm_id = 0
                else:
                    print(colored("Could not set alarm for %s" % data[1]))

                if alarm_id is not None:
                    alarm_state = int(data[2])

                    print(colored("Set alarm %d (%s) to %d" % (alarm_id, data[1], alarm_state), 'red'))

                    message = SetAlarm()
                    message.alarm_id = alarm_id
                    message.state = alarm_state

            elif data[0] == 'motor-rotate-by':
                print("Hello world")
                print(colored("rotate %s degrees and pwm" % data[1], 'red'))
                #degrees = 90 #int(data[1])
                #pwm = 10 #int(data[2])
                currentdata = data[1].split(",")
                degrees = int(currentdata[0])
                pwm = int(currentdata[1])

                state = 1
                '''
                if (data[3] == "forward"):
                    state = 1
                elif(data[3] == "reverse"):
                    state = 2
                else:
                    continue
                '''
                print(colored("rotate %d degrees at %d pwm" % (degrees, pwm), 'red'))
                message = MotorRotateBy()
                message.degrees_d = degrees
                message.rpm_d = pwm

            elif data[0] == 'bno055-calibrate':

                #print("Calibrate")
                #print(colored("Calibrate " % data[1], 'red'))

                currentdata = data[1].split(",")
                functiondata = int(currentdata[0])
                slotdata = int(currentdata[1])

                state = 1
                
                if (functiondata == 0):
                    print(colored("Load BNO055 calibration slot %d" % (slotdata), 'green'))
                else:
                    print(colored("Save BNO055 calibration slot %d" % (slotdata), 'red'))
                
                message = Bno055SaveLoadCalibration()
                message.load_save = functiondata
                message.slot = slotdata
                
            elif data[0] == 'motor-set-tachometer':
                target = int(data[1])

                message = MotorSetTachometer()
                message.tachometer = target
                
            else:
                print(colored("I don't understand command %s" % data[0], 'red'))

            if message is not None:
                print(colored(message, 'red'))
                packet = pyvesc.encode(message)
                transport.write(packet)

                logger.info(item["data"].decode('ascii'))
                
