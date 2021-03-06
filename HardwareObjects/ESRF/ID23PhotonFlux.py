from HardwareRepository.BaseHardwareObjects import Equipment
from HardwareRepository.TaskUtils import *
import numpy
import time
import logging
import math
from calc_flux import *
from PyTango.gevent import DeviceProxy


class ID23PhotonFlux(Equipment):
    def __init__(self, *args, **kwargs):
        Equipment.__init__(self, *args, **kwargs)
        self.threshold = []

    def init(self):
        self.counter = DeviceProxy(self.getProperty("url"))
        try:
            self.threshold = map(float, self.getProperty("threshold").split())
        except AttributeError:
            self.threshold = [0, 9999]
        self.shutter = self.getDeviceByRole("shutter")
        self.energy_motor = self.getObjectByRole("energy")
        self.aperture = self.getObjectByRole("aperture")
        fname = self.getProperty("calibrated_diodes_file")

        self.flux_calc = CalculateFlux()
        self.flux_calc.init(fname)
        self.shutter.connect("shutterStateChanged", self.shutterStateChanged)

        self.counts_reading_task = self._read_counts_task(wait=False)

    @task
    def _read_counts_task(self):
        old_counts = None
        while True:
            counts = self._get_counts()
            if counts != old_counts:
                old_counts = counts
                self.countsUpdated(counts)
            time.sleep(1)

    def _get_counts(self):
        try:
            self.counter.MeasureSingle()
            counts = abs(self.counter.ReadData)
            if counts < self.threshold[0] or counts > self.threshold[1]:
                counts = 0
        except AttributeError as TypeError:
            counts = 0
            logging.getLogger("HWR").exception("%s: could not get counts", self.name())
        try:
            egy = self.energy_motor.getCurrentEnergy() * 1000.0
            calib = self.flux_calc.calc_flux_coef(egy)
        except BaseException:
            logging.getLogger("HWR").exception("%s: could not get energy", self.name())
        else:
            if self.aperture is None:
                aperture_coef = 1
            else:
                try:
                    aperture_coef = self.aperture.getApertureCoef()
                except BaseException:
                    aperture_coef = 1.0
            counts = math.fabs(counts * calib[0] * aperture_coef) * 10e6
        return counts

    def connectNotify(self, signal):
        if signal == "valueChanged":
            self.emitValueChanged()

    def shutterStateChanged(self, _):
        self.countsUpdated(self._get_counts())

    def updateFlux(self, _):
        self.countsUpdated(self._get_counts(), ignore_shutter_state=False)

    def countsUpdated(self, counts, ignore_shutter_state=False):
        self.emitValueChanged("%1.3g" % counts)

    def getCurrentFlux(self):
        self.updateFlux("dummy")
        return self.current_flux

    def emitValueChanged(self, flux=None):
        if flux is None:
            self.current_flux = None
            self.emit("valueChanged", ("?",))
        else:
            self.current_flux = flux
            self.emit("valueChanged", (self.current_flux,))
