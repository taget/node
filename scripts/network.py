#!/usr/bin/python
# network.py - Copyright (C) 2010 Red Hat, Inc.
# Written by Joey Boggs <jboggs@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.  A copy of the GNU General Public License is
# also available at http://www.gnu.org/copyleft/gpl.html.
from ovirtnode.ovirtfunctions import *
from glob import glob
import tempfile
import sys
import logging
import os

class Network:

    def __init__(self):
        OVIRT_VARS = parse_defaults()
        self.WORKDIR=tempfile.mkdtemp()
        self.IFSCRIPTS_PATH ="/etc/sysconfig/network-scripts/ifcfg-"
        self.IFCONFIG_FILE_ROOT="/files%s" % self.IFSCRIPTS_PATH
        self.NTP_CONFIG_FILE="/etc/ntp.conf"
        self.NTPSERVERS=""
        self.CONFIGURED_NIC = ""
        self.CONFIGURED_NICS = []
        self.IF_CONFIG = ""
        self.BR_CONFIG = ""
        self.VL_CONFIG = ""
        self.VLAN_ID=""
        self.VL_ROOT=""
        self.VL_FILENAME =""
        self.nic=""
        self.bridge=""
        self.vlan_id=""
        self.localhost_entry = self.get_localhost_entry()
        self.alias_count = self.get_num_localhost_aliases()

    def configure_interface(self):
        logger.info("Configuring Interface")
        self.disabled_nic = 0
        if OVIRT_VARS.has_key("OVIRT_IP_ADDRESS"):
            IPADDR = OVIRT_VARS["OVIRT_IP_ADDRESS"]
            NETMASK = OVIRT_VARS["OVIRT_IP_NETMASK"]
            GATEWAY = OVIRT_VARS["OVIRT_IP_GATEWAY"]

        if self.CONFIGURED_NIC is None:
            logger.warn("Aborting Network Configuration")
            return False

        if OVIRT_VARS.has_key("OVIRT_BOOTIF"):
            if OVIRT_VARS["OVIRT_BOOTIF"].endswith("-DISABLED"):
                self.disabled_nic = 1
            self.CONFIGURED_NIC = OVIRT_VARS["OVIRT_BOOTIF"].strip("-DISABLED")

        n_address = open("/sys/class/net/" + self.CONFIGURED_NIC + "/address")
        nic_hwaddr = n_address.readline().strip("\n")
        n_address.close()
        BRIDGE = "br" + self.CONFIGURED_NIC
        self.CONFIGURED_NICS.append(self.CONFIGURED_NIC)
        self.CONFIGURED_NICS.append(BRIDGE)
        IF_FILENAME = self.WORKDIR + "/augtool-" + self.CONFIGURED_NIC
        BR_FILENAME = self.WORKDIR + "/augtool-" + BRIDGE
        logger.info("Configure %s for use by %s" % (BRIDGE, self.CONFIGURED_NIC))
        IF_ROOT = "%s%s" % (self.IFCONFIG_FILE_ROOT, self.CONFIGURED_NIC)
        self.IF_CONFIG += "rm %s\nset %s/DEVICE %s\n" % (IF_ROOT, IF_ROOT, self.CONFIGURED_NIC)
        self.IF_CONFIG += "set %s/HWADDR %s\n" % (IF_ROOT, nic_hwaddr)
        BR_ROOT = "%s%s" % (self.IFCONFIG_FILE_ROOT, BRIDGE)
        self.BR_CONFIG += "rm %s\nset %s/DEVICE %s\n" % (BR_ROOT, BR_ROOT, BRIDGE)
        self.BR_CONFIG += "set %s/TYPE Bridge\n" % BR_ROOT
        self.BR_CONFIG += "set %s/PEERNTP yes\n" % BR_ROOT
        self.BR_CONFIG += "set %s/DELAY 0\n" % BR_ROOT
        if OVIRT_VARS.has_key("OVIRT_IPV6"):
            if OVIRT_VARS["OVIRT_IPV6"]  == "auto":
                self.BR_CONFIG += "set %s/IPV6INIT yes\n" % BR_ROOT
                self.BR_CONFIG += "set %s/IPV6FORWARDING no\n" % BR_ROOT
                self.BR_CONFIG += "set %s/IPV6_AUTOCONF yes\n" % BR_ROOT
            elif OVIRT_VARS["OVIRT_IPV6"] == "dhcp":
                self.BR_CONFIG += "set %s/IPV6INIT yes\n" % BR_ROOT
                self.BR_CONFIG += "set %s/IPV6_AUTOCONF no\n" % BR_ROOT
                self.BR_CONFIG += "set %s/IPV6FORWARDING no\n" % BR_ROOT
                self.BR_CONFIG += "set %s/DHCPV6C yes\n" % BR_ROOT
            elif OVIRT_VARS["OVIRT_IPV6"] == "static":
                self.BR_CONFIG += "set %s/IPV6INIT yes\n" % BR_ROOT
                self.BR_CONFIG += "set %s/IPV6ADDR %s/%s\n" % (BR_ROOT, OVIRT_VARS["OVIRT_IPV6_ADDRESS"], OVIRT_VARS["OVIRT_IPV6_NETMASK"])
                self.BR_CONFIG += "set %s/IPV6_AUTOCONF no\n" % BR_ROOT
                self.BR_CONFIG += "set %s/IPV6FORWARDING no\n" % BR_ROOT
                self.BR_CONFIG += "set %s/IPV6_DEFAULTGW %s\n" % (BR_ROOT, OVIRT_VARS["OVIRT_IPV6_GATEWAY"])
        else:
            self.BR_CONFIG += "set %s/IPV6INIT no\n" % BR_ROOT
            self.BR_CONFIG += "set %s/IPV6_AUTOCONF no\n" % BR_ROOT
            self.BR_CONFIG += "set %s/IPV6FORWARDING no\n" % BR_ROOT


        if OVIRT_VARS.has_key("OVIRT_VLAN"):
            VLAN_ID=OVIRT_VARS["OVIRT_VLAN"]
            self.CONFIGURED_NICS.append("%s.%s" % (self.CONFIGURED_NIC, VLAN_ID))
            VL_ROOT = "%s.%s" % (IF_ROOT, VLAN_ID)
            self.VL_CONFIG += "rm %s\n" % VL_ROOT
            self.VL_CONFIG += "set %s/DEVICE %s.%s\n" % (VL_ROOT, self.CONFIGURED_NIC, VLAN_ID)
            self.VL_CONFIG += "set %s/HWADDR %s\n" % (VL_ROOT, nic_hwaddr)
            self.VL_CONFIG += "set %s/BRIDGE %s\n" % (VL_ROOT, BRIDGE)
            self.VL_CONFIG += "set %s/VLAN yes\n" % VL_ROOT
            self.VL_FILENAME = "%s.%s" % (IF_FILENAME, OVIRT_VARS["OVIRT_VLAN"])
            self.VL_CONFIG +="set %s/ONBOOT yes" % VL_ROOT


        if not OVIRT_VARS.has_key("OVIRT_IP_ADDRESS"):
            if OVIRT_VARS.has_key("OVIRT_BOOTIF") and self.disabled_nic == 0:
                if not self.VL_CONFIG:
	            self.IF_CONFIG += "set %s/BRIDGE %s\n" % (IF_ROOT, BRIDGE)
                self.BR_CONFIG += "set %s/BOOTPROTO dhcp\n" % BR_ROOT
            elif self.disabled_nic == 1:
                self.BR_CONFIG += "set %s/BOOTPROTO none\n" % BR_ROOT

        elif OVIRT_VARS.has_key("OVIRT_IP_ADDRESS"):
            if OVIRT_VARS.has_key("OVIRT_IP_ADDRESS") and OVIRT_VARS["OVIRT_IP_ADDRESS"] != "off":
                self.BR_CONFIG += "set %s/BOOTPROTO static\n" % (BR_ROOT)
		if self.VL_CONFIG == "":
                    self.IF_CONFIG += "set %s/BRIDGE %s\n" % (IF_ROOT, BRIDGE)
                self.BR_CONFIG += "set %s/IPADDR %s\n" % (BR_ROOT, OVIRT_VARS["OVIRT_IP_ADDRESS"])
                if OVIRT_VARS.has_key("OVIRT_IP_NETMASK"):
                    self.BR_CONFIG += "set %s/NETMASK %s\n" % (BR_ROOT, OVIRT_VARS["OVIRT_IP_NETMASK"])
                if OVIRT_VARS.has_key("OVIRT_IP_GATEWAY"):
                    self.BR_CONFIG += "set %s/GATEWAY %s\n" % (BR_ROOT, OVIRT_VARS["OVIRT_IP_GATEWAY"])

        self.IF_CONFIG += "set %s/ONBOOT yes" % IF_ROOT
        self.BR_CONFIG += "set %s/ONBOOT yes" % BR_ROOT
        self.IF_CONFIG = self.IF_CONFIG.split("\n")
        self.BR_CONFIG = self.BR_CONFIG.split("\n")
        try:
            self.VL_CONFIG = self_VL_CONFIG.split("\n")
        except:
            pass
        return True

    def get_localhost_entry(self):
        entries = augtool("match","/files/etc/hosts/*","")
        for entry in entries:
            ipaddr = augtool("get",entry + "/ipaddr", "")
            if ipaddr == "127.0.0.1":
                return entry
        return None

    def get_num_localhost_aliases(self):
        if self.localhost_entry:
            aliases = augtool("match", self.localhost_entry+"/alias", "")
            return len(aliases)
        return 0

    def remove_non_localhost(self):
        last_alias = augtool("get", self.localhost_entry+"/alias["+str(self.alias_count)+"]", "")
        while self.alias_count != 0:
            if last_alias == "localhost":
                break
            elif last_alias == "localhost.localdomain":
                break
            augtool("rm", self.localhost_entry+"/alias["+str(self.alias_count)+"]", "")
            self.alias_count = self.alias_count - 1

    def add_localhost_alias(self, alias):
        self.alias_count = self.alias_count + 1
        augtool("set", self.localhost_entry+"/alias["+str(self.alias_count)+"]",alias)


    def configure_dns(self):
        OVIRT_VARS = parse_defaults()
        if OVIRT_VARS.has_key("OVIRT_DNS"):
            DNS=OVIRT_VARS["OVIRT_DNS"]
            try:
                if DNS is not None:
                    tui_cmt = ("Please make changes through the TUI. " + \
                               "Manual edits to this file will be " + \
                               "lost on reboot")
                    augtool("set", "/files/etc/resolv.conf/#comment[1]", \
                            tui_cmt)
                    DNS = DNS.split(",")
                    i = 1
                    for server in DNS:
                        logger.debug("Setting DNS server %d: %s" % (i, server))
                        setting = "/files/etc/resolv.conf/nameserver[%s]" % i
                        augtool("set", setting, server)
                        i = i + i
                    ovirt_store_config("/etc/resolv.conf")
                else:
                    logger.debug("No DNS servers given.")
            except:
                logger.warn("Failed to set DNS servers")
            finally:
                if len(DNS) < 2:
                    augtool("rm", "/files/etc/resolv.conf/nameserver[2]", "")
                for nic in glob("/etc/sysconfig/network-scripts/ifcfg-*"):
                    if not "ifcfg-lo" in nic:
                        path="/files%s/PEERDNS" % nic
                        augtool("set", path, "no")

    def configure_ntp(self):
        if OVIRT_VARS.has_key("OVIRT_NTP"):
            NTPSERVERS=OVIRT_VARS["OVIRT_NTP"]
        else:
            NTPSERVERS=""

    def save_ntp_configuration(self):
        ntproot = "/files/etc/ntp.conf"
        ntpconf = "rm %s\n" % ntproot
        ntpconf += "set %s/driftfile /var/lib/ntp/drift\n" % ntproot
        ntpconf += "set %s/includefile /etc/ntp/crypto/pw\n" % ntproot
        ntpconf += "set %s/keys /etc/ntp/keys" % ntproot
        ntpconf = ntpconf.split("\n")
        for line in ntpconf:
            try:
                oper, key, value = line.split()
                augtool(oper, key, value)
            except:
                oper, key = line.split()
                augtool(oper, key, "")

        if OVIRT_VARS.has_key("OVIRT_NTP"):
            offset=1
            SERVERS = OVIRT_VARS["OVIRT_NTP"].split(",")
            for server in SERVERS:
                if offset == 1:
                    augtool("set", "/files/etc/ntp.conf/server[1]", server)
                elif offset == 2:
                    augtool("set", "/files/etc/ntp.conf/server[2]", server)
                offset = offset + 1
            system_closefds("service ntpd stop &> /dev/null")
            system_closefds("service ntpdate start &> /dev/null")
            system_closefds("service ntpd start &> /dev/null")

    def save_network_configuration(self):
        aug.load()
        net_configured=0
        augtool_workdir_list = "ls %s/augtool-* >/dev/null"
        logger.info("Configuring network for NIC %s" % self.CONFIGURED_NIC)
        system("ifdown br" + self.CONFIGURED_NIC)
        for vlan in get_system_vlans():
            # XXX wrong match e.g. eth10.1 with eth1
            if self.CONFIGURED_NIC in vlan:
                system_closefds("vconfig rem " + vlan + "&> /dev/null")
                ovirt_safe_delete_config(self.IFSCRIPTS_PATH + vlan)
                system_closefds("rm -rf " + self.IFSCRIPTS_PATH + vlan)

        logger.debug("Removing persisted network configs")
        # This should cover NICs, VLANs and bridges
        for script in glob("%s*" % (self.IFSCRIPTS_PATH)):
            if not is_persisted(script):
                continue
            logger.debug("Removing Script: " + script)
            ovirt_safe_delete_config(script)
        aug.load()

        logger.debug("Updating interface config")
        for line in self.IF_CONFIG:
            logger.debug(line)
            try:
                oper, key, value = line.split()
                augtool(oper, key, value)
            except:
                oper, key = line.split()
                augtool(oper, key, "")

        logger.debug("Updating bridge config")
        for line in self.BR_CONFIG:
            logger.debug(line)
            try:
                oper, key, value = line.split()
                augtool(oper, key, value)
            except:
                try:
                    oper, key = line.split()
                    augtool(oper, key, "")
                except:
                    pass

        logger.debug("Updating VLAN config")
        for line in self.VL_CONFIG.split("\n"):
            logger.debug(line)
            try:
                oper, key, value = line.split()
                augtool(oper, key, value)
            except:
                try:
                    oper, key = line.split()
                    augtool(oper, key, "")
                except:
                    pass

        # preserve current MAC mappings for *all physical* network interfaces
        logger.debug("Preserving current MAC mappings")
        for nicdev in glob('/sys/class/net/*/device'):
            nic=nicdev.split('/')[4]
            if nic != self.CONFIGURED_NIC:
                f=open('/sys/class/net/%s/address' % nic)
                mac=f.read().strip()
                f.close()
                if len(mac) > 0:
                    logger.debug ("Mapping for %s" % nic)
                    self.CONFIGURED_NICS.append(nic)
                    nicroot = "%s%s" % (self.IFCONFIG_FILE_ROOT, nic)
                    # XXX augtool does save every time!
                    augtool("set", "%s/DEVICE" % nicroot, nic)
                    augtool("set", "%s/HWADDR" % nicroot, mac)
                    augtool("set", "%s/ONBOOT" % nicroot, "no")

        logger.debug("Storing configured NICs")
        net_configured=1
        for nic in self.CONFIGURED_NICS:
            logger.debug("Storing %s" % nic)
            ovirt_store_config("%s%s" % (self.IFSCRIPTS_PATH, nic) )
        ovirt_store_config(self.NTP_CONFIG_FILE)
        augtool("set", "/files/etc/sysconfig/network/NETWORKING", "yes")
        ovirt_store_config("/etc/sysconfig/network")
        ovirt_store_config ("/etc/hosts")
        logger.info("Network configured successfully")
        if net_configured == 1:
            logger.info("Stopping Network services")
            system_closefds("service network stop &> /dev/null")
            system_closefds("service ntpd stop &> /dev/null")
            # XXX eth assumed in breth
            brctl_cmd = "brctl show| awk 'NR>1 && /^br[ep]/ {print $1}'"
            brctl = subprocess_closefds(brctl_cmd, shell=True, stdout=PIPE, stderr=STDOUT)
            brctl_output = brctl.stdout.read()
            for i in brctl_output.split():
                if_down_cmd = "ifconfig %s down &> /dev/null" % i
                system_closefds(if_down_cmd)
                del_br_cmd = "brctl delbr %s &> /dev/null" % i
                system_closefds(del_br_cmd)
            logger.info("Starting Network service")
            system_closefds("service network start &> /dev/null")
            system_closefds("service ntpdate start &> /dev/null")
            system_closefds("service ntpd start &> /dev/null")
            # rhbz#745541
            system_closefds("service rpcbind start &> /dev/null")
            system_closefds("service nfslock start &> /dev/null")
            system_closefds("service rpcidmapd start &> /dev/null")
            system_closefds("service rpcgssd start &> /dev/null")
            if OVIRT_VARS.has_key("NTP"):
                logger.info("Testing NTP Configuration")
                test_ntp_configuration()

