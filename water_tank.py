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
import xmpp
import smtplib
from email.mime.text import MIMEText

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings
from sip import template_render  #  Needed for working with web.py templates
from urls import urls  # Get access to SIP's URLs
import web  # web.py framework
from webpages import ProtectedPage  # Needed for security
from webpages import showInFooter # Enable plugin to display readings in UI footer
from webpages import showOnTimeline # Enable plugin to display station data on timeline
from webpages import report_program_toggle 
from plugins import mqtt
from helpers import load_programs, jsave, run_program


class WaterTankType(IntEnum):
    RECTANGULAR = 1
    CYLINDRICAL_HORIZONTAL = 2
    CYLINDRICAL_VERTICAL = 3
    ELLIPTICAL = 4


class WaterTankState(IntEnum):
    NORMAL = 1
    OVERFLOW = 2
    OVERFLOW_UNSAFE = 3
    WARNING = 4
    WARNING_UNSAFE = 5
    CRITICAL = 6
    CRITICAL_UNSAFE = 7


class WaterTankProgram():
    def __init__(self, id, run, enable, suspend, original_enabled = None):
        self.id = id
        self.original_enabled = original_enabled
        self.run = run
        self.enable = enable
        self.suspend = suspend


class WaterTank(ABC):
    def __init__(self, id, label, type, sensor_mqtt_topic, invalid_sensor_measurement_email, invalid_sensor_measurement_xmpp, sensor_id, sensor_offset_from_top, min_valid_sensor_measurement, max_valid_sensor_measurement, enabled, overflow_level, overflow_email, overflow_xmpp, overflow_safe_level, overflow_programs, warning_level, warning_safe_level, warning_email, warning_xmpp, warning_programs, critical_level, critical_safe_level, critical_email, critical_xmpp, critical_programs, loss_email, loss_xmpp):
        self.id = id
        self.label = label
        self.type = type
        self.sensor_mqtt_topic = sensor_mqtt_topic
        self.invalid_sensor_measurement_email = invalid_sensor_measurement_email
        self.invalid_sensor_measurement_xmpp = invalid_sensor_measurement_xmpp
        self.sensor_id = sensor_id
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
        self.warning_safe_level = warning_safe_level
        self.warning_email = warning_email
        self.warning_xmpp = warning_xmpp
        self.warning_programs = warning_programs
        self.critical_level = critical_level
        self.critical_safe_level = critical_safe_level
        self.critical_email = critical_email
        self.critical_xmpp = critical_xmpp
        self.critical_programs = critical_programs
        self.loss_email = loss_email
        self.loss_xmpp = loss_xmpp
        self.last_updated = None
        self.sensor_measurement = None
        self.invalid_sensor_measurement = False
        self.percentage = None
        self.order = None
        self.state = None

    def InitFromDict(self, d):
        overflow_programs = {}
        warning_programs = {}
        critical_programs = {}
        for i in range(0, len(gv.pnames)):
            overflow_programs[i] = WaterTankProgram(
                id = i,
                run = ('overflow_pr_run_' + str(i) in d and str(d['overflow_pr_run_' + str(i)]) in ["on", "true", "True"]),
                enable = ('overflow_pr_enable_' + str(i) in d and str(d['overflow_pr_enable_' + str(i)]) in ["on", "true", "True"]),
                suspend = ('overflow_pr_suspend_' + str(i) in d and str(d['overflow_pr_suspend_' + str(i)]) in ["on", "true", "True"]),
                original_enabled = None if 'overflow_original_enabled_pr' + str(i) not in d else d['overflow_original_enabled_pr' + str(i)]
            )
        
            warning_programs[i] = WaterTankProgram(
                id = i,
                run = ('warning_pr_run_' + str(i) in d and str(d['warning_pr_run_' + str(i)]) in ["on", "true", "True"]),
                enable = ('warning_pr_enable_' + str(i) in d and str(d['warning_pr_enable_' + str(i)]) in ["on", "true", "True"]),
                suspend = ('warning_pr_suspend_' + str(i) in d and str(d['warning_pr_suspend_' + str(i)]) in ["on", "true", "True"]),
                original_enabled = None if 'warning_original_enabled_pr' + str(i) not in d else d['warning_original_enabled_pr' + str(i)]
            )
        
            critical_programs[i] = WaterTankProgram(
                id = i,
                run = ('critical_pr_run_' + str(i) in d and str(d['critical_pr_run_' + str(i)]) in ["on", "true", "True"]),
                enable = ('critical_pr_enable_' + str(i) in d and str(d['critical_pr_enable_' + str(i)]) in ["on", "true", "True"]),
                suspend = ('critical_pr_suspend_' + str(i) in d and str(d['critical_pr_suspend_' + str(i)]) in ["on", "true", "True"]),
                original_enabled = None if 'critical_original_enabled_pr' + str(i) not in d else d['critical_original_enabled_pr' + str(i)]
            )
                
        self.id = d["id"]
        self.label = d["label"]
        self.sensor_mqtt_topic = d["sensor_mqtt_topic"]
        self.invalid_sensor_measurement_email = (INVALID_SENSOR_MEASUREMENT_EMAIL in d and (str(d[INVALID_SENSOR_MEASUREMENT_EMAIL]) in ["on", "true", "True"]))
        self.invalid_sensor_measurement_xmpp = (INVALID_SENSOR_MEASUREMENT_XMPP in d and (str(d[INVALID_SENSOR_MEASUREMENT_XMPP]) in ["on", "true", "True"]))
        self.sensor_id = d["sensor_id"]
        self.sensor_offset_from_top = float(d["sensor_offset_from_top"])
        self.min_valid_sensor_measurement = None if "min_valid_sensor_measurement" not in d or not d["min_valid_sensor_measurement"] else float(d["min_valid_sensor_measurement"])
        self.max_valid_sensor_measurement = None if "max_valid_sensor_measurement"not in d or not d["max_valid_sensor_measurement"] else float(d["max_valid_sensor_measurement"])
        self.enabled = ("enabled" in d and str(d["enabled"]) in ["on", "true", "True"])
        self.overflow_level = None if not d["overflow_level"] else float(d["overflow_level"])
        self.overflow_email = ('overflow_email' in d and (str(d["overflow_email"]) in ["on", "true", "True"]))
        self.overflow_xmpp = ('overflow_xmpp' in d and (str(d["overflow_xmpp"]) in ["on", "true", "True"]))
        self.overflow_safe_level = None if not d["overflow_safe_level"] else float(d["overflow_safe_level"])
        self.overflow_programs = overflow_programs
        self.warning_level = None if not d["warning_level"] else float(d["warning_level"])
        self.warning_safe_level = None if not d["warning_safe_level"] else float(d["warning_safe_level"])
        self.warning_email = ('warning_email' in d and (str(d["warning_email"]) in ["on", "true", "True"]))
        self.warning_xmpp = ('warning_xmpp' in d and (str(d["warning_xmpp"]) in ["on", "true", "True"]))
        self.warning_programs = warning_programs
        self.critical_level = None if not d["critical_level"] else float( d["critical_level"])
        self.critical_safe_level = None if not d["critical_safe_level"] else float( d["critical_safe_level"])
        self.critical_email = ('critical_email' in d and (str(d["critical_email"]) in ["on", "true", "True"]))
        self.critical_xmpp = ('critical_xmpp' in d and (str(d["critical_xmpp"]) in ["on", "true", "True"]))
        self.critical_programs = critical_programs
        self.loss_email = ('loss_email' in d and (str(d["loss_email"]) in ["on", "true", "True"]))
        self.loss_xmpp = ('loss_xmpp' in d and (str(d["loss_xmpp"]) in ["on", "true", "True"]))
        self.last_updated = None if 'last_updated' not in d else d["last_updated"]
        self.sensor_measurement = None if 'sensor_measurement' not in d else d["sensor_measurement"]
        self.invalid_sensor_measurement = None if 'invalid_sensor_measurement' not in d else d["invalid_sensor_measurement"]
        self.percentage = None if 'percentage' not in d else d["percentage"]
        self.order = None if "order" not in d else int( d["order"])
        self.state = None if "state" not in d or d["state"] is None or d["state"] == "null" else WaterTankState( int(d["state"]) )


    def UpdateSensorMeasurement(self, sensor_id, measurement):
        self.last_updated = datetime.now().replace(microsecond=0)
        self.sensor_measurement = measurement
        if( (self.min_valid_sensor_measurement is not None and measurement < self.min_valid_sensor_measurement) or 
           (self.max_valid_sensor_measurement is not None and measurement > self.max_valid_sensor_measurement) or
           (self.GetHeight() < (measurement - self.sensor_offset_from_top)) ):
            self.invalid_sensor_measurement = True
            self.percentage = None
            send_invalid_measurement_msg(self, self.AdditionalInfo4Msg())
            return False

        self.invalid_sensor_measurement = False
        return True

    def AdditionalInfo4Msg(self):
        return "type: {}, min_valid_sensor_measurement: '{}', max_valid_sensor_measurement: '{}'".format(WaterTankType(self.type).name, self.min_valid_sensor_measurement, self.max_valid_sensor_measurement)
    
    @abstractmethod
    def GetHeight(self):
        """
        Should return the actual height of the tank. Straightforward for rectangular and vertical cylindrical.
        For hosizontal cylindrical it should be the diameter, and for elliptical it should be the vertical axis.
        """
        pass
        
    def CalculateNewState(self):
        print("In CalculateNewState, existing state:{}".format("None" if self.state is None else WaterTankState(self.state).name))

        if(self.percentage is None):
            print("New state is None")
            return None
        
        if(self.overflow_level is not None and self.percentage >= self.overflow_level):
            print("New state is OVERFLOW")
            return WaterTankState.OVERFLOW
        
        if(self.overflow_safe_level is not None and 
           (self.state in [WaterTankState.OVERFLOW, WaterTankState.OVERFLOW_UNSAFE]) and
           self.percentage >= self.overflow_safe_level and self.percentage < self.overflow_level
        ):
            print("New state is OVERFLOW_UNSAFE")
            return WaterTankState.OVERFLOW_UNSAFE
    
        if(self.critical_level is not None and self.percentage <= self.critical_level):
            print("New state is CRITICAL")
            return WaterTankState.CRITICAL
        
        if(self.critical_safe_level is not None and 
           (self.state in [WaterTankState.CRITICAL, WaterTankState.CRITICAL_UNSAFE]) and
           self.percentage <= self.critical_safe_level and self.percentage > self.critical_level
        ):
            print("New state is CRITICAL_UNSAFE")
            return WaterTankState.CRITICAL_UNSAFE

        # Tank is not in OVERFLOW, OVERFLOW_UNSAFE, CRITICAL, CRITICAL_UNSAFE
        if(self.warning_level is not None and self.percentage <= self.warning_level):
            print("New state is WARNING")
            return WaterTankState.WARNING
        
        # Tank is not in OVERFLOW, OVERFLOW_UNSAFE, CRITICAL, CRITICAL_UNSAFE, WARNING
        if(self.warning_safe_level is not None and 
           (self.state in [WaterTankState.WARNING, WaterTankState.WARNING_UNSAFE]) and
           self.percentage <= self.warning_safe_level and self.percentage > self.warning_level
        ):
            print("New state is WARNING_UNSAFE")
            return WaterTankState.WARNING_UNSAFE

        # Tank is not in OVERFLOW, OVERFLOW_UNSAFE, CRITICAL, CRITICAL_UNSAFE, WARNING, WARNING_UNSAFE
        # and there is a valid percentage
        print("New state is NORMAL")
        return WaterTankState.NORMAL

    def RevertPrograms(self, state):
        """
        Put progams to their original enabled state.
        This method should called when exiting one of OVERFLOW, WARNING, CRITICAL states
        """
        valid_states = [WaterTankState.OVERFLOW, WaterTankState.WARNING, WaterTankState.CRITICAL]
        if(state not in valid_states):
            raise Exception("Invalid state: '{}'. Only states {} allowed in ActivatePrograms".
                            format(state.name, ", ".join(valid_states)))
        
        print("Reverting {} programs".format(state.name))
        prs = self.overflow_programs
        if(state == WaterTankState.WARNING):
            prs = self.warning_programs
        elif(state == WaterTankState.CRITICAL):
            prs = self.critical_programs

        program_changed = False
        for i in range(0, len(gv.pd) ):
            if(prs[i].original_enabled is not None and gv.pd[i]["enabled"] != prs[i].original_enabled):
                gv.pd[i]["enabled"] = prs[i].original_enabled
                program_changed = True

        if(program_changed):
            jsave(gv.pd, "programData")
            report_program_toggle()

    def ActivatePrograms(self, state):
        """
        Enable progams.
        This method should called when entering one of OVERFLOW, WARNING, CRITICAL states
        """
        valid_states = [WaterTankState.OVERFLOW, WaterTankState.WARNING, WaterTankState.CRITICAL]
        if(state not in valid_states):
            raise Exception("Invalid state: '{}'. Only states {} allowed in ActivatePrograms".
                            format(state.name, ", ".join(valid_states)))
        
        print("Enabling {} programs".format(state.name))
        prs = self.overflow_programs
        if(state == WaterTankState.WARNING):
            prs = self.warning_programs
        elif(state == WaterTankState.CRITICAL):
            prs = self.critical_programs

        program_changed = False
        for i in range(0, len(gv.pd) ):
            if(prs[i].run):
                print("Running program {}. {}".format(i, gv.pnames[i]))
                run_program(i)
            if(prs[i].suspend and gv.pd[i]["enabled"] == 1):
                print("Disabling previously enabled program {}. {}".format(i, gv.pnames[i]))
                prs[i].original_enabled = gv.pd[i]["enabled"]
                gv.pd[i]["enabled"] = 0
                program_changed = True
            if(prs[i].enable and gv.pd[i]["enabled"] == 0):
                print("Enabling previously disabled program {}. {}".format(i, gv.pnames[i]))
                prs[i].original_enabled = gv.pd[i]["enabled"]
                gv.pd[i]["enabled"] = 1
                program_changed = True

        if(program_changed):
            jsave(gv.pd, "programData")
            report_program_toggle()

    def SetState(self):
        new_state = self.CalculateNewState()
        if(new_state is None or self.state == new_state):
            return
        
        # water tank is definitely entering a new state
        #
        # Revert activated programs
        if( (self.state == WaterTankState.OVERFLOW and new_state != WaterTankState.OVERFLOW_UNSAFE) or
            (self.state == WaterTankState.OVERFLOW_UNSAFE and new_state != WaterTankState.OVERFLOW) or
            (self.state == WaterTankState.CRITICAL and new_state != WaterTankState.CRITICAL_UNSAFE) or
            (self.state == WaterTankState.CRITICAL_UNSAFE and new_state != WaterTankState.CRITICAL) or
            (self.state == WaterTankState.WARNING and new_state != WaterTankState.WARNING_UNSAFE) or
            (self.state == WaterTankState.WARNING_UNSAFE and new_state != WaterTankState.WARNING)
        ):
            self.RevertPrograms(self.state)

        #
        # Activate programs for entering new state
        if( (new_state == WaterTankState.OVERFLOW and self.state != WaterTankState.OVERFLOW_UNSAFE) or
            (new_state == WaterTankState.CRITICAL and self.state != WaterTankState.CRITICAL_UNSAFE) or
            (new_state == WaterTankState.WARNING and self.state != WaterTankState.WARNING_UNSAFE)
        ):
            self.ActivatePrograms(new_state)

        self.state = new_state
            
    # def ObsoleteSetState(self, percentageBefore):
    #     """
    #     Set the state of the water tank. A measurement has been used to calculate
    #     the new percentage, and self.state still holds the value it had from before
    #     updating percentage.
    #     """
    #     print("SetState. percentage: {}".format(self.percentage))
    #     if( self.percentage is None ):
    #         self.state = None
    #         return
        
    #     # entry to overflow for ***activating programs***: 
    #     # overflow_level exists
    #     # cross over overflow_level
    #     # there is no previous measurement or 
    #     # there is one lower than overflow_level and the tank is not already in OVERFLOW_UNSAFE
    #     if( self.overflow_level is not None and 
    #         self.percentage >= self.overflow_level and
    #         (percentageBefore is None or ( self.state != WaterTankState.OVERFLOW_UNSAFE and percentageBefore < self.overflow_level) )
    #     ):
    #         print("Entered OVERFLOW, ***activating programs***")
    #         self.state = WaterTankState.OVERFLOW
    #         return
        
    #     # in overlfow
    #     if( self.overflow_level is not None and 
    #         self.percentage >= self.overflow_level  
    #     ):
    #         print("In OVERFLOW")
    #         self.state = WaterTankState.OVERFLOW
    #         return
        
    #     # exiting overflow when no overflow_safe_level exists for ***reverting programs***:
    #     # tank is already in OVERFLOW
    #     # level is lower than overflow_level
    #     # there is no overflow_safe_level
    #     if( self.state == WaterTankState.OVERFLOW and
    #         self.percentage < self.overflow_level and
    #         self.overflow_safe_level is None
    #     ):
    #         print("Exited OVERFLOW, no SAFE LEVEL, ***reverting programs***")            
        
    #     #entry to overflow_unsafe from overflow
    #     if( self.state == WaterTankState.OVERFLOW and 
    #         self.overflow_safe_level is not None and
    #         percentageBefore is not None and
    #         percentageBefore >= self.overflow_level and
    #         self.percentage < self.overflow_level and  
    #         self.percentage > self.overflow_safe_level
    #     ):
    #         print("Entered OVERFLOW_UNSAFE")
    #         self.state = WaterTankState.OVERFLOW_UNSAFE
    #         return
        
    #     # in overlfow unsafe
    #     if( self.state == WaterTankState.OVERFLOW_UNSAFE and
    #         self.overflow_safe_level is not None and 
    #         self.percentage < self.overflow_level  and
    #         self.percentage > self.overflow_safe_level  
    #     ):
    #         print("In OVERFLOW_UNSAFE")            
    #         self.state = WaterTankState.OVERFLOW_UNSAFE
    #         return
                
    #     # exiting OVERFLOW_UNSAFE to lower level for ***reverting programs***:
    #     # tank is already in state OVERFLOW_UNSAFE
    #     # level is lower than overflow_safe_level
    #     if( self.state == WaterTankState.OVERFLOW_UNSAFE and
    #         self.percentage < self.overflow_safe_level 
    #     ):
    #         print("Exited OVERFLOW_UNSAFE, ***reverting programs***")
            
    #     # entry to critical for ***activating programs***: 
    #     # critical_level exists
    #     # cross over critical_level
    #     # there is no previous measurement or 
    #     # there is one higher than critical_level and the tank is not already in CRITICAL_UNSAFE
    #     if( self.critical_level is not None and 
    #         self.percentage <= self.critical_level and
    #         (percentageBefore is None or ( self.state != WaterTankState.CRITICAL_UNSAFE and percentageBefore > self.critical_level) )
    #     ):
    #         print("Entered CRITICAL, ***activating programs***")
    #         self.state = WaterTankState.CRITICAL
    #         return
        
    #     # in critical
    #     if( self.critical_level is not None and
    #         self.percentage <= self.critical_level
    #     ):
    #         print("In CRITICAL")            
    #         self.state = WaterTankState.CRITICAL
    #         return

    #     # exiting critical when no critical_safe_level exists for ***reverting programs***:
    #     # tank is already in CRITICAL
    #     # level is lower than critical_level
    #     # there is no critical_safe_level
    #     if( self.state == WaterTankState.CRITICAL and
    #         self.percentage > self.critical_level and
    #         self.critical_safe_level is None
    #     ):
    #         print("Exited CRITICAL, no SAFE LEVEL, ***reverting programs***")            
        
    #     # entry to critical unsafe from critical
    #     if( self.state == WaterTankState.CRITICAL and
    #         self.critical_safe_level is not None and
    #         percentageBefore is not None and
    #         percentageBefore <= self.critical_level and
    #         self.percentage > self.critical_level and 
    #         self.percentage < self.critical_safe_level
    #     ):
    #         print("Entered CRITICAL_UNSAFE")
    #         self.state = WaterTankState.CRITICAL_UNSAFE
    #         return
        
    #     # in critical unsafe
    #     if( self.state == WaterTankState.CRITICAL_UNSAFE and
    #         self.critical_safe_level is not None and
    #         self.percentage > self.critical_level and 
    #         self.percentage < self.critical_safe_level
    #     ):
    #         print("In CRITICAL_UNSAFE")            
    #         self.state = WaterTankState.CRITICAL_UNSAFE
    #         return

    #     # exiting CRITICAL_UNSAFE to higher level for ***reverting programs***:
    #     # tank is already in state CRITICAL_UNSAFE
    #     # level is higher than critical_safe_level
    #     if( self.state == WaterTankState.CRITICAL_UNSAFE and
    #         self.percentage > self.critical_safe_level 
    #     ):
    #         print("Exited CRITICAL_UNSAFE, ***reverting programs***")

    #     # entry to warning for ***activating programs***: 
    #     # warning_level exists
    #     # cross over warning_level
    #     # there is no previous measurement or 
    #     # there is one higher than warning_level and the tank is not already in WARNING_UNSAFE
    #     if( self.warning_level is not None and 
    #         self.percentage <= self.warning_level and
    #         (percentageBefore is None or ( self.state != WaterTankState.WARNING_UNSAFE and percentageBefore > self.warning_level) )
    #     ):
    #         print("Entered WARNING, ***activating programs***")
    #         self.state = WaterTankState.WARNING
    #         return
        
    #     # in warning
    #     if( self.warning_level is not None and
    #         self.percentage <= self.warning_level
    #     ):
    #         print("In WARNING")
    #         self.state = WaterTankState.WARNING
    #         return
        
    #     # exiting warning when no warning_safe_level exists for ***reverting programs***:
    #     # tank is already in WARNING
    #     # level is higher than warning_level
    #     # there is no overflow_safe_level
    #     if( self.state == WaterTankState.WARNING and
    #         self.percentage > self.warning_level and
    #         self.warning_safe_level is None
    #     ):
    #         print("Exited WARNING, no SAFE LEVEL, ***reverting programs***") 

    #     # entry to warning unsafe from warning
    #     if( self.state == WaterTankState.WARNING and
    #         self.warning_safe_level is not None and
    #         percentageBefore is not None and
    #         percentageBefore <= self.warning_level and
    #         self.percentage > self.warning_level and 
    #         self.percentage < self.warning_safe_level
    #     ):
    #         print("Entered WARNING_UNSAFE")
    #         self.state = WaterTankState.WARNING_UNSAFE
    #         return
        
    #     # in warning unsafe
    #     if( self.state == WaterTankState.WARNING_UNSAFE and
    #         self.warning_safe_level is not None and
    #         self.percentage > self.warning_level and 
    #         self.percentage < self.warning_safe_level
    #     ):
    #         print("In WARNING_UNSAFE")            
    #         self.state = WaterTankState.WARNING_UNSAFE
    #         return
        
    #     # exiting WARNING_UNSAFE to higher level for ***reverting programs***:
    #     # tank is already in state WARNING_UNSAFE
    #     # level is higher than warning_safe_level
    #     if( self.state == WaterTankState.OVERFLOW_UNSAFE and
    #         self.percentage < self.warning_safe_level 
    #     ):
    #         print("Exited WARNING_UNSAFE, ***reverting programs***")
        
    #     # if the percentage is not in any of the level ranges
    #     # it is normal
    #     self.state = WaterTankState.NORMAL


