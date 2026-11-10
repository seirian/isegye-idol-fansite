<?php
declare(strict_types=1);
namespace Isegye\Access;

/** Data-only album feed, called strictly after the existing access gate. */
final class AlbumsFeed
{
    private static function read(string $path, int $limit): string
    {
        if (!is_file($path) || is_link($path) || realpath($path) !== $path || filesize($path) > $limit) {
            throw new \RuntimeException('Album file unavailable');
        }
        $raw = file_get_contents($path);
        if ($raw === false || strlen($raw) > $limit) throw new \RuntimeException('Album read failed');
        return $raw;
    }
    private static function respond(int $status, string $body, string $type): void
    {
        http_response_code($status); header('Content-Type: '.$type);
        if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'HEAD') echo $body;
    }
    public static function serve(string $root, string $path): void
    {
        $type = 'application/json; charset=utf-8';
        if ($path !== '/api/albums' && !preg_match('~\A/api/albums/assets/([a-f0-9]{64})\.webp\z~D', $path, $match)) {
            self::respond(404, '{"error":"not_found"}', $type); return;
        }
        try {
            $folder = $root.'/.albums-feed';
            if (self::read($folder.'/.owner', 64) !== "isegye-daily-albums:v1\n") throw new \RuntimeException('Wrong owner');
            $raw = self::read($folder.'/current.json', 8000000);
            $data = json_decode($raw, true, 32, JSON_THROW_ON_ERROR);
            if (($data['schemaVersion'] ?? null) !== 1 || ($data['feed'] ?? '') !== 'daily-albums'
                || !is_array($data['tracks'] ?? null) || !is_array($data['providers'] ?? null)
                || !is_string($data['generatedAt'] ?? null)) throw new \RuntimeException('Invalid album feed');
            if ($path === '/api/albums') { self::respond(200, $raw, $type); return; }
            $sha = $match[1]; $found = false;
            foreach (['covers', 'brands', 'badges'] as $group) {
                foreach (($data['assets'][$group] ?? []) as $asset) {
                    if (($asset['sha256'] ?? '') === $sha && ($asset['path'] ?? '') === 'albums/asset-cache/'.$sha.'.webp') $found = true;
                }
            }
            if (!$found) { self::respond(404, '{"error":"not_found"}', $type); return; }
            $image = self::read($folder.'/assets/'.$sha.'.webp', 180000);
            if (hash('sha256', $image) !== $sha || substr($image, 0, 4) !== 'RIFF' || substr($image, 8, 4) !== 'WEBP') {
                throw new \RuntimeException('Album image integrity failed');
            }
            self::respond(200, $image, 'image/webp');
        } catch (\Throwable) {
            self::respond(503, '{"error":"albums_unavailable"}', $type);
        }
    }
}
