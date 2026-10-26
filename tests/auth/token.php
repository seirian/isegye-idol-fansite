<?php
// CLI test signer only. Excluded from every deployed bundle.
declare(strict_types=1);
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
require __DIR__.'/../../auth/vendor/autoload.php';
use Firebase\JWT\JWT;
$input=json_decode(stream_get_contents(STDIN),true,16,JSON_THROW_ON_ERROR);
echo JWT::encode($input['claims'],file_get_contents($argv[1]),'RS256','fixture-key');