class WaterTankRectangular(WaterTank):
    def __init__(self, id = None, label = None, width = None, length = None, height = None, sensor_mqtt_topic = None, invalid_sensor_measurement_email = None, invalid_sensor_measurement_xmpp = None, sensor_id = None, sensor_offset_from_top = None, min_valid_sensor_measurement = None,max_valid_sensor_measurement = None, enabled = None, overflow_level = None, overflow_email = None, overflow_xmpp = None, overflow_safe_level = None, overflow_programs = None, warning_level = None, warning_safe_level = None, warning_email = None, warning_xmpp = None, warning_programs = None, critical_level = None, critical_safe_level = None, critical_email = None, critical_xmpp = None, critical_programs = None, loss_email = None, loss_xmpp = None):
        super().__init__(id, label, WaterTankType.RECTANGULAR.value, sensor_mqtt_topic, invalid_sensor_measurement_email, invalid_sensor_measurement_xmpp, sensor_id, sensor_offset_from_top, min_valid_sensor_measurement, max_valid_sensor_measurement, enabled, overflow_level, overflow_email, overflow_xmpp, overflow_safe_level, overflow_programs, warning_level, warning_safe_level, warning_email, warning_xmpp, warning_programs, critical_level, critical_safe_level, critical_email, critical_xmpp, critical_programs, loss_email, loss_xmpp)
        self.width = width
        self.length = length
        self.height = height
    
    def FromDict(d):
        wt = WaterTankRectangular()
        wt.InitFromDict(d)
        wt.width = None if not d["width"] else float(d["width"])
        wt.length = None if not d["length"] else float(d["length"])
        wt.height = None if not d["height"] else float(d["height"])
        return wt
                

    def UpdateSensorMeasurement(self, sensor_id, measurement):
        if not super().UpdateSensorMeasurement(sensor_id, measurement):
            return False
        
        if self.width is not None and self.length is not None and self.height is not None:
            volume = self.width * self.length * self.height
            self.percentage = round(100.0 * (self.height - (measurement-self.sensor_offset_from_top)) / self.height)
            if self.height < (measurement-self.sensor_offset_from_top):
                self.invalid_sensor_measurement = True
                send_invalid_measurement_msg(self,self.AdditionalInfo4Msg())
                # print('WaterTankRectangular.UpdateSensorMeasurement returning False')
                return False
        
        self.SetState()
        return True

    def GetHeight(self):
        return self.height


