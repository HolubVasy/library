"""Shared access to the archive on the VPS: commands over ssh, DB queries as archive_app, and the encrypted store.

The store is reached through an ssh tunnel to archive_files, which decrypts and encrypts on the fly;
its upload password is read from the VPS for the run only and never written on this PC.
"""
import contextlib, csv, glob, io, os, subprocess, sys, time

VPS = 'jobsearch-vps'
PSQL = '/root/archive_app/psql.sh'


def ssh(cmd, stdin=None):
    # keep-alives turn a silently dropped connection into an error instead of an endless wait
    r = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ServerAliveInterval=30', '-o', 'ServerAliveCountMax=4',
                        VPS, cmd], input=stdin, capture_output=True,
                       text=True, encoding='utf-8')
    if r.returncode:
        sys.exit(f'VPS command failed: {cmd}\n{r.stderr[-1500:]}')
    return r.stdout


def query(sql):
    return list(csv.reader(io.StringIO(ssh(f'{PSQL} -At', f'copy ({sql}) to stdout with csv;'))))


def rclone_exe():
    found = glob.glob(os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\WinGet\Packages\**\rclone.exe'), recursive=True)
    if not found:
        sys.exit('rclone.exe not found')
    return found[0]


@contextlib.contextmanager
def store():
    """Yields (rclone.exe, remote prefix) for the decrypted view of the store while an ssh tunnel is open."""
    exe = rclone_exe()
    pw = ssh("grep '^RCLONE_PASS=' /root/archive_files/.env | cut -d= -f2").strip()
    obscured = subprocess.run([exe, 'obscure', pw], capture_output=True, text=True).stdout.strip()
    del pw
    tunnel = subprocess.Popen(['ssh', '-N', '-o', 'ExitOnForwardFailure=yes', '-o', 'ServerAliveInterval=30',
                               '-L', '2022:127.0.0.1:2022', VPS], stderr=subprocess.DEVNULL)
    time.sleep(4)
    try:
        yield exe, f':sftp,host=127.0.0.1,port=2022,user=upload,pass={obscured}:'
    finally:
        tunnel.terminate()
