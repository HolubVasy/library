#!/bin/sh
# Full level 3 run, cheap passes first; images (OCR) are run separately. Re-runnable: done work is skipped.
# Lives on the VPS at /root/archive_extractor/run_all.sh; start with: nohup ./run_all.sh > run_all.log 2>&1 &
cd /root/archive_extractor
for step in "format" "meta" "content --kind letters" "rtf" "content --kind documents" "content --kind text" "content --kind other"; do
  echo "=== $(date -Is) $step"
  ./run.sh $step 2>&1 | tail -n 3
done
echo "=== $(date -Is) done"