class WaterTankCylindricalHorizontal(WaterTank):
    def __init__(self, id = None, label = None, length = None, diameter = None, sensor_mqtt_topic = None, invalid_sensor_measurement_email = None, invalid_sensor_measurement_xmpp = None, sensor_id = None, sensor_offset_from_top = None, min_valid_sensor_measurement = None,max_valid_sensor_measurement = None, enabled = None, overflow_level = None, overflow_email = None, overflow_xmpp = None, overflow_safe_level = None, overflow_programs = None, warning_level = None, warning_safe_level = None, warning_email = None, warning_xmpp = None, warning_programs = None, critical_level = None, critical_safe_level = None, critical_email = None, critical_xmpp = None, critical_programs = None, loss_email = None, loss_xmpp = None):
        super().__init__(id, label, WaterTankType.CYLINDRICAL_HORIZONTAL.value, sensor_mqtt_topic, invalid_sensor_measurement_email, invalid_sensor_measurement_xmpp, sensor_id, sensor_offset_from_top, min_valid_sensor_measurement, max_valid_sensor_measurement, enabled, overflow_level, overflow_email, overflow_xmpp, overflow_safe_level, overflow_programs, warning_level, warning_safe_level, warning_email, warning_xmpp, warning_programs, critical_level, critical_safe_level, critical_email, critical_xmpp, critical_programs, loss_email, loss_xmpp)
        self.length = length
        self.diameter = diameter

    def FromDict(d):
        wt = WaterTankCylindricalHorizontal()
        wt.InitFromDict(d)
        wt.length = None if not d["length"] else float(d["length"])
        wt.diameter = None if not d["diameter"] else float(d["diameter"])
        return wt

    def UpdateSensorMeasurement(self, sensor_id, measurement):
        if not super().UpdateSensorMeasurement(sensor_id, measurement):
            return False
        if self.diameter is not None and self.length is not None:
            volume = self.diameter * self.length
            r = self.diameter / 2.0
            h = self.diameter - (measurement-self.sensor_offset_from_top)
            if self.diameter < (measurement-self.sensor_offset_from_top):
                self.invalid_sensor_measurement = True
            try:
                liquid_volume = acos((r-h)/r)*(r**2) - (r-h)*sqrt(2*r*h - (h**2))
                self.percentage = round(100.0 * liquid_volume / volume)
            except:
                self.invalid_sensor_measurement = True
                self.percentage = None
                return False

        self.SetState()
        return True

    def GetHeight(self):
        return self.diameter


