#!/bin/bash -e

autoreconf -vfi
( cd widgets && ./autogen.sh )
