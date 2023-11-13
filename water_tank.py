# !/usr/bin/env python
# -*- coding: utf-8 -*-

# standard library imports
import json  # for working with data file
from threading import Thread
from time import sleep
import os
from enum import IntEnum
from datetime import datetime
from abc import ABC, abstractmethod
from math import acos, pi, sqrt

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings
from sip import template_render  #  Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security
from webpages import showInFooter # Enable plugin to display readings in UI footer
from webpages import showOnTimeline # Enable plugin to display station data on timeline
from plugins import mqtt
from helpers import load_programs

class WaterTankType(IntEnum):
    RECTANGULAR = 1
    CYLINDRICAL_HORIZONTAL = 2
    CYLINDRICAL_VERTICAL = 3
    ELLIPTICAL = 4

class WaterTank(ABC):
    def __init__(self, id, label, type, sensor_mqtt_topic, sensor_offset_from_top, min_valid_sensor_measurement, max_valid_sensor_measurement, enabled, overflow_level, overflow_email, overflow_xmpp, overflow_safe_level, overflow_programs, warning_level, warning_email, warning_xmpp, warning_suspend_programs, warning_activate_programs, critical_level, critical_email, critical_xmpp, critical_suspend_programs,critical_activate_programs,loss_email, loss_xmpp):
        self.id = id
        self.label = label
        self.type = type
        self.sensor_mqtt_topic = sensor_mqtt_topic
        self.sensor_offset_from_top = sensor_offset_from_top
        self.min_valid_sensor_measurement = min_valid_sensor_measurement
        self.max_valid_sensor_measurement = max_valid_sensor_measurement
        self.enabled = enabled
        self.overflow_level = overflow_level
        self.overflow_email = overflow_email
        self.overflow_xmpp = overflow_xmpp
        self.overflow_safe_level = overflow_safe_level
        self.overflow_programs = overflow_programs
        self.warning_level = warning_level
        self.warning_email = warning_email
        self.warning_xmpp = warning_xmpp
        self.warning_suspend_programs = warning_suspend_programs
        self.warning_activate_programs = warning_activate_programs
        self.critical_level = critical_level
        self.critical_email = critical_email
        self.critical_xmpp = critical_xmpp
        self.critical_suspend_programs = critical_suspend_programs
        self.critical_activate_programs = critical_activate_programs
        self.loss_email = loss_email
        self.loss_xmpp = loss_xmpp
        self.last_updated = None
        self.sensor_measurement = None
        self.invalid_sensor_measurement = False
        self.percentage = None

    def UpdateSensorMeasurement(self, measurement):
        if (self.min_valid_sensor_measurement is not None and measurement < self.min_valid_sensor_measurement) or (self.max_valid_sensor_measurement is not None and measurement > self.max_valid_sensor_measurement):
            self.invalid_sensor_measurement = True
            self.percentage = None
            return

        self.invalid_sensor_measurement = False
        self.sensor_measurement = measurement
        self.last_updated = datetime.now().replace(microsecond=0)


class WaterTankRectangular(WaterTank):
    def __init__(self, id, label, width, length, height, sensor_mqtt_topic, sensor_offset_from_top, min_valid_sensor_measurement,max_valid_sensor_measurement, enabled, overflow_level, overflow_email, overflow_xmpp, overflow_safe_level, overflow_programs, warning_level, warning_email, warning_xmpp, warning_suspend_programs, warning_activate_programs, critical_level, critical_email, critical_xmpp, critical_suspend_programs,critical_activate_programs,loss_email, loss_xmpp):
        super().__init__(id, label, WaterTankType.RECTANGULAR.value, sensor_mqtt_topic, sensor_offset_from_top, min_valid_sensor_measurement,max_valid_sensor_measurement, enabled, overflow_level, overflow_email, overflow_xmpp, overflow_safe_level, overflow_programs, warning_level, warning_email, warning_xmpp, warning_suspend_programs, warning_activate_programs, critical_level, critical_email, critical_xmpp, critical_suspend_programs,critical_activate_programs,loss_email, loss_xmpp)
        self.width = width
        self.length = length
        self.height = height
    
    def UpdateSensorMeasurement(self, measurement):
        super().UpdateSensorMeasurement(measurement)
        if self.width is not None and self.length is not None and self.height is not None:
            volume = self.width * self.length * self.height
            self.percentage = 100.0 * (self.height - (measurement-self.sensor_offset_from_top)) / self.height
            if self.height < (measurement-self.sensor_offset_from_top):
                self.invalid_sensor_measurement = True


