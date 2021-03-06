#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# @Author: Vlad Doster <mvdoster@gmail.com>
# @Date: 2020-06-19 22:23:56
# @Last Modified by: Vlad Doster <mvdoster@gmail.com>
# @Last Modified time: 2020-06-19 23:38:21

# arch_installer.py --- dialog program that takes user input and uses it to install Arch Linux

##-> User inputs
# - [x] preinstall system checks
# - [x] select install drive
# - [x] confirm install
# - [x] select hostname
# - [x] select timezone
# - [x] select bootloader
# - [x] confirm bootloader
# - [ ] select partition sizes
# - [ ] confirm partition sizes
# - [x] run reflector
##-> Installer
# - [ ] clean partition cruft
# - [ ] create partitions
# - [ ] create partition filesystems
# - [ ] refresh arch keyring
# - [ ] generate fstab
# - [ ] install arch
# - [ ] set hostname
# - [ ] user select root password
# - [ ] enter chroot environment
# - [ ] user postinstall options
##-> Chroot
# - [ ] set timezone
# - [x] ntp sync

import inspect
import os
import subprocess
import sys
import textwrap
import time
from collections import namedtuple
from textwrap import dedent, indent

import blkinfo
import dialog
import pytz
from humanfriendly import format_size, parse_size
from tzlocal import get_localzone

from base import BaseDialog, DialogContextManager

default_debug_filename = "arch_installer.debug"
progname = os.path.basename(sys.argv[0])
progversion = "0.0.1"
version_blurb = """ \
This is free software; see the source for copying conditions. \
There is NO warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE."""

usage = """Usage: {progname} [option ...]
Program that installs Arch Linux.
Options:
      --debug                  enable logging of all dialog command lines
      --debug-file=FILE        where to write debug information (default:
                               {debug_file} in the current directory)
  -E, --debug-expand-file-opt  expand the '--file' options in the debug file
                               generated by '--debug'
      --help                   display this message and exit
      --version                output version information and exit""".format(
    progname=progname, debug_file=default_debug_filename
)

help_msg = """\
             I can hear your cry for help, and would really like to help you. However, I \
             am afraid there is not much I can do for you here; you will have to decide
             for yourself on this matter.\
             Keep in mind that you can always rely on me. \
             You have all my support, be brave!"""

dialog_unavailable = """\
             Unable to retrieve the version of the dialog-like backend.:w
             Not running cdialog?"""

term_size_warning = """\
             Your terminal has less than {0} rows or less than {1} columns;
             you may experience problems with the demo. You have been warned."""

params = {
    "debug": False,
    "debug_expand_file_opt": False,
    "debug_filename": default_debug_filename,
    "progversion": progversion,
}

tw = textwrap.TextWrapper(width=78, break_long_words=True, break_on_hyphens=True)

persistent_dlg_args = [
    "--backtitle",
    "Arch Installer",
]


def caller(parent_func):
    return " ".join(parent_func[1:]), "_".join(parent_func)


