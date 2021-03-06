import logging
from HardwareRepository.BaseHardwareObjects import Device
import time

"""
Use the exporter to set different MD2 actuators in/out.
If private_state not specified, True will be send to set in and False for out.
Example xml file:
<device class="MicrodiffInOut">
  <username>Scintilator</username>
  <exporter_address>wid30bmd2s:9001</exporter_address>
  <cmd_name>ScintillatorPosition</cmd_name>
  <private_state>{"PARK":"out", "SCINTILLATOR":"in"}</private_state>
  <use_hwstate>True</use_hwstate>
</device>
"""


class MicrodiffInOut(Device):
    def __init__(self, name):
        Device.__init__(self, name)
        self.actuatorState = "unknown"
        self.username = "unknown"
        # default timeout - 5 sec
        self.timeout = 5
        self.hwstate_attr = None

    def init(self):
        self.cmdname = self.getProperty("cmd_name")
        self.username = self.getProperty("username")
        self.cmd_attr = self.addChannel(
            {"type": "exporter", "name": "move"}, self.cmdname
        )
        self.cmd_attr.connectSignal("update", self.valueChanged)

        self.statecmdname = self.getProperty("statecmd_name")
        if self.statecmdname is None:
            self.statecmdname = self.cmdname

        self.state_attr = self.addChannel(
            {"type": "exporter", "name": "state"}, self.statecmdname
        )
        self.state_attr.connectSignal("update", self.valueChanged)

        self.states = {True: "in", False: "out"}
        self.offset = self.getProperty("offset")
        if self.offset > 0:
            self.states = {self.offset: "out", self.offset - 1: "in"}

        states = self.getProperty("private_state")
        if states:
            import ast

            self.states = ast.literal_eval(states)
        try:
            tt = float(self.getProperty("timeout"))
            self.timeout = tt
        except BaseException:
            pass

        if self.getProperty("use_hwstate"):
            self.hwstate_attr = self.addChannel(
                {"type": "exporter", "name": "hwstate"}, "HardwareState"
            )

        self.swstate_attr = self.addChannel(
            {"type": "exporter", "name": "swstate"}, "State"
        )

        self.moves = dict((self.states[k], k) for k in self.states)

    def connectNotify(self, signal):
        if signal == "actuatorStateChanged":
            self.valueChanged(self.state_attr.getValue())

    def valueChanged(self, value):
        self.actuatorState = self.states.get(value, "unknown")
        self.emit("actuatorStateChanged", (self.actuatorState,))

    def _ready(self):
        if self.hwstate_attr:
            if (
                self.hwstate_attr.getValue() == "Ready"
                and self.swstate_attr.getValue() == "Ready"
            ):
                return True
        else:
            if self.swstate_attr.getValue() == "Ready":
                return True
        return False

    def _wait_ready(self, timeout=None):
        timeout = timeout or self.timeout
        tt1 = time.time()
        while time.time() - tt1 < timeout:
            if self._ready():
                break
            else:
                time.sleep(0.5)

    def getActuatorState(self, read=False):
        if read is True:
            value = self.state_attr.getValue()
            self.actuatorState = self.states.get(value, "unknown")
            self.connectNotify("actuatorStateChanged")
        else:
            if self.actuatorState == "unknown":
                self.connectNotify("actuatorStateChanged")
        return self.actuatorState

    def actuatorIn(self, wait=True, timeout=None):
        if self._ready():
            try:
                self.cmd_attr.setValue(self.moves["in"])
                if wait:
                    timeout = timeout or self.timeout
                    self._wait_ready(timeout)
                self.valueChanged(self.state_attr.getValue())
            except BaseException:
                logging.getLogger("user_level_log").error(
                    "Cannot put %s in", self.username
                )
        else:
            logging.getLogger("user_level_log").error(
                "Microdiff is not ready, will not put %s in", self.username
            )

    def actuatorOut(self, wait=True, timeout=None):
        if self._ready():
            try:
                self.cmd_attr.setValue(self.moves["out"])
                if wait:
                    timeout = timeout or self.timeout
                    self._wait_ready(timeout)
                self.valueChanged(self.state_attr.getValue())
            except BaseException:
                logging.getLogger("user_level_log").error(
                    "Cannot put %s out", self.username
                )
        else:
            logging.getLogger("user_level_log").error(
                "Microdiff is not ready, will not put %s out", self.username
            )
