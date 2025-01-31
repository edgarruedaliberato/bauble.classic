# -*- coding: utf-8 -*-
#
# Copyright (c) 2005,2006,2007,2008,2009 Brett Adams <brett@belizebotanic.org>
# Copyright (c) 2012-2015 Mario Frasca <mario@anche.no>
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

"""
The top level module for Bauble.
"""

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
consoleLevel = logging.INFO

import imp
import os
import sys
import bauble.paths as paths

from bauble.version import version
version_tuple = tuple(version.split('.'))

from bauble.i18n import _


def pb_set_fraction(fraction):
    """set progressbar fraction safely

    provides a safe way to handle the progress bar if the gui isn't started,
    we use this in the tests where there is no gui
    """
    if gui is not None and gui.progressbar is not None:
        gui.progressbar.set_fraction(fraction)


def main_is_frozen():
    """
    Return True if we are running in a py2exe environment, else
    return False
    """
    return (hasattr(sys, "frozen") or  # new py2exe
            hasattr(sys, "importers") or  # old py2exe
            imp.is_frozen("__main__"))  # tools/freeze


if main_is_frozen():  # main is frozen
    # put library.zip first in the path when using py2exe so libxml2
    # gets imported correctly,
    zipfile = sys.path[-1]
    sys.path.insert(0, zipfile)
    # put the bundled gtk at the beginning of the path to make it the
    # preferred version
    os.environ['PATH'] = '%s%s%s%s%s%s' \
        % (os.pathsep, os.path.join(paths.main_dir(), 'gtk', 'bin'),
           os.pathsep, os.path.join(paths.main_dir(), 'gtk', 'lib'),
           os.pathsep, os.environ['PATH'])


# if not hasattr(gtk.Widget, 'set_tooltip_markup'):
#     msg = _('Bauble requires GTK+ version 2.12 or greater')
#     utils.message_dialog(msg, gtk.MESSAGE_ERROR)
#     sys.exit(1)

# make sure we look in the lib path for modules
sys.path.append(paths.lib_dir())

#if False:
#    sys.stderr.write('sys.path: %s\n' % sys.path)
#    sys.stderr.write('PATH: %s\n' % os.environ['PATH'])


# set SQLAlchemy logging level
import logging
logging.getLogger('sqlalchemy').setLevel(logging.WARNING)

gui = None
"""bauble.gui is the instance :class:`bauble.ui.GUI`
"""

default_icon = None
"""The default icon.
"""

conn_name = None
"""The name of the current connection.
"""

import traceback
import bauble.error as err


def save_state():
    """
    Save the gui state and preferences.
    """
    from bauble.prefs import prefs
    # in case we quit before the gui is created
    if gui is not None:
        gui.save_state()
    prefs.save()


def quit():
    """
    Stop all tasks and quit Bauble.
    """
    import gtk
    import bauble.utils as utils
    try:
        import bauble.task as task
    except Exception, e:
        logger.error('bauble.quit(): %s' % utils.utf8(e))
    else:
        task.kill()
    try:
        save_state()
        gtk.main_quit()
    except RuntimeError, e:
        # in case main_quit is called before main, e.g. before
        # bauble.main() is called
        sys.exit(1)


last_handler = None


def command_handler(cmd, arg):
    """
    Call a command handler.

    :param cmd: The name of the command to call
    :type cmd: str

    :param arg: The arg to pass to the command handler
    :type arg: list
    """
    logger.debug('entering ui.command_handler %s %s' % (cmd, arg))
    import gtk
    import bauble.utils as utils
    import bauble.pluginmgr as pluginmgr
    global last_handler
    handler_cls = None
    try:
        handler_cls = pluginmgr.commands[cmd]
    except KeyError, e:
        if cmd is None:
            utils.message_dialog(_('No default handler registered'))
        else:
            utils.message_dialog(_('No command handler for %s') % cmd)
            return

    if not isinstance(last_handler, handler_cls):
        last_handler = handler_cls()
    handler_view = last_handler.get_view()
    old_view = gui.get_view()
    if type(old_view) != type(handler_view) and handler_view:
        # remove the accel_group from the window if the previous view
        # had one
        if hasattr(old_view, 'accel_group'):
            gui.window.remove_accel_group(old_view.accel_group)
        # add the new view, and its accel_group if it has one
        gui.set_view(handler_view)
        if hasattr(handler_view, 'accel_group'):
            gui.window.add_accel_group(handler_view.accel_group)
    try:
        last_handler(cmd, arg)
    except Exception, e:
        msg = utils.xml_safe(e)
        logger.error('bauble.command_handler(): %s' % msg)
        utils.message_details_dialog(
            msg, traceback.format_exc(), gtk.MESSAGE_ERROR)


