#
# Copyright (C) 2008 Red Hat, Inc.
# Copyright (C) 2008 Cole Robinson <crobinso@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301 USA.
#

import logging
import gtk
import libxml2

import libvirt

import virtManager
import virtinst

DEFAULT_POOL_NAME = "default"
DEFAULT_POOL_PATH = "/var/lib/libvirt/images"

def build_default_pool(conn):
    """Helper to build the 'default' storage pool"""
    # FIXME: This should use config.get_default_image_path ?

    if not virtinst.util.is_storage_capable(conn):
        # VirtualDisk will raise an error for us
        return
    pool = None
    try:
        pool = conn.storagePoolLookupByName(DEFAULT_POOL_NAME)
    except libvirt.libvirtError:
        pass

    if pool:
        return

    try:
        logging.debug("Attempting to build default pool with target '%s'" %
                      DEFAULT_POOL_PATH)
        defpool = virtinst.Storage.DirectoryPool(conn=conn,
                                                 name=DEFAULT_POOL_NAME,
                                                 target_path=DEFAULT_POOL_PATH)
        newpool = defpool.install(build=True, create=True)
        newpool.setAutostart(True)
    except Exception, e:
        raise RuntimeError(_("Couldn't create default storage pool '%s': %s") %
                             (DEFAULT_POOL_PATH, str(e)))

def tooltip_wrapper(obj, txt, func="set_tooltip_text"):
    # Catch & ignore errors - set_tooltip_* is in gtk >= 2.12
    # and we can easily work with lower versions
    try:
        funcptr = getattr(obj, func)
        funcptr(txt)
    except:
        ver = gtk.gtk_version
        if ver[0] >= 2 and ver[1] >= 12:
            logging.exception("Couldn't set tooltip.")

def xml_parse_wrapper(xml, parse_func, *args, **kwargs):
    """
    Parse the passed xml string into an xpath context, which is passed
    to parse_func, along with any extra arguments.
    """

    doc = None
    ctx = None
    ret = None
    try:
        doc = libxml2.parseDoc(xml)
        ctx = doc.xpathNewContext()
        ret = parse_func(doc, ctx, *args, **kwargs)
    finally:
        if ctx != None:
            ctx.xpathFreeContext()
        if doc != None:
            doc.freeDoc()
    return ret


def browse_local(parent, dialog_name, start_folder=None, _type=None,
                 dialog_type=gtk.FILE_CHOOSER_ACTION_OPEN,
                 foldermode=False, confirm_func=None):

    overwrite_confirm = False
    choose_button = gtk.STOCK_OPEN
    if dialog_type == gtk.FILE_CHOOSER_ACTION_SAVE:
        choose_button = gtk.STOCK_SAVE
        overwrite_confirm = True

    fcdialog = gtk.FileChooserDialog(dialog_name, parent,
                                     dialog_type,
                                     (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                      choose_button, gtk.RESPONSE_ACCEPT),
                                      None)
    fcdialog.set_default_response(gtk.RESPONSE_ACCEPT)

    if confirm_func:
        overwrite_confirm = True
        fcdialog.connect("confirm-overwrite", confirm_func)
    fcdialog.set_do_overwrite_confirmation(overwrite_confirm)

    if _type != None:
        pattern = _type
        name = None
        if type(_type) is tuple:
            pattern = _type[0]
            name = _type[1]

        f = gtk.FileFilter()
        f.add_pattern("*." + pattern)
        if name:
            f.set_name(name)
        fcdialog.set_filter(f)

    if start_folder != None:
        fcdialog.set_current_folder(start_folder)

    response = fcdialog.run()
    fcdialog.hide()
    if(response == gtk.RESPONSE_ACCEPT):
        filename = fcdialog.get_filename()
        fcdialog.destroy()
        return filename
    else:
        fcdialog.destroy()
        return None

def dup_conn(config, conn, libconn=None, return_conn_class=False):

    is_readonly = False

    if libconn:
        uri = libconn.getURI()
        is_test = uri.startswith("test")
        vmm = libconn
    else:
        is_test = conn.is_test_conn()
        is_readonly = conn.is_read_only()
        uri = conn.get_uri()
        vmm = conn.vmm

    if is_test:
        # Skip duplicating a test conn, since it doesn't maintain state
        # between instances
        return vmm

    logging.debug("Duplicating connection for async operation.")
    newconn = virtManager.connection.vmmConnection(config, uri, is_readonly)
    newconn.open()
    newconn.connectThreadEvent.wait()

    if return_conn_class:
        return newconn
    else:
        return newconn.vmm

def pretty_hv(gtype, domtype):
    """
    Convert XML <domain type='foo'> and <os><type>bar</type>
    into a more human relevant string.
    """

    gtype = gtype.lower()
    domtype = domtype.lower()

    label = domtype
    if domtype == "kvm":
        if gtype == "xen":
            label = "xenner"
    elif domtype == "xen":
        if gtype == "xen":
            label = "xen (paravirt)"
        elif gtype == "hvm":
            label = "xen (fullvirt)"
    elif domtype == "test":
        if gtype == "xen":
            label = "test (xen)"
        elif gtype == "hvm":
            label = "test (hvm)"

    return label
