#!/bin/sh
# One more round once after.sh is done: picks up what the first round skipped because files were not uploaded yet
# and what the format pass missed when dict.format ran out of ids. Everything is re-runnable.
# Lives on the VPS at /root/archive_extractor/after_again.sh; start with: nohup ./after_again.sh > after_again.log 2>&1 &
cd /root/archive_extractor
while pgrep -f 'sh ./after.sh' >/dev/null; do sleep 60; done
./after.sh
