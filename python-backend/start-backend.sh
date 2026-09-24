#!/bin/bash
# Daemon launcher for ZeniTrade Python backend that survives parent shell exit.
# Uses double-fork + setsid + nohup to fully detach from the controlling terminal.
cd /home/z/my-project/python-backend
exec setsid .venv/bin/python main.py >> /tmp/zenitrade-backend.log 2>&1 < /dev/null