class WaterTankCylindricalHorizontal(WaterTank):
    def __init__(self, id, label, length, diameter, sensor_mqtt_topic, sensor_offset_from_top, min_valid_sensor_measurement,max_valid_sensor_measurement, enabled, overflow_level, overflow_email, overflow_xmpp, overflow_safe_level, overflow_programs, warning_level, warning_email, warning_xmpp, warning_suspend_programs, warning_activate_programs, critical_level, critical_email, critical_xmpp, critical_suspend_programs,critical_activate_programs,loss_email, loss_xmpp):
        super().__init__(id, label, WaterTankType.CYLINDRICAL_HORIZONTAL.value, sensor_mqtt_topic, sensor_offset_from_top, min_valid_sensor_measurement,max_valid_sensor_measurement, enabled, overflow_level, overflow_email, overflow_xmpp, overflow_safe_level, overflow_programs, warning_level, warning_email, warning_xmpp, warning_suspend_programs, warning_activate_programs, critical_level, critical_email, critical_xmpp, critical_suspend_programs,critical_activate_programs,loss_email, loss_xmpp)
        self.length = length
        self.diameter = diameter

    def UpdateSensorMeasurement(self, measurement):
        super().UpdateSensorMeasurement(measurement)
        if self.diameter is not None and self.length is not None:
            volume = self.diameter * self.length
            r = self.diameter / 2.0
            h = self.diameter - (measurement-self.sensor_offset_from_top)
            if self.diameter < (measurement-self.sensor_offset_from_top):
                self.invalid_sensor_measurement = True
            try:
                liquid_volume = acos((r-h)/r)*(r**2) - (r-h)*sqrt(2*r*h - (h**2))
                self.percentage = 100.0 * liquid_volume / volume
            except:
                self.invalid_sensor_measurement = True
                self.percentage = None                        


class WaterTankCylindricalVertical(WaterTank):
    def __init__(self, id, label, diameter, height, sensor_mqtt_topic, sensor_offset_from_top, min_valid_sensor_measurement,max_valid_sensor_measurement, enabled, overflow_level, overflow_email, overflow_xmpp, overflow_safe_level, overflow_programs, warning_level, warning_email, warning_xmpp, warning_suspend_programs, warning_activate_programs, critical_level, critical_email, critical_xmpp, critical_suspend_programs,critical_activate_programs,loss_email, loss_xmpp):
        super().__init__(id, label, WaterTankType.CYLINDRICAL_VERTICAL.value, sensor_mqtt_topic, sensor_offset_from_top, min_valid_sensor_measurement,max_valid_sensor_measurement, enabled, overflow_level, overflow_email, overflow_xmpp, overflow_safe_level, overflow_programs, warning_level, warning_email, warning_xmpp, warning_suspend_programs, warning_activate_programs, critical_level, critical_email, critical_xmpp, critical_suspend_programs,critical_activate_programs,loss_email, loss_xmpp)
        self.height = height
        self.diameter = diameter

    def UpdateSensorMeasurement(self, measurement):
        super().UpdateSensorMeasurement(measurement)
        if self.diameter is not None and self.height is not None:
            volume = self.diameter * self.height
            self.percentage = 100.0 * (self.height - (measurement-self.sensor_offset_from_top)) / self.height

            if self.height < (measurement-self.sensor_offset_from_top):
                self.invalid_sensor_measurement = True
        

class WaterTankElliptical(WaterTank):
    def __init__(self, id, label, length, horizontal_axis, vertical_axis, sensor_mqtt_topic, sensor_offset_from_top, min_valid_sensor_measurement,max_valid_sensor_measurement, enabled, overflow_level, overflow_email, overflow_xmpp, overflow_safe_level, overflow_programs, warning_level, warning_email, warning_xmpp, warning_suspend_programs, warning_activate_programs, critical_level, critical_email, critical_xmpp, critical_suspend_programs,critical_activate_programs,loss_email, loss_xmpp):
        super().__init__(id, label, WaterTankType.ELLIPTICAL.value, sensor_mqtt_topic, sensor_offset_from_top, min_valid_sensor_measurement,max_valid_sensor_measurement, enabled, overflow_level, overflow_email, overflow_xmpp, overflow_safe_level, overflow_programs, warning_level, warning_email, warning_xmpp, warning_suspend_programs, warning_activate_programs, critical_level, critical_email, critical_xmpp, critical_suspend_programs,critical_activate_programs,loss_email, loss_xmpp)
        self.length = length
        self.horizontal_axis = horizontal_axis
        self.vertical_axis = vertical_axis

    def UpdateSensorMeasurement(self, measurement):
        super().UpdateSensorMeasurement(measurement)
        if self.length is not None and self.horizontal_axis is not None and self.vertical_axis is not None:
            # from https://www.had2know.org/academics/ellipse-segment-tank-volume-calculator.html
            A = self.vertical_axis
            B = self.horizontal_axis
            H = self.vertical_axis - (measurement-self.sensor_offset_from_top)
            L = self.length
            volume = self.horizontal_axis/2.0 * self.vertical_axis/2.0 * self.length * pi
            if self.vertical_axis < (measurement-self.sensor_offset_from_top):
                self.invalid_sensor_measurement = True

            try:
                liquid_volume = ((A*B*L)/4)*( acos(1.0 - 2.0*H/A) - (1.0 - 2.0*H/A)*sqrt(4*H/A - 4*(H**2)/(A**2)) )
                self.percentage = 100.0 * liquid_volume / volume
            except:
                self.invalid_sensor_measurement = True
                self.percentage = None


