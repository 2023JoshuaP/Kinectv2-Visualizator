import ipaddress
import json
import tempfile
import threading
import unittest
from pathlib import Path

from smart_devices import SmartDevice, SmartHome, local_networks

OFFLINE = {"Error": "Network Error: Unable to Connect", "Err": "901", "Payload": None}


class FakeTuya:
    """Mimics tinytuya: failures are returned as error dictionaries."""

    reachable = {"192.168.1.20"}

    def __init__(self, kind, device_id, ip, key, version):
        self.ip, self.on, self.calls = ip, False, []

    def _reply(self, value):
        return value if self.ip in self.reachable else OFFLINE

    def status(self):
        return self._reply({"dps": {"1": self.on, "20": self.on}})

    def state(self):
        return self._reply({"is_on": self.on})

    def turn_on(self):
        self.on = True
        self.calls.append("on")
        return self._reply({})

    def turn_off(self):
        self.on = False
        self.calls.append("off")
        return self._reply({})

    def get_brightness_percentage(self):
        return 60.0

    def set_brightness_percentage(self, value):
        self.calls.append(("brightness", value))
        return self._reply({})

    def set_colour(self, r, g, b):
        self.calls.append(("colour", r, g, b))
        return self._reply({})


def write_config(directory, ip):
    path = Path(directory) / "smart-devices.json"
    path.write_text(json.dumps({"devices": [
        {"name": "Plug", "type": "plug", "id": "abc", "key": "k", "ip": ip, "bindings": {"p": "toggle"}},
        {"name": "Bulb", "category": "dj", "id": "def", "key": "k2", "ip": "192.168.1.20", "extra": 1},
    ]}))
    return path


class SmartDeviceTests(unittest.TestCase):
    def wait(self, home, messages, count):
        done = threading.Event()
        home.notify = lambda message: (messages.append(message), len(messages) >= count and done.set())
        return done

    def test_config_handlers_and_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            home = SmartHome(write_config(directory, "auto"), factory=FakeTuya)
            self.assertEqual([d.kind for d in home.devices], ["plug", "bulb"])
            self.assertEqual(home.devices[0].ip, "")
            self.assertEqual(home.bindings(), {"P": "Plug: toggle"})
            self.assertIn("Bulb: next colour", home.handlers())
            home.shutdown()

    def test_missing_file_means_no_devices(self):
        home = SmartHome("/nonexistent/smart-devices.json")
        self.assertEqual(home.devices, [])
        self.assertIn("smart-devices.example.json", home.summary())
        home.shutdown()

    def test_scan_networks_are_validated_and_passed_to_scanner(self):
        seen = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "smart-devices.json"
            path.write_text(json.dumps({"scan_networks": ["192.168.169.7/24"], "devices": [
                {"name": "Plug", "type": "plug", "id": "abc", "key": "k"}]}))
            home = SmartHome(path, factory=FakeTuya,
                             scanner=lambda devices, seconds, networks: seen.append(networks) or {})
            self.assertEqual(home.networks, ["192.168.169.0/24"])
            home._discover(home.devices, force=True)
            self.assertEqual(seen, [["192.168.169.0/24"]])
            home.shutdown()
            path.write_text(json.dumps({"scan_networks": ["not-a-network"], "devices": []}))
            with self.assertRaises(ValueError):
                SmartHome(path)

    def test_local_networks_returns_bounded_subnets(self):
        for network in local_networks():
            self.assertGreaterEqual(ipaddress.ip_network(network).prefixlen, 22)

    def test_invalid_binding_is_rejected(self):
        with self.assertRaises(ValueError):
            SmartDevice({"id": "a", "key": "b", "type": "plug", "bindings": {"L": "brighter"}})

    def test_toggle_and_bulb_actions(self):
        device = SmartDevice({"id": "a", "key": "b", "type": "bulb", "ip": "192.168.1.20"}, FakeTuya)
        self.assertEqual(device.run("toggle"), "a on")
        self.assertEqual(device.run("toggle"), "a off")
        self.assertEqual(device.run("brighter"), "a brightness 85%")
        self.assertEqual(device.run("next colour"), "a red")
        self.assertEqual(device.device.calls,
                         ["on", "off", "on", ("brightness", 85), ("colour", 255, 0, 0)])

    def test_unreachable_ip_is_rediscovered_retried_and_saved(self):
        scans = []

        def scanner(devices, seconds, networks):
            scans.append([d.id for d in devices])
            return {"abc": {"ip": "192.168.1.20", "version": "3.5"}}

        with tempfile.TemporaryDirectory() as directory:
            path = write_config(directory, "192.168.1.99")
            home = SmartHome(path, factory=FakeTuya, scanner=scanner)
            messages = []
            done = self.wait(home, messages, 1)
            self.assertTrue(home.handlers()["Plug: toggle"]().startswith("Sending"))
            self.assertTrue(done.wait(5))
            home.shutdown()
            self.assertEqual(messages, ["Plug on"])
            self.assertEqual(scans, [["abc"]])
            saved = json.loads(path.read_text())["devices"]
            self.assertEqual(saved[0]["ip"], "192.168.1.20")
            self.assertEqual(saved[1]["extra"], 1)

    def test_offline_device_reports_error_without_raising(self):
        with tempfile.TemporaryDirectory() as directory:
            home = SmartHome(write_config(directory, "192.168.1.99"), factory=FakeTuya,
                             scanner=lambda devices, seconds, networks: {})
            messages = []
            done = self.wait(home, messages, 1)
            home.submit(home.devices[0], "on")
            self.assertTrue(done.wait(5))
            home.shutdown()
            self.assertIn("Unable to Connect", messages[0])


if __name__ == "__main__":
    unittest.main()
