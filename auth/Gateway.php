<?php
declare(strict_types=1);
namespace Isegye\Access;

final class Gateway
{
    private Store $store;
    private bool $hasSession = false;
    public function __construct(private string $root, private string $runtime, private array $config)
    {
        $key = base64_decode($config['siteKey'] ?? '', true);
        if ($key === false || strlen($key) !== 32 || ($config['origin'] ?? '') !== 'https://isegye-idol.kr' ||
            !preg_match('/\A[0-9]+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com\z/D', $config['clientId'] ?? '')) {
            throw new \RuntimeException('Google access is not configured');
        }
        $this->store = new Store($root . '/.auth-private', $key, $config['adminEmailDigest'] ?? '');
    }
    private function session(): void
    {
        if (!$this->hasSession) { Session::start($this->root . '/.auth-private/sessions'); $this->hasSession = true; }
    }
    public static function path(string $request): string
    {
        $raw = explode('?', $request, 2)[0];
        if (!str_starts_with($raw, '/') || strlen($raw) > 2048) throw new \RuntimeException('Invalid request path');
        $path = rawurldecode($raw);
        if (preg_match('/[\x00-\x20\x7f\\\\%]/', $path) || str_contains($path, '//')) throw new \RuntimeException('Invalid path encoding');
        foreach (explode('/', $path) as $part) if ($part === '.' || $part === '..') throw new \RuntimeException('Invalid path segment');
        return $path;
    }
    private static function respond(int $status, string $body, string $type = 'text/html; charset=utf-8'): void
    {
        http_response_code($status); header('Content-Type: ' . $type);
        if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'HEAD') echo $body;
    }
    private function sendFile(string $file, string $type): void
    {
        if (!is_file($file) || is_link($file)) { self::respond(404, 'Not found', 'text/plain'); return; }
        self::respond(200, file_get_contents($file), $type);
    }
    private function release(): string
    {
        $router = file_get_contents($this->root . '/.htaccess');
        if (!preg_match('/\A# ISEGYE-AUTH-ROOT-V1 (r[a-f0-9]{12})\n/', $router, $match)) throw new \RuntimeException('Active release unavailable');
        $dir = $this->root . '/_isegye_releases/' . $match[1];
        if (is_link($dir) || realpath($dir) !== $dir) throw new \RuntimeException('Unsafe release');
        return $dir;
    }
    public function run(): void
    {
        $host = strtolower($_SERVER['HTTP_HOST'] ?? '');
        if (!in_array($host, ['isegye-idol.kr', 'isegye-idol.kr:443'], true)) { self::respond(404, 'Not found', 'text/plain'); return; }
        if (($_SERVER['HTTPS'] ?? '') !== 'on' && ($_SERVER['SERVER_PORT'] ?? '') !== '443') {
            header('Location: ' . $this->config['origin'] . '/', true, 308); return;
        }
        header('Cache-Control: private, no-store, max-age=0'); header('Pragma: no-cache'); header('Vary: Cookie');
        header('X-Content-Type-Options: nosniff'); header('Referrer-Policy: no-referrer'); header('X-Frame-Options: DENY');
        header('Cross-Origin-Opener-Policy: same-origin-allow-popups');
        $path = self::path($_SERVER['REQUEST_URI'] ?? '/');
        $method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
        if (!in_array($method, ['GET','HEAD','POST'], true)) { self::respond(405, 'Method not allowed', 'text/plain'); return; }
        $public = ['/auth/account.css'=>['account.css','text/css; charset=utf-8'], '/auth/style.css'=>['style.css','text/css; charset=utf-8'], '/auth/client.js'=>['client.js','text/javascript; charset=utf-8'],
                   '/auth/google-client.js'=>['google-client.js','text/javascript; charset=utf-8'], '/auth/background.webp'=>['background.webp','image/webp']];
        if (isset($public[$path]) && $method !== 'POST') { [$file,$type]=$public[$path]; $this->sendFile($this->runtime.'/'.$file,$type); return; }
        if (isset($_COOKIE['__Host-ISEGYE']) || in_array($path, ['/auth/login','/auth/google','/auth/logout'], true)) $this->session();
        $access = $this->store->access($this->hasSession ? Session::account() : null);
        if ($path === '/auth/google') {
            $this->session();
            try {
                Session::requirePost($this->config['origin'], $_SERVER['HTTP_X_CSRF_TOKEN'] ?? null);
                if ((int)($_SERVER['CONTENT_LENGTH'] ?? 0) > 20000 || explode(';', $_SERVER['CONTENT_TYPE'] ?? '')[0] !== 'application/json') throw new \RuntimeException('Invalid submission');
                $input = json_decode(file_get_contents('php://input', false, null, 0, 20001), true, 8, JSON_THROW_ON_ERROR);
                if (!is_array($input) || array_keys($input) !== ['credential'] || !is_string($input['credential'])) throw new \RuntimeException('Invalid credential payload');
                $nonce = Session::consumeNonce();
                $identity = (new GoogleVerifier($this->config['clientId'], $this->root.'/.auth-private'))->verify($input['credential'], $nonce);
                unset($input);
                $registered = $this->store->registerVerified($identity['subject'], $identity['verifiedEmail']);
                unset($identity);
                Session::login($registered['key']);
                self::respond(200, '{"ok":true}', 'application/json; charset=utf-8');
            } catch (\Throwable) {
                // Never log credentials, provider claims or exception messages.
                self::respond(401, '{"ok":false,"error":"login_failed"}', 'application/json; charset=utf-8');
            }
            return;
        }
        if ($path === '/auth/logout') {
            try { Session::requirePost($this->config['origin'], $_POST['csrf'] ?? null); Session::logout(); header('Location: /', true, 303); }
            catch (\Throwable) { self::respond(403, 'Request rejected', 'text/plain'); }
            return;
        }
        if ($method === 'POST') { self::respond(405, 'Method not allowed', 'text/plain'); return; }
        if ($path === '/auth/status') {
            self::respond(200, json_encode(['authenticated'=>$access['role']!==null,'administrator'=>$access['role']==='admin',
                'maintenance'=>$access['maintenance'],'allowed'=>$access['allowed']], JSON_THROW_ON_ERROR), 'application/json; charset=utf-8'); return;
        }
        if (in_array($path, ['/auth/login','/auth/privacy'], true)) {
            header("Content-Security-Policy: default-src 'self'; script-src 'self' https://accounts.google.com/gsi/client; style-src 'self' https://accounts.google.com/gsi/style; frame-src https://accounts.google.com/gsi/; connect-src 'self' https://accounts.google.com/gsi/; img-src 'self' data: https://*.gstatic.com; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; form-action 'self'");
            if ($path === '/auth/privacy') self::respond(200, View::privacy());
            elseif ($access['role'] !== null) self::respond(200, View::account($access['role'], Session::csrf()));
            else self::respond(200, View::login($this->config['clientId'], Session::issueNonce(), Session::csrf()));
            return;
        }
        if (!$access['allowed']) {
            header('Retry-After: 3600'); header('X-Robots-Tag: noindex, nofollow');
            header("Content-Security-Policy: default-src 'self'; style-src 'self'; img-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");
            self::respond(503, View::maintenance($access['role'] !== null)); return;
        }
        if ($this->hasSession && ($path === '/' || $path === '/index.html')) Session::touch();
        // Only canonical, allowlisted app paths. No old-release, PHP, source or private-directory URLs.
        $relative = ltrim($path, '/');
        if ($relative === '') $relative = 'index.html';
        $allowed = in_array($relative, ['index.html','robots.txt','build-info.json'], true) ||
            preg_match('~\A(?:src|assets)/[A-Za-z0-9_/-]+\.(?:js|css|svg|png|webp|jpg|json)\z~D', $relative);
        if (!$allowed) { self::respond(404, 'Not found', 'text/plain'); return; }
        $release = $this->release(); $file = $release . '/' . $relative;
        if (realpath($file) !== $file || is_link($file)) { self::respond(404, 'Not found', 'text/plain'); return; }
        if ($relative === 'index.html') {
            $html = file_get_contents($file);
            $html = str_replace('form-action https://github.com', "form-action 'self' https://github.com", $html);
            $html = str_replace('</head>', '<link rel="stylesheet" href="/auth/account.css"><script defer src="/auth/client.js"></script></head>', $html);
            self::respond(200, $html); return;
        }
        $mime = ['js'=>'text/javascript; charset=utf-8','css'=>'text/css; charset=utf-8','json'=>'application/json; charset=utf-8',
                 'svg'=>'image/svg+xml','png'=>'image/png','webp'=>'image/webp','jpg'=>'image/jpeg','txt'=>'text/plain; charset=utf-8'];
        $this->sendFile($file, $mime[pathinfo($file, PATHINFO_EXTENSION)] ?? 'application/octet-stream');
    }
}