class WaterTankCylindricalVertical(WaterTank):
    def __init__(self, id = None, label = None, diameter = None, height = None, sensor_mqtt_topic = None, invalid_sensor_measurement_email = None, invalid_sensor_measurement_xmpp = None, sensor_id = None, sensor_offset_from_top = None, min_valid_sensor_measurement = None,max_valid_sensor_measurement = None, enabled = None, overflow_level = None, overflow_email = None, overflow_xmpp = None, overflow_safe_level = None, overflow_programs = None, warning_level = None, warning_safe_level = None, warning_email = None, warning_xmpp = None, warning_programs = None, critical_level = None, critical_safe_level = None, critical_email = None, critical_xmpp = None, critical_programs = None, loss_email = None, loss_xmpp = None):
        super().__init__(id, label, WaterTankType.CYLINDRICAL_VERTICAL.value, sensor_mqtt_topic, invalid_sensor_measurement_email, invalid_sensor_measurement_xmpp, sensor_id, sensor_offset_from_top, min_valid_sensor_measurement, max_valid_sensor_measurement, enabled, overflow_level, overflow_email, overflow_xmpp, overflow_safe_level, overflow_programs, warning_level, warning_safe_level, warning_email, warning_xmpp, warning_programs, critical_level, critical_safe_level, critical_email, critical_xmpp, critical_programs, loss_email, loss_xmpp)
        self.height = height
        self.diameter = diameter

    def FromDict(d):
        wt = WaterTankCylindricalVertical()
        wt.InitFromDict(d)
        wt.height = None if not d["height"] else float(d["height"])
        wt.diameter = None if not d["diameter"] else float(d["diameter"])
        return wt

    def UpdateSensorMeasurement(self, sensor_id, measurement):
        if not super().UpdateSensorMeasurement(sensor_id, measurement):
            return False
        
        if self.diameter is not None and self.height is not None:
            volume = self.diameter * self.height
            self.percentage = round(100.0 * (self.height - (measurement-self.sensor_offset_from_top)) / self.height)

            if self.height < (measurement-self.sensor_offset_from_top):
                self.invalid_sensor_measurement = True
                return False
            
        self.SetState()
        return True

    def GetHeight(self):
        return self.height


class WaterTankElliptical(WaterTank):
    def __init__(self, id = None, label = None, length = None, horizontal_axis = None, vertical_axis = None, sensor_mqtt_topic = None, invalid_sensor_measurement_email = None, invalid_sensor_measurement_xmpp = None, sensor_id = None, sensor_offset_from_top = None, min_valid_sensor_measurement = None,max_valid_sensor_measurement = None, enabled = None, overflow_level = None, overflow_email = None, overflow_xmpp = None, overflow_safe_level = None, overflow_programs = None, warning_level = None, warning_safe_level = None, warning_email = None, warning_xmpp = None, warning_programs = None, critical_level = None, critical_safe_level = None, critical_email = None, critical_xmpp = None, critical_programs = None, loss_email = None, loss_xmpp = None):
        super().__init__(id, label, WaterTankType.ELLIPTICAL.value, sensor_mqtt_topic, invalid_sensor_measurement_email, invalid_sensor_measurement_xmpp, sensor_id, sensor_offset_from_top, min_valid_sensor_measurement, max_valid_sensor_measurement, enabled, overflow_level, overflow_email, overflow_xmpp, overflow_safe_level, overflow_programs, warning_level, warning_safe_level, warning_email, warning_xmpp, warning_programs, critical_level, critical_safe_level, critical_email, critical_xmpp, critical_programs, loss_email, loss_xmpp)
        self.length = length
        self.horizontal_axis = horizontal_axis
        self.vertical_axis = vertical_axis

    def FromDict(d):
        wt = WaterTankElliptical()
        wt.InitFromDict(d)
        wt.length = None if not d["length"] else float(d["length"])
        wt.horizontal_axis = None if not d["horizontal_axis"] else float(d["horizontal_axis"])
        wt.vertical_axis = None if not d["vertical_axis"] else float(d["vertical_axis"])
        return wt

    def UpdateSensorMeasurement(self, sensor_id, measurement):
        if not super().UpdateSensorMeasurement(sensor_id, measurement):
            return False
        
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
                self.percentage = round(100.0 * liquid_volume / volume)
            except:
                self.invalid_sensor_measurement = True
                self.percentage = None
                return False
            
        self.SetState()
        return True

    def GetHeight(self):
        return self.vertical_axis


class WaterTankFactory():
    def FromDict(d, addSettingsProperties = True):
        wt = None
        type = int(d["type"])
        if type == WaterTankType.RECTANGULAR.value:
            wt = WaterTankRectangular.FromDict(d)
        elif type == WaterTankType.CYLINDRICAL_HORIZONTAL.value:
            wt = WaterTankCylindricalHorizontal.FromDict(d)
        elif type == WaterTankType.CYLINDRICAL_VERTICAL.value:
            wt = WaterTankCylindricalVertical.FromDict(d)
        elif type == WaterTankType.ELLIPTICAL.value:
            wt = WaterTankElliptical.FromDict(d)
        
        # if(addSettingsProperties):
        #     settings = get_settings()
        #     if( wt.id in settings["water_tanks"]):
        #         wt.last_updated = settings["water_tanks"][wt.id]["last_updated"]
        #         wt.sensor_measurement = settings["water_tanks"][wt.id]["sensor_measurement"]
        #         wt.invalid_sensor_measurement = settings["water_tanks"][wt.id]["invalid_sensor_measurement"]
        #         wt.percentage = settings["water_tanks"][wt.id]["percentage"]

        return wt