def get_system_nics():
    client = gudev.Client(['net'])
    configured_nics = 0
    ntp_dhcp = 0
    nic_dict = {}
    for device in client.query_by_subsystem("net"):
        try:
            dev_interface = device.get_property("INTERFACE")
            dev_vendor = device.get_property("ID_VENDOR_FROM_DATABASE")
            dev_type = device.get_property("DEVTYPE")
            dev_path = device.get_property("DEVPATH")
            try:
                dev_vendor = dev_vendor.replace(",", "")
            except AttributeError:
                try:
                    # rhevh workaround since udev version doesn't have vendor info
                    dev_path = dev_path.split('/')
                    if "virtio" in dev_path[4]:
                        pci_dev = dev_path[3].replace("0000:","")
                    else:
                        pci_dev = dev_path[4].replace("0000:","")
                    pci_lookup_cmd = " lspci|grep %s|awk -F \":\" {'print $3'}" % pci_dev
                    pci_lookup = subprocess_closefds(pci_lookup_cmd, shell=True, stdout=PIPE, stderr=STDOUT)
                    dev_vendor = pci_lookup.stdout.read().strip()
                except:
                    dev_vendor = "unknown"
            try:
                dev_vendor = dev_vendor.replace(",", "")
            except AttributeError:
                dev_vendor = "unknown"
            dev_vendor = pad_or_trim(25, dev_vendor)
            try:
                dev_driver = os.readlink("/sys/class/net/" + dev_interface + "/device/driver")
                dev_driver = os.path.basename(dev_driver)
            except:
                pass
            nic_addr_file = open("/sys/class/net/" + dev_interface + "/address")
            dev_address = nic_addr_file.read().strip()
            cmd = "/files/etc/sysconfig/network-scripts/ifcfg-%s/BOOTPROTO" % str(dev_interface)
            dev_bootproto = augtool_get(cmd)
            type_cmd = "/files/etc/sysconfig/network-scripts/ifcfg-%s/TYPE" % str(dev_interface)
            bridge_cmd = "/files/etc/sysconfig/network-scripts/ifcfg-%s/BRIDGE" % str(dev_interface)
            dev_bridge =  augtool_get(bridge_cmd)
            if dev_bootproto is None:
                cmd = "/files/etc/sysconfig/network-scripts/ifcfg-%s/BOOTPROTO" % str(dev_bridge)
                dev_bootproto = augtool_get(cmd)
                if dev_bootproto is None:
                    dev_bootproto = "Disabled"
                    dev_conf_status = "Unconfigured"
                    # check for vlans
                    logger.debug("checking for vlan")
                    if len(glob("/etc/sysconfig/network-scripts/ifcfg-" + dev_interface + ".*")) > 0:
                        logger.debug("found vlan")
                        dev_conf_status = "Configured  "
                else:
                    dev_conf_status = "Configured  "
            else:
                dev_conf_status = "Configured  "
            if dev_conf_status == "Configured  ":
                configured_nics = configured_nics + 1
        except:
            pass
        if "." in dev_interface:
            dev_interface = dev_interface.split(".")[0]
        if not dev_interface == "lo" and not dev_interface.startswith("bond") and not dev_interface.startswith("sit") and not "." in dev_interface:
            if not dev_type == "bridge":
                nic_dict[dev_interface] = "%s,%s,%s,%s,%s,%s,%s" % (dev_interface,dev_bootproto,dev_vendor,dev_address, dev_driver, dev_conf_status,dev_bridge)
                if dev_bootproto == "dhcp":
                    ntp_dhcp = 1
    return nic_dict, configured_nics, ntp_dhcp

