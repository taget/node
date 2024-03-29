
%include version.ks

if [ -f "ovirt-authorized_keys" ]; then
  echo "Adding authorized_keys to Image"
  mkdir -p $INSTALL_ROOT/root/.ssh
  cp -v ovirt-authorized_keys $INSTALL_ROOT/root/.ssh/authorized_keys
  chown -R root:root $INSTALL_ROOT/root/.ssh
  chmod 755 $INSTALL_ROOT/root/.ssh
  chmod 644 $INSTALL_ROOT/root/.ssh/authorized_keys
fi

echo "Fixing boot menu"
# remove quiet from Node bootparams, added by livecd-creator
sed -i -e 's/ quiet//' $LIVE_ROOT/isolinux/isolinux.cfg

# Remove Verify and Boot option
sed -i -e '/label check0/{N;N;N;d;}' $LIVE_ROOT/isolinux/isolinux.cfg

# Rename Boot option to Install or Upgrade
sed -i 's/^  menu label Boot$/  menu label Install or Upgrade/' $LIVE_ROOT/isolinux/isolinux.cfg

# add serial console boot entry
menu=$(mktemp)
awk '
/^label linux0/ { linux0=1 }
linux0==1 && $1=="append" {
  append0=$0
}
linux0==1 && $1=="label" && $2!="linux0" {
  linux0=2
  print "label serial-console"
  print "  menu label Install or Upgrade with serial console"
  print "  kernel vmlinuz0"
  print append0" console=ttyS0,115200n8 "
  print "label reinstall"
  print "  menu label Reinstall"
  print "  kernel vmlinuz0"
  print append0" reinstall "
  print "label reinstall-serial"
  print "  menu label Reinstall with serial console"
  print "  kernel vmlinuz0"
  print append0" reinstall console=ttyS0,115200n8 "
  print "label uninstall"
  print "  menu label Uninstall"
  print "  kernel vmlinuz0"
  print append0" uninstall "
}
{ print }
' $LIVE_ROOT/isolinux/isolinux.cfg > $menu
# change the title
sed -i -e '/^menu title/d' $menu
echo "say This is the $PRODUCT $VERSION ($RELEASE)" > $LIVE_ROOT/isolinux/isolinux.cfg
echo "menu title ${PRODUCT_SHORT} $VERSION ($RELEASE)" >> $LIVE_ROOT/isolinux/isolinux.cfg
cat $menu >> $LIVE_ROOT/isolinux/isolinux.cfg
rm $menu
cp $INSTALL_ROOT/usr/share/ovirt-node/syslinux-vesa-splash.jpg $LIVE_ROOT/isolinux/splash.jpg

# store image version info in the ISO and rootfs
cat > $LIVE_ROOT/isolinux/version <<EOF
PRODUCT='$PRODUCT'
PRODUCT_SHORT='${PRODUCT_SHORT}'
PRODUCT_CODE=$PRODUCT_CODE
RECIPE_SHA256=$RECIPE_SHA256
RECIPE_RPM=$RECIPE_RPM
PACKAGE=$PACKAGE
VERSION=$VERSION
RELEASE=$RELEASE
EOF
cp $LIVE_ROOT/isolinux/version $INSTALL_ROOT/etc/default/

# overwrite user visible banners with the image versioning info
cat > $INSTALL_ROOT/etc/$PACKAGE-release <<EOF
$PRODUCT release $VERSION ($RELEASE)
EOF
ln -snf $PACKAGE-release $INSTALL_ROOT/etc/redhat-release
ln -snf $PACKAGE-release $INSTALL_ROOT/etc/system-release
cp $INSTALL_ROOT/etc/$PACKAGE-release $INSTALL_ROOT/etc/issue
echo "Kernel \r on an \m (\l)" >> $INSTALL_ROOT/etc/issue
cp $INSTALL_ROOT/etc/issue $INSTALL_ROOT/etc/issue.net

NAME=$(grep CDLABEL $LIVE_ROOT/isolinux/isolinux.cfg |head -n1|sed -r 's/^.*CDLABEL\=([a-zA-Z0-9_-]+) .*$/\1/g')

#setup efi boot menu
cat > $LIVE_ROOT/EFI/BOOT/BOOTX64.conf <<EOF
default=0
splashimage=/EFI/BOOT/splash.xpm.gz
timeout 30
hiddenmenu
title Install or Upgrade
  kernel /EFI/BOOT/vmlinuz0 root=live:CDLABEL=$NAME rootfstype=auto ro liveimg check rootflags=ro crashkernel=512M-2G:64M,2G-:128M elevator=deadline install quiet rd_NO_LVM rd.luks=0 rd.md=0 rd.dm=0
  initrd /EFI/BOOT/initrd0.img
title Install or Upgrade (Basic Video)
  kernel /EFI/BOOT/vmlinuz0 root=live:CDLABEL=$NAME rootfstype=auto ro liveimg check rootflags=ro crashkernel=512M-2G:64M,2G-:128M elevator=deadline install quiet rd_NO_LVM rd.luks=0 rd.md=0 rd.dm=0
  initrd /EFI/BOOT/initrd0.img
title Install or Upgrade with serial console
  kernel /EFI/BOOT/vmlinuz0 root=live:CDLABEL=$NAME rootfstype=auto ro liveimg check rootflags=ro crashkernel=512M-2G:64M,2G-:128M elevator=deadline install quiet rd_NO_LVM rd.luks=0 rd.md=0 rd.dm=0  console=ttyS0,115200n8
  initrd /EFI/BOOT/initrd0.img
title Reinstall
  kernel /EFI/BOOT/vmlinuz0 root=live:CDLABEL=$NAME rootfstype=auto ro liveimg check rootflags=ro crashkernel=512M-2G:64M,2G-:128M elevator=deadline install quiet rd_NO_LVM rd.luks=0 rd.md=0 rd.dm=0  reinstall
  initrd /EFI/BOOT/initrd0.img
title Reinstall (Basic Video)
  kernel /EFI/BOOT/vmlinuz0 root=live:CDLABEL=$NAME rootfstype=auto ro liveimg check rootflags=ro crashkernel=512M-2G:64M,2G-:128M elevator=deadline install quiet rd_NO_LVM rd.luks=0 rd.md=0 rd.dm=0  reinstall
  initrd /EFI/BOOT/initrd0.img
title Reinstall with serial console
  kernel /EFI/BOOT/vmlinuz0 root=live:CDLABEL=$NAME rootfstype=auto ro liveimg check rootflags=ro crashkernel=512M-2G:64M,2G-:128M elevator=deadline install quiet rd_NO_LVM rd.luks=0 rd.md=0 rd.dm=0  reinstall console=ttyS0,115200n8
  initrd /EFI/BOOT/initrd0.img
title Uninstall
  kernel /EFI/BOOT/vmlinuz0 root=live:CDLABEL=$NAME rootfstype=auto ro liveimg check rootflags=ro crashkernel=512M-2G:64M,2G-:128M elevator=deadline install quiet rd_NO_LVM rd.luks=0 rd.md=0 rd.dm=0  uninstall
  initrd /EFI/BOOT/initrd0.img
title Start $PRODUCT in basic graphics mode.
  kernel /EFI/BOOT/vmlinuz0 root=live:CDLABEL=$NAME rootfstype=auto ro liveimg check rootflags=ro crashkernel=512M-2G:64M,2G-:128M elevator=deadline install quiet rd_NO_LVM rd.luks=0 rd.md=0 rd.dm=0 nomodeset
  initrd /EFI/BOOT/initrd0.img
EOF
