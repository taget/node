# -*-Shell-script-*-
echo "Starting Kickstart Post"
PATH=/sbin:/usr/sbin:/bin:/usr/bin
export PATH

# Import SELinux Modules
echo "Enabling selinux modules"
SEMODULES="base automount avahi consolekit cyrus dhcp dnsmasq guest hal ipsec \
iscsi kerberos kerneloops ldap lockdev logadm mozilla ntp \
portmap qemu rpcbind sasl snmp stunnel sysstat tcpd unprivuser \
unconfined usbmodules userhelper virt"

lokkit -v --selinuxtype=minimum

tmpdir=$(mktemp -d)

for semodule in $SEMODULES; do
    found=0
    pp_file=/usr/share/selinux/minimum/$semodule.pp
    if [ -f $pp_file.bz2 ]; then
        bzip2 -dc $pp_file.bz2 > "$tmpdir/$semodule.pp"
        rm $pp_file.bz2
        found=1
    elif [ -f $pp_file ]; then
        mv $pp_file "$tmpdir"
        found=1
    fi
    # Don't put "base.pp" on the list.
    test $semodule = base \
        && continue
    test $found=1 \
        && modules="$modules $semodule.pp"
done

if test -n "$modules"; then
    (cd "$tmpdir" \
        && test -f base.pp \
        && semodule -v -b base.pp -i $modules \
        && semodule -v -B )
fi
rm -rf "$tmpdir"

echo "Running ovirt-install-node-stateless"
ovirt-install-node-stateless

echo "Creating shadow files"
# because we aren't installing authconfig, we aren't setting up shadow
# and gshadow properly.  Do it by hand here
pwconv
grpconv

echo "Forcing C locale"
# force logins (via ssh, etc) to use C locale, since we remove locales
cat >> /etc/profile << \EOF
# oVirt: force our locale to C since we don't have locale stuff'
export LC_ALL=C LANG=C
EOF

echo "Configuring IPTables"
# here, we need to punch the appropriate holes in the firewall
cat > /etc/sysconfig/iptables << \EOF
# oVirt automatically generated firewall configuration
*filter
:INPUT ACCEPT [0:0]
:FORWARD ACCEPT [0:0]
:OUTPUT ACCEPT [0:0]
-A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
-A INPUT -p icmp -j ACCEPT
-A INPUT -i lo -j ACCEPT
# libvirt
-A INPUT -p tcp --dport 16509 -j ACCEPT
# SSH
-A INPUT -p tcp --dport 22 -j ACCEPT
# anyterm
-A INPUT -p tcp --dport 81 -j ACCEPT
# guest consoles
-A INPUT -p tcp -m multiport --dports 5800:6000 -j ACCEPT
# migration
-A INPUT -p tcp -m multiport --dports 49152:49216 -j ACCEPT
-A INPUT -j REJECT --reject-with icmp-host-prohibited
-A FORWARD -m physdev ! --physdev-is-bridged -j REJECT --reject-with icmp-host-prohibited
COMMIT
EOF
# configure IPv6 firewall, default is all ACCEPT
cat > /etc/sysconfig/ip6tables << \EOF
# oVirt automatically generated firewall configuration
*filter
:INPUT ACCEPT [0:0]
:FORWARD ACCEPT [0:0]
:OUTPUT ACCEPT [0:0]
-A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
-A INPUT -p ipv6-icmp -j ACCEPT
-A INPUT -i lo -j ACCEPT
# libvirt
-A INPUT -p tcp --dport 16509 -j ACCEPT
# SSH
-A INPUT -p tcp --dport 22 -j ACCEPT
# anyterm
-A INPUT -p tcp --dport 81 -j ACCEPT
# guest consoles
-A INPUT -p tcp -m multiport --dports 5800:6000 -j ACCEPT
# migration
-A INPUT -p tcp -m multiport --dports 49152:49216 -j ACCEPT
-A INPUT -j REJECT --reject-with icmp6-adm-prohibited
-A FORWARD -m physdev ! --physdev-is-bridged -j REJECT --reject-with icmp6-adm-prohibited
COMMIT
EOF

# remove errors from /sbin/dhclient-script
DHSCRIPT=/sbin/dhclient-script
sed -i 's/mv /cp -p /g'  $DHSCRIPT
sed -i '/rm -f.*${interface}/d' $DHSCRIPT
sed -i '/rm -f \/etc\/localtime/d' $DHSCRIPT
sed -i '/rm -f \/etc\/ntp.conf/d' $DHSCRIPT
sed -i '/rm -f \/etc\/yp.conf/d' $DHSCRIPT

if rpm -q --qf '%{release}' ovirt-node | grep -q "^0\." ; then
    echo "Building in developer mode, leaving root account unlocked"
    augtool <<\EOF
set /files/etc/ssh/sshd_config/PermitEmptyPasswords yes
save
EOF
else
    echo "Building in production mode, locking root account"
    passwd -l root
fi

# directories required in the image with the correct perms
# config persistance currently handles only regular files
mkdir -p /root/.ssh
chmod 700 /root/.ssh

# fix iSCSI/LVM startup issue
sed -i 's/node\.session\.initial_login_retry_max.*/node.session.initial_login_retry_max = 60/' /etc/iscsi/iscsid.conf

# root's bash profile
cat >> /root/.bashrc <<EOF
# aliases used for the temporary
function mod_vi() {
  /bin/vi \$@
  restorecon -v \$@
}
alias vi="mod_vi"
alias ping='ping -c 3'
EOF

# Remove the default logrotate daily cron job
# since we run it every 10 minutes instead.
rm -f /etc/cron.daily/logrotate

# comment out /etc/* entries in rwtab to prevent overlapping mounts
touch /var/lib/random-seed
mkdir /live
mkdir /boot
sed -i '/^files	\/etc*/ s/^/#/' /etc/rwtab
cat > /etc/rwtab.d/ovirt <<EOF
dirs	/var/lib/multipath
files	/etc
dirs    /var/lib/dnsmasq
files	/var/cache/libvirt
files	/var/cache/hald
files	/var/empty/sshd/etc/localtime
files	/var/lib/dbus
files	/var/lib/libvirt
empty	/mnt
empty	/live
empty	/boot
EOF