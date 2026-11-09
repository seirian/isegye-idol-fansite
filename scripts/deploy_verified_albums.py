#!/usr/bin/env python3
"""Bounded pipelined transport for the unchanged main-only access deployer.
All path, owner, host-key, immutable-file, read-back and activation checks remain.
"""
import stat
import sys
import time
import inour_sftp as d

class VerifiedTransferRemote(d.Remote):
    def read(self, path):
        info = self.info(path)
        if info is None:
            return None
        d.require(stat.S_ISREG(info.st_mode) and info.st_uid == d.UID and info.st_size <= 9 * 1024 * 1024,
                  'Unsafe file type/owner/size')
        with self.s.open(path, 'rb') as handle:
            if info.st_size >= 65536:
                # Limit outstanding reads rather than scheduling an unbounded queue.
                handle.prefetch(file_size=info.st_size, max_concurrent_requests=16)
            raw = handle.read(9 * 1024 * 1024)
        d.require(len(raw) == info.st_size, 'Remote file changed during read')
        return raw

    def new(self, path, data):
        self.parents(path)
        d.require(self.info(path) is None, 'Refusing existing file')
        started = time.monotonic()
        with self.s.open(path, 'wx') as handle:
            # Errors deferred by pipelining are raised by close, before activation.
            handle.set_pipelined(True)
            handle.write(data)
            handle.flush()
        self.s.chmod(path, 0o644)
        d.require(self.read(path) == data, 'Upload verification failed')
        print('Verified staged file:', len(data), 'bytes;', round(time.monotonic()-started, 2), 'seconds', flush=True)

def main():
    import deploy_google_access as access
    # Transport substitution only. All original main/environment/owner/auth guards run.
    access.d.Remote = VerifiedTransferRemote
    return access.main()

if __name__ == '__main__':
    sys.exit(main())
