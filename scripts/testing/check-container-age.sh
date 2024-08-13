#!/usr/bin/bash
# container image name, eg. "quay.io/rhinstaller/anaconda-ci:master"
container_name="$1"
# when is an image too old - string for `date --date=`
too_old_description="60 hours ago"

container_created=$(podman image inspect --format '{{.Created}}' "$container_name")
# dates in unix epoch seconds
ts_container_created=$(date --date="$(echo "$container_created" | awk '{print($1 " " $2)}')" +%s)
ts_too_old=$(date +%s --date="$too_old_description")

if [ "$ts_too_old" -gt "$ts_container_created" ] ; then
  echo "====================================================================="
  echo "WARNING: Container is too old!"
  echo
  echo "name:    $container_name"
  echo "created: $container_created"
  echo
  echo "To update it, run: 'podman pull $container_name'"
  echo "====================================================================="
  # give user time to see the message before it scrolls away
  sleep 5
fi
