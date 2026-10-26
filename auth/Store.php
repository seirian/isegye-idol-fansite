<?php
declare(strict_types=1);
namespace Isegye\Access;

/** A small, private, atomic account store; the hosting PHP has no SQLite driver.
 * Persisted account fields: keyed Google-sub digest and role, never raw claims.
 * One shared lock coordinates readers/writers across atomic file replacements.
 */
final class Store
{
    private const MAX_BYTES = 2097152;
    private const MAX_ACCOUNTS = 10000;
    public function __construct(private string $directory, private string $key, private string $adminEmailDigest)
    {
        if (strlen($key) !== 32 || !preg_match('/\A[a-f0-9]{64}\z/D', $adminEmailDigest)) {
            throw new \RuntimeException('Invalid identity configuration');
        }
        if (!is_dir($directory) || is_link($directory)) throw new \RuntimeException('Private directory missing');
    }
    public static function emailDigest(string $email, string $key): string
    {
        return hash_hmac('sha256', "admin-email\0" . hash('sha256', strtolower($email)), $key);
    }
    public function accountKey(string $subject): string
    {
        if (!preg_match('/\A[A-Za-z0-9_-]{1,255}\z/D', $subject)) throw new \RuntimeException('Invalid subject');
        return hash_hmac('sha256', "google-sub\0" . $subject, $this->key);
    }
    private function lock(int $mode)
    {
        $path = $this->directory . '/accounts.lock';
        if (!is_file($path) || is_link($path) || (fileperms($path) & 0777) !== 0600) {
            throw new \RuntimeException('Account lock not provisioned');
        }
        $lock = fopen($path, 'r+');
        if (!$lock || !flock($lock, $mode)) throw new \RuntimeException('Account lock unavailable');
        return $lock;
    }
    private function load(): array
    {
        $path = $this->directory . '/accounts.json';
        clearstatcache(true, $path);
        if (!is_file($path) || is_link($path) || filesize($path) > self::MAX_BYTES || (fileperms($path) & 0777) !== 0600) {
            throw new \RuntimeException('Account store unavailable');
        }
        $state = json_decode(file_get_contents($path), true, 16, JSON_THROW_ON_ERROR);
        if (!is_array($state) || array_keys($state) !== ['schema', 'administrator', 'accounts'] || $state['schema'] !== 1 || !is_array($state['accounts'])) {
            throw new \RuntimeException('Invalid account state');
        }
        $admins = [];
        foreach ($state['accounts'] as $id => $role) {
            if (!is_string($id) || !preg_match('/\A[a-f0-9]{64}\z/D', $id) || !in_array($role, ['member', 'admin'], true)) {
                throw new \RuntimeException('Invalid account record');
            }
            if ($role === 'admin') $admins[] = $id;
        }
        if (($state['administrator'] === null && $admins !== []) ||
            ($state['administrator'] !== null && $admins !== [$state['administrator']])) {
            throw new \RuntimeException('Administrator state inconsistent');
        }
        return $state;
    }
    private function save(array $state): void
    {
        $json = json_encode($state, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . "\n";
        if (strlen($json) > self::MAX_BYTES) throw new \RuntimeException('Account capacity exceeded');
        $temp = $this->directory . '/accounts.tmp-' . bin2hex(random_bytes(16));
        $handle = fopen($temp, 'x+b');
        if (!$handle) throw new \RuntimeException('Account write unavailable');
        try {
            chmod($temp, 0600);
            $written = 0;
            while ($written < strlen($json)) {
                $n = fwrite($handle, substr($json, $written));
                if (!$n) throw new \RuntimeException('Account write incomplete');
                $written += $n;
            }
            if (!fflush($handle) || !fsync($handle)) throw new \RuntimeException('Account flush failed');
            fclose($handle); $handle = null;
            if (!rename($temp, $this->directory . '/accounts.json')) throw new \RuntimeException('Account commit failed');
        } finally {
            if (is_resource($handle)) fclose($handle);
            if (is_file($temp)) unlink($temp);
        }
    }
    /** Call only with the server-verified claims returned by GoogleVerifier. */
    public function registerVerified(string $subject, string $verifiedEmail): array
    {
        $id = $this->accountKey($subject);
        $matchesAdmin = hash_equals($this->adminEmailDigest, self::emailDigest($verifiedEmail, $this->key));
        $lock = $this->lock(LOCK_EX);
        try {
            $state = $this->load();
            $changed = false;
            if (!isset($state['accounts'][$id])) {
                if (count($state['accounts']) >= self::MAX_ACCOUNTS) throw new \RuntimeException('Account capacity reached');
                $state['accounts'][$id] = 'member'; $changed = true;
            }
            // The first arbitrary visitor can NEVER claim ownership.
            // Binding is permanent once the one approved Google subject has signed in.
            $activated = false;
            if ($matchesAdmin && $state['administrator'] === null) {
                $state['administrator'] = $id;
                $state['accounts'][$id] = 'admin';
                $changed = true; $activated = true;
            }
            if ($changed) $this->save($state);
            return ['key' => $id, 'role' => $state['accounts'][$id], 'activated' => $activated];
        } finally { flock($lock, LOCK_UN); fclose($lock); }
    }
    public function access(?string $id): array
    {
        $lock = $this->lock(LOCK_SH);
        try {
            $state = $this->load();
            $role = $id !== null ? ($state['accounts'][$id] ?? null) : null;
            $maintenance = $state['administrator'] !== null;
            return ['role' => $role, 'maintenance' => $maintenance,
                    'allowed' => !$maintenance || ($role === 'admin' && $id === $state['administrator'])];
        } finally { flock($lock, LOCK_UN); fclose($lock); }
    }
}