class WaterTankFactory():
    def FromDict(d):
        wt = None
        type = int(d["type"])

        overflow_programs = {}
        warning_suspend_programs = {}
        warning_activate_programs = {}
        critical_suspend_programs = {}
        critical_activate_programs = {}
        for pn in gv.pnames:
            overflow_programs[pn] = True if ('overflow_program_' + pn) in d else False
            warning_suspend_programs[pn] = True if ('warning_suspend_program_' + pn) in d else False
            warning_activate_programs[pn] = True if ('warning_activate_program_' + pn) in d else False
            critical_suspend_programs[pn] = True if ('critical_suspend_program_' + pn) in d else False
            critical_activate_programs[pn] = True if ('critical_activate_program_' + pn) in d else False

        if type == WaterTankType.RECTANGULAR.value:
            wt = WaterTankRectangular(
                d["id"],
                d["label"],
                None if not d["width"] else float(d["width"]),
                None if not d["length"] else float(d["length"]),
                None if not d["height"] else float(d["height"]),
                d["sensor_mqtt_topic"],
                float(d["sensor_offset_from_top"]),
                None if "min_valid_sensor_measurement" not in d or not d["min_valid_sensor_measurement"] else float(d["min_valid_sensor_measurement"]),
                None if "max_valid_sensor_measurement"not in d or not d["max_valid_sensor_measurement"] else float(d["max_valid_sensor_measurement"]),
                ("enabled" in d),
                None if not d["overflow_level"] else float(d["overflow_level"]),
                d["overflow_email"],
                d["overflow_xmpp"],
                None if not d["overflow_safe_level"] else float(d["overflow_safe_level"]),
                overflow_programs,
                None if not d["warning_level"] else float(d["warning_level"]),
                d["warning_email"],
                d["warning_xmpp"],
                warning_suspend_programs,
                warning_activate_programs,
                None if not d["critical_level"] else float( d["critical_level"]),
                d["critical_email"],
                d["critical_xmpp"],
                critical_suspend_programs,
                critical_activate_programs,
                d["loss_email"],
                d["loss_xmpp"]
            )
        elif type == WaterTankType.CYLINDRICAL_HORIZONTAL.value:
            wt = WaterTankCylindricalHorizontal(
                d["id"],
                d["label"],
                None if not d["length"] else float(d["length"]),
                None if not d["diameter"] else float(d["diameter"]),
                d["sensor_mqtt_topic"],
                float(d["sensor_offset_from_top"]),
                None if "min_valid_sensor_measurement" not in d or not d["min_valid_sensor_measurement"] else float(d["min_valid_sensor_measurement"]),
                None if "max_valid_sensor_measurement"not in d or not d["max_valid_sensor_measurement"] else float(d["max_valid_sensor_measurement"]),
                ("enabled" in d),
                None if not d["overflow_level"] else float(d["overflow_level"]),
                d["overflow_email"],
                d["overflow_xmpp"],
                None if not d["overflow_safe_level"] else float(d["overflow_safe_level"]),
                overflow_programs,
                None if not d["warning_level"] else float(d["warning_level"]),
                d["warning_email"],
                d["warning_xmpp"],
                warning_suspend_programs,
                warning_activate_programs,
                None if not d["critical_level"] else float( d["critical_level"]),
                d["critical_email"],
                d["critical_xmpp"],
                critical_suspend_programs,
                critical_activate_programs,
                d["loss_email"],
                d["loss_xmpp"]
            )
        elif type == WaterTankType.CYLINDRICAL_VERTICAL.value:
            wt = WaterTankCylindricalVertical(
                d["id"],
                d["label"],
                None if not d["diameter"] else float(d["diameter"]),
                None if not d["height"] else float(d["height"]),
                d["sensor_mqtt_topic"],
                float(d["sensor_offset_from_top"]),
                None if "min_valid_sensor_measurement" not in d or not d["min_valid_sensor_measurement"] else float(d["min_valid_sensor_measurement"]),
                None if "max_valid_sensor_measurement"not in d or not d["max_valid_sensor_measurement"] else float(d["max_valid_sensor_measurement"]),
                ("enabled" in d),
                None if not d["overflow_level"] else float(d["overflow_level"]),
                d["overflow_email"],
                d["overflow_xmpp"],
                None if not d["overflow_safe_level"] else float(d["overflow_safe_level"]),
                overflow_programs,
                None if not d["warning_level"] else float(d["warning_level"]),
                d["warning_email"],
                d["warning_xmpp"],
                warning_suspend_programs,
                warning_activate_programs,
                None if not d["critical_level"] else float( d["critical_level"]),
                d["critical_email"],
                d["critical_xmpp"],
                critical_suspend_programs,
                critical_activate_programs,
                d["loss_email"],
                d["loss_xmpp"]
            )
        elif type == WaterTankType.ELLIPTICAL.value:
            wt = WaterTankElliptical(
                d["id"],
                d["label"],
                None if not d["length"] else float(d["length"]),
                None if not d["horizontal_axis"] else float(d["horizontal_axis"]),
                None if not d["vertical_axis"] else float(d["vertical_axis"]),
                d["sensor_mqtt_topic"],
                float(d["sensor_offset_from_top"]),
                None if "min_valid_sensor_measurement" not in d or not d["min_valid_sensor_measurement"] else float(d["min_valid_sensor_measurement"]),
                None if "max_valid_sensor_measurement"not in d or not d["max_valid_sensor_measurement"] else float(d["max_valid_sensor_measurement"]),
                ("enabled" in d),
                None if not d["overflow_level"] else float(d["overflow_level"]),
                d["overflow_email"],
                d["overflow_xmpp"],
                None if not d["overflow_safe_level"] else float(d["overflow_safe_level"]),
                overflow_programs,
                None if not d["warning_level"] else float(d["warning_level"]),
                d["warning_email"],
                d["warning_xmpp"],
                warning_suspend_programs,
                warning_activate_programs,
                None if not d["critical_level"] else float( d["critical_level"]),
                d["critical_email"],
                d["critical_xmpp"],
                critical_suspend_programs,
                critical_activate_programs,
                d["loss_email"],
                d["loss_xmpp"]
            )
        
        return wt

