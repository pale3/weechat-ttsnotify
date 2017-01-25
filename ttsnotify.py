# -*- coding: utf-8 -*-
#
# script: ttsnotify.py
# forked from: lnotify.py
#
# Copyright (c) 2011 Marko Rakamaric <marko.rakamaric@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

try:
    import weechat as weechat
    import subprocess # should we use pynotify instead?
    from os import environ, path, getpid
    IMPORT = True
except ImportError as message:
    print("Missing package(s) for {}: {}".format(SCRIPT_NAME, message))
    IMPORT = False

SCRIPT_NAME  = 'ttsnotify'
SCRIPT_AUTHOR = 'marko.rakamaric@gmail.com'
SCRIPT_VERSION  = '0.1.0'
SCRIPT_LICENSE = 'GPL3'
SCRIPT_DESC = 'Multiplexer aware (Screen/Tmux) libnotify script for weechat as well as plain terminal'

true = { "on": True, "off": False }

cfg = None
class config(object):
    def __init__(self):
        self.opts = {
            "enabled": (
                "on",
                "Enable or disable notifications" ),
            # "buffer_ignore": (
                # "",
                # "List of buffers which are ignored from notification system" ),
            # "on_away": (
                # "on",
                # "Should we show notifications when user status is /away" ),
            "on_highlight": (
                "on",              
                "Should we show notifications when our nick is highlighted even when channel is active" ),
            "urgency": (
                "normal",          
                "Set urgency for notified messages. E.g (low/normal/critical)" ),
            "icon": (
                "weechat",
                "Set icon for notifications. E.g (gtk-dialog-info)" ),
            "term_title": (
                "",
                "Set terminal title of weechat if you want, default match which is included is WeeChat. Use xorg-xprop tool to determine WM_NAME(STRING)" ),
            "mux_path": (
                "",
                "Set absolute muxer path where WeeChat is child process. E.g (/usr/bin/tmux)" ),
            "xdotool_path": (
                "/usr/bin/xdotool",
                "Set xdotool absolute path. E.g (/usr/bin/xdotool)"),
        }

        self.init_config()
        self.check_config()

    def init_config(self):
        version = weechat.info_get('version_number', '') or 0
        for opt, (value, desc) in self.opts.iteritems():
            if not weechat.config_is_set_plugin(opt):
                weechat.config_set_plugin(opt, value)
            if int(version) >= 0x00030500:
                # I'm not aware of way to insert default values inside of weechat [default: xxx]
                weechat.config_set_desc_plugin(opt, '%s (default: "%s")' % (desc, value)) 

    def check_config(self):
        for opt in self.opts:
            self.opts[opt] = weechat.config_get_plugin(opt)

    def __getitem__(self, key):
        return self.opts[key]

# Determine which tmux pane is active, tmux has fancy IPC to get it, 
# screen is not capable of doing it (AFAK)
# 
# return:
#   true if tmux window/pane is active 
#   false if window is inactive
def is_tmux_pane_active():

    parent_pid = getpid()
    tmux_pane_active_pid = subprocess.check_output(("tmux", "list-panes", "-F", "'#{pane_pid}'"))[1:-2]

    if int(parent_pid) == int(tmux_pane_active_pid):
        return True

    return False

# Determine if weechat window has focus
# 
# return: 
#   true: if focus matches one from cfg[term_title], or WeeChat
#   false: anything else
def term_title_has_focus(window):
    
    if window == cfg["term_title"]:
        return True
    elif "WeeChat" in window:
        return True
    
    return False

# Determine we have started weechat from any muxer
# by checking for environ variables set by muxer
def is_in_mux():

    if (environ.get('TMUX') != None):
        return "tmux"
    elif (environ.get('STY') != None):
        return "screen"
    
    return ""

# Determine if weechat channel is active
def is_channel_active(pbuffer):

    if pbuffer == weechat.current_buffer():
        return True
    else:
        return False

def handle_msg(data, pbuffer, date, tags, displayed, highlight, prefix, message):

    if not (true[cfg["enabled"]] or displayed):
        return weechat.WEECHAT_RC_OK

    # if there is no X available, no libnotify is triggered
    if environ.get('DISPLAY') == None:
        return weechat.WEECHAT_RC_OK
    
    if not path.isfile(cfg["xdotool_path"]):
        return weechat.WEECHAT_RC_OK

    buffer_type = weechat.buffer_get_string(pbuffer, "localvar_type")
    if not (buffer_type == "private" or buffer_type == "channel" and highlight):
        return weechat.WEECHAT_RC_OK

    buffer_name = weechat.buffer_get_string(pbuffer, "short_name")
    # if cfg["buffer_ignore"] in buffer_name:
        # return weechat.WEECHAT_RC_OK

    # if highlight is on, dont check if there is active window, just notify
    highlight = bool(highlight) and cfg["on_highlight"]
    if highlight:
        return notify(buffer_name + ":", message)       
    
    my_nickname = "nick_" + weechat.buffer_get_string(pbuffer, "localvar_nick")
    if my_nickname in tags:
        return weechat.WEECHAT_RC_OK

    # away = weechat.buffer_get_string(pbuffer, "localvar_away")
    # if away and not true[cfg['on_away']]:
        # return weechat.WEECHAT_RC_OK
    
    mux = is_in_mux()
    window_name = subprocess.check_output(["xdotool", "getwindowfocus", "getwindowname"]).strip()
    if mux == "screen":
       
        if not term_title_has_focus(window_name):
                return notify(buffer_name + ":", message)       
        else:
            if not is_channel_active(pbuffer):
                return notify(buffer_name + ":", message)       
    
    elif mux == "tmux":

        if not term_title_has_focus(window_name):
                return notify(buffer_name + ":", message)       
        else:
            if not is_tmux_pane_active():
                return notify(buffer_name + ":", message)       
            elif is_tmux_pane_active() and not is_channel_active(pbuffer):
                return notify(buffer_name + ":", message)       
    else:

        if not term_title_has_focus(window_name):
            return notify(buffer_name + ":", message)       
        elif not is_channel_active(pbuffer):
            return notify(buffer_name + ":", message)       
    
    return weechat.WEECHAT_RC_OK

def process_cb(data, command, return_code, out, err):

    if return_code == weechat.WEECHAT_HOOK_PROCESS_ERROR:
        weechat.prnt("", "Error with command '%s'" % command)

    elif return_code != 0:
        weechat.prnt("", "return_code = %d" % return_code)
        weechat.prnt("", "notify-send has an error")

    return weechat.WEECHAT_RC_OK

def notify(origin, message):

    weechat.hook_process_hashtable("notify-send",
        { "arg1": "-i", "arg2": cfg["icon"],
          "arg3": "-a", "arg4": "WeeChat",
          "arg5": "-u", "arg6": cfg["urgency"],
          "arg7": origin, "arg8": message },
        20000, "process_cb", "")

    return weechat.WEECHAT_RC_OK

if __name__ == "__main__" and IMPORT:

    weechat.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION, SCRIPT_LICENSE,
        SCRIPT_DESC, "", "")
    
    cfg = config()
    weechat.hook_print("", "notify_message", "", 1, "handle_msg", "")
    weechat.hook_print("", "notify_private", "", 1, "handle_msg", "private")
