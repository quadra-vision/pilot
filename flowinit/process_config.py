import os

from cereal import car
from common.params import Params
from flowinit.process import PythonProcess, NativeProcess, DaemonProcess

WEBCAM = os.getenv("USE_WEBCAM") is not None

def driverview(started: bool, params: Params, CP: car.CarParams) -> bool:
  return params.get_bool("IsDriverViewEnabled")  # type: ignore

def notcar(started: bool, params: Params, CP: car.CarParams) -> bool:
  return CP.notCar  # type: ignore

def logging(started, params, CP: car.CarParams) -> bool:
  run = (not CP.notCar) or not params.get_bool("DisableLogging")
  return started and run

procs = [
  PythonProcess("calibrationd", "selfdrive.calibration.calibrationd"),
  PythonProcess("plannerd", "selfdrive.controls.plannerd"),
  PythonProcess("controlsd", "selfdrive.controls.controlsd"),
  PythonProcess("logmessaged", "selfdrive.logmessaged", nowait=True),
  PythonProcess("keyvald", "selfdrive.keyvald", nowait=True),
  PythonProcess("pandad", "selfdrive.boardd.pandad", nowait=True),
  NativeProcess("gradled", "", ["./gradlew", "--quiet", "--console=plain",  "desktop:run"], nowait=True),
]

managed_processes = {p.name: p for p in procs}