conn_default_pref = "conn.default"
conn_list_pref = "conn.list"


def newer_version_on_github(input_stream):
    """is there a new patch on github for this production line

    if the remote version is higher than the running one, return
    something evaluating to True (possibly the remote version string).
    otherwise, return something evaluating to False
    """

    try:
        version_lines = input_stream.read().split('\n')
        valid_lines = [i for i in version_lines
                       if not i.startswith('#') and i.strip()]
        if len(valid_lines) == 1:
            try:
                github_version = eval('"' + valid_lines[0].split('"')[1] + '"')
            except:
                logger.warning("can't parse github version.")
                return False
            github_patch = github_version.split('.')[2]
            if int(github_patch) > int(version_tuple[2]):
                return github_version
            if int(github_patch) < int(version_tuple[2]):
                logger.info("running unreleased version")
    except TypeError:
        logger.warning('TypeError while reading github stream')
    except IndexError:
        logger.warning('incorrect format for github version')
    except ValueError:
        logger.warning('incorrect format for github version')
    return False


def check_and_notify_new_version():
    ## check whether there's a newer version on github.  this is executed in
    ## a different thread, which does nothing or terminates the program.
    version_on_github = (
        'https://raw.githubusercontent.com/Bauble/bauble' +
        '.classic/bauble-%s.%s/bauble/version.py') % version_tuple[:2]
    try:
        import urllib2
        import ssl
        import gtk
        github_version_stream = urllib2.urlopen(
            version_on_github, timeout=5)
        remote = newer_version_on_github(github_version_stream)
        if remote:
            md = gtk.MessageDialog(
                None, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_INFO,
                gtk.BUTTONS_OK_CANCEL,
                _("new remote version available.\n\n"
                  "remote version: %(1)s,\n"
                  "running version: %(2)s.\n\n"
                  "Cancel to stop and upgrade;\n"
                  "OK to continue.") %
                {'1': remote,
                 '2': version})
            response = md.run()
            md.destroy()
            if response != gtk.RESPONSE_OK:
                exit(0)
    except urllib2.URLError:
        logger.info('connection is slow or down')
        pass
    except ssl.SSLError, e:
        logger.info('SSLError %s while checking for newer version' % e)
        pass
    except urllib2.HTTPError:
        logger.info('HTTPError while checking for newer version')
        pass
    except Exception, e:
        logger.warning('unhandled %s(%s) while checking for newer version'
                       % type(e), e)
        pass


