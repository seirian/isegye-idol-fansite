<?php
declare(strict_types=1);
namespace Isegye\Access;

/** Administrator-only, read-only projection. Never invokes GitHub or a batch. */
final class BatchMonitor
{
    public const LOGIN = '/auth/login?notice=batch-admin';
    public const MESSAGE = '관리자 계정만 해당 사이트에 접근이 가능합니다.';
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
            // Only human-facing documents redirect. Data/assets keep their denial status.
            if (in_array($path, ['/ops/batches','/ops/batches/'], true) &&
                in_array($_SERVER['REQUEST_METHOD'] ?? 'GET', ['GET','HEAD'], true)) {
                header('Location: '.self::LOGIN, true, 303);
                self::reply(303, View::page('관리자 전용 안내',
                    '<section class="access-card"><p class="access-kicker">관리자 전용</p><h1>관리자 로그인이 필요합니다</h1>'
                    . '<p class="access-description">'.self::MESSAGE.'</p><a class="access-button" href="'.self::LOGIN.'">로그인 페이지로 이동</a></section>'), 'text/html; charset=utf-8');
                return;
            }
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
    /** Shared login UI with a fixed context, never a client-provided return URL. */
    public static function login(array $access, string $clientId, string $nonce, string $csrf): void
    {
        header('Cache-Control: private, no-store, max-age=0');
        header('Vary: Cookie');
        header('X-Robots-Tag: noindex, nofollow, noarchive');
        header("Content-Security-Policy: default-src 'self'; script-src 'self' https://accounts.google.com/gsi/client; style-src 'self' https://accounts.google.com/gsi/style; frame-src https://accounts.google.com/gsi/; connect-src 'self' https://accounts.google.com/gsi/; img-src 'self' data: https://*.gstatic.com; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; form-action 'self'");
        header('Referrer-Policy: strict-origin-when-cross-origin');
        if (!in_array($_SERVER['REQUEST_METHOD'] ?? 'GET', ['GET','HEAD'], true)) {
            self::reply(405, 'Method not allowed'); return;
        }
        if (($access['role'] ?? null) === 'admin' && ($access['allowed'] ?? false) === true) {
            header('Location: /ops/batches/', true, 303); return;
        }
        $signedIn = ($access['role'] ?? null) !== null;
        $html = $signedIn ? View::account($access['role'], $csrf) : View::login($clientId, $nonce, $csrf);
        $hint = $signedIn ? '현재 계정에는 접근 권한이 없습니다. 로그아웃 후 관리자 계정으로 다시 로그인해 주세요.'
                          : '관리자 권한이 있는 Google 계정으로 로그인해 주세요. 일반 계정으로는 접근할 수 없습니다.';
        $notice = '<p class="access-description access-legal-notice" role="status" data-batch-access="required"><strong>'
            . self::MESSAGE . '</strong><br>' . $hint . '</p>';
        $anchor = '<section class="access-card">';
        if (substr_count($html, $anchor) !== 1) throw new \RuntimeException('Shared access UI changed');
        $html = str_replace($anchor, $anchor.$notice, $html);
        if ($signedIn) {
            $html = str_replace('action="/auth/logout"', 'action="/auth/logout?notice=batch-admin"', $html);
            $html = str_replace('>로그아웃</button>', '>로그아웃 후 관리자 계정으로 로그인</button>', $html);
        } else {
            $html = str_replace('<div id="google-signin"', '<div id="google-signin" data-intent="batch-monitor"', $html);
        }
        self::reply(200, $html, 'text/html; charset=utf-8');
    }
    public static function switchAccount(string $origin): void
    {
        // Explicit user action only. GET never logs anyone out; existing CSRF stays mandatory.
        header('Cache-Control: private, no-store, max-age=0');
        if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'POST') {
            header('Allow: POST'); self::reply(405, 'Method not allowed'); return;
        }
        try {
            Session::requirePost($origin, $_POST['csrf'] ?? null);
            Session::logout();
            header('Location: '.self::LOGIN, true, 303);
        } catch (\Throwable) { self::reply(403, 'Request rejected'); }
    }
    private static function read(string $file, int $limit): string
    {
        if (is_link($file) || !is_file($file) || realpath($file) !== $file || filesize($file) > $limit) throw new \RuntimeException('Unsafe file');
        $raw = file_get_contents($file, false, null, 0, $limit+1);
        if (!is_string($raw) || strlen($raw) > $limit) throw new \RuntimeException('Read failed');
        return $raw;
    }
}
