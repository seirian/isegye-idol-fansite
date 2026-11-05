<?php
declare(strict_types=1);
namespace Isegye\Access;

/** Read-only preview, reached only after Gateway's normal account/maintenance gate. */
final class ReviewPreview
{
    private static function read(string $path, int $limit): string
    {
        if (is_link($path) || realpath($path) !== $path || !is_file($path) || filesize($path) > $limit) {
            throw new \RuntimeException('Preview file unavailable');
        }
        $raw = file_get_contents($path);
        if ($raw === false || strlen($raw) > $limit) throw new \RuntimeException('Preview read failed');
        return $raw;
    }
    private static function respond(int $status, string $body, string $type = 'text/html; charset=utf-8'): void
    {
        http_response_code($status); header('Content-Type: '.$type);
        if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'HEAD') echo $body;
    }
    public static function serve(string $root, string $path, ?string $role): void
    {
        header('Cache-Control: private, no-store, max-age=0');
        header('X-Robots-Tag: noindex, nofollow, noarchive');
        header('X-Content-Type-Options: nosniff');
        header("Content-Security-Policy: frame-ancestors 'none'");
        if ($role !== 'admin') {
            self::respond(403, '<!doctype html><html lang="ko"><meta charset="utf-8"><title>검토 접근 제한</title><h1>관리자 로그인 후 확인할 수 있습니다.</h1><a href="/auth/login">기존 Google 로그인</a></html>'); return;
        }
        if (!in_array($_SERVER['REQUEST_METHOD'] ?? '', ['GET', 'HEAD'], true)) {
            self::respond(405, 'Method not allowed', 'text/plain'); return;
        }
        if ($path === '/review-1st') { header('Location: /review-1st/', true, 308); return; }
        if (!in_array($path, ['/review-1st/', '/review-1st/index.html', '/review-1st/build-info.json'], true)) {
            self::respond(404, 'Not found', 'text/plain'); return;
        }
        try {
            $folder = $root.'/.review-1st';
            if (self::read($folder.'/.owner', 100) !== "isegye-first-review:v1\n") throw new \RuntimeException('Owner marker');
            $active = json_decode(self::read($folder.'/active.json', 4096), true, 8, JSON_THROW_ON_ERROR);
            if (!preg_match('/\Ap[a-f0-9]{12}\z/D', $active['release'] ?? '') ||
                !preg_match('/\A[a-f0-9]{64}\z/D', $active['sha256'] ?? '') ||
                !preg_match('/\A[a-f0-9]{64}\z/D', $active['metadataSha256'] ?? '')) throw new \RuntimeException('Pointer');
            $dir = $folder.'/releases/'.$active['release'];
            if ($path === '/review-1st/build-info.json') {
                $raw = self::read($dir.'/build-info.json', 8192);
                if (!hash_equals($active['metadataSha256'], hash('sha256', $raw))) throw new \RuntimeException('Metadata digest');
                self::respond(200, $raw, 'application/json; charset=utf-8'); return;
            }
            $html = self::read($dir.'/review.html', 9*1024*1024);
            if (!hash_equals($active['sha256'], hash('sha256', $html))) throw new \RuntimeException('Artifact digest');
            Session::touch();
            self::respond(200, $html);
        } catch (\Throwable) {
            self::respond(503, '검토본을 확인할 수 없습니다. 운영 페이지는 기존 주소를 이용해 주세요.', 'text/plain; charset=utf-8');
        }
    }
}