def main(uri=None):
    """
    Run the main Bauble application.

    :param uri:  the URI of the database to connect to.  For more information
                 about database URIs see `<http://www.sqlalchemy.org/docs/05/dbengine.html#create-engine-url-arguments>`_

    :type uri: str
    """
    # TODO: it would be nice to show a Tk dialog here saying we can't
    # import gtk...but then we would have to include all of the Tk libs in
    # with the win32 batteries-included installer
    try:
        import gtk
        import gobject
    except ImportError, e:
        print _('** Error: could not import gtk and/or gobject')
        print e
        if sys.platform == 'win32':
            print _('Please make sure that GTK_ROOT\\bin is in your PATH.')
        sys.exit(1)

    # create the user directory
    if not os.path.exists(paths.user_dir()):
        os.makedirs(paths.user_dir())

    # add console root handler, and file root handler, set it at the logging
    # level specified by BAUBLE_LOGGING, or at INFO level.
    filename = os.path.join(paths.user_dir(), 'bauble.log')
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fileHandler = logging.FileHandler(filename, 'w+')
    logging.getLogger().addHandler(fileHandler)
    consoleHandler = logging.StreamHandler()
    logging.getLogger().addHandler(consoleHandler)
    fileHandler.setFormatter(formatter)
    consoleHandler.setFormatter(formatter)
    fileHandler.setLevel(logging.DEBUG)
    consoleHandler.setLevel(consoleLevel)

    try:
        # no raven.conf.setup_logging: just standard Python logging
        from raven import Client
        from raven.handlers.logging import SentryHandler
        sentry_client = Client('https://59105d22a4ad49158796088c26bf8e4c:'
                               '00268114ed47460b94ce2b1b0b2a4a20@'
                               'app.getsentry.com/45704')
        handler = SentryHandler(sentry_client)
        logging.getLogger().addHandler(handler)
        handler.setLevel(logging.WARNING)
    except:
        logger.warning("can't configure sentry client")

    import gtk.gdk
    import pygtk
    if not main_is_frozen():
        pygtk.require("2.0")

    display = gtk.gdk.display_get_default()
    if display is None:
        print _("**Error: Bauble must be run in a windowed environment.")
        sys.exit(1)

    import bauble.pluginmgr as pluginmgr
    from bauble.prefs import prefs
    import bauble.utils as utils

    # initialize threading
    gobject.threads_init()

    try:
        import bauble.db as db
    except Exception, e:
        utils.message_dialog(utils.xml_safe(e), gtk.MESSAGE_ERROR)
        sys.exit(1)

    # declare module level variables
    global gui, default_icon, conn_name

    default_icon = os.path.join(paths.lib_dir(), "images", "icon.svg")

    # intialize the user preferences
    prefs.init()

    gobject.idle_add(check_and_notify_new_version)

    open_exc = None
    # open default database
    if uri is None:
        from bauble.connmgr import start_connection_manager
        while True:
            if not uri or not conn_name:
                conn_name, uri = start_connection_manager()
                if conn_name is None:
                    quit()
            try:
                if db.open(uri, True, True):
                    prefs[conn_default_pref] = conn_name
                    break
                else:
                    uri = conn_name = None
            except err.VersionError, e:
                logger.warning("%s(%s)" % (type(e), e))
                db.open(uri, False)
                break
            except (err.EmptyDatabaseError, err.MetaTableError,
                    err.VersionError, err.TimestampError,
                    err.RegistryError), e:
                logger.info("%s(%s)" % (type(e), e))
                open_exc = e
                # reopen without verification so that db.Session and
                # db.engine, db.metadata will be bound to an engine
                db.open(uri, False)
                break
            except err.DatabaseError, e:
                logger.debug("%s(%s)" % (type(e), e))
                # traceback.format_exc()
                open_exc = e
                # break
            except Exception, e:
                msg = _("Could not open connection.\n\n%s") % \
                    utils.xml_safe(repr(e))
                utils.message_details_dialog(msg, traceback.format_exc(),
                                             gtk.MESSAGE_ERROR)
                uri = None
    else:
        db.open(uri, True, True)

    # load the plugins
    pluginmgr.load()

    # save any changes made in the conn manager before anything else has
    # chance to crash
    prefs.save()

    # set the default command handler
    import bauble.view as view
    pluginmgr.register_command(view.DefaultCommandHandler)

    # now that we have a connection create the gui, start before the plugins
    # are initialized in case they have to do anything like add a menu
    import bauble.ui as ui
    gui = ui.GUI()

    def _post_loop():
        gtk.gdk.threads_enter()
        try:
            if isinstance(open_exc, err.DatabaseError):
                msg = _('Would you like to create a new Bauble database at '
                        'the current connection?\n\n<i>Warning: If there is '
                        'already a database at this connection any existing '
                        'data will be destroyed!</i>')
                if utils.yes_no_dialog(msg, yes_delay=2):
                    try:
                        db.create()
                        # db.create() creates all tables registered with
                        # the default metadata so the pluginmgr should be
                        # loaded after the database is created so we don't
                        # inadvertantly create tables from the plugins
                        pluginmgr.init()
                        # set the default connection
                        prefs[conn_default_pref] = conn_name
                    except Exception, e:
                        utils.message_details_dialog(utils.xml_safe(e),
                                                     traceback.format_exc(),
                                                     gtk.MESSAGE_ERROR)
                        logger.error("%s(%s)" % (type(e), e))
            else:
                pluginmgr.init()
        except Exception, e:
            logger.warning("%s\n%s(%s)"
                           % (traceback.format_exc(), type(e), e))
            utils.message_dialog(utils.utf8(e), gtk.MESSAGE_WARNING)
        gtk.gdk.threads_leave()

    gobject.idle_add(_post_loop)

    gui.show()
    gtk.threads_enter()
    gtk.main()
    gtk.threads_leave()
