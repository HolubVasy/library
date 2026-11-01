# The VPS now stores artifacts by hash (objects/<aa>/<sha256>), not by source path.
# Uploading and the layer 1-2 load are one step: db\sync_cold.py. This wrapper only runs it.
python -I "$PSScriptRoot\db\sync_cold.py" @args
