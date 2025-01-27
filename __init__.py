# Copyright 2016 Eugene R. Miller
#
# This file is a 3rd party skill for mycroft.
#
# The Mycroft diagnostics skill is free software: you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.
#
# diagnostics kill is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with the diagnostics skill.
# If not, see <http://www.gnu.org/licenses/>.

from os.path import dirname, exists, isfile, expanduser
from os import access, X_OK

from ovos_workshop.intents import IntentBuilder
from ovos_workshop.skills import OVOSSkill
from ovos_utils.log import getLogger
import psutil
import subprocess
import json
from time import time

__author__ = 'the7erm'

LOGGER = getLogger(__name__)


def and_(strings):
    """
    Join a list of strings with , and add 'and' at the end, because grammar
    matters.
    """
    if len(strings) <= 1:
        return " ".join(strings)

    return "%s and %s" % (", ".join(strings[0:-1]), strings[-1])


def sizeof_fmt(num, suffix='Bytes'):
    # Attribution: http://stackoverflow.com/a/1094933/2444609
    for unit in [
            'Bytes', 'Kilo bytes', 'Megs', 'Gig', 'Tera bytes', 'Peta bytes',
            'Exa bytes', 'Yotta bytes'
    ]:
        if abs(num) < 1024.0:
            return "%3.1f %s" % (num, unit)
        num /= 1024.0

    return "%.1f %s" % (num, 'Yi')


def is_exe(fpath):
    # Attribution: http://stackoverflow.com/a/377028/2444609
    return isfile(fpath) and access(fpath, X_OK)


class DiagnosticsSkill(OVOSSkill):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.public_ip = None
        self.public_ip_expire = 0
        self.diagnostic_script = None
        if self.config is not None:
            self.diagnostic_script = self.config.get('script')

    def initialize(self):

        cpu_intent = IntentBuilder("CpuIntent")\
            .require("CpuKeyword")\
            .build()
        self.register_intent(cpu_intent, self.handle_cpu_intent)

        drive_intent = IntentBuilder("DriveIntent")\
            .require("DriveSpaceKeyword")\
            .build()
        self.register_intent(drive_intent, self.handle_drive_intent)

        # There's already an IP skill.
        ip_intent = IntentBuilder("IpIntent")\
            .require("IpKeyword")\
            .build()
        self.register_intent(ip_intent, self.handle_ip_intent)

        uptime_intent = IntentBuilder("UptimeIntent")\
            .require("UptimeKeyword")\
            .build()
        self.register_intent(uptime_intent, self.handle_updtime_intent)

        custom_intent = IntentBuilder("CustomIntent")\
            .require("CustomKeyword")\
            .build()
        self.register_intent(custom_intent, self.handle_custom_intent)

    def handle_cpu_intent(self, message):
        data = {"percent": psutil.cpu_percent(interval=1)}
        self.speak_dialog("cpu", data)
        self.speak_dialog("WorkingHardOn")
        output = subprocess.check_output(
            "ps -eo pcpu,comm --no-headers|"
            "sort -t. -nk1,2 -k4,4 -r |"
            "head -n 4 |"
            "awk '{print $2}'",
            shell=True)
        output = output.strip()
        self.speak(and_(output.split("\n")))

    def handle_drive_intent(self, message):
        partitions = psutil.disk_partitions()
        for partition in partitions:
            print(("partition.mountpoint: %s" % partition.mountpoint))
            if partition.mountpoint.startswith("/snap/"):
                continue
            partition_data = psutil.disk_usage(partition.mountpoint)
            # total=21378641920, used=4809781248, free=15482871808,
            # percent=22.5
            data = {
                "mountpoint": partition.mountpoint,
                "total": sizeof_fmt(partition_data.total),
                "used": sizeof_fmt(partition_data.used),
                "free": sizeof_fmt(partition_data.free),
                "percent": partition_data.percent
            }
            if partition_data.percent >= 90:
                self.speak_dialog("drive.low", data)
            else:
                self.speak_dialog("drive", data)

    def handle_ip_intent(self, message):
        ips = subprocess.check_output(['hostname', "-I"])
        ips = ips.strip()
        ips = ips.split(" ")

        public_json = subprocess.check_output(
            ["wget", "-qO-", "https://api.ipify.org/?format=json"])

        public_ip = {"ip": "undetermined"}
        try:
            if self.public_ip is None or time() > self.public_ip_expire:
                public_ip = json.loads(public_json)
                self.public_ip = public_ip
                self.public_ip_expire = time() + 60
        except:
            pass
        data = {
            "ips": and_(ips),
            "public": public_ip.get("ip", "undetermined")
        }
        self.speak_dialog("ip", data)

    def handle_updtime_intent(self, message):
        uptime = subprocess.check_output(['uptime', '-p'])
        data = {'uptime': uptime.strip()}
        self.speak_dialog("uptime", data)

    def handle_custom_intent(self, message):
        script = expanduser(self.config.get("script"))

        if not script:
            self.speak_dialog("no.script")
            return

        if not exists(script):
            data = {"script": script}
            self.speak_dialog("missing.script", data)
            return

        if not is_exe(script):
            data = {"script": script}
            self.speak_dialog("not.executable.script", data)
            return

        self.speak_dialog("processing.script")

        result = subprocess.check_output([script])
        self.speak(result.strip())

    def stop(self):
        pass
