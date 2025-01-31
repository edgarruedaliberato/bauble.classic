# -*- coding: utf-8 -*-
#
# Copyright 2008-2010 Brett Adams
# Copyright 2015 Mario Frasca <mario@anche.no>.
#
# This file is part of bauble.classic.
#
# bauble.classic is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# bauble.classic is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with bauble.classic. If not, see <http://www.gnu.org/licenses/>.
#
# connmgr.py
#

"""
The connection manager provides a GUI for creating and opening
connections. This is the first thing displayed when Bauble starts.
"""
import os
import copy

import logging
logger = logging.getLogger(__name__)
#logger.setLevel(logging.DEBUG)

import gtk

from bauble.i18n import _
import bauble.utils as utils
from bauble.error import check
import bauble
import bauble.paths as paths
import bauble.prefs as prefs

from bauble.editor import (
    GenericEditorView, GenericEditorPresenter)


def is_package_name(name):
    '''True if name identifies a package and it can be imported
    '''

    try:
        __import__(name)
        return True
    except ImportError:
        return False

working_dbtypes = []
dbtypes = []


def populate_dbtypes(package_list):
    '''initialize dbtypes and working_dbtypes

    package_list is a list of pairs, in each pair, first is the package
    name, second the mnemonic name by which we identify the package
    '''

    global dbtypes, working_dbtypes
    dbtypes = [second for first, second in package_list]
    working_dbtypes = [second for first, second in package_list
                       if is_package_name(first)]

populate_dbtypes([('sqlite3', 'SQLite'),
                  ('psycopg2', 'PostgreSQL'),
                  ('MySQLdb', 'MySQL'),
                  ('pyodbc', 'MS SQL Server'),
                  ('cx_Oracle', 'Oracle'),
                  ])


def type_combo_cell_data_func(combo, renderer, model, iter, data=None):
    """passed to the gtk method set_cell_data_func

    item is sensitive iff in working_dbtypes
    """
    dbtype = model[iter][0]
    sensitive = dbtype in working_dbtypes
    renderer.set_property('sensitive', sensitive)
    renderer.set_property('text', dbtype)