DATA_FILE = u"./data/water_tank.json"
WATER_PLUGIN_REQUEST_MQTT_TOPIC = u"request_subscribe_mqtt_topic"
WATER_PLUGIN_DATA_PUBLISH_MQTT_TOPIC = u"data_publish_mqtt_topic"

_settings = {
    u"mqtt_broker_ws_port": 8080,
    WATER_PLUGIN_REQUEST_MQTT_TOPIC: "WaterTankDataRequest",
    WATER_PLUGIN_DATA_PUBLISH_MQTT_TOPIC: "WaterTankData",
    u"water_tanks": {
        "water_tank_1": {
            "id": "water_tank_1",
            "label": "\u03a4\u03c3\u03b9\u03bc\u03b5\u03bd\u03c4\u03ad\u03bd\u03b9\u03b1",
            "type": 1,
            "sensor_mqtt_topic": "WATER_TANK_MEASUREMENT",
            "sensor_offset_from_top": 0.0,
            "enabled": True,
            "overflow_level": 80.0,
            "overflow_email": "",
            "overflow_xmpp": "",
            "overflow_safe_level": None,
            "overflow_programs": {
                "1": False,
                "2": False,
                "3": False,
                "4": False
            },
            "warning_level": 25.0,
            "warning_email": "",
            "warning_xmpp": "",
            "warning_suspend_programs": {
                "1": False,
                "2": False,
                "3": False,
                "4": False
            },
            "warning_activate_programs": {
                "1": False,
                "2": False,
                "3": False,
                "4": False
            },
            "critical_level": 8.0,
            "critical_email": "",
            "critical_xmpp": "",
            "critical_suspend_programs": {
                "1": False,
                "2": False,
                "3": False,
                "4": False
            },
            "critical_activate_programs": {
                "1": False,
                "2": False,
                "3": False,
                "4": False
            },
            "loss_email": "",
            "loss_xmpp": "",
            "last_updated": None,
            "sensor_measurement": None,
            "invalid_sensor_measurement": False,
            "percentage": None,
            "width": 2.0,
            "length": 5.0,
            "height": 2.0
        },
        "water_tank_2": {
            "id": "water_tank_2",
            "label": "\u03a3\u03b9\u03b4\u03b5\u03c1\u03ad\u03bd\u03b9\u03b1",
            "type": 1,
            "sensor_mqtt_topic": "WATER_TANK_MEASUREMENT",
            "sensor_offset_from_top": 0.0,
            "enabled": True,
            "overflow_level": 85.0,
            "overflow_email": "",
            "overflow_xmpp": "",
            "overflow_safe_level": None,
            "overflow_programs": {
                "1": False,
                "2": False,
                "3": False,
                "4": False
            },
            "warning_level": 30.0,
            "warning_email": "",
            "warning_xmpp": "",
            "warning_suspend_programs": {
                "1": False,
                "2": False,
                "3": False,
                "4": False
            },
            "warning_activate_programs": {
                "1": False,
                "2": False,
                "3": False,
                "4": False
            },
            "critical_level": 5.0,
            "critical_email": "",
            "critical_xmpp": "",
            "critical_suspend_programs": {
                "1": False,
                "2": False,
                "3": False,
                "4": False
            },
            "critical_activate_programs": {
                "1": False,
                "2": False,
                "3": False,
                "4": False
            },
            "loss_email": "",
            "loss_xmpp": "",
            "last_updated": "2023-11-12 13:47",
            "sensor_measurement": 0.9,
            "invalid_sensor_measurement": True,
            "percentage": 40.0,
            "width": 2.0,
            "length": 3.0,
            "height": 1.5
        },
        "water_tank_3": {
            "id": "water_tank_3",
            "label": "\u039c\u03b1\u03cd\u03c1\u03b7",
            "type": 3,
            "sensor_mqtt_topic": "WATER_TANK_MEASUREMENT",
            "sensor_offset_from_top": 0.0,
            "enabled": True,
            "overflow_level": 85.0,
            "overflow_email": "",
            "overflow_xmpp": "",
            "overflow_safe_level": None,
            "overflow_programs": {
                "1": False,
                "2": False,
                "3": False,
                "4": False
            },
            "warning_level": 30.0,
            "warning_email": "",
            "warning_xmpp": "",
            "warning_suspend_programs": {
                "1": False,
                "2": False,
                "3": False,
                "4": False
            },
            "warning_activate_programs": {
                "1": False,
                "2": False,
                "3": False,
                "4": False
            },
            "critical_level": 5.0,
            "critical_email": "",
            "critical_xmpp": "",
            "critical_suspend_programs": {
                "1": False,
                "2": False,
                "3": False,
                "4": False
            },
            "critical_activate_programs": {
                "1": False,
                "2": False,
                "3": False,
                "4": False
            },
            "loss_email": "",
            "loss_xmpp": "",
            "last_updated": "2023-11-12 13:47",
            "sensor_measurement": 1.5,
            "invalid_sensor_measurement": False,
            "percentage": 25.0,
            "height": 2.0,
            "diameter": 2.0
        },
        "water_tank_4": {
            "id": "water_tank_4",
            "label": "\u039d\u03b5\u03c1\u03cc \u03b4\u03b9\u03ba\u03c4\u03cd\u03bf\u03c5",
            "type": 4,
            "sensor_mqtt_topic": "WATER_TANK_MEASUREMENT",
            "sensor_offset_from_top": 0.0,
            "enabled": True,
            "overflow_level": 85.0,
            "overflow_email": "",
            "overflow_xmpp": "",
            "overflow_safe_level": None,
            "overflow_programs": {
                "1": False,
                "2": False,
                "3": False,
                "4": False
            },
            "warning_level": 40.0,
            "warning_email": "",
            "warning_xmpp": "",
            "warning_suspend_programs": {
                "1": False,
                "2": False,
                "3": False,
                "4": False
            },
            "warning_activate_programs": {
                "1": False,
                "2": False,
                "3": False,
                "4": False
            },
            "critical_level": 5.0,
            "critical_email": "",
            "critical_xmpp": "",
            "critical_suspend_programs": {
                "1": False,
                "2": False,
                "3": False,
                "4": False
            },
            "critical_activate_programs": {
                "1": False,
                "2": False,
                "3": False,
                "4": False
            },
            "loss_email": "",
            "loss_xmpp": "",
            "last_updated": "2023-11-12 13:47",
            "sensor_measurement": 0.6,
            "invalid_sensor_measurement": False,
            "percentage": 61.41848493043786,
            "length": 2.0,
            "horizontal_axis": 1.0,
            "vertical_axis": 0.8
        }
    }
}

# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend([
    u"/water-tank-sp", u"plugins.water_tank.settings",
    u"/water-tank-save", u"plugins.water_tank.save_settings",
    u"/water-tank-get-all", u"plugins.water_tank.get_all",
    u"/water-tank-get_mqtt_settings", u"plugins.water_tank.get_mqtt_settings",
    u"/water-tank-delete", u"plugins.water_tank.delete"
    ])
# fmt: on

# Add this plugin to the PLUGINS menu ["Menu Name", "URL"], (Optional)
gv.plugin_menu.append([_(u"Water Tank Plugin"), u"/water-tank-sp"])


# Define a custom function to serialize datetime objects 
def serialize_datetime(obj): 
    # print('Serializing: {}'.format(obj))
    if isinstance(obj, datetime): 
        return obj.isoformat(sep=' ', timespec='minutes')
    elif isinstance(obj, WaterTankType):
        return obj.value
    elif  isinstance(obj, WaterTank):
        return obj.__dict__
    raise TypeError("Type not serializable") 

def get_settings():
    global _settings
    try:
        fh = open(DATA_FILE, "r")
        try:
            settings = json.load(fh)
            _settings = settings
        except ValueError as e:
            print(u"Water Tank pluging couldn't parse data file:", e)
        finally:
            fh.close()
    except IOError as e:
        print(u"Water-Tank Plugin couldn't open data file:", e)
        # with open(DATA_FILE, u"w") as f:
        #     json.dump(_settings, f, default=serialize_datetime, indent=4)
    # print( 'returning : {}'.format(repr(_settings))
    return _settings