DATA_FILE = u"./data/water_tank.json"
WATER_PLUGIN_REQUEST_MQTT_TOPIC = u"request_subscribe_mqtt_topic"
WATER_PLUGIN_DATA_PUBLISH_MQTT_TOPIC = u"data_publish_mqtt_topic"
XMPP_USERNAME = u"xmpp_username"
XMPP_PASSWORD = u"xmpp_password"
XMPP_SERVER = u"xmpp_server"
XMPP_SUBJECT = u"xmpp_subject"
XMPP_RECIPIENTS = u"xmpp_recipients"
EMAIL_USERNAME = u"email_username"
EMAIL_PASSWORD = u"email_password"
EMAIL_SERVER = u"email_server"
EMAIL_SERVER_PORT = u"email_server_port"
EMAIL_SUBJECT = u"email_subject"
EMAIL_RECIPIENTS = u"email_recipients"
UNRECOGNISED_MSG = u"unrecognised_msg"
UNRECOGNISED_MSG_EMAIL = u"unrecognised_msg_email"
UNRECOGNISED_MSG_XMPP = u"unrecognised_msg_xmpp"
XMPP_UNASSOCIATED_SENSOR_MSG = u"xmpp_unassociated_sensor_msg"
UNASSOCIATED_SENSOR_XMPP = u"unassociated_sensor_xmpp"
UNASSOCIATED_SENSOR_EMAIL = u"unassociated_sensor_email"
XMPP_INVALID_SENSOR_MEASUREMENT_MSG = u"xmpp_invalid_sensor_measurement_msg"
INVALID_SENSOR_MEASUREMENT_XMPP = u"invalid_sensor_measurement_xmpp"
INVALID_SENSOR_MEASUREMENT_EMAIL = u"invalid_sensor_measurement_email"
XMPP_OVERFLOW_MSG = u"xmpp_overflow_msg"
XMPP_WARNING_MSG = u"xmpp_warning_msg"
XMPP_CRITICAL_MSG = u"xmpp_critical_msg"
XMPP_WATER_LOSS_MSG = u"water_loss_msg"
xmpp_msg_placeholders = ["water_tank_id", "water_tank_label", "sensor_id", "measurement", "last_updated", "mqtt_topic"]
_settings = {
    u"mqtt_broker_ws_port": 8080,
    WATER_PLUGIN_REQUEST_MQTT_TOPIC: "WaterTankDataRequest",
    WATER_PLUGIN_DATA_PUBLISH_MQTT_TOPIC: "WaterTankData",
    XMPP_USERNAME: "ahat_sip@ahat1.duckdns.org",
    XMPP_PASSWORD: u"312ggp12",
    XMPP_SERVER: u"ahat1.duckdns.org",
    XMPP_SUBJECT: u"SIP",
    XMPP_RECIPIENTS: u"ahat@ahat1.duckdns.org",
    EMAIL_USERNAME: "ahatzikonstantinou.SIP@gmail.com",
    EMAIL_PASSWORD: u"pbem zcnq noiq zygz",
    EMAIL_SERVER: u"smtp.gmail.com",
    EMAIL_SERVER_PORT: 465,
    EMAIL_SUBJECT: u"SIP",
    EMAIL_RECIPIENTS: u"ahatzikonstantinou@gmail.com,ahatzikonstantinou@protonmail.com",
    UNRECOGNISED_MSG: u"Unrecognised mqtt msg! MQTT topic:'{mqtt_topic}', date:'{date}', msg:[{message}]",
    UNRECOGNISED_MSG_EMAIL: True,
    UNRECOGNISED_MSG_XMPP: True,
    XMPP_UNASSOCIATED_SENSOR_MSG: u"Unassociated sensor measurement msg! sensor_id:'{sensor_id}', measurement:'{measurement}', date:'{last_updated}', mqtt topic:'{mqtt_topic}'",
    UNASSOCIATED_SENSOR_XMPP: True,
    UNASSOCIATED_SENSOR_EMAIL: True,
    XMPP_INVALID_SENSOR_MEASUREMENT_MSG: u"Invalid sensor measurement! water tank:'{water_tank_id}'/'{water_tank_label}', sensor_id:'{sensor_id}', percentage: {percentage}%, measurement:'{measurement}', date:'{last_updated}', mqtt topic:'{mqtt_topic}'. Additional info:[{additional_info}]",
    XMPP_OVERFLOW_MSG: u"Overflow! water tank:'{water_tank_id}'/'{water_tank_label}', sensor_id:'{sensor_id}', percentage: {percentage}%, measurement:'{measurement}', date:'{last_updated}', mqtt topic:'{mqtt_topic}'. Additional info:[{additional_info}]",
    XMPP_WARNING_MSG: u"Warning! water tank:'{water_tank_id}'/'{water_tank_label}', sensor_id:'{sensor_id}', percentage: {percentage}%, measurement:'{measurement}', date:'{last_updated}', mqtt topic:'{mqtt_topic}'. Additional info:[{additional_info}]",
    XMPP_CRITICAL_MSG: u"Critical! water tank:'{water_tank_id}'/'{water_tank_label}', sensor_id:'{sensor_id}', percentage: {percentage}%, measurement:'{measurement}', date:'{last_updated}', mqtt topic:'{mqtt_topic}'. Additional info:[{additional_info}]",
    XMPP_WATER_LOSS_MSG: u"Water loss! water tank:'{water_tank_id}'/'{water_tank_label}', sensor_id:'{sensor_id}', percentage: {percentage}%, measurement:'{measurement}', date:'{last_updated}', mqtt topic:'{mqtt_topic}'. Additional info:[{additional_info}]",
    
    u"water_tanks": {}
        # {
        # "water_tank_1": {
        #     "id": "water_tank_1",
        #     "label": "\u03a4\u03c3\u03b9\u03bc\u03b5\u03bd\u03c4\u03ad\u03bd\u03b9\u03b1",
        #     "type": 1,
        #     "sensor_mqtt_topic": "WATER_TANK_MEASUREMENT",
        #     INVALID_SENSOR_MEASUREMENT_XMPP: True,
        #     INVALID_SENSOR_MEASUREMENT_EMAIL: True,
        #     "sensor_offset_from_top": 0.0,
        #     "enabled": True,
        #     "overflow_level": 80.0,
        #     "overflow_email": True,
        #     "overflow_xmpp": True,
        #     "overflow_safe_level": None,
        #     "overflow_programs": {
        #         "1": False,
        #         "2": False,
        #         "3": False,
        #         "4": False
        #     },
        #     "warning_level": 25.0,
        #     "warning_email": True,
        #     "warning_xmpp": True,
        #     "warning_suspend_programs": {
        #         "1": False,
        #         "2": False,
        #         "3": False,
        #         "4": False
        #     },
        #     "warning_activate_programs": {
        #         "1": False,
        #         "2": False,
        #         "3": False,
        #         "4": False
        #     },
        #     "critical_level": 8.0,
        #     "critical_email": True,
        #     "critical_xmpp": True,
        #     "critical_suspend_programs": {
        #         "1": False,
        #         "2": False,
        #         "3": False,
        #         "4": False
        #     },
        #     "critical_activate_programs": {
        #         "1": False,
        #         "2": False,
        #         "3": False,
        #         "4": False
        #     },
        #     "loss_email": True,
        #     "loss_xmpp": True,
        #     "last_updated": None,
        #     "sensor_id": None, 
        #     "sensor_measurement": None,
        #     "invalid_sensor_measurement": False,
        #     "percentage": None,
        #     "width": 2.0,
        #     "length": 5.0,
        #     "height": 2.0,
        #     "order": 0
        # },
        # "water_tank_2": {
        #     "id": "water_tank_2",
        #     "label": "\u03a3\u03b9\u03b4\u03b5\u03c1\u03ad\u03bd\u03b9\u03b1",
        #     "type": 1,
        #     "sensor_mqtt_topic": "WATER_TANK_MEASUREMENT",
        #     INVALID_SENSOR_MEASUREMENT_XMPP: True,
        #     INVALID_SENSOR_MEASUREMENT_EMAIL: True,
        #     "sensor_offset_from_top": 0.0,
        #     "enabled": True,
        #     "overflow_level": 85.0,
        #     "overflow_email": True,
        #     "overflow_xmpp": True,
        #     "overflow_safe_level": None,
        #     "overflow_programs": {
        #         "1": False,
        #         "2": False,
        #         "3": False,
        #         "4": False
        #     },
        #     "warning_level": 30.0,
        #     "warning_email": True,
        #     "warning_xmpp": True,
        #     "warning_suspend_programs": {
        #         "1": False,
        #         "2": False,
        #         "3": False,
        #         "4": False
        #     },
        #     "warning_activate_programs": {
        #         "1": False,
        #         "2": False,
        #         "3": False,
        #         "4": False
        #     },
        #     "critical_level": 5.0,
        #     "critical_email": False,
        #     "critical_xmpp": False,
        #     "critical_suspend_programs": {
        #         "1": False,
        #         "2": False,
        #         "3": False,
        #         "4": False
        #     },
        #     "critical_activate_programs": {
        #         "1": False,
        #         "2": False,
        #         "3": False,
        #         "4": False
        #     },
        #     "loss_email": True,
        #     "loss_xmpp": True,
        #     "last_updated": "2023-11-12 13:47",
        #     "sensor_id": "Sensor_2", 
        #     "sensor_measurement": 0.9,
        #     "invalid_sensor_measurement": True,
        #     "percentage": 40.0,
        #     "width": 2.0,
        #     "length": 3.0,
        #     "height": 1.5,
        #     "order": 1
        # },
        # "water_tank_3": {
        #     "id": "water_tank_3",
        #     "label": "\u039c\u03b1\u03cd\u03c1\u03b7",
        #     "type": 3,
        #     "sensor_mqtt_topic": "WATER_TANK_MEASUREMENT",
        #     INVALID_SENSOR_MEASUREMENT_XMPP: True,
        #     INVALID_SENSOR_MEASUREMENT_EMAIL: True,
        #     "sensor_offset_from_top": 0.0,
        #     "enabled": True,
        #     "overflow_level": 85.0,
        #     "overflow_email": True,
        #     "overflow_xmpp": False,
        #     "overflow_safe_level": None,
        #     "overflow_programs": {
        #         "1": False,
        #         "2": False,
        #         "3": False,
        #         "4": False
        #     },
        #     "warning_level": 30.0,
        #     "warning_email": False,
        #     "warning_xmpp": True,
        #     "warning_suspend_programs": {
        #         "1": False,
        #         "2": False,
        #         "3": False,
        #         "4": False
        #     },
        #     "warning_activate_programs": {
        #         "1": False,
        #         "2": False,
        #         "3": False,
        #         "4": False
        #     },
        #     "critical_level": 5.0,
        #     "critical_email": True,
        #     "critical_xmpp": True,
        #     "critical_suspend_programs": {
        #         "1": False,
        #         "2": False,
        #         "3": False,
        #         "4": False
        #     },
        #     "critical_activate_programs": {
        #         "1": False,
        #         "2": False,
        #         "3": False,
        #         "4": False
        #     },
        #     "loss_email": False,
        #     "loss_xmpp": False,
        #     "last_updated": "2023-11-12 13:47",
        #     "sensor_id": "Sensor_3", 
        #     "sensor_measurement": 1.5,
        #     "invalid_sensor_measurement": False,
        #     "percentage": 25.0,
        #     "height": 2.0,
        #     "diameter": 2.0,
        #     "order": 2
        # },
        # "water_tank_4": {
        #     "id": "water_tank_4",
        #     "label": "\u039d\u03b5\u03c1\u03cc \u03b4\u03b9\u03ba\u03c4\u03cd\u03bf\u03c5",
        #     "type": 4,
        #     "sensor_mqtt_topic": "WATER_TANK_MEASUREMENT",
        #     INVALID_SENSOR_MEASUREMENT_XMPP: True,
        #     INVALID_SENSOR_MEASUREMENT_EMAIL: True,
        #     "sensor_offset_from_top": 0.0,
        #     "enabled": True,
        #     "overflow_level": 85.0,
        #     "overflow_email": False,
        #     "overflow_xmpp": True,
        #     "overflow_safe_level": None,
        #     "overflow_programs": {
        #         "1": False,
        #         "2": False,
        #         "3": False,
        #         "4": False
        #     },
        #     "warning_level": 40.0,
        #     "warning_email": True,
        #     "warning_xmpp": True,
        #     "warning_suspend_programs": {
        #         "1": False,
        #         "2": False,
        #         "3": False,
        #         "4": False
        #     },
        #     "warning_activate_programs": {
        #         "1": False,
        #         "2": False,
        #         "3": False,
        #         "4": False
        #     },
        #     "critical_level": 5.0,
        #     "critical_email": True,
        #     "critical_xmpp": True,
        #     "critical_suspend_programs": {
        #         "1": False,
        #         "2": False,
        #         "3": False,
        #         "4": False
        #     },
        #     "critical_activate_programs": {
        #         "1": False,
        #         "2": False,
        #         "3": False,
        #         "4": False
        #     },
        #     "loss_email": True,
        #     "loss_xmpp": True,
        #     "last_updated": "2023-11-12 13:47",
        #     "sensor_id": "Sensor_4", 
        #     "sensor_measurement": 0.6,
        #     "invalid_sensor_measurement": False,
        #     "percentage": 61.41848493043786,
        #     "length": 2.0,
        #     "horizontal_axis": 1.0,
        #     "vertical_axis": 0.8,
        #     "order": 4
        # }
    # }
}


