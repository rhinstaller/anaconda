#!/bin/sh
# Copy over s390 config /etc/ccw.conf for anaconda before pivot
[ -e /etc/ccw.conf ] && cp /etc/ccw.conf /run/install
