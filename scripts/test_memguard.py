"""Run a command in its own process group; sample total RSS of the tree every
second; kill the whole group if it exceeds the limit. Logs peak + a timeline.
Usage: memguard.py LIMIT_MB LOGFILE -- cmd args...
"""
import os, signal, subprocess, sys, time
import psutil

limit_mb, log = int(sys.argv[1]), sys.argv[2]
cmd = sys.argv[sys.argv.index("--") + 1:]
proc = subprocess.Popen(cmd, start_new_session=True)
root = psutil.Process(proc.pid)
peak, t0, killed = 0, time.time(), False
with open(log, "w") as out:
    while proc.poll() is None:
        try:
            procs = [root] + root.children(recursive=True)
            rss = sum(p.memory_info().rss for p in procs if p.is_running()) / 2**20
        except psutil.Error:
            rss = 0
        peak = max(peak, rss)
        out.write(f"{time.time()-t0:7.1f}s rss={rss:8.0f}MB procs={len(procs)}\n"); out.flush()
        if rss > limit_mb:
            biggest = max(procs, key=lambda p: p.memory_info().rss)
            subprocess.run([os.path.expanduser("~/.local/bin/py-spy"), "dump", "--pid",
                            str(biggest.pid)], stdout=open(log + ".pyspy", "w"),
                           stderr=subprocess.STDOUT, timeout=30)
            os.killpg(proc.pid, signal.SIGKILL); killed = True
            out.write(f"KILLED: {rss:.0f}MB > {limit_mb}MB\n"); break
        time.sleep(1)
    out.write(f"PEAK={peak:.0f}MB killed={killed} exit={proc.poll()}\n")
print(f"peak={peak:.0f}MB killed={killed} exit={proc.wait()}")