defaults = {
    UNRECOGNISED_MSG: u"Unrecognised mqtt msg! MQTT topic:'{mqtt_topic}', date:'{date}', msg:[{message}]",
    UNRECOGNISED_MSG_EMAIL: True,
    UNRECOGNISED_MSG_XMPP: True,
    XMPP_UNASSOCIATED_SENSOR_MSG: u"Unassociated sensor measurement msg! sensor_id:'{sensor_id}', measurement:'{measurement}', date:'{last_updated}', mqtt topic:'{mqtt_topic}'",
    UNASSOCIATED_SENSOR_XMPP: True,
    UNASSOCIATED_SENSOR_EMAIL: True,
    XMPP_INVALID_SENSOR_MEASUREMENT_MSG: u"Invalid sensor measurement! water tank:'{water_tank_id}'/'{water_tank_label}', sensor_id:'{sensor_id}', percentage: {percentage}%, measurement:'{measurement}', date:'{last_updated}', mqtt topic:'{mqtt_topic}'. Additional info:[{additional_info}]",
    XMPP_OVERFLOW_MSG: u"Overflow! water tank:'{water_tank_id}'/'{water_tank_label}', sensor_id:'{sensor_id}', percentage: {percentage}%, measurement:'{measurement}', date:'{last_updated}', mqtt topic:'{mqtt_topic}'. Additional info:[{additional_info}]",
    XMPP_WARNING_MSG: u"Warning! water tank:'{water_tank_id}'/'{water_tank_label}', sensor_id:'{sensor_id}', percentage: {percentage}%, measurement:'{measurement}', date:'{last_updated}', mqtt topic:'{mqtt_topic}'. Additional info:[{additional_info}]",
    XMPP_CRITICAL_MSG: u"Critical! water tank:'{water_tank_id}'/'{water_tank_label}', sensor_id:'{sensor_id}', percentage: {percentage}%, measurement:'{measurement}', date:'{last_updated}', mqtt topic:'{mqtt_topic}'. Additional info:[{additional_info}]",
    XMPP_WATER_LOSS_MSG: u"Water loss! water tank:'{water_tank_id}'/'{water_tank_label}', sensor_id:'{sensor_id}', percentage: {percentage}%, measurement:'{measurement}', date:'{last_updated}', mqtt topic:'{mqtt_topic}'. Additional info:[{additional_info}]"
}