class ConnMgrPresenter(GenericEditorPresenter):
    """
    The main class that starts the connection manager GUI.

    :param default: the name of the connection to select from the list
      of connection names
    """

    widget_to_field_map = {
        'name_combo': 'connection_name',  # and self.connection_names
        'usedefaults_chkbx': 'use_defaults',
        'type_combo': 'dbtype',
        'file_entry': 'filename',
        'database_entry': 'database',
        'host_entry': 'host',
        'user_entry': 'user',
        'passwd_chkbx': 'passwd',
        'pictureroot2_entry': 'pictureroot',
        'pictureroot_entry': 'pictureroot',
        }

    view_accept_buttons = ['cancel_button', 'connect_button']

    def __init__(self, view=None):
        self.filename = self.database = self.host = self.user = \
            self.pictureroot = self.connection_name = ''
        self.use_defaults = True
        self.passwd = False
        ## following two look like overkill, since they will be initialized
        ## in the parent class constructor. but we need these attributes in
        ## place before we can invoke get_params
        self.model = self
        self.view = view

        ## initialize comboboxes, so we can fill them in
        view.combobox_init('name_combo')
        view.combobox_init('type_combo', dbtypes, type_combo_cell_data_func)
        self.connection_names = []
        self.connections = prefs.prefs[bauble.conn_list_pref] or {}
        for ith_connection_name in self.connections:
            view.combobox_append_text('name_combo', ith_connection_name)
            self.connection_names.append(ith_connection_name)
        if self.connection_names:
            self.connection_name = prefs.prefs[bauble.conn_default_pref]
            if self.connection_name not in self.connections:
                self.connection_name = self.connection_names[0]
            self.dbtype = None
            self.set_params()
        else:
            self.dbtype = ''
            self.connection_name = None
        GenericEditorPresenter.__init__(
            self, model=self, view=view, refresh_view=True)
        logo_path = os.path.join(paths.lib_dir(), "images", "bauble_logo.png")
        view.image_set_from_file('logo_image', logo_path)
        view.set_title('%s %s' % ('Bauble', bauble.version))
        try:
            view.set_icon(gtk.gdk.pixbuf_new_from_file(bauble.default_icon))
        except:
            pass

    def on_file_btnbrowse_clicked(self, *args):
        previously = self.view.widget_get_value('file_entry')
        last_folder, bn = os.path.split(previously)
        self.view.run_file_chooser_dialog(
            _("Choose a file..."), None,
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=(gtk.STOCK_OK, gtk.RESPONSE_ACCEPT,
                     gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL),
            last_folder=last_folder, target='file_entry')

    def on_pictureroot_btnbrowse_clicked(self, *args):
        previously = self.view.widget_get_value('pictureroot_entry')
        last_folder, bn = os.path.split(previously)
        self.view.run_file_chooser_dialog(
            _("Choose a file..."), None,
            action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            buttons=(gtk.STOCK_OK, gtk.RESPONSE_ACCEPT,
                     gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL),
            last_folder=last_folder, target='pictureroot_entry')

    def on_pictureroot2_btnbrowse_clicked(self, *args):
        previously = self.view.widget_get_value('pictureroot2_entry')
        last_folder, bn = os.path.split(previously)
        self.view.run_file_chooser_dialog(
            _("Choose a file..."), None,
            action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            buttons=(gtk.STOCK_OK, gtk.RESPONSE_ACCEPT,
                     gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL),
            last_folder=last_folder, target='pictureroot2_entry')

    def refresh_view(self):
        GenericEditorPresenter.refresh_view(self)
        conn_dict = self.connections
        if conn_dict is None or len(conn_dict.keys()) == 0:
            self.view.widget_set_visible('noconnectionlabel', True)
            self.view.widget_set_visible('expander', False)
        else:
            self.view.widget_set_visible('expander', True)
            self.view.widget_set_visible('noconnectionlabel', False)
            if self.dbtype == 'SQLite':
                self.view.widget_set_visible('sqlite_parambox', True)
                self.view.widget_set_visible('dbms_parambox', False)
                self.refresh_entries_sensitive()
            else:
                self.view.widget_set_visible('dbms_parambox', True)
                self.view.widget_set_visible('sqlite_parambox', False)

    def on_usedefaults_chkbx_toggled(self, widget, *args):
        self.on_chkbx_toggled(widget, *args)
        self.refresh_entries_sensitive()

    def refresh_entries_sensitive(self):
        x = not self.use_defaults
        self.view.widget_set_sensitive('file_entry', x)
        self.view.widget_set_sensitive('pictureroot_entry', x)
        self.view.widget_set_sensitive('file_btnbrowse', x)
        self.view.widget_set_sensitive('pictureroot_btnbrowse', x)

    def on_dialog_response(self, dialog, response, data=None):
        """
        The dialog's response signal handler.
        """
        if response == gtk.RESPONSE_OK:
            settings = self.get_params()
            valid, msg = self.check_parameters_valid(settings)
            if not valid:
                self.view.run_message_dialog(msg, gtk.MESSAGE_ERROR)
            if valid:
                ## picture root is also made available in global setting
                prefs.prefs[prefs.picture_root_pref] = settings['pictures']
                self.save_current_to_prefs()
        elif response == gtk.RESPONSE_CANCEL or \
                response == gtk.RESPONSE_DELETE_EVENT:
            if not self.compare_prefs_to_saved(self.connection_name):
                msg = _("Do you want to save your changes?")
                if self.view.run_yes_no_dialog(msg):
                    self.save_current_to_prefs()

        # system-defined GtkDialog responses are always negative, in which
        # case we want to hide it
        if response < 0:
            dialog.hide()
            #dialog.emit_stop_by_name('response')

        return response

    def on_dialog_close_or_delete(self, widget, event=None):
        self.view.get_window().hide()
        return True

    def remove_connection(self, name):
        """remove named connection, from combobox and from self
        """
        if name in self.connections:
            position = self.connection_names.index(name)
            del self.connection_names[position]
            del self.connections[name]
            self.view.combobox_remove('name_combo', position)
            self.refresh_view()
        prefs.prefs[bauble.conn_list_pref] = self.connections
        prefs.prefs.save()

    def on_remove_button_clicked(self, button, data=None):
        """
        remove the connection from connection list, this does not affect
        the database or its data
        """
        msg = (_('Are you sure you want to remove "%s"?\n\n'
                 '<i>Note: This only removes the connection to the database '
                 'and does not affect the database or its data</i>')
               % self.connection_name)

        if not self.view.run_yes_no_dialog(msg):
            return
        self.remove_connection(self.connection_name)
        if self.connection_names:
            self.view.combobox_set_active('name_combo', 0)

    def on_add_button_clicked(self, *args):
        name = self.view.run_entry_dialog(
            _("Enter a connection name"),
            self.view.get_window(),
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            (gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        if name is not '':
            self.connection_name = name
            self.connection_names.insert(0, name)
            self.connections[name] = self.get_params(new=name)
            self.view.combobox_prepend_text('name_combo', name)
            self.view.widget_set_expanded('expander', True)
            self.view.combobox_set_active('name_combo', 0)

    def save_current_to_prefs(self):
        """add current named params to saved connections
        """
        if self.connection_name is None:
            return
        if bauble.conn_list_pref not in prefs.prefs:
            prefs.prefs[bauble.conn_list_pref] = {}
        params = copy.copy(self.get_params())
        conn_dict = self.connections
        conn_dict[self.connection_name] = params
        prefs.prefs[bauble.conn_list_pref] = conn_dict
        prefs.prefs.save()

    def compare_prefs_to_saved(self, name):
        """
        name is the name of the connection in the prefs
        """
        if name is None:  # in case no name selected, can happen on first run
            return True
        conn_dict = prefs.prefs[bauble.conn_list_pref]
        if conn_dict is None or name not in conn_dict:
            return False
        stored_params = conn_dict[name]
        params = copy.copy(self.get_params())
        return params == stored_params

    def on_name_combo_changed(self, combo, data=None):
        """
        the name changed so fill in everything else
        """
        prev_connection_name = self.connection_name

        conn_dict = self.connections
        if prev_connection_name is not None and \
                prev_connection_name in self.connection_names:
            ## we are leaving some valid settings
            if prev_connection_name not in conn_dict:
                msg = _("Do you want to save %s?") % prev_connection_name
                if self.view.run_yes_no_dialog(msg):
                    self.save_current_to_prefs()
                else:
                    self.remove_connection(prev_connection_name)
            elif not self.compare_prefs_to_saved(prev_connection_name):
                msg = (_("Do you want to save your changes to %s ?")
                       % prev_connection_name)
                if self.view.run_yes_no_dialog(msg):
                    self.save_current_to_prefs()

        if self.connection_names:
            self.on_combo_changed(combo, data)  # this updates connection_name
        logger.debug("changing form >%s< to >%s<" %
                     (prev_connection_name, self.connection_name))

        if self.connection_name in conn_dict:
            ## we are retrieving connection info from the global settings
            if conn_dict[self.connection_name]['type'] not in dbtypes:
                # in case the connection type has changed or isn't supported
                # on this computer
                self.view.combobox_set_active('type_combo', -1)
            else:
                index = dbtypes.index(conn_dict[self.connection_name]
                                      ["type"])
                self.view.combobox_set_active('type_combo', index)
                self.set_params(conn_dict[self.connection_name])
        else:  # this is for new connections
            self.view.combobox_set_active('type_combo', 0)
        self.refresh_view()

    def get_passwd(self, title=_("Enter your password"), before_main=False):
        """
        Show a dialog with and entry and return the value entered.
        """
        # TODO: if self.dialog is None then ask from the command line
        # or just set dialog parent to None
        passwd = self.view.run_entry_dialog(
            title,
            self.view.get_window(),
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            (gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        return passwd

    def parameters_to_uri(self, params):
        """
        return connections paramaters as a uri
        """
        import copy
        subs = copy.copy(params)
        if params['type'].lower() == "sqlite":
            filename = params['file'].replace('\\', '/')
            uri = "sqlite:///" + filename
            return uri
        subs['type'] = params['type'].lower()
        if 'port' in params:
            template = "%(type)s://%(user)s@%(host)s:%(port)s/%(db)s"
        else:
            template = "%(type)s://%(user)s@%(host)s/%(db)s"
        if params["passwd"] is True:
            subs["passwd"] = self.get_passwd()
            if subs["passwd"]:
                template = template.replace('@', ':%(passwd)s@')
        uri = template % subs
        options = []
        if 'options' in params:
            options = '&'.join(params['options'])
            uri += '?'
            uri += options
        return uri

    @property
    def connection_uri(self):
        params = copy.copy(self.get_params())
        return self.parameters_to_uri(params)

    def check_parameters_valid(self, params):
        """
        check for errors in the connection params,
        return a pair:
        first is a boolean indicating validity;
        second is the localized error message.
        """
        if self.view.combobox_get_active_text('name_combo') == "":
            return False, _("Please choose a name for this connection")
        valid = True
        msg = None
        ## first check connection parameters, then pictures path
        if params['type'] == 'SQLite':
            filename = params['file']
            if not os.path.exists(filename):
                path, f = os.path.split(filename)
                if not os.access(path, os.R_OK):
                    valid = False
                    msg = _("Bauble does not have permission to "
                            "read the directory:\n\n%s") % path
                elif not os.access(path, os.W_OK):
                    valid = False
                    msg = _("Bauble does not have permission to "
                            "write to the directory:\n\n%s") % path
            elif not os.access(filename, os.R_OK):
                valid = False
                msg = _("Bauble does not have permission to read the "
                        "database file:\n\n%s") % filename
            elif not os.access(filename, os.W_OK):
                valid = False
                msg = _("Bauble does not have permission to "
                        "write to the database file:\n\n%s") % filename
        else:
            fields = []
            if params["user"] == "":
                valid = False
                fields.append(_("user name"))
            if params["db"] == "":
                valid = False
                fields.append(_("database name"))
            if params["host"] == "":
                valid = False
                fields.append(_("DBMS host name"))
            if not valid:
                msg = _("Current connection does not specify the fields:\n"
                        "%s\n"
                        "Please specify and try again.") % "\n".join(fields)
        if not valid:
            return valid, msg
        ## now check the params['pictures']
        # if it's a file, things are not OK
        root = params['pictures']
        thumbs = os.path.join(root, 'thumbs')
        # root should exist as a directory
        if os.path.exists(root):
            if not os.path.isdir(root):
                valid = False
                msg = _("Pictures root name occupied by non directory.")
            elif os.path.exists(thumbs):
                if not os.path.isdir(thumbs):
                    valid = False
                    msg = _("Thumbnails name occupied by non directory.")
        else:
            os.mkdir(root)
        # root should contain the thumbs directory
        if valid and not os.path.exists(thumbs):
            os.mkdir(thumbs)
        return valid, msg

    def get_params(self, new=None):
        if new is not None:
            self.dbtype = 'SQLite'
            self.use_defaults = True
        if self.dbtype == 'SQLite':
            if self.use_defaults is True:
                name = new or self.connection_name
                self.filename = os.path.join(
                    paths.user_dir(), name + '.db')
                self.pictureroot = os.path.join(
                    paths.user_dir(), name)
            result = {'file': self.filename,
                      'default': self.use_defaults,
                      'pictures': self.pictureroot}
        else:
            result = {'db': self.database,
                      'host': self.host,
                      'user': self.user,
                      'pictures': self.pictureroot,
                      'passwd': self.passwd,
                      }
        result['type'] = self.dbtype
        return result

    def set_params(self, params=None):
        if params is None:
            params = self.connections[self.connection_name]
            self.dbtype = params['type']
        if self.dbtype == 'SQLite':
            self.filename = params['file']
            self.use_defaults = params['default']
            self.pictureroot = params.get('pictures', '')
        else:
            self.database = params['db']
            self.host = params['host']
            self.user = params['user']
            self.pictureroot = params.get('pictures', '')
            self.passwd = params['passwd']
        self.refresh_view()


def start_connection_manager(default_conn=None):
    '''activate connection manager and return connection name and uri
    '''
    glade_path = os.path.join(paths.lib_dir(), "connmgr.glade")
    view = GenericEditorView(
        glade_path,
        parent=None,
        root_widget_name='main_dialog')

    cm = ConnMgrPresenter(view)
    result = cm.start()
    if result == gtk.RESPONSE_OK:
        return cm.connection_name, cm.connection_uri
    else:
        return None, None
