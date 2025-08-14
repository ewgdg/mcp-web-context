#!/usr/bin/env python3
import subprocess
import sys
import os
from pathlib import Path

# Simple tray application for terminal button
try:
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import Gtk, AppIndicator3, GObject
except ImportError:
    print("Installing required packages...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PyGObject"], check=True)
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import Gtk, AppIndicator3, GObject

class TerminalTray:
    def __init__(self):
        self.indicator = AppIndicator3.Indicator.new(
            "terminal-tray",
            "utilities-terminal",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_menu(self.create_menu())

    def create_menu(self):
        menu = Gtk.Menu()
        
        # Terminal item
        terminal_item = Gtk.MenuItem(label="Open Terminal")
        terminal_item.connect("activate", self.open_terminal)
        menu.append(terminal_item)
        
        # Separator
        separator = Gtk.SeparatorMenuItem()
        menu.append(separator)
        
        # Quit item
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self.quit)
        menu.append(quit_item)
        
        menu.show_all()
        return menu

    def open_terminal(self, widget):
        subprocess.Popen(["alacritty"])

    def quit(self, widget):
        Gtk.main_quit()

if __name__ == "__main__":
    tray = TerminalTray()
    Gtk.main()