def detect_water_tank_js():
    """
    Search base.html for the line that includes the water_tank.js script
    """
    path = os.getcwd()
    print('Current dir is {}'.format(path))
    file_path = path + '/templates/base.html'
    mqtt_line = '\t<script src="static/scripts/mqttws31.js"></script>\n'
    validation_line = '\t<script src="static/scripts/jquery.validate.min.js"></script>\n'
    additional_validation_line = '\t<script src="static/scripts/additional-methods.min.js"></script>\n'
    script_line = '\t<script src="static/scripts/water_tank.js"></script>\n'
    css_line = '\t<link href="static/css/water_tank.css" rel="stylesheet" type="text/css"/>\n'
    header_end_word = '</head>'
    header_end_word_index = 0
    found = False
    contents = []
    with open(file_path, 'r') as file:
        for(i, line) in enumerate(file):
            contents.append(line)
            if script_line in line:
                found = True
                print('{} found in {}:{}'.format(script_line, file_path, i))
                break
            if header_end_word in line:
                print('{} found in {}:{}'.format(header_end_word, file_path, header_end_word_index))
                header_end_word_index = i

    if not found:
        if header_end_word_index == 0:
            print('{} was not found in {}. Water Tank plugin cannot work.')
        else:
            print('{} not found in {}, will add it above {} to line {}'.format(script_line, file_path, header_end_word, header_end_word_index-1))
            contents.insert(header_end_word_index, script_line)
            contents.insert(header_end_word_index, additional_validation_line)
            contents.insert(header_end_word_index, validation_line)
            contents.insert(header_end_word_index, mqtt_line)
            contents.insert(header_end_word_index, css_line)
            with open(file_path, 'w') as file:
                contents = "".join(contents)
                file.write(contents)
            print('{} and {} were added to line {}. Please refresh the page in you browser.'.format(script_line, mqtt_line, header_end_word_index-1))
        return

### Station Completed ###
def notify_station_completed(station, **kw):
    print(u"Station {} run completed".format(station))


complete = signal(u"station_completed")
complete.connect(notify_station_completed)

def readWaterTankData():
    water_tank_data = {}
    try:
        # with open(DATA_FILE, "r") as f:# Read settings from json file if it exists
        #     water_tank_data = list(json.load(f)[u"water_tanks"].values())
        settings = get_settings()
        water_tank_data = list(settings[u"water_tanks"].values())
    except IOError:  # If file does not exist return empty value
        water_tank_data = [] #list(_settings[u"water_tanks"].values())
        #testing/debugging
#         water_tank_data = json.loads('''
# [
#     {"id": "water_tank_2", "label": "Τσιμεντένια", "percentage": 24},
#     {"id": "water_tank_3", "label": "Σιδερένια", "percentage": 80},
#     {"id": "water_tank_4", "label": "Μαύρη", "percentage": 90},
#     {"id": "water_tank_5", "label": "Νερό δικτύου", "percentage": 90}
# ]
#                                      ''')
    return water_tank_data  # open settings page


def updateSensorMeasurementFromCmd(cmd, water_tanks):
    # print("updateSensorMeasurementFromCmd for '{}'".format(cmd[u"id"]))
    if cmd[u"id"] in water_tanks:
        wt = WaterTankFactory.FromDict(water_tanks[cmd[u"id"]])
        wt.last_updated = datetime.now()
        wt.UpdateSensorMeasurement(cmd[u"measurement"])
        water_tanks[cmd[u"id"]] = wt.__dict__
        # print("Update water tank '{}' with measurment: {}".format(wt.id, wt.sensor_measurement))
        return True
    else:
        print(u"Incomming mqtt sensor message for water tank with id:'{}'. Id not found in water tanks".format( cmd[u"id"]))

    return False


