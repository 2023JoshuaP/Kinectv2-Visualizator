"""Local control of Tuya / Smart Life plugs and bulbs for sign actions.

Devices are described in a JSON file (see ``smart-devices.example.json``).
Commands run on a single background thread, so the Qt interface never waits
for the network. If a device does not answer at its saved IP, the module
listens for the UDP broadcasts that Tuya devices send every few seconds. If a
firewall blocks those broadcasts, it probes TCP port 6668 on the local subnet
(detected automatically or set with ``scan_networks``). It then updates the IP
and retries once. No ``nmap``, cloud access or fixed IP is required.
"""

import ipaddress
import json
import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ACTIONS = {
    "plug": ("toggle", "on", "off"),
    "bulb": ("toggle", "on", "off", "brighter", "dimmer", "next colour", "white"),
}
# Tuya cloud categories for lights; everything else is controlled as a plug.
LIGHT_CATEGORIES = {"dj", "dd", "xdd", "fwd", "dc", "tyndj", "gyd"}
COLOURS = (("red", (255, 0, 0)), ("green", (0, 255, 0)), ("blue", (0, 0, 255)),
           ("yellow", (255, 200, 0)), ("purple", (160, 0, 255)), ("cyan", (0, 255, 255)))
NETWORK_ERRORS = {"901", "902", "905"}
LETTERS = set("ABCDEFGHIJKLMNÑOPQRSTUVWXYZ")
INSTALL_HINT = ("tinytuya is not installed. Run: pip install -r requirements.txt "
                "(or micromamba env update -n kinectv2-dev -f environment.yml)")


class DeviceError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = None if code is None else str(code)

    @property
    def network(self):
        return self.code in NETWORK_ERRORS


def check(result):
    """tinytuya reports most failures as ``{"Error": ..., "Err": ...}``."""
    if isinstance(result, dict) and "Error" in result:
        raise DeviceError(result["Error"], result.get("Err"))
    return result


def import_tinytuya():
    try:
        import tinytuya
        from tinytuya import scanner
    except ImportError as error:
        raise DeviceError(INSTALL_HINT) from error
    return tinytuya, scanner


