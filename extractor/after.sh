#!/bin/sh
# Second round, unattended: waits for the running passes, then takes everything still without a result
# (artifacts added meanwhile, e.g. unpacked archives), re-reads lost Cyrillic from RTF, and marks noise
# with the current rules version. Every step is re-runnable and skips done work. Images (OCR) are not here.
# Lives on the VPS at /root/archive_extractor/after.sh; start with: nohup ./after.sh > after.log 2>&1 &
cd /root/archive_extractor
while pgrep -f run_all.sh >/dev/null || pgrep -f 'extract.py content' >/dev/null; do sleep 60; done
for step in "format" "meta" "content --kind letters" "rtf" "content --kind documents" "content --kind text" "content --kind other"; do
  echo "=== $(date -Is) $step"
  ./run.sh $step 2>&1 | tail -n 3
done
echo "=== $(date -Is) noise rules"
/root/archive_app/psql.sh -v code="$(cat /root/archive_app/work/noise.b64)" -v version=9c2b0d5d8a1e -f /work/noise_rules.sql
echo "=== $(date -Is) done"
