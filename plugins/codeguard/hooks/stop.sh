#!/bin/sh
codeguard review >&2
case $? in
  0) exit 0 ;;
  1) exit 2 ;;
  *) exit 1 ;;
esac
