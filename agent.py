#!/usr/bin/env python
"""采集器入口（从根目录运行用这个）"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent.agent import cmd_start, cmd_stop, cmd_status, cmd_analyze, cmd_detach

if __name__ == '__main__':
    cmds = {
        'start': cmd_start, 'stop': cmd_stop, 'status': cmd_status,
        'analyze': cmd_analyze, 'detach': cmd_detach,
    }
    if len(sys.argv) > 1 and sys.argv[1] in cmds:
        cmds[sys.argv[1]]()
    else:
        print('用法: python agent.py [start|stop|status|analyze]')