def get_system_vlans():
    """Retrieves a list of VLANs on this host
    """
    vlandir = "/proc/net/vlan/"
    vlans = []
    if os.path.exists(vlandir):
        vlans = os.listdir(vlandir)
        vlans.remove("config")
    return vlans

def convert_to_biosdevname():
    if not "BIOSDEVNAMES_CONVERSION" in OVIRT_VARS:
        nics = {}
        cmd = "biosdevname -d"
        biosdevname, err = subprocess.Popen(cmd, shell=True, stdout=PIPE).communicate()
        biosdevname_output = biosdevname.splitlines()

        for line in biosdevname_output:
            if line is not None:
                if "BIOS device:" in line:
                    nic = line.split()[2]
                if "Permanent" in line:
                    mac = line.split()[2]
                    nics[mac.upper()] = nic
        logger.debug(nics)
        scripts_path="/etc/sysconfig/network-scripts"
        logger.debug(glob(scripts_path + "/ifcfg-*"))
        for file in glob(scripts_path + "/ifcfg-*"):
            logger.debug("Processing %s" % file)
            # get mac for matching
            existing_mac = augtool_get("/files/"+file+"/HWADDR")
            # check dictionary for mac
            if not existing_mac is None and existing_mac.upper() in nics:
                old_nic_script = os.path.basename(file)
                new_nic_name = nics[existing_mac.upper()]
                logger.debug("Found %s in %s" % (existing_mac, file))
                # change device name within script file
                logger.debug("Setting to new device name: %s" % new_nic_name)
                augtool("set","/files"+file+"/DEVICE", new_nic_name)
                new_nic_file = "%s/ifcfg-%s" % (scripts_path, new_nic_name)
                cmd = "cp %s %s" % (file,new_nic_file)
                remove_config(file)
                if system(cmd):
                    logging.debug("Conversion on %s to %s succeed" % (file,new_nic_file))
                    ovirt_store_config(new_nic_file)
                else:
                    return False
        system("service network restart")
        augtool("set", "/files/etc/default/ovirt/BIOSDEVNAMES_CONVERSION", "y")
        ovirt_store_config("/etc/default/ovirt")
    return True
def network_auto():
    try:
        network = Network()
        network.configure_interface()
        network.configure_dns()
        network.configure_ntp()
        network.save_ntp_configuration()
        network.save_network_configuration()
    except:
        logger.warn("Network Configuration Failed....")
        return False