def on_sensor_mqtt_message(client, msg):
    """
    Callback when MQTT message is received from sensor
    """
    print('Received MQTT message: {}'.format(msg.payload))
    try:
        cmd = json.loads(msg.payload)
        print('MQTT cmd: {}'.format(cmd))
    except ValueError as e:
        print(u"Water Tank plugin could not decode command: ", msg.payload, e)
        return

    settings = get_settings()
    water_tanks = settings[u"water_tanks"]
    water_tank_id_updated = False
    if isinstance(cmd, dict) and 'id' in cmd:
        water_tank_id_updated = updateSensorMeasurementFromCmd(cmd, water_tanks)
    elif isinstance(cmd, list):
        print('Cmd is a list')
        for singleTankCmd in cmd:
            print('Cmd item:{}'.format(json.dumps(singleTankCmd, default=serialize_datetime,indent=4)))
            if isinstance(singleTankCmd, dict) and 'id' in singleTankCmd:
                print("Will call updateSensorMeasurementFromCmd for '{}'".format(singleTankCmd["id"]))
                water_tank_id_updated = updateSensorMeasurementFromCmd(singleTankCmd, water_tanks) or water_tank_id_updated
            else:
                print("Skipping {}".format(singleTankCmd["id"]))
    else:
        print("Unknown mqtt command {}".format(repr(cmd)))
        return

    if not water_tank_id_updated:
        print("No water tank with cmd '{}' was updated.".format(cmd))
        return
    
    settings[u"water_tanks"] = water_tanks
    with open(DATA_FILE, u"w") as f:
            json.dump(settings, f, default=serialize_datetime, indent=4)  # save to file

    client = mqtt.get_client()
    if client:
        client.publish(settings[WATER_PLUGIN_DATA_PUBLISH_MQTT_TOPIC], json.dumps(water_tanks, default=serialize_datetime), qos=1, retain=True)


def on_data_request_mqtt_message(client, msg):
    """
    Callback when MQTT message is received requesting water tank data
    """
    settings = get_settings()
    water_tanks = settings[u"water_tanks"]
    client = mqtt.get_client()
    if client:
        client.publish(settings[WATER_PLUGIN_DATA_PUBLISH_MQTT_TOPIC], json.dumps(water_tanks, default=serialize_datetime), qos=1, retain=True)


def subscribe_mqtt():
    """
    Start listening for mqtt messages
    """
    settings = get_settings()

    #subscribe to data-request topic
    topic = settings[WATER_PLUGIN_REQUEST_MQTT_TOPIC]
    if topic:
        print("Subscribing to topic '{}'".format(topic))
        mqtt.subscribe(topic, on_data_request_mqtt_message, 2)

    #subscribe to sensor topics
    for wt in list( settings[u"water_tanks"].values() ):
        topic = wt[u"sensor_mqtt_topic"]
        if topic:
            print("Subscribing to topic '{}'".format(topic))
            mqtt.subscribe(topic, on_sensor_mqtt_message, 2)

def unsubscribe_mqtt():
    settings = get_settings()
    topic = settings[WATER_PLUGIN_REQUEST_MQTT_TOPIC]
    if topic:
        mqtt.unsubscribe(topic)

    for wt in list( settings[u"water_tanks"].values() ):
        topic = wt[u"sensor_mqtt_topic"]
        if topic:
            mqtt.unsubscribe(topic)

def refresh_mqtt_subscriptions():
    unsubscribe_mqtt()
    subscribe_mqtt()    

