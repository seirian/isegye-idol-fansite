<?php
declare(strict_types=1);
namespace Isegye\Access;

/** Read-only presentation boundary; never trusts query strings or client flags. */
final class Visibility
{
    private static function policy(): array
    {
        static $policy;
        if ($policy === null) {
            $policy = json_decode(file_get_contents(__DIR__.'/public-view-policy.json'), true, 16, JSON_THROW_ON_ERROR);
            if (($policy['schemaVersion'] ?? null) !== 1) throw new \RuntimeException('Visibility policy unavailable');
        }
        return $policy;
    }
    public static function administratorOnly(string $path): bool
    {
        return in_array($path, self::policy()['protectedPaths'], true);
    }
    public static function file(string $relative, ?string $role): string
    {
        return $role === 'admin' ? $relative : (self::policy()['publicFiles'][$relative] ?? $relative);
    }
    public static function project(mixed $value, string $context = ''): mixed
    {
        $policy = self::policy();
        if (is_array($value)) {
            return array_map(fn($item) => self::project($item, $context === 'sources' ? 'source' : ($context === 'channels' ? 'channel' : '')), $value);
        }
        if (!is_object($value)) return $value;
        // Provider availability, credentials setup hints and collector errors are operational.
        if ($context === 'providers') return new \stdClass();
        $allowed = $context === 'source' ? $policy['sourceKeys'] : ($context === 'channel' ? $policy['channelKeys'] : null);
        $result = new \stdClass();
        foreach (get_object_vars($value) as $key => $item) {
            if (in_array($key, $policy['removeKeys'], true) || ($allowed !== null && !in_array($key, $allowed, true))) continue;
            $result->$key = self::project($item, $key);
        }
        return $result;
    }
    public static function json(string $raw, ?string $role): string
    {
        if ($role === 'admin') return $raw;
        $original = json_decode($raw, false, 64, JSON_THROW_ON_ERROR);
        $public = self::project($original);
        return $public == $original ? $raw : json_encode($public, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);
    }
}