# Add new URLs to access classes in this plugin.
# fmt: off
urls.extend([
    u"/water-tank-sp", u"plugins.water_tank.settings",
    u"/water-tank-save-settings", u"plugins.water_tank.save_settings",
    u"/water-tank-save-water-tanks", u"plugins.water_tank.save_water_tanks",
    u"/water-tank-get-all", u"plugins.water_tank.get_all",
    u"/water-tank-get_mqtt_settings", u"plugins.water_tank.get_mqtt_settings",
    u"/water-tank-delete", u"plugins.water_tank.delete",
    u"/water-tank-save-order", u"plugins.water_tank.save_order"
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
    elif isinstance(obj, WaterTankState):
        return obj.value
    elif  isinstance(obj, WaterTankProgram):
        return obj.__dict__
    elif  isinstance(obj, WaterTank):
        return obj.__dict__
    raise TypeError("Type {} not serializable".format(type(obj))) 


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
    # print( 'get_settings() returns : {}'.format(json.dumps(_settings, default=serialize_datetime, indent=4)))
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


def readWaterTankData():
    water_tank_data = {}
    try:
        # with open(DATA_FILE, "r") as f:# Read settings from json file if it exists
        #     water_tank_data = list(json.load(f)[u"water_tanks"].values())
        settings = get_settings()
        water_tank_data = []
        if( len(settings[u"water_tanks"]) > 0):
            water_tank_data = sorted(list(settings[u"water_tanks"].values()), key= lambda wt : wt["order"])
            # print("readWaterTankData returns sorted list: {}".format(json.dumps(water_tank_data, default=serialize_datetime, indent=4 )))
    except IOError:  # If file does not exist return empty value
        water_tank_data = []
        
    return water_tank_data


def no_stations_are_on():
    print("gv.srvals: {}, open valve exists: {}".format(''.join(str(gv.srvals)), (1 in gv.srvals)))
    return 1 not in gv.srvals


def email_send_msg(text, tank_event):
    """Send email"""
    settings = get_settings()
    print("Sending email [{}] for tank event: {}, with subject: '{}'".format(text, tank_event,settings[EMAIL_SUBJECT]))
    
    if settings[EMAIL_USERNAME] != "" and settings[EMAIL_PASSWORD] != "" and settings[EMAIL_SERVER] != "" and settings[EMAIL_SERVER_PORT] != "" and settings[EMAIL_RECIPIENTS] != "":
        mail_user = settings[EMAIL_USERNAME]  # SMTP username
        mail_from = mail_user
        mail_pwd = settings[EMAIL_PASSWORD]  # SMTP password
        mail_server = settings[EMAIL_SERVER]  # SMTP server address
        mail_port = settings[EMAIL_SERVER_PORT]  # SMTP port
        # --------------
        msg = MIMEText(text)
        msg[u"From"] = mail_from
        msg[u"To"] = settings[EMAIL_RECIPIENTS]
        # print("Sending email to: {}".format(msg[u"To"]))
        msg[u"Subject"] = settings[EMAIL_SUBJECT] + " " + tank_event
        
        with smtplib.SMTP_SSL(mail_server, mail_port) as smtp_server:
            smtp_server.login(mail_user, mail_pwd)
            smtp_server.sendmail(mail_user, [x.strip() for x in settings[EMAIL_RECIPIENTS].split(',')], msg.as_string())
        print("Message sent!")

    else:
        raise Exception(u"E-mail plug-in is not properly configured!")


def get_xmpp_receipients():
    """
    Returns a list of recipients for xmpp messages
    """
    settings = get_settings()
    if "," not in settings[XMPP_RECIPIENTS]:
        return [settings[XMPP_RECIPIENTS]]

    return [s.strip() for s in settings[XMPP_RECIPIENTS].split(", ")]


def xmpp_send_msg(message):
    print("Will try to send message '{}'".format(message))
    settings = get_settings()

    if( (not(settings[XMPP_USERNAME] and not settings[XMPP_USERNAME].isspace())) or
       (not(settings[XMPP_PASSWORD] and not settings[XMPP_PASSWORD].isspace())) or
       (not(settings[XMPP_SERVER] and not settings[XMPP_SERVER].isspace()))
       ):
       print("XMPP_USERNAME:'{}', or XMPP_PASSWORD:'{}', or XMPP_SERVER:'{}' are empty, cannot send xmpp message."
             .format(settings[XMPP_USERNAME], settings[XMPP_PASSWORD], settings[XMPP_SERVER]))
       return

    jid = xmpp.protocol.JID( settings[XMPP_USERNAME] )
    cl = xmpp.Client( settings[XMPP_SERVER], debug=[] )
    con = cl.connect()
    if not con:
        print('could not connect!')
        return False
    print('connected with {} to {} with user {}'.format(con, settings[XMPP_SERVER], settings[XMPP_USERNAME]))
    auth = cl.auth( jid.getNode(), settings[XMPP_PASSWORD], resource = jid.getResource() )
    if not auth:
        print('could not authenticate!')
        return False
    print('authenticated using {}'.format(auth) )

    #cl.SendInitPresence(requestRoster=0)   # you may need to uncomment this for old server
    for r in get_xmpp_receipients():
        id = cl.send(xmpp.protocol.Message( r, message ) )
        print('sent message with id {} to {}'.format(id, r) )


def send_unrecognised_msg(mqtt_topic, date, message):
    settings = get_settings()
    msg = settings[UNRECOGNISED_MSG].format(
        mqtt_topic = mqtt_topic,
        date = date,
        message = message
    )
    if( settings[UNRECOGNISED_MSG_EMAIL] ):
        email_send_msg( msg, "Unrecognised MQTT message!" )
    if( settings[UNRECOGNISED_MSG_XMPP] ):
        xmpp_send_msg( msg )


def send_unassociated_sensor_msg(sensor_id, measurement, last_updated, mqtt_topic):
    settings = get_settings()
    msg = settings[XMPP_UNASSOCIATED_SENSOR_MSG].format(
        sensor_id = sensor_id,
        measurement = measurement,
        last_updated = last_updated,
        mqtt_topic = mqtt_topic
    )
    if( settings[UNASSOCIATED_SENSOR_XMPP] ):
        xmpp_send_msg( msg )
    if( settings[UNASSOCIATED_SENSOR_EMAIL] ):
        email_send_msg( msg, "Unassociated sensor" )


def send_invalid_measurement_msg(water_tank, additional_info):
    settings = get_settings()
    msg = settings[XMPP_INVALID_SENSOR_MEASUREMENT_MSG].format(
        water_tank_id = water_tank.id,
        water_tank_label = water_tank.label,
        sensor_id = water_tank.sensor_id,
        percentage = water_tank.percentage,
        measurement = water_tank.sensor_measurement,
        last_updated = water_tank.last_updated,
        mqtt_topic = water_tank.sensor_mqtt_topic,
        additional_info = additional_info
    )
    print("Invalid measurement email:{}, xmpp:{}".format(water_tank.invalid_sensor_measurement_email, water_tank.invalid_sensor_measurement_xmpp))
    if( water_tank.invalid_sensor_measurement_xmpp ):
        xmpp_send_msg( msg )
    if( water_tank.invalid_sensor_measurement_email ):
        email_send_msg( msg, "Invalid measurement" )


def check_events_and_send_msg(cmd, percentageBefore, water_tank, mqtt_msg):
    percentage = water_tank.percentage
    print("Checking events for percentageBefore:'{}', percentage:'{}', water-tank:'{}' ".format(
        percentageBefore, percentage, water_tank.label
    ))
    if percentage is None:
        return
    
    settings = get_settings()
    if( water_tank.overflow_level is not None and 
        water_tank.percentage is not None and
        water_tank.percentage >= water_tank.overflow_level and  
        (percentageBefore is None or percentageBefore < water_tank.overflow_level) 
      ):
        print("Will send overflow message")
        msg = settings[XMPP_OVERFLOW_MSG].format(
            water_tank_id = water_tank.id,
            water_tank_label = water_tank.label,
            sensor_id = water_tank.sensor_id,
            percentage = water_tank.percentage,
            measurement = water_tank.sensor_measurement,
            last_updated = water_tank.last_updated,
            mqtt_topic = mqtt_msg.topic,
            additional_info = water_tank.AdditionalInfo4Msg()
        )
        print("Overflow email:{}, xmpp:{}".format(water_tank.overflow_email, water_tank.overflow_xmpp))
        if( water_tank.overflow_xmpp ):
            xmpp_send_msg( msg )
        if( water_tank.overflow_email ):
            email_send_msg( msg, "Overflow" )

    if( water_tank.critical_level is not None and 
        water_tank.percentage is not None and
        water_tank.percentage <= water_tank.critical_level and  
        (percentageBefore is None or percentageBefore > water_tank.critical_level) 
      ):
        print("Will send xmpp critical message")
        msg = settings[XMPP_CRITICAL_MSG].format(
            water_tank_id = water_tank.id,
            water_tank_label = water_tank.label,
            sensor_id = water_tank.sensor_id,
            percentage = water_tank.percentage,
            measurement = water_tank.sensor_measurement,
            last_updated = water_tank.last_updated,
            mqtt_topic = mqtt_msg.topic,
            additional_info = water_tank.AdditionalInfo4Msg()
        )
        print("Critical email:{}, xmpp:{}".format(water_tank.critical_email, water_tank.critical_xmpp))
        if( water_tank.critical_xmpp ):
            xmpp_send_msg( msg )
        if( water_tank.critical_email ):
            email_send_msg( msg, "Critical" )

    elif( water_tank.warning_level is not None and 
        water_tank.percentage is not None and
        water_tank.percentage <= water_tank.warning_level and  
        (percentageBefore is None or percentageBefore > water_tank.warning_level) 
      ):
        print("Will send xmpp warning message")
        msg = settings[XMPP_WARNING_MSG].format(
            water_tank_id = water_tank.id,
            water_tank_label = water_tank.label,
            sensor_id = water_tank.sensor_id,
            percentage = water_tank.percentage,
            measurement = water_tank.sensor_measurement,
            last_updated = water_tank.last_updated,
            mqtt_topic = mqtt_msg.topic,
            additional_info = water_tank.AdditionalInfo4Msg()
        )
        print("Warning email:{}, xmpp:{}".format(water_tank.warning_email, water_tank.warning_xmpp))
        if( water_tank.warning_xmpp ):
            xmpp_send_msg( msg )
        if( water_tank.warning_email ):
            email_send_msg( msg, "Warning" )


    # print("Will check water loss water_tank.loss_xmpp: {}, water_tank.percentage: {}, percentageBefore: {}, water_tank.percentage: {}".format(water_tank.loss_xmpp, water_tank.percentage, percentageBefore, water_tank.percentage))
    if( water_tank.percentage is not None and 
        (percentageBefore is not None and percentageBefore > water_tank.percentage) and
        no_stations_are_on()
        ):
        print("Will send xmpp water loss message")
        msg = settings[XMPP_WATER_LOSS_MSG].format(
            water_tank_id = water_tank.id,
            water_tank_label = water_tank.label,
            sensor_id = water_tank.sensor_id,
            percentage = water_tank.percentage,
            measurement = water_tank.sensor_measurement,
            last_updated = water_tank.last_updated,
            mqtt_topic = mqtt_msg.topic,
            additional_info = water_tank.AdditionalInfo4Msg()
        )
        print("Water Loss email:{}, xmpp:{}".format(water_tank.loss_email, water_tank.loss_xmpp))
        if( water_tank.loss_xmpp ):
            xmpp_send_msg( msg )
        if( water_tank.loss_email ):
            email_send_msg( msg, "Water Loss" )


def updateSensorMeasurementFromCmd(cmd, water_tanks, msg):
    settings = get_settings()
    associated_wts = [ wt for wt in list(water_tanks.values()) if wt["sensor_id"] == cmd["sensor_id"]]
    if len(associated_wts) == 0:
        send_unassociated_sensor_msg(
            cmd[u"sensor_id"],
            cmd[u"measurement"],
            datetime.now().replace(microsecond=0),
            msg.topic
        )
        return
    
    water_tank_updated = False
    for awt in associated_wts:
        wt = WaterTankFactory.FromDict(awt)
        # print("Wt from {}".format(json.dumps(awt, default=serialize_datetime, indent=4)))
        # print("Before UpdateSensorMeasurement. awt['enabled']:{}, wt.enabled:{}".format(awt['enabled'], wt.enabled))
        percentageBefore = wt.percentage
        if wt.UpdateSensorMeasurement(cmd[u"sensor_id"], cmd[u"measurement"]):
            water_tanks[wt.id] = wt.__dict__
            # print("After UpdateSensorMeasurement. water_tanks[wt.id]['enabled']:{}, wt.enabled:{}".format(water_tanks[wt.id]['enabled'], wt.enabled))        
            # check_events_and_send_msg(cmd, percentageBefore, wt, msg)
            water_tank_updated = True
            # print("Update water tank '{}' with measurment: {}".format(wt.id, wt.sensor_measurement))

    return water_tank_updated


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
        send_unrecognised_msg(msg.topic, datetime.now().replace(microsecond=0), msg.payload)
        return

    try:
        settings = get_settings()
        water_tanks = settings[u"water_tanks"]
        water_tank_updated = False
        if isinstance(cmd, dict) and 'sensor_id' in cmd:
            water_tank_updated = updateSensorMeasurementFromCmd(cmd, water_tanks, msg)
        elif isinstance(cmd, list):
            print('Cmd is a list')
            for singleTankCmd in cmd:
                print('Cmd item:{}'.format(json.dumps(singleTankCmd, default=serialize_datetime,indent=4)))
                if isinstance(singleTankCmd, dict) and 'sensor_id' in singleTankCmd:
                    print("Will call updateSensorMeasurementFromCmd for sensor '{}'".format(singleTankCmd["sensor_id"]))
                    water_tank_updated = updateSensorMeasurementFromCmd(singleTankCmd, water_tanks, msg) or water_tank_updated
                else:
                    print("Skipping sensor: {}".format(singleTankCmd["sensor_id"]))
        else:
            print("Unknown mqtt command {}".format(repr(cmd)))
            send_unrecognised_msg(msg.topic, datetime.now().replace(microsecond=0), msg.payload)
            return

        if not water_tank_updated:
            print("No water tank with cmd '{}' was updated.".format(cmd))
            return
        
        settings[u"water_tanks"] = water_tanks
        with open(DATA_FILE, u"w") as f:
                json.dump(settings, f, default=serialize_datetime, indent=4)  # save to file                

        publish_water_tanks_mqtt()
    except Exception as e:
        print("An unexpected error occured", e)


def on_data_request_mqtt_message(client, msg):
    """
    Callback when MQTT message is received requesting water tank data
    """
    publish_water_tanks_mqtt()


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
        if topic and topic not in mqtt._subscriptions:
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


def publish_water_tanks_mqtt():
    settings = get_settings()
    client = mqtt.get_client()
    if client:
        # print("Publishing: {}".format(json.dumps(settings['water_tanks'], default=serialize_datetime, indent=4)))
        client.publish(
            settings[WATER_PLUGIN_DATA_PUBLISH_MQTT_TOPIC], 
            json.dumps(readWaterTankData(), default=serialize_datetime, indent=4), 
            qos=1, 
            retain=True
        )


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

        show_settings = 'showSettings' in web.input()
        water_tank_id = None
        if 'water_tank_id' in web.input():
            water_tank_id = web.input()["water_tank_id"]

        settings[u"water_tanks"] = sorted(list(settings[u"water_tanks"].values()), key= lambda wt : wt["order"])
        # print("Sending settings: {}".format(json.dumps(settings, default=serialize_datetime, indent=4)))
        return template_render.water_tank(settings, json.dumps(defaults, ensure_ascii=False), gv.pnames, water_tank_id, show_settings)  # open settings page


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
        settings[XMPP_USERNAME] = d[XMPP_USERNAME]
        settings[XMPP_PASSWORD] = d[XMPP_PASSWORD]
        settings[XMPP_SERVER] = d[XMPP_SERVER]
        settings[XMPP_SUBJECT] = d[XMPP_SUBJECT]
        settings[XMPP_RECIPIENTS] = d[XMPP_RECIPIENTS]
        settings[UNRECOGNISED_MSG] = d[UNRECOGNISED_MSG]
        settings[UNRECOGNISED_MSG_EMAIL] = (UNRECOGNISED_MSG_EMAIL in d)
        settings[UNRECOGNISED_MSG_XMPP] = (UNRECOGNISED_MSG_XMPP in d)
        settings[XMPP_UNASSOCIATED_SENSOR_MSG] = d[XMPP_UNASSOCIATED_SENSOR_MSG]
        settings[UNASSOCIATED_SENSOR_EMAIL] = (UNASSOCIATED_SENSOR_EMAIL in d)
        settings[UNASSOCIATED_SENSOR_XMPP] = (UNASSOCIATED_SENSOR_XMPP in d)
        settings[XMPP_INVALID_SENSOR_MEASUREMENT_MSG] = d[XMPP_INVALID_SENSOR_MEASUREMENT_MSG]
        settings[XMPP_OVERFLOW_MSG] = d[XMPP_OVERFLOW_MSG]
        settings[XMPP_WARNING_MSG] = d[XMPP_WARNING_MSG]
        settings[XMPP_CRITICAL_MSG] = d[XMPP_CRITICAL_MSG]
        settings[XMPP_WATER_LOSS_MSG] = d[XMPP_WATER_LOSS_MSG]
        settings[EMAIL_USERNAME] = d[EMAIL_USERNAME]
        settings[EMAIL_PASSWORD] = d[EMAIL_PASSWORD]
        settings[EMAIL_SERVER] = d[EMAIL_SERVER]
        settings[EMAIL_SERVER_PORT] = d[EMAIL_SERVER_PORT]
        settings[EMAIL_SUBJECT] = d[EMAIL_SUBJECT]
        settings[EMAIL_RECIPIENTS] = d[EMAIL_RECIPIENTS]

        with open(DATA_FILE, u"w") as f:
            json.dump(settings, f, default=serialize_datetime, indent=4)  # save to file
        # print('Saved settings: {}'.format(json.dumps(settings, default=serialize_datetime, indent=4)))

        raise web.seeother(u"/water-tank-sp?showSettings") 


class save_water_tanks(ProtectedPage):
    """
    Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """

    def POST(self):
        d = (
            web.input()
        )  # Dictionary of values returned as query string from settings page.
        print('Received: {}'.format(json.dumps(d, default=serialize_datetime, indent=4, sort_keys=True))) # for testing
        settings = get_settings()
        
        water_tank = WaterTankFactory.FromDict(d)
        original_water_tank_id = d[u"original_water_tank_id"]
        
        if d[u"id"]:
            if d[u"action"] == "add":
                #add new water_Tank
                # print('Adding new water tank: {}'.format(json.dumps(water_tank, default=serialize_datetime, indent=4)))
                water_tank.order = len(settings['water_tanks'])
                settings['water_tanks'][water_tank.id] = water_tank
            elif d[u"action"] == "update" and original_water_tank_id:
                # print('Updating water tank with id: "{}". New values: {}'.format(original_water_tank_id, json.dumps(water_tank, default=serialize_datetime, indent=4)))
                wt = settings['water_tanks'][original_water_tank_id]
                # print('Old values: {}'.format(json.dumps(wt, default=serialize_datetime, indent=4)))
                water_tank.last_updated = wt["last_updated"]
                water_tank.order = wt["order"]
                # if wt["sensor_measurement"]:
                #     water_tank.UpdateSensorMeasurement(wt["sensor_measurement"])
                if water_tank.id == original_water_tank_id:
                    settings['water_tanks'][original_water_tank_id] = water_tank
                else:
                    del settings['water_tanks'][original_water_tank_id]
                    settings['water_tanks'][water_tank.id] = water_tank
                
        with open(DATA_FILE, u"w") as f:
            json.dump(settings, f, default=serialize_datetime, indent=4)  # save to file
        # print('Saved water tanks: {}'.format(json.dumps(settings, default=serialize_datetime, indent=4)))

        if d[u"id"] and (d[u"action"] == "add" or (d[u"action"] == "update" and original_water_tank_id)):
            refresh_mqtt_subscriptions()
            publish_water_tanks_mqtt()
            raise web.seeother(u"/water-tank-sp?water_tank_id=" + d[u"id"])
        else:
            raise web.seeother(u"/water-tank-sp")


class get_all(ProtectedPage):
    """
    Read last saved water-tank data and return it as json
    """
    def GET(self):
        print(u"Reading water tank data")
        data = readWaterTankData()
        web.header('Content-Type', 'application/json')
        return json.dumps(data, default=serialize_datetime, indent=4)
    

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
    
        return json.dumps(settings, default=serialize_datetime, indent=4)


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
                json.dump(settings, f, default=serialize_datetime, indent=4)  # save to file
            refresh_mqtt_subscriptions()
        raise web.seeother(u"/water-tank-sp")  # open settings page        


class save_order(ProtectedPage):
    """
    Saves the order of a water tank
    """
    def POST(self):
        data = web.input()
        try:
            print(repr(data))
            id = data["water_tank_id"]
            order = int(data["order"])
            move = data["move"]
            print('id: {}, move: {}, order: {}'.format(id, move, order))
            settings = get_settings()
            if id in settings[u"water_tanks"]:
                previous_order = settings[u"water_tanks"][id]["order"]
                for x in settings[u"water_tanks"]:
                    if( x == id ):
                        settings[u"water_tanks"][id]["order"] = order
                    elif( move == "down" and settings[u"water_tanks"][x]["order"] >= order and settings[u"water_tanks"][x]["order"] < previous_order):
                        settings[u"water_tanks"][x]["order"] += 1 
                    elif( move == "up" and settings[u"water_tanks"][x]["order"] <= order and settings[u"water_tanks"][x]["order"] > previous_order):
                        settings[u"water_tanks"][x]["order"] -= 1 
                with open(DATA_FILE, u"w") as f:
                    json.dump(settings, f, default=serialize_datetime, indent=4)  # save to file

                # publish all water-tank data for new order
                publish_water_tanks_mqtt()
                return json.dumps('{"success": true, "reason": ""}')
            return json.dumps('{"success": false, "reason": "water tank with id [' + str(id) + '] was not found"}')
        except Exception as e:
            return json.dumps('{"success": false, "reason": "An exception occured: ' + e + '"}')



#  Run when plugin is loaded
detect_water_tank_js() # add water_tank.js to base.html if ncessary
load_programs() # in order to load program names in gv.pnames
subscribe_mqtt()