def local_networks(widest_prefix=22):
    """Subnet of the interface used for the default route, e.g. ``["192.168.1.0/24"]``.

    Docker, libvirt and VPN interfaces are ignored. Very large subnets are
    narrowed around this machine's address so a scan stays short.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))  # Selects a route; no packet is sent.
            address = probe.getsockname()[0]
    except OSError:
        return []
    prefix = 24
    try:
        output = subprocess.run(["ip", "-j", "-4", "addr"], capture_output=True, text=True,
                                timeout=2, check=True).stdout
        for interface in json.loads(output):
            for info in interface.get("addr_info", []):
                if info.get("local") == address:
                    prefix = int(info["prefixlen"])
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        pass  # Without iproute2, assume the common /24.
    prefix = max(prefix, widest_prefix)
    return [str(ipaddress.ip_interface(f"{address}/{prefix}").network)]


def tuya_factory(kind, device_id, ip, key, version):
    tinytuya, _ = import_tinytuya()
    cls = tinytuya.BulbDevice if kind == "bulb" else tinytuya.OutletDevice
    device = cls(device_id, ip, key, version=version,
                 connection_timeout=2, connection_retry_limit=1, connection_retry_delay=1)
    device.set_socketPersistent(False)
    return device


def tuya_scan(devices, seconds, networks=None):
    """Find devices by UDP broadcast, then by probing ``networks`` for missing ones.

    Returns ``{id: {"ip": ..., "version": ...}}``.
    """
    _, scanner = import_tinytuya()
    networks = list(networks) if networks else local_networks()
    # Passing tuyadevices prevents tinytuya from reading ./devices.json; the keys
    # let the force-scan identify devices that did not broadcast.
    known = [{"id": d.id, "key": d.key, "name": d.name} for d in devices]
    found = scanner.devices(verbose=False, scantime=seconds, color=False, poll=False,
                            byID=True, wantids=[d.id for d in devices], tuyadevices=known,
                            forcescan=networks or False, assume_yes=True) or {}
    return {gw_id: {"ip": info.get("ip"), "version": info.get("version")}
            for gw_id, info in found.items() if info.get("ip")}



class SmartDevice:
    def __init__(self, config, factory=tuya_factory):
        if not isinstance(config, dict):
            raise ValueError("Each device must be a JSON object")
        self.id = config.get("id") or config.get("device_id")
        self.key = config.get("key") or config.get("local_key")
        if not isinstance(self.id, str) or not self.id or not isinstance(self.key, str) or not self.key:
            raise ValueError("Each device needs 'id' and 'key' (local key)")
        self.name = str(config.get("name") or self.id)
        kind = config.get("type")
        if kind is None:
            kind = "bulb" if config.get("category") in LIGHT_CATEGORIES else "plug"
        if kind not in ACTIONS:
            raise ValueError(f"{self.name}: type must be 'plug' or 'bulb'")
        self.kind = kind
        ip = config.get("ip") or ""
        self.ip = "" if str(ip).lower() == "auto" else str(ip)
        self.version = float(config.get("version") or 3.5)
        self.bindings = {}
        for letter, action in (config.get("bindings") or {}).items():
            letter = str(letter).upper()
            if letter not in LETTERS or action not in ACTIONS[kind]:
                raise ValueError(f"{self.name}: invalid binding {letter!r} → {action!r}")
            self.bindings[letter] = action
        self.factory = factory
        self.device = None
        self.colour_index = -1

    def label(self, action):
        return f"{self.name}: {action}"

    def _connection(self):
        if not self.ip:
            raise DeviceError("IP unknown", "905")
        if self.device is None:
            device = self.factory(self.kind, self.id, self.ip, self.key, self.version)
            check(device.status())  # also lets BulbDevice detect its data points
            self.device = device
        return self.device

    def forget_connection(self):
        self.device = None

    def is_on(self):
        device = self._connection()
        if self.kind == "bulb":
            return bool(check(device.state()).get("is_on"))
        dps = check(device.status()).get("dps", {})
        return bool(dps.get("1", dps.get(1)))

    def run(self, action):
        if action not in ACTIONS[self.kind]:
            raise DeviceError(f"{self.name} does not support {action!r}")
        device = self._connection()
        if action == "toggle":
            action = "off" if self.is_on() else "on"
        if action == "on":
            check(device.turn_on())
            return f"{self.name} on"
        if action == "off":
            check(device.turn_off())
            return f"{self.name} off"
        if not self.is_on():
            check(device.turn_on())
        if action in ("brighter", "dimmer"):
            try:
                current = float(device.get_brightness_percentage())
            except (RuntimeError, TypeError, ValueError):
                current = 50.0
            target = min(100, current + 25) if action == "brighter" else max(10, current - 25)
            check(device.set_brightness_percentage(round(target)))
            return f"{self.name} brightness {target:.0f}%"
        if action == "white":
            check(device.set_mode("white"))
            return f"{self.name} white"
        self.colour_index = (self.colour_index + 1) % len(COLOURS)
        name, rgb = COLOURS[self.colour_index]
        check(device.set_colour(*rgb))
        return f"{self.name} {name}"


class SmartHome:
    """Owns the device list, the worker thread and IP rediscovery."""

    def __init__(self, path, factory=tuya_factory, scanner=tuya_scan, notify=print,
                 scan_seconds=8, rescan_interval=30):
        self.path = Path(path)
        self.notify = notify
        self.scanner = scanner
        self.scan_seconds = scan_seconds
        self.rescan_interval = rescan_interval
        self.devices = []
        self.raw = None
        self.networks = []
        self.last_scan = float("-inf")
        self.pending = 0
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="smart-devices")
        if self.path.exists():
            self.raw = json.loads(self.path.read_text(encoding="utf-8"))
            entries = self.raw.get("devices") if isinstance(self.raw, dict) else self.raw
            if not isinstance(entries, list):
                raise ValueError("Expected a list of devices or {\"devices\": [...]}")
            self.devices = [SmartDevice(entry, factory) for entry in entries]
            if len({d.name for d in self.devices}) != len(self.devices):
                raise ValueError("Device names must be unique")
            # Optional: subnets to probe when broadcasts are blocked, e.g. ["192.168.1.0/24"].
            networks = self.raw.get("scan_networks", []) if isinstance(self.raw, dict) else []
            if not isinstance(networks, list):
                raise ValueError("scan_networks must be a list such as [\"192.168.1.0/24\"]")
            self.networks = [str(ipaddress.ip_network(n, strict=False)) for n in networks]

    def handlers(self):
        return {device.label(action): (lambda d=device, a=action: self.submit(d, a))
                for device in self.devices for action in ACTIONS[device.kind]}

    def bindings(self):
        return {letter: device.label(action)
                for device in self.devices for letter, action in device.bindings.items()}

    def summary(self):
        if not self.devices:
            return (f"No smart devices configured. Copy smart-devices.example.json to {self.path} "
                    "and add each device id and local key.")
        return " · ".join(f"{d.name} ({d.kind}) @ {d.ip or 'unknown IP'}" for d in self.devices)

    def _queue(self, job, message):
        with self.lock:
            if self.pending >= 2:
                return "Smart devices busy; command ignored"
            self.pending += 1
        self.executor.submit(self._guarded, job)
        return message

    def _guarded(self, job):
        try:
            self.notify(job())
        except DeviceError as error:
            self.notify(f"Device error: {error}")
        except Exception as error:  # Never let a worker exception disappear silently.
            self.notify(f"Device error: {type(error).__name__}: {error}")
        finally:
            with self.lock:
                self.pending -= 1

    def submit(self, device, action):
        return self._queue(lambda: self._run(device, action), f"Sending {device.label(action)}…")

    def discover(self):
        return self._queue(lambda: self._discover(self.devices, force=True),
                           "Searching the local network for devices…")

    def _run(self, device, action):
        try:
            return device.run(action)
        except DeviceError as error:
            device.forget_connection()
            if not error.network or not self._discover([device]):
                raise
        return device.run(action)

    def _discover(self, devices, force=False):
        """Update IPs from broadcasts; return True if any IP or version changed."""
        if not devices:
            return "No smart devices configured"
        now = time.monotonic()
        if not force and now - self.last_scan < self.rescan_interval:
            return False
        self.last_scan = now
        found = self.scanner(devices, self.scan_seconds, self.networks)
        changed = False
        for device in devices:
            info = found.get(device.id)
            if not info or not info.get("ip"):
                continue
            version = float(info.get("version") or device.version)
            if (info["ip"], version) != (device.ip, device.version):
                device.ip, device.version = info["ip"], version
                device.forget_connection()
                changed = True
        if changed:
            self._save()
        if force:
            missing = [d.name for d in devices if d.id not in found]
            return self.summary() + (f" · not found: {', '.join(missing)}" if missing else "")
        return changed

    def _save(self):
        """Persist discovered IPs while keeping the rest of the file untouched."""
        if self.raw is None:
            return
        entries = self.raw.get("devices") if isinstance(self.raw, dict) else self.raw
        by_id = {d.id: d for d in self.devices}
        for entry in entries:
            device = by_id.get(entry.get("id") or entry.get("device_id"))
            if device is not None:
                entry["ip"], entry["version"] = device.ip, device.version
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.chmod(0o600)  # The file contains local keys.
        temporary.replace(self.path)

    def shutdown(self):
        self.executor.shutdown(wait=False, cancel_futures=True)