class ArchInstaller(object):
    user_input = {
        "add_swap": "",
        "bootloader": "",
        "host_name": "",
        "install_drive": "",
        "partition_scheme": "",
        "root_password": "",
        "timezone": "",
        "user_name": "",
        "user_password": "",
    }

    def __init__(self):
        self.Dlg = dialog.Dialog(dialog="dialog")
        self.d = BaseDialog(self.Dlg)
        self.d.add_persistent_args(self.Dlg.dash_escape_nf(persistent_dlg_args))
        self.dlg_dims = {"width": 0, "height": 0}
        self.max_lines, self.max_cols = self.d.maxsize(use_persistent_args=True)
        self.min_rows, self.min_cols = (24, 80)
        self.term_rows, self.term_cols, self.backend_version = self.get_term_size_and_sys_dlg_ver()

    def run(self):
        self.welcome_user()
        self.set_user_name()
        self.set_user_password()
        self.set_root_password()
        self.set_user_shell()
        self.set_drive()
        self.set_bootloader()
        self.set_hostname()
        self.set_timezone()
        self.set_partition_scheme()
        self.set_partition_sizes()
        self.start_ntp_sync()

    def setup_debug(self):
        return DialogContextManager()

    def get_term_size_and_sys_dlg_ver(self):
        backend_version = self.d.cached_backend_version
        if not backend_version:
            sys.exit(self.warning_msg(dialog_unavailable))
        term_rows, term_cols = self.d.maxsize(use_persistent_args=False)
        if term_rows < self.min_rows or term_cols < self.min_cols:
            self.warning_msg(term_size_warning.format(self.min_rows, self.min_cols))
        return (term_rows, term_cols, backend_version)

    def simple_msg(self, msg, title):
        self.d.msgbox(msg, title)

    def welcome_user(self):
        self.d.msgbox(
            """
        Hello, and welcome to the Arch Installer {0}.\n\n
        This script is being run by the Python interpreter identified as: {1}\n
        """.format(
                params["progversion"], indent(sys.version, "  ")
            ),
            title="Welcome to Arch Installer",
            **self.dlg_dims
        )

    def warning_msg(self, msg, *args):
        print(tw.fill(dedent(msg) + "\nPress Enter to continue."))
        input()

    def confirm_selection(self, selection, **kwargs):
        var, func = caller(str(inspect.stack()[1][3]).split("_"))
        msg = kwargs.get("msg", "'%s' is selected %s, continue?" % (selection, var))
        if self.d.yes_no(msg, title=("Confirm %s" % var)):
            return True
        eval("self.%s()" % func)

    def run_reflector(self):
        cmd = "Reflector"
        while True:
            if self.d.yes_no(
                ("\nRun '%s'? It helps speed up package installs" % cmd),
                title=("Speed up package downloads with %s" % cmd),
            ):
                self.d.infobox(("Running '%s'" % cmd.lower()), title=cmd)
                reflector_cmd = "reflector --latest 200 --protocol http --protocol https --sort rate --save /etc/pacman.d/mirrorlist"
                self.run_sh_cmd(reflector_cmd, cmd)
            else:
                return

    def set_bootloader(self):
        self.d.menu(
            "Select a bootloader to use",
            choices=[
                (
                    "Systemd-boot",
                    "A simple UEFI boot loader",
                    "Systemd-boot (Bootctl) is simple to configure but it can only start EFI executables such as the Linux kernel EFISTUB, UEFI Shell, GRUB, or the Windows Boot Manager.",
                ),
                (
                    "Grub2",
                    "A very powerful boot loader",
                    "GNU GRUB is a very powerful boot loader, which can load a wide variety of free operating systems, as well as proprietary operating systems with chain-loading. GRUB is designed to address the complexity of booting a personal computer.",
                ),
            ],
            title="Arch Installer",
            help_label="More info",
            help_button=True,
            help_tags=False,
            item_help=True,
            **self.dlg_dims
        )

    def input_form(self):
        _, answer = self.d.inputbox("What's your name?", init="")
        self.confirm_selection(answer)

    def set_hostname(self):
        self.input_form()

    def set_user_name(self):
        self.input_form()

    def password_form(self, user, error=""):
        while True:
            elements = [
                ("Set {}'s password".format(user), 1, 1, "", 1, 20, 12, 0),
                ("Confirm root password", 2, 1, "", 2, 20, 12, 0),
            ]
            _, fields = self.d.passwordform(
                "Enter a password for root user\n{0}".format(error),
                elements,
                title="Root password",
                insecure=True,
                **self.dlg_dims
            )
            if "" in fields:
                error = "ERROR: Password fields cant be empty."
            elif fields[0] != fields[1]:
                error = "ERROR: Passwords do not match."
            else:
                return fields[0]

    def set_user_password(self):
        user_password = self.password_form(ArchInstaller.user_input.get("user_name"))
        ArchInstaller.user_input.update({"user_password": user_password})

    def set_root_password(self):
        if self.d.yes_no("Set %s's password to be root password?", title="Root password"):
            ArchInstaller.user_input.update({"root_password": ArchInstaller.user_input.get("user_password")})
        ArchInstaller.user_input.update({"root_password": self.password_form("root")})

    def set_user_shell(self):
        while True:
            shells = [
                ("Bash", "The default login shell for most Linux distributions"),
                ("Zsh", "Zsh is an extended Bourne shell with many improvements"),
            ]
            code, shell = self.d.menu(
                "Select a system shell", menu_height=4, choices=shells, title="Shell selection", height=30
            )
            if code:
                break
        self.confirm_selection(shell)
        ArchInstaller.shell = shell

    def set_drive(self):
        Drive = namedtuple("Drive", ["name", "size", "partitions"])
        while True:
            drives = [
                Drive(
                    name=(drive.get("name")),
                    size=(format_size(int(drive.get("size")))),
                    partitions=(drive.get("children")),
                )
                for drive in blkinfo.BlkDiskInfo().get_disks()
            ]
            code, drive = self.d.menu(
                "Select a drive to install Arch on",
                menu_height=4,
                choices=[
                    (
                        drive.name,
                        "{0!r} is {1} and has {2} partitions".format(
                            drive.name, drive.size, len(drive.partitions)
                        ),
                    )
                    for drive in drives
                ],
                title="Installation drive selection",
                height=30,
            )
            if code:
                break
        self.confirm_selection(drive)
        ArchInstaller.install_drive = drive

    def set_timezone(self, usr_tz=str(get_localzone())):
        while True:
            usr_tz = str(get_localzone())
            if self.d.yes_no(
                "Set {} as system timezone?".format(usr_tz),
                no_label="Use different timezone",
                title="Timezone selection",
                **self.dlg_dims
            ):
                break
            else:
                code, usr_tz = self.d.menu(
                    "Timezone choices",
                    choices=[
                        [tz, "%s timezone" % str(tz).split("/")[0]]
                        for tz in sorted(pytz.common_timezones_set)
                    ],
                    title="Timezone selection",
                    **self.dlg_dims
                )
                if code:
                    break
        self.confirm_selection(usr_tz)
        ArchInstaller.timezone = usr_tz

    def set_partition_scheme(self):
        while True:
            sel, p_scheme = self.d.menu(
                "Select a scheme",
                menu_height=2,
                choices=[
                    ("Single root partition", "simplest and should be enough for most use cases."),
                    ("Discrete partitions", "Separates paths as a partition"),
                ],
                title="Partition schemes",
                **self.dlg_dims
            )
            if sel:
                break
        self.confirm_selection(p_scheme)
        ArchInstaller.user_input.update({"partition_scheme": p_scheme})

    def set_swap_creation(self):
        while True:
            add_swap = self.d.yes_no("Create swap partition?", title="Swap Partiton")
            break
        self.confirm_selection(add_swap, msg=("%s, create swap partition" % add_swap))
        ArchInstaller.user_input.update({"add_swap": add_swap})

    def set_partition_sizes(self):
        disk = blkinfo.BlkDiskInfo().get_disks({"name": self.user_input.get("install_drive")})[0]
        disk_size = StorageInput(disk.get("size"))
        boot, root, swap = StorageInput("250mb"), StorageInput("30gb"), StorageInput("10gb")
        home_size = StorageInput(format_size(disk_size.raw - boot.raw + root.raw + swap.raw))
        while True:
            partitions = self.d.inputmenu(
                "Edit GPT partition defaults",
                menu_height=5,
                choices=[
                    ("/boot", boot.humanized),
                    ("/", root.humanized),
                    ("/swap", swap.humanized),
                    ("/home", home_size.humanized),
                ],
                height=30,
            )

    def start_ntp_sync(self):
        ntp_cmd = "timedatectl set-ntp true"
        self.d.infobox(("Running '%s'" % ntp_cmd), title="NTP sync")
        self.run_sh_cmd(ntp_cmd, ntp_cmd)

    def run_sh_cmd(self, sh_cmd, name):
        start = time.time()
        output = subprocess.run(sh_cmd, shell=True, check=True, capture_output=False)
        total_time = round(time.time() - start, 2)
        if output.returncode == 0:
            self.d.msgbox(
                "{0!r} finished successfully in {1} seconds.".format(name, total_time),
                title="Successful {0!r} run".format(name),
                **self.dlg_dims
            )
            return True
        self.d.msgbox("{} failed to run.\n{}".format(name, output), title="{0!r} failure".format(name))


class StorageInput(object):
    def __init__(self, val):
        self.raw = parse_size(val)
        self.humanized = val
