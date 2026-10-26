<?php
declare(strict_types=1);
namespace Isegye\Access;
final class Session
{
    public static function start(string $directory): void
    {
        if (!is_dir($directory) || is_link($directory)) throw new \RuntimeException('Session storage missing');
        ini_set('session.use_strict_mode', '1'); ini_set('session.use_only_cookies', '1');
        ini_set('session.use_trans_sid', '0'); ini_set('session.upload_progress.enabled', '0');
        ini_set('session.gc_maxlifetime', '43200');
        ini_set('session.gc_probability', '1'); ini_set('session.gc_divisor', '100');
        session_name('__Host-ISEGYE'); session_save_path($directory);
        session_set_cookie_params(['lifetime'=>0,'path'=>'/','secure'=>true,'httponly'=>true,'samesite'=>'Lax']);
        if (!session_start()) throw new \RuntimeException('Session unavailable');
        $now = time();
        if (isset($_SESSION['account']) && (($now - ($_SESSION['issued'] ?? 0)) >= 43200 || ($now - ($_SESSION['activity'] ?? 0)) >= 1800)) {
            $_SESSION = []; session_regenerate_id(true);
        }
        if (!isset($_SESSION['csrf'])) $_SESSION['csrf'] = bin2hex(random_bytes(32));
    }
    public static function csrf(): string { return $_SESSION['csrf']; }
    public static function account(): ?string
    {
        $id = $_SESSION['account'] ?? null;
        return is_string($id) && preg_match('/\A[a-f0-9]{64}\z/D', $id) ? $id : null;
    }
    public static function issueNonce(): string
    {
        $_SESSION['nonce'] = bin2hex(random_bytes(32)); $_SESSION['nonce_at'] = time();
        return $_SESSION['nonce'];
    }
    public static function consumeNonce(): string
    {
        $nonce = $_SESSION['nonce'] ?? ''; $at = $_SESSION['nonce_at'] ?? 0;
        unset($_SESSION['nonce'], $_SESSION['nonce_at']);
        if (!is_string($nonce) || !preg_match('/\A[a-f0-9]{64}\z/D', $nonce) || $at < time()-600 || $at > time()) {
            throw new \RuntimeException('Login expired; start again');
        }
        return $nonce;
    }
    public static function requirePost(string $origin, ?string $csrf): void
    {
        if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST' || ($_SERVER['HTTP_ORIGIN'] ?? '') !== $origin ||
            (isset($_SERVER['HTTP_SEC_FETCH_SITE']) && $_SERVER['HTTP_SEC_FETCH_SITE'] !== 'same-origin') ||
            !is_string($csrf) || !hash_equals(self::csrf(), $csrf)) {
            throw new \RuntimeException('Request authenticity rejected');
        }
    }
    public static function login(string $id): void
    {
        if (!preg_match('/\A[a-f0-9]{64}\z/D', $id)) throw new \RuntimeException('Invalid account key');
        // Session fixation defense and removal of pre-login nonce and claims.
        $_SESSION = [];
        if (!session_regenerate_id(true)) throw new \RuntimeException('Session rotation failed');
        $_SESSION = ['account'=>$id, 'issued'=>time(), 'activity'=>time(), 'csrf'=>bin2hex(random_bytes(32))];
    }
    public static function touch(): void { if (self::account() !== null) $_SESSION['activity'] = time(); }
    public static function logout(): void
    {
        $_SESSION = []; session_destroy();
        setcookie('__Host-ISEGYE', '', ['expires'=>1,'path'=>'/','secure'=>true,'httponly'=>true,'samesite'=>'Lax']);
    }
}
