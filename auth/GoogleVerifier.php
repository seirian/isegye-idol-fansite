<?php
declare(strict_types=1);
namespace Isegye\Access;
use Firebase\JWT\JWT;
use Firebase\JWT\JWK;

final class GoogleVerifier
{
    public function __construct(private string $clientId, private string $directory) {}
    public function verify(string $token, string $nonce): array
    {
        if (strlen($token) > 16000 || !preg_match('/\A[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\z/D', $token) || !preg_match('/\A[a-f0-9]{64}\z/D', $nonce)) {
            throw new \RuntimeException('Invalid credential');
        }
        $header = JWT::jsonDecode(JWT::urlsafeB64Decode(explode('.', $token)[0]));
        if (($header->alg ?? '') !== 'RS256' || !is_string($header->kid ?? null) || strlen($header->kid) > 200) {
            throw new \RuntimeException('Unapproved signing algorithm');
        }
        $keys = $this->keys($header->kid);
        // The pinned library verifies the signature and time claims; never tokeninfo in production.
        JWT::$leeway = 30;
        $claims = (array) JWT::decode($token, JWK::parseKeySet($keys, 'RS256'));
        $now = time();
        if (!in_array($claims['iss'] ?? null, ['https://accounts.google.com', 'accounts.google.com'], true) ||
            ($claims['aud'] ?? null) !== $this->clientId ||
            (isset($claims['azp']) && $claims['azp'] !== $this->clientId) ||
            !is_int($claims['exp'] ?? null) || $claims['exp'] <= $now ||
            !is_int($claims['iat'] ?? null) || $claims['iat'] > $now + 30 || $claims['iat'] < $now - 7200 ||
            !is_string($claims['nonce'] ?? null) || !hash_equals($nonce, $claims['nonce']) ||
            ($claims['email_verified'] ?? null) !== true ||
            !is_string($claims['email'] ?? null) || !filter_var($claims['email'], FILTER_VALIDATE_EMAIL) || strlen($claims['email']) > 254 ||
            !is_string($claims['sub'] ?? null) || !preg_match('/\A[A-Za-z0-9_-]{1,255}\z/D', $claims['sub'])) {
            throw new \RuntimeException('Credential claims rejected');
        }
        // Drop names, pictures and every unnecessary claim immediately.
        return ['subject' => $claims['sub'], 'verifiedEmail' => $claims['email']];
    }
    private function keys(string $kid): array
    {
        $lockPath = $this->directory . '/jwks.lock';
        if (is_link($lockPath)) throw new \RuntimeException('Unsafe cache lock');
        $lock = fopen($lockPath, 'c+b');
        if (!$lock || !flock($lock, LOCK_EX)) throw new \RuntimeException('Key cache unavailable');
        chmod($lockPath, 0600);
        try {
            $path = $this->directory . '/google-jwks.json';
            if (is_link($path)) throw new \RuntimeException('Unsafe key cache');
            $cache = null;
            if (is_file($path) && filesize($path) <= 262144) {
                try { $cache = json_decode(file_get_contents($path), true, 20, JSON_THROW_ON_ERROR); }
                catch (\Throwable) { $cache = null; }
            }
            $hasKey = is_array($cache) && in_array($kid, array_column($cache['keys'] ?? [], 'kid'), true);
            if ($hasKey && ($cache['expires'] ?? 0) > time()) return ['keys' => $cache['keys']];
            // Unknown kids cannot force unbounded outbound requests.
            if (is_array($cache) && ($cache['fetched'] ?? 0) > time() - 60) throw new \RuntimeException('Signing key unavailable');
            $curl = curl_init('https://www.googleapis.com/oauth2/v3/certs');
            $body = ''; $maxAge = 300;
            curl_setopt_array($curl, [CURLOPT_CONNECTTIMEOUT => 5, CURLOPT_TIMEOUT => 10,
                CURLOPT_FOLLOWLOCATION => false, CURLOPT_PROTOCOLS => CURLPROTO_HTTPS,
                CURLOPT_SSL_VERIFYPEER => true, CURLOPT_SSL_VERIFYHOST => 2,
                CURLOPT_USERAGENT => 'IsegyeGoogleAccess/1.0',
                CURLOPT_WRITEFUNCTION => static function ($c, string $data) use (&$body): int {
                    if (strlen($body) + strlen($data) > 262144) return 0;
                    $body .= $data; return strlen($data);
                },
                CURLOPT_HEADERFUNCTION => static function ($c, string $line) use (&$maxAge): int {
                    if (preg_match('/^Cache-Control:.*max-age=(\d+)/i', $line, $m)) $maxAge = max(60, min(21600, (int)$m[1]));
                    return strlen($line);
                }]);
            $ok = curl_exec($curl); $status = curl_getinfo($curl, CURLINFO_RESPONSE_CODE); curl_close($curl);
            if ($ok === false || $status !== 200) throw new \RuntimeException('Google signing service unavailable');
            $jwks = json_decode($body, true, 20, JSON_THROW_ON_ERROR);
            $keys = array_values(array_filter($jwks['keys'] ?? [], static fn($key) =>
                is_array($key) && ($key['kty'] ?? '') === 'RSA' && ($key['use'] ?? '') === 'sig' &&
                ($key['alg'] ?? 'RS256') === 'RS256' && is_string($key['kid'] ?? null)));
            if (!$keys || count($keys) > 20) throw new \RuntimeException('Invalid signing keys');
            $data = json_encode(['fetched' => time(), 'expires' => time() + $maxAge, 'keys' => $keys], JSON_THROW_ON_ERROR);
            $temp = $path . '.' . bin2hex(random_bytes(8));
            if (file_put_contents($temp, $data, LOCK_EX) !== strlen($data)) throw new \RuntimeException('Key cache write failed');
            chmod($temp, 0600); rename($temp, $path);
            if (!in_array($kid, array_column($keys, 'kid'), true)) throw new \RuntimeException('Signing key not found');
            return ['keys' => $keys];
        } finally { flock($lock, LOCK_UN); fclose($lock); }
    }
}
