<?php
declare(strict_types=1);
namespace Isegye\Access;

/** Administrator-only, read-only projection. Never invokes GitHub or a batch. */
final class BatchMonitor
{
    private static function reply(int $status, string $body, string $type = 'text/plain; charset=utf-8'): void
    {
        http_response_code($status);
        header('Content-Type: '.$type);
        if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'HEAD') echo $body;
    }
    public static function serve(string $root, string $path, array $access): void
    {
        header('Cache-Control: private, no-store, max-age=0');
        header('Vary: Cookie');
        header('X-Robots-Tag: noindex, nofollow, noarchive');
        header('X-Content-Type-Options: nosniff');
        header('Referrer-Policy: no-referrer');
        header("Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; form-action 'none'");
        if (($access['role'] ?? null) !== 'admin' || ($access['allowed'] ?? false) !== true) {
            self::reply(($access['role'] ?? null) === null ? 401 : 403, 'Administrator access required'); return;
        }
        if (!in_array($_SERVER['REQUEST_METHOD'] ?? 'GET', ['GET','HEAD'], true)) {
            header('Allow: GET, HEAD'); self::reply(405, 'Read-only monitoring'); return;
        }
        if ($path === '/ops/batches') { header('Location: /ops/batches/', true, 308); return; }
        $routes = ['/ops/batches/'=>['index.html','text/html; charset=utf-8'],
                   '/ops/batches/monitor.css'=>['monitor.css','text/css; charset=utf-8'],
                   '/ops/batches/monitor.js'=>['monitor.js','text/javascript; charset=utf-8'],
                   '/ops/batches/data.json'=>['data.json','application/json; charset=utf-8']];
        if (!isset($routes[$path])) { self::reply(404, 'Not found'); return; }
        try {
            $folder = $root.'/.batch-monitoring';
            if (is_link($folder) || realpath($folder) !== $folder) throw new \RuntimeException('Unsafe folder');
            $pointer = json_decode(self::read($folder.'/active.json', 4096), true, 8, JSON_THROW_ON_ERROR);
            if (!preg_match('/\Am[0-9a-f]{12}\z/D', $pointer['release'] ?? '') ||
                !preg_match('/\A[0-9a-f]{64}\z/D', $pointer['manifestSha256'] ?? '')) throw new \RuntimeException('Invalid pointer');
            $directory = $folder.'/releases/'.$pointer['release'];
            if (is_link($folder.'/releases') || is_link($directory) || realpath($directory) !== $directory) throw new \RuntimeException('Unsafe release');
            $raw = self::read($directory.'/manifest.json', 4096);
            if (!hash_equals($pointer['manifestSha256'], hash('sha256', $raw))) throw new \RuntimeException('Manifest mismatch');
            $manifest = json_decode($raw, true, 8, JSON_THROW_ON_ERROR);
            [$file,$type] = $routes[$path];
            $body = self::read($directory.'/'.$file, 4000000);
            $digest = $manifest['files'][$file] ?? '';
            if (!is_string($digest) || !hash_equals($digest, hash('sha256', $body))) throw new \RuntimeException('File mismatch');
            if ($file === 'data.json') {
                $doc = json_decode($body, true, 32, JSON_THROW_ON_ERROR);
                if (($doc['schemaVersion'] ?? null) !== 1 || ($doc['readOnly'] ?? null) !== true || !is_array($doc['batches'] ?? null)) throw new \RuntimeException('Invalid snapshot');
            }
            self::reply(200, $body, $type);
        } catch (\Throwable) {
            self::reply(503, '{"error":"monitoring_evidence_unavailable"}', 'application/json; charset=utf-8');
        }
    }
    private static function read(string $file, int $limit): string
    {
        if (is_link($file) || !is_file($file) || realpath($file) !== $file || filesize($file) > $limit) throw new \RuntimeException('Unsafe file');
        $raw = file_get_contents($file, false, null, 0, $limit+1);
        if (!is_string($raw) || strlen($raw) > $limit) throw new \RuntimeException('Read failed');
        return $raw;
    }
}