class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """

    def GET(self):
        try:
            with open(DATA_FILE, u"r") as f:  # Read settings from json file if it exists
                settings = json.load(f)
        except IOError:  # If file does not exist return empty value
            settings = _settings

        water_tank_id = None
        if 'water_tank_id' in web.input():
            water_tank_id = web.input()["water_tank_id"]

        # settings["water_tanks"] = settings["water_tanks"].values()        
        # print("Sending settings: {}".format(json.dumps(settings, default=serialize_datetime, indent=4)))
        return template_render.water_tank(settings, gv.pnames, water_tank_id)  # open settings page


class save_settings(ProtectedPage):
    """
    Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """

    def POST(self):
        d = (
            web.input()
        )  # Dictionary of values returned as query string from settings page.
        print('Received: {}'.format(json.dumps(d, default=serialize_datetime, indent=4))) # for testing
        settings = get_settings()
        settings[u"mqtt_broker_ws_port"] = d[u"mqtt_broker_ws_port"]
        settings[WATER_PLUGIN_REQUEST_MQTT_TOPIC] = d[WATER_PLUGIN_REQUEST_MQTT_TOPIC]
        settings[WATER_PLUGIN_REQUEST_MQTT_TOPIC] = d[WATER_PLUGIN_REQUEST_MQTT_TOPIC]
        
        water_tank = WaterTankFactory.FromDict(d)
        original_water_tank_id = d[u"original_water_tank_id"]
        
        if d[u"id"]:
            if d[u"action"] == "add":
                #add new water_Tank
                print('Adding new water tank: {}'.format(json.dumps(water_tank, default=serialize_datetime, indent=4)))
                settings['water_tanks'][water_tank.id] = water_tank
            elif d[u"action"] == "update" and original_water_tank_id:
                print('Updating water tank with id: "{}". New values: {}'.format(original_water_tank_id, json.dumps(water_tank, default=serialize_datetime, indent=4)))
                wt = settings['water_tanks'][original_water_tank_id]
                print('Old values: {}'.format(json.dumps(wt, default=serialize_datetime, indent=4)))
                water_tank.last_updated = wt["last_updated"]
                # if wt["sensor_measurement"]:
                #     water_tank.UpdateSensorMeasurement(wt["sensor_measurement"])
                if water_tank.id == original_water_tank_id:
                    settings['water_tanks'][original_water_tank_id] = water_tank
                else:
                    del settings['water_tanks'][original_water_tank_id]
                    settings['water_tanks'][water_tank.id] = water_tank
                
        with open(DATA_FILE, u"w") as f:
            json.dump(settings, f, default=serialize_datetime, indent=4)  # save to file
        print('Saved: {}'.format(json.dumps(settings, default=serialize_datetime, indent=4)))

        if d[u"id"] and (d[u"action"] == "add" or (d[u"action"] == "update" and original_water_tank_id)):
            refresh_mqtt_subscriptions()
            raise web.seeother(u"/water-tank-sp?water_tank_id=" + d[u"id"])  # Return user to home page.
        else:
            raise web.seeother(u"/water-tank-sp")  # Return user to home page.


class get_all(ProtectedPage):
    """
    Read last saved water-tank data and return it as json
    """
    def GET(self):
        print(u"Reading water tank data")
        data = readWaterTankData()
        web.header('Content-Type', 'application/json')
        return json.dumps(data, default=serialize_datetime)
    
class get_mqtt_settings(ProtectedPage):
    """
    Return the mqtt settings. Js/Paho will use them to
    subscibe to water tank topics and update the relevant
    widgets
    """
    def GET(self):
        water_tank_settings = get_settings()
        settings = mqtt.get_settings()
        settings[u"mqtt_broker_ws_port"] = int(water_tank_settings[u"mqtt_broker_ws_port"])
        settings[WATER_PLUGIN_REQUEST_MQTT_TOPIC] = water_tank_settings[WATER_PLUGIN_REQUEST_MQTT_TOPIC]
        settings[WATER_PLUGIN_DATA_PUBLISH_MQTT_TOPIC] = water_tank_settings[WATER_PLUGIN_DATA_PUBLISH_MQTT_TOPIC]
        # Get the ip in case of localhost or 127.0.0.1
        # from https://stackoverflow.com/a/28950776
        if settings['broker_host'].lower() in ['localhost', '127.0.0.1']:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0)
            try:
                # doesn't even have to be reachable
                s.connect(('10.254.254.254', 1))
                IP = s.getsockname()[0]
            except Exception:
                IP = '127.0.0.1'
            finally:
                s.close()
            settings['broker_host'] = IP
    
        return json.dumps(settings, default=serialize_datetime)

class delete(ProtectedPage)    :
    """
    Deletes a water tank record from settings based on water tank id
    """
    def POST(self):
        data = web.input()
        # print(repr(data))
        id = data[u"original_water_tank_id"]
        # print('id: {}\n'.format(id))
        settings = get_settings()
        if id in settings[u"water_tanks"]:
            del settings[u"water_tanks"][id]
            # print('Settings after delete:{}'.format(repr(settings)))            
            with open(DATA_FILE, u"w") as f:
                json.dump(settings, f, default=serialize_datetime)  # save to file
            refresh_mqtt_subscriptions()
        raise web.seeother(u"/water-tank-sp")  # open settings page        

#  Run when plugin is loaded
detect_water_tank_js() # add water_tank.js to base.html if ncessary
load_programs() # in order to load program names in gv.pnames
subscribe_mqtt()
