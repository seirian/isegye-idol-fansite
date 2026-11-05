<?php
declare(strict_types=1);
namespace Isegye\Access;

/** Read-only member documents, never an alternative route to the application. */
final class MemberLegal
{
    public static function serve(string $release, string $runtime, string $path): void
    {
        header('X-Robots-Tag: noindex, nofollow');
        header("Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'");
        $files = ['/account/legal.css'=>['styles.css','text/css; charset=utf-8'],
                  '/account/legal.js'=>['member-legal.js','text/javascript; charset=utf-8']];
        $name = $files[$path][0] ?? 'member-legal.json';
        $file = $release.'/src/'.$name;
        if (!is_file($file) || is_link($file) || realpath($file) !== $file || filesize($file) > 2000000) {
            http_response_code(503); header('Content-Type: text/plain; charset=utf-8');
            if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'HEAD') echo '이용 안내 문서를 불러올 수 없습니다.';
            return;
        }
        $body = file_get_contents($file);
        if (isset($files[$path])) {
            header('Content-Type: '.$files[$path][1]);
        } else {
            $kind = $path === '/account/terms' ? 'terms' : 'privacy';
            $bundle = json_decode($body, true, 8, JSON_THROW_ON_ERROR);
            if (($bundle['schemaVersion'] ?? null) !== 1 || !is_string($bundle['documents'][$kind] ?? null) ||
                !hash_equals(hash_file('sha256', $runtime.'/'.$kind.'.html'), $bundle['sourceHashes'][$kind] ?? '')) {
                throw new \RuntimeException('Member policy source mismatch');
            }
            $body = $bundle['documents'][$kind];
            header('Content-Type: text/html; charset=utf-8');
        }
        http_response_code(200);
        if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'HEAD') echo $body;
    }
}
