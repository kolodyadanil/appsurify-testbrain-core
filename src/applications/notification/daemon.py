# -*- coding: utf-8 -*-
import atexit
import os
import sys
import time
from signal import SIGTERM
from django.db import connection, transaction
from django.conf import settings
from .utils import *


PIDFILE = os.path.join(settings.BASE_DIR, 'notification.pid')


class Daemon(object):
    """
        A generic daemon class.
        Usage: subclass the Daemon class and override the run() method
    """

    startmsg = "started with pid %s"

    def __init__(self, pidfile=PIDFILE, stdin='/dev/null', stdout='/dev/stdout', stderr='/dev/stderr'):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile

    def daemonize(self):
        """
        do the UNIX double-fork magic, see Stevens' "Advanced
        Programming in the UNIX Environment" for details (ISBN 0201563177)
        http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
        """
        try:
            pid = os.fork()
            if pid > 0:
                # exit first parent
                sys.exit(0)
        except OSError as e:
            sys.stderr.write("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)

        # decouple from parent environment
        os.chdir("/")
        os.setsid()
        os.umask(0)

        # do second fork
        try:
            pid = os.fork()
            if pid > 0:
                # exit from second parent
                sys.exit(0)
        except OSError as e:
            sys.stderr.write("fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)

        # redirect standard file descriptors
        si = file(self.stdin, 'r')
        so = file(self.stdout, 'a+')
        se = file(self.stderr, 'a+', 0)

        pid = str(os.getpid())

        # sys.stdout.write("\n%s\n" % self.startmsg % pid)
        # sys.stdout.flush()

        if self.pidfile:
            file(self.pidfile, 'w+').write("%s\n" % pid)

        atexit.register(self.delpid)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

    def delpid(self):
        try:
            os.remove(self.pidfile)
        except OSError:
            pass

    def start(self):
        """
        Start the daemon
        """
        # Check for a pidfile to see if the daemon already runs

        try:
            pf = file(self.pidfile, 'r')
            pf_val = pf.read().strip()

            if pf_val == '':
                pid = 0
            else:
                pid = int(pf_val)

            pf.close()
        except IOError:
            pid = None
        except SystemExit:
            pid = None

        if pid:
            message = "pidfile %s already exist. Daemon already running?\n"
            sys.stderr.write(message % self.pidfile)
            sys.exit(1)

        # Start the daemon

        self.daemonize()
        self.run()

    def get_pid(self):
        try:
            pf = file(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None
        except SystemExit:
            pid = None
        return pid

    def stop(self):
        """
        Stop the daemon
        """
        # Get the pid from the pidfile
        try:
            pf = file(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None

        if not pid:
            message = "pidfile %s does not exist. Daemon not running?\n"
            sys.stderr.write(message % self.pidfile)
            return  # not an error in a restart

        # Try killing the daemon process
        try:
            while 1:
                os.kill(pid, SIGTERM)
                time.sleep(0.1)
        except OSError as err:
            err = str(err)
            if err.find("No such process") > 0:
                if os.path.exists(self.pidfile):
                    os.remove(self.pidfile)
                else:
                    str(err)
                    sys.exit(1)

    def restart(self):
        """
        Restart the daemon
        """
        self.stop()
        self.start()

    def status(self):
        return self.get_pid()

    def run(self):
        """
        You should override this method when you subclass Daemon. It will be called after the process has been
        daemonized by start() or restart().
        """


class NotificationDaemon(Daemon):

    def run(self):
        try:
            # TODO: Special obligitary close connection created by parent process
            connection.close()
        except Exception as e:
            # logging.exception('An error occured when running notification daemon')
            pass
        while True:
            try:

                check_updates_one_off()
                check_updates_immediately()
                check_updates_daily()
                check_updates_weekly()
                check_updates_fortnightly()

            except Exception as e:
                # logging.debug(e)
                pass

            time.sleep(120)

    def cron(self):

        try:
            pf = file(self.pidfile, 'r')
            pf_val = pf.read().strip()

            if pf_val == '':
                pid = 0
            else:
                pid = int(pf_val)

            pf.close()
        except IOError:
            pid = None
        except SystemExit:
            pid = None

        if pid:
            message = "pidfile %s already exist. Daemon already running?\n" % self.pidfile
            raise Exception(message)

        if self.pidfile:
            pid = os.getpid()
            file(self.pidfile, 'w+').write("%s\n" % pid)

        try:
            # TODO: Special obligitary close connection created by parent process
            connection.close()
        except Exception as e:
            # logging.exception('An error occured when running notification daemon')
            pass

        check_updates_one_off()
        check_updates_immediately()
        check_updates_daily()
        check_updates_weekly()
        check_updates_fortnightly()

        if os.path.exists(self.pidfile):
            os.remove(self.pidfile)